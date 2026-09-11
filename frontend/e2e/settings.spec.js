// 설정 화면 (SR-I-101). 브라우저만 사용한다.
import { expect, test } from '@playwright/test'
import { addKeyword, gotoSettings, removeKeyword, saveSettings, tag } from './helpers.js'

const KW = `키워드${tag()}`

test.afterAll(async ({ browser }) => {
  const page = await browser.newPage()
  await gotoSettings(page)
  await removeKeyword(page, KW)
  await page.close()
})

test('AC-07 화면에서 등록한 키워드가 저장되고 새로고침 후에도 남는다', async ({ page }) => {
  await gotoSettings(page)
  const before = await page.locator('.chip span').allInnerTexts()
  expect(before).not.toContain(KW)

  await addKeyword(page, KW)

  await page.reload()
  await gotoSettings(page)
  await expect(page.locator('.chip span', { hasText: KW })).toBeVisible()
})

test('SR-F-103 이미 등록된 키워드는 다시 추가할 수 없다', async ({ page }) => {
  await gotoSettings(page)
  const existing = (await page.locator('.chip span').allInnerTexts())[0]
  test.skip(!existing, '등록된 키워드가 없어 확인할 수 없다')

  await page.getByPlaceholder('예: AI').fill(existing)
  await page.getByRole('button', { name: '추가' }).click()

  await expect(page.getByText('이미 등록된 키워드입니다')).toBeVisible()
})

test('SR-F-104 수신자 주소 형식이 아니면 항목별 오류를 보여준다', async ({ page }) => {
  await gotoSettings(page)
  const original = await page.getByLabel('수신자 주소').inputValue()

  await page.getByLabel('수신자 주소').fill('주소아님')
  await page.getByRole('button', { name: '저장' }).click()
  await expect(page.getByText('이메일 주소 형식이 아닙니다')).toBeVisible() // SR-I-106

  // 원상 복구
  await page.getByLabel('수신자 주소').fill(original)
  await saveSettings(page)
})

test('SR-F-105 소스당 최대 건수가 범위를 벗어나면 저장되지 않는다', async ({ page }) => {
  await gotoSettings(page)
  const original = await page.getByLabel(/소스당 최대 수집 건수/).inputValue()

  await page.getByLabel(/소스당 최대 수집 건수/).fill('101')
  await page.getByRole('button', { name: '저장' }).click()
  await expect(page.getByText(/1 이상 100 이하/)).toBeVisible()

  await page.getByLabel(/소스당 최대 수집 건수/).fill(original)
  await saveSettings(page)
})

test('SR-F-805 자동 실행 시각을 화면에서 바꿀 수 있다', async ({ page }) => {
  await gotoSettings(page)
  const hour = await page.getByLabel('시', { exact: true }).inputValue()
  const minute = await page.getByLabel('분', { exact: true }).inputValue()

  await page.getByLabel('시', { exact: true }).fill('21')
  await page.getByLabel('분', { exact: true }).fill('45')
  await saveSettings(page)

  await page.reload()
  await gotoSettings(page)
  await expect(page.getByLabel('시', { exact: true })).toHaveValue('21')
  await expect(page.getByLabel('분', { exact: true })).toHaveValue('45')

  // 원상 복구
  await page.getByLabel('시', { exact: true }).fill(hour)
  await page.getByLabel('분', { exact: true }).fill(minute)
  await saveSettings(page)
})
