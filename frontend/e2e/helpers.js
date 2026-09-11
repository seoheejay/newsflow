// 화면 조작 공용 헬퍼. 테스트는 브라우저만 쓴다 — API 를 직접 부르지 않는다.
import { expect } from '@playwright/test'

// 실제 DB 를 쓰므로 이름이 겹치면 SR-F-206(표시명 중복 불가), SR-F-103(키워드 중복 불가)에
// 걸린다. 실행마다 고유한 꼬리표를 붙인다.
export const tag = () => `e2e${Date.now().toString().slice(-7)}`

export const GOOGLE_TEMPLATE =
  'https://news.google.com/rss/search?q={keyword}&hl=ko&gl=KR&ceid=KR:ko'

/** 화면의 "불러오는 중…" 이 사라질 때까지 기다린다. */
export async function settled(page) {
  await page.waitForFunction(() => !document.body.innerText.includes('불러오는 중'), {
    timeout: 25_000,
  })
}

export async function gotoSettings(page) {
  await page.goto('/#/settings')
  await expect(page.getByRole('heading', { name: '설정' })).toBeVisible()
  await settled(page)
}

export async function gotoFeedSources(page) {
  await page.goto('/#/feed-sources')
  await expect(page.getByRole('heading', { name: '피드 소스', exact: true })).toBeVisible()
  await settled(page)
}

export async function gotoArticles(page) {
  await page.goto('/#/articles')
  await expect(page.getByRole('heading', { name: '기사 목록' })).toBeVisible()
  await settled(page)
}

export async function gotoExecutions(page) {
  await page.goto('/#/executions')
  await expect(page.getByRole('heading', { name: '실행 이력' })).toBeVisible()
  await settled(page)
}

/** 설정 화면에서 키워드를 추가하고 저장한다. */
export async function addKeyword(page, keyword) {
  await page.getByPlaceholder('예: AI').fill(keyword)
  await page.getByRole('button', { name: '추가' }).click()
  await expect(page.locator('.chip span', { hasText: keyword })).toBeVisible()
  await saveSettings(page)
}

/** 설정 화면에서 키워드를 빼고 저장한다. 없으면 아무것도 하지 않는다. */
export async function removeKeyword(page, keyword) {
  if (!(await page.locator('.chip', { hasText: keyword }).count())) return
  await page.getByRole('button', { name: `${keyword} 삭제` }).click()
  await saveSettings(page)
}

export async function saveSettings(page) {
  await page.getByRole('button', { name: '저장' }).click()
  await expect(page.locator('.alert--success')).toBeVisible()
}

/** 피드 소스를 등록한다. */
export async function addFeedSource(page, { name, url = GOOGLE_TEMPLATE, sortOrder = 1 }) {
  await page.getByLabel(/표시명/).fill(name)
  await page.getByLabel(/주소 템플릿/).fill(url)
  await page.getByLabel(/정렬 순서/).fill(String(sortOrder))
  await page.getByRole('button', { name: '등록' }).click()
  await expect(page.locator('tbody tr', { hasText: name })).toBeVisible()
}

/** 피드 소스를 지운다. 없으면 아무것도 하지 않는다. window.confirm 은 호출자가 수락해 둘 것. */
export async function deleteFeedSource(page, name) {
  const row = page.locator('tbody tr', { hasText: name })
  if (!(await row.count())) return
  await row.first().getByRole('button', { name: '삭제' }).click()
  await expect(row).toHaveCount(0)
}

/**
 * 수집 버튼을 누르고 완료까지 기다린다.
 * CollectPanel 의 배지 문구: 대기 중 / 수집 중 / 완료 / 실패
 */
export async function runCollection(page, { onBadge } = {}) {
  const badge = page.locator('.badge').first()
  let watcher
  if (onBadge) {
    watcher = setInterval(async () => {
      try {
        if (await badge.count()) onBadge((await badge.innerText()).trim())
      } catch {
        /* 페이지 전환 중에는 무시 */
      }
    }, 100)
  }

  const started = Date.now()
  await page.getByRole('button', { name: /수집|실행/ }).first().click()
  await expect(badge).toBeVisible({ timeout: 10_000 })
  const firstBadgeMs = Date.now() - started

  try {
    await expect(page.locator('.badge', { hasText: /완료|실패/ }).first()).toBeVisible({
      timeout: 150_000,
    })
  } catch (err) {
    const last = (await badge.innerText().catch(() => '?')).trim()
    throw new Error(
      `수집이 끝나지 않았습니다 (마지막 상태: ${last}).\n` +
        '  "대기 중" 에서 멈췄다면 Celery 워커가 떠 있는지 확인하세요:\n' +
        '    cd backend && poetry run celery -A app.worker.celery_app worker --loglevel=info --pool=solo',
    )
  } finally {
    clearInterval(watcher)
  }

  const panel = (await page.locator('.collect-panel, .badge').first().locator('..').innerText())
    .replace(/\s+/g, ' ')
    .trim()
  return { firstBadgeMs, totalMs: Date.now() - started, summary: panel }
}

/** "수집 25건 · 신규 2건 · ..." 에서 신규 건수를 뽑는다. */
export function parseNewCount(summary) {
  const m = summary.match(/신규\s*(\d+)\s*건/)
  return m ? Number(m[1]) : null
}
