# NewsFlow

키워드 기반 뉴스 스크랩 자동화. 매일 정해진 시각에 RSS를 수집해 메일로 발송한다.

## 개발 환경 준비

### 1. 사전 설치

- Python 3.13
- Node.js 20 이상
- Docker Desktop
- Poetry

### 2. 저장소 받기

```
git clone https://github.com/seoheejay/newsflow.git
cd newsflow
```

### 3. 환경변수

`.env.example`을 복사해 `.env`로 만들고 값을 채운다.

```
copy .env.example .env
```

Gmail을 쓸 경우 계정 비밀번호가 아니라 **앱 비밀번호**가 필요하다.
Google 계정 → 보안 → 2단계 인증 → 앱 비밀번호에서 발급받는다.

### 4. DB / Redis 실행

```
docker compose up -d
docker ps
```

`newsflow-db`, `newsflow-redis` 두 개가 보이면 정상.

### 5. 백엔드

```
cd backend
poetry install
poetry run uvicorn main:app --reload
```

http://localhost:8000/docs 접속해서 엔드포인트가 보이면 정상.

### 6. Celery 워커

수집 실행(`POST /collect`)을 처리한다. 백엔드와 별도 창에서 띄운다.

```
cd backend
poetry run celery -A app.worker.celery_app worker --loglevel=info --pool=solo
```

`--pool=solo`는 Windows에서 필수다. 기본 prefork 풀은 `fork()`에 기대는데 Windows에는 없다.

### 7. Celery beat (자동 실행)

매일 정해진 시각에 수집을 실행한다. **또 다른 창**에서 띄운다.

```
cd backend
poetry run celery -A app.worker.celery_app beat --loglevel=info
```

Windows에서는 워커의 `-B` / `--beat` 옵션이 막혀 있어(`-B option does not work on Windows`)
beat를 반드시 별도 프로세스로 띄워야 한다.

**시각은 설정 화면에서 바꾼다** (SR-F-805). 기본값은 한국 시간 08:00이다.
beat는 매분 틱만 보내고 지금이 실행 시각인지는 작업이 DB를 보고 판단하므로,
시각을 바꿔도 beat를 다시 띄울 필요가 없다.

`.env`의 `SCHEDULE_HOUR` / `SCHEDULE_MINUTE`는 설정 행이 아직 없을 때의 초기값으로만 쓰인다.

워커 없이 수집만 한 번 돌려보려면 (메일 발송 포함):

```
poetry run python -m app.cli.collect --keyword AI --store --send
```

### 8. 프론트엔드

```
cd frontend
npm install
npm run dev
```

http://localhost:5173 접속 확인.

---

## 프로젝트 구조

```
newsflow/
├── backend/            FastAPI + SQLAlchemy + Celery
├── frontend/           React + Vite
├── docs/               요구사항 문서
├── docker-compose.yml  MySQL + Redis
└── .env.example        환경변수 예시
```

---

## 개발 규칙

### API

- JSON 속성명은 `snake_case`
- 일시는 ISO 8601 UTC (`2026-09-08T14:30:00Z`)
- 목록 응답은 `{ total_count, page, items_per_page, items }`
- 오류 응답은 `{ code, message, fields? }`

입력값 오류는 FastAPI 기본값인 422가 아니라 **400**으로 응답한다 (SRS 부록 C.2).
프론트는 `detail`이 아니라 `code`를 읽는다.

상세 명세는 `docs/` 의 SRS 부록 A 참조.

### 상태 코드

| 상황 | 코드 |
|---|---|
| 조회 성공 | 200 |
| 생성 성공 | 201 |
| 실행 접수 | 202 |
| 삭제 성공 | 204 |
| 입력값 오류 | 400 |
| 없는 리소스 | 404 |
| 충돌 (이름 중복, 실행 진행 중) | 409 |

### 커밋 메시지

요구사항 ID를 포함한다.

```
feat(SR-F-405): 저장소 대비 신규 기사 판정 추가
fix(SR-F-306): 동시 요청 수 제한 누락 수정
chore: 개발 환경 구성
```

| 접두어 | 의미 |
|---|---|
| feat | 기능 추가 |
| fix | 버그 수정 |
| refactor | 구조 개선 |
| chore | 설정 · 패키지 |
| wip | 작업 중 |

### 브랜치

```
main                    항상 동작하는 상태
feat/backend-collect    백엔드 작업
feat/frontend-articles  프론트 작업
```

---

## 담당

| 영역 | 담당 |
|---|---|
| 백엔드 | |
| 프론트엔드 | |

---

## 문서

`docs/` 폴더 참조.

| 문서 | 내용 |
|---|---|
| URS | 사용자 요구사항. 무엇이 필요한가 |
| SRS | 소프트웨어 요구사항. 시스템이 무엇을 하는가 |

---

## 자주 막히는 지점

| 증상 | 원인 |
|---|---|
| 브라우저 콘솔에만 에러, 서버 로그엔 없음 | CORS 미설정 |
| 400 `VALIDATION_ERROR`가 계속 남 | `Content-Type: application/json` 헤더 누락 |
| 특정 경로만 404 | 라우터 등록 순서 (`/{id}`가 위에 있음) |
| `res.json()`에서 에러 | 204 응답은 본문이 없음 |
| 필드가 undefined | snake_case 확인 |
| Celery 워커가 안 돎 | Windows는 `--pool=solo` 필요 |
| `-B option does not work on Windows` | beat를 별도 프로세스로 띄울 것 (7절) |
| 수집 버튼을 눌러도 `queued`에서 멈춤 | Celery 워커가 안 떠 있음 (6절) |
| 3307 포트 충돌 | 다른 MySQL 컨테이너 실행 중인지 확인 |