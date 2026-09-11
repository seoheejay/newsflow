// 수집 실행과 실행 이력 (SR-I-104, SR-I-105). Celery 워커가 떠 있어야 한다.
import { expect, test } from '@playwright/test'
import {
  gotoArticles,
  gotoExecutions,
  parseNewCount,
  runCollection,
  settled,
} from './helpers.js'

test.describe.configure({ mode: 'serial' })

test('AC-08 수집 버튼을 누르면 즉시 응답하고 상태가 완료까지 바뀐다', async ({ page }) => {
  await gotoArticles(page)

  const badges = []
  const { firstBadgeMs, summary } = await runCollection(page, {
    onBadge: (t) => {
      if (badges[badges.length - 1] !== t) badges.push(t)
    },
  })

  // 실행 요청에 대한 화면 응답은 1초 이내여야 한다 (SR-N-102)
  expect(firstBadgeMs).toBeLessThan(1000)
  // 상태 배지가 최종 상태까지 갱신된다 (UR-EXE-04)
  expect(badges.at(-1)).toMatch(/완료|실패/)
  expect(summary).toMatch(/수집 \d+건/)
})

test('AC-04 연속으로 두 번 실행하면 두 번째는 신규 기사만 전달한다', async ({ page }) => {
  await gotoArticles(page)
  const first = await runCollection(page)
  const firstNew = parseNewCount(first.summary)

  await page.reload()
  await gotoArticles(page)
  const second = await runCollection(page)
  const secondNew = parseNewCount(second.summary)

  expect(firstNew).not.toBeNull()
  expect(secondNew).not.toBeNull()
  // 같은 피드를 곧바로 다시 읽었으므로 신규는 첫 번째보다 적어야 한다.
  // 그 사이 새 기사가 올라올 수 있어 0 을 단정하지는 않는다.
  expect(secondNew).toBeLessThanOrEqual(firstNew)
})

test('SR-F-705 진행 중에는 수집 버튼을 다시 누를 수 없다', async ({ page }) => {
  await gotoArticles(page)
  const button = page.getByRole('button', { name: /수집|실행/ }).first()
  await button.click()

  // 진행 중에는 버튼이 비활성이라 409 를 볼 일이 없어야 한다 (SR-I-104)
  await expect(button).toBeDisabled()

  await expect(page.locator('.badge', { hasText: /완료|실패/ }).first()).toBeVisible({
    timeout: 150_000,
  })
  await expect(button).toBeEnabled()
})

test('SR-F-807 실행 이력에 수동 실행이 기록되고 수동/자동이 구분된다', async ({ page }) => {
  await gotoExecutions(page)
  const first = page.locator('tbody tr').first()

  await expect(first).toBeVisible()
  await expect(first).toContainText(/수동|자동/)
  await expect(first).toContainText(/성공|실패|진행 중|대기/)
})

test('SR-F-707 실행 이력이 시작 시각 내림차순으로 정렬된다', async ({ page }) => {
  await gotoExecutions(page)
  const times = await page.locator('tbody tr td:nth-child(1)').allInnerTexts()
  test.skip(times.length < 2, '이력이 2건 미만이라 순서를 확인할 수 없다')

  const parsed = times.map((t) => t.trim())
  const sorted = [...parsed].sort().reverse()
  expect(parsed).toEqual(sorted)
})

test('SR-I-304 실행 이력이 봉투 응답의 총계를 보여준다', async ({ page }) => {
  await gotoExecutions(page)
  await settled(page)
  await expect(page.locator('.pagination__count')).toContainText('총')
})
