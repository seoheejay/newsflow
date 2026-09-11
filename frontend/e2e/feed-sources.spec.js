// 피드 소스 관리 화면 (SR-I-102). 브라우저만 사용한다.
import { expect, test } from '@playwright/test'
import {
  GOOGLE_TEMPLATE,
  addFeedSource,
  deleteFeedSource,
  gotoFeedSources,
  tag,
} from './helpers.js'

const SRC = `소스${tag()}`

// 삭제 확인 대화상자를 수락한다.
test.beforeEach(async ({ page }) => {
  page.on('dialog', (d) => d.accept())
})

test.afterAll(async ({ browser }) => {
  const page = await browser.newPage()
  page.on('dialog', (d) => d.accept())
  await gotoFeedSources(page)
  await deleteFeedSource(page, SRC)
  await page.close()
})

test('SR-F-201 화면에서 피드 소스를 등록하면 목록에 나타난다', async ({ page }) => {
  await gotoFeedSources(page)
  const before = await page.locator('tbody tr').count()

  await addFeedSource(page, { name: SRC, sortOrder: 99 })

  await expect(page.locator('tbody tr')).toHaveCount(before + 1)
  const row = page.locator('tbody tr', { hasText: SRC })
  await expect(row).toContainText(GOOGLE_TEMPLATE)
})

test('SR-F-207 비활성화한 피드 소스는 새로고침 후에도 비활성이다', async ({ page }) => {
  await gotoFeedSources(page)
  const toggle = page.getByLabel(`${SRC} 활성 여부`)
  await expect(toggle).toBeChecked()

  // 통제된 체크박스라 서버 응답 뒤에 상태가 바뀐다. 클릭하고 라벨 변화를 기다린다.
  await toggle.click()
  await expect(
    page.locator('tbody tr', { hasText: SRC }).locator('.switch span', { hasText: '비활성' }),
  ).toBeVisible()

  await page.reload()
  await gotoFeedSources(page)
  await expect(page.getByLabel(`${SRC} 활성 여부`)).not.toBeChecked()
})

test('SR-F-206 표시명이 중복되면 등록이 거부된다', async ({ page }) => {
  await gotoFeedSources(page)
  await page.getByLabel(/표시명/).fill(SRC)
  await page.getByLabel(/주소 템플릿/).fill(GOOGLE_TEMPLATE)
  await page.getByRole('button', { name: '등록' }).click()

  await expect(page.locator('.alert--error')).toBeVisible()
})

test('SR-F-202 http(s) 로 시작하지 않는 주소 템플릿은 거부된다', async ({ page }) => {
  const name = `${SRC}-잘못된주소`
  await gotoFeedSources(page)
  await page.getByLabel(/표시명/).fill(name)
  await page.getByLabel(/주소 템플릿/).fill('ftp://example.com/rss')
  await page.getByRole('button', { name: '등록' }).click()

  // 오류가 뜨면 FormField 가 힌트를 오류 문구로 바꿔 보여준다 (SR-I-106)
  await expect(page.locator('.field__error')).toContainText('http:// 또는 https://')
  // 거부됐으므로 목록에 들어가지 않아야 한다
  await expect(page.locator('tbody tr', { hasText: name })).toHaveCount(0)
})

test('SR-F-205 {keyword} 없는 주소 템플릿도 등록할 수 있다', async ({ page }) => {
  const name = `${SRC}-전체피드`
  await gotoFeedSources(page)
  await addFeedSource(page, { name, url: 'https://example.com/rss', sortOrder: 98 })

  await expect(page.locator('tbody tr', { hasText: name })).toBeVisible()
  await deleteFeedSource(page, name)
})

test('SR-F-208 피드 소스를 삭제해도 이미 수집된 기사는 남는다', async ({ page }) => {
  const name = `${SRC}-삭제대상`
  await gotoFeedSources(page)
  await addFeedSource(page, { name, sortOrder: 97 })

  await page.goto('/#/articles')
  const before = (await page.locator('.pagination__count').innerText()).trim()

  await gotoFeedSources(page)
  await deleteFeedSource(page, name)

  await page.goto('/#/articles')
  await expect(page.locator('.pagination__count')).toHaveText(before)
})
