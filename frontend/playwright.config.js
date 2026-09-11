import { defineConfig, devices } from '@playwright/test'

// 실제 백엔드·워커·DB를 상대로 도는 통합 점검이다. 목을 쓰지 않는다.
// 사전 조건은 docs/README.md 의 "E2E 통합 점검" 참조.
const BASE_URL = process.env.NF_E2E_BASE ?? 'http://localhost:5173'

export default defineConfig({
  testDir: './e2e',
  // 같은 DB를 건드리므로 순차 실행한다. 병렬로 돌리면 수집 실행이 409로 막힌다 (SR-F-705).
  fullyParallel: false,
  workers: 1,
  // 실제 RSS 조회와 메일 발송이 들어가므로 넉넉히 잡는다.
  timeout: 180_000,
  expect: { timeout: 20_000 },
  reporter: [['list']],
  globalSetup: './e2e/global-setup.js',
  use: {
    baseURL: BASE_URL,
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
    viewport: { width: 1280, height: 1100 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // 프론트는 자동으로 띄운다. 백엔드와 워커는 사람이 띄워야 한다 (global-setup 이 확인).
  webServer: {
    command: 'npm run dev',
    url: BASE_URL,
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
