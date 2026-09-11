// 기사 목록 화면 (SR-I-103). 브라우저만 사용한다.
import { expect, test } from '@playwright/test'
import { gotoArticles, settled } from './helpers.js'

const KEYWORD_COL = '.articles tbody tr td:nth-child(4)'

test('SR-F-602 기사 목록이 페이지 단위로 조회된다', async ({ page }) => {
  await gotoArticles(page)
  const total = Number(
    (await page.locator('.pagination__count').innerText()).replace(/[^0-9]/g, ''),
  )
  test.skip(total === 0, '저장된 기사가 없다. 먼저 수집을 한 번 실행할 것')

  const rows = await page.locator('.articles tbody tr').count()
  expect(rows).toBeGreaterThan(0)
  expect(rows).toBeLessThanOrEqual(20) // 기본 페이지 크기
})

test('SR-F-603 키워드로 검색하면 그 키워드의 기사만 나온다', async ({ page }) => {
  await gotoArticles(page)
  const options = (await page.locator('select').first().locator('option').allInnerTexts())
    .map((o) => o.trim())
    .filter((o) => o && o !== '전체')
  test.skip(options.length === 0, '등록된 키워드가 없다')

  await page.locator('select').first().selectOption({ label: options[0] })
  await settled(page)

  const cells = (await page.locator(KEYWORD_COL).allInnerTexts()).map((c) => c.trim())
  test.skip(cells.length === 0, `'${options[0]}' 로 수집된 기사가 아직 없다`)
  expect(new Set(cells)).toEqual(new Set([options[0]]))
})

test('SR-F-603 피드 소스로 검색하면 그 소스의 기사만 나온다', async ({ page }) => {
  await gotoArticles(page)
  const selects = page.locator('select')
  const options = (await selects.nth(1).locator('option').allInnerTexts())
    .map((o) => o.trim())
    .filter((o) => o && o !== '전체')
  test.skip(options.length === 0, '등록된 피드 소스가 없다')

  await selects.nth(1).selectOption({ label: options[0] })
  await settled(page)

  const cells = (await page.locator('.articles tbody tr td:nth-child(3)').allInnerTexts()).map((c) =>
    c.trim(),
  )
  test.skip(cells.length === 0, `'${options[0]}' 로 수집된 기사가 아직 없다`)
  expect(new Set(cells)).toEqual(new Set([options[0]]))
})

test('SR-F-606 조건에 맞는 기사가 없으면 빈 목록을 보여준다', async ({ page }) => {
  await gotoArticles(page)
  // 미래 날짜로 조회하면 결과가 없어야 한다
  await page.getByLabel('수집 시작').fill('2099-01-01')
  await settled(page)

  await expect(page.locator('.pagination__count')).toContainText('총 0건')
  await expect(page.locator('.articles tbody tr')).toHaveCount(0)
})

test('SR-F-604 수집 기간으로 검색할 수 있다', async ({ page }) => {
  await gotoArticles(page)
  const all = (await page.locator('.pagination__count').innerText()).trim()

  const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Seoul' })
  await page.getByLabel('수집 시작').fill(today)
  await settled(page)
  const filtered = (await page.locator('.pagination__count').innerText()).trim()

  // 오늘 수집분은 전체보다 많을 수 없다
  const num = (s) => Number(s.replace(/[^0-9]/g, ''))
  expect(num(filtered)).toBeLessThanOrEqual(num(all))
})

test('SR-F-303 목록 제목에 HTML 엔티티가 남아 있지 않다', async ({ page }) => {
  await gotoArticles(page)
  const titles = await page.locator('.articles tbody tr td a').allInnerTexts()
  test.skip(titles.length === 0, '표시할 기사가 없다')

  const leaked = titles.filter((t) => /&(quot|amp|lt|gt|apos|#x?\w+);/.test(t))
  expect(leaked).toEqual([])
})

test('SR-F-503 기사 제목이 원문 링크로 연결된다', async ({ page }) => {
  await gotoArticles(page)
  const link = page.locator('.articles tbody tr td a').first()
  test.skip((await link.count()) === 0, '표시할 기사가 없다')

  await expect(link).toHaveAttribute('href', /^https?:\/\//)
  await expect(link).toHaveAttribute('target', '_blank')
})
