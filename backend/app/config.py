"""환경 설정. 인증 정보는 코드가 아닌 .env에서 온다 (SR-N-301)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    # 기본값을 두지 않는다. root:test 같은 값을 코드에 박는 것은 SR-N-301 위반이고,
    # 기본값은 .env 누락을 조용히 감춘다.
    database_url: str

    # .env로 빼지 않는다 — pydantic-settings는 list[str] 환경변수를 JSON으로 파싱한다.
    cors_origins: list[str] = ["http://localhost:5173"]

    # SR-I-204 / SR-N-301: SMTP 접속 정보는 환경 변수로만 주입한다.
    # API 서버는 메일을 보내지 않으므로 선택값이다. 없으면 발송 시점에 실패한다.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    mail_from: str | None = None

    model_config = SettingsConfigDict(
        # 앱은 backend/에서 실행되지만 .env는 저장소 루트에 있다. cwd가 아닌 __file__ 기준.
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        # .env.example에 한글이 있고 Windows 기본 인코딩은 cp949다.
        env_file_encoding="utf-8",
        # 필수. .env의 SMTP_*, REDIS_URL, SCHEDULE_*, VITE_API_URL을 거부하지 않도록.
        extra="ignore",
    )


settings = Settings()
