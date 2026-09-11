// 사전 조건 확인. 빠지면 테스트가 알 수 없는 이유로 무너지므로 여기서 먼저 막는다.
const API = process.env.VITE_API_URL ?? 'http://localhost:8000'

function fail(lines) {
  throw new Error(['', 'E2E 사전 조건이 갖춰지지 않았습니다.', '', ...lines, ''].join('\n'))
}

export default async function globalSetup() {
  let res
  try {
    res = await fetch(`${API}/settings`)
  } catch (err) {
    fail([
      `  API 서버(${API})에 연결할 수 없습니다: ${err.message}`,
      '',
      '  docs/README.md 5절대로 띄우세요:',
      '    cd backend && poetry run uvicorn main:app --reload',
      '',
      '  DB·Redis 도 필요합니다:',
      '    docker compose up -d',
    ])
  }

  if (!res.ok) {
    fail([`  API 서버가 ${res.status} 를 돌려줍니다. DB 마이그레이션이 적용됐는지 확인하세요:`,
      '    cd backend && poetry run alembic upgrade head'])
  }

  const settings = await res.json()
  if (!settings.mail_to) {
    console.warn(
      '\n[경고] 설정에 수신자가 없습니다. 수집 실행은 되지만 메일 발송 단계에서 실패합니다.\n' +
        '       설정 화면에서 수신자를 채우면 메일까지 확인됩니다.\n',
    )
  }

  // 수집 실행 테스트는 Celery 워커가 있어야 끝난다. 여기서는 알릴 수만 있다.
  console.log(
    '\n[사전 조건] Celery 워커가 떠 있어야 수집 실행 테스트가 통과합니다.\n' +
      '            cd backend && poetry run celery -A app.worker.celery_app worker --loglevel=info --pool=solo\n',
  )
}
