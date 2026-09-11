"""메일 본문 생성과 발송 (SR-F-501~506, 508).

본문은 인라인 스타일 + table 레이아웃만 쓴다 (SR-F-505). 외부 스타일시트,
<style> 블록, flexbox, grid는 쓰지 않는다 — Outlook·네이버 메일 등에서 깨진다.
"""

from __future__ import annotations

import smtplib
import ssl
from datetime import timezone
from email.message import EmailMessage
from email.utils import formataddr
from html import escape

from app.clock import KST
from app.config import Settings, settings as default_settings
from app.errors import EmailSendFailedError
from app.services.collector import CollectedItem

SMTP_TIMEOUT_SECONDS = 30

# 인라인 스타일 (SR-F-505). 테이블 셀마다 되풀이되므로 상수로 둔다.
_TH = (
    "padding:8px 10px;border:1px solid #d0d0d0;background-color:#f4f4f4;"
    "font-size:13px;font-weight:bold;text-align:left;color:#333333;"
)
_TD = "padding:8px 10px;border:1px solid #d0d0d0;font-size:13px;color:#333333;"
_TD_CENTER = _TD + "text-align:center;white-space:nowrap;"
_TD_NOWRAP = _TD + "white-space:nowrap;"


def format_published(item: CollectedItem) -> str:
    """SR-F-504. UTC 보관값을 Asia/Seoul로 바꿔 표시한다."""
    if item.published_at is None:
        return "-"  # SR-F-304로 비워둔 값
    return (
        item.published_at.replace(tzinfo=timezone.utc)
        .astimezone(KST)
        .strftime("%Y-%m-%d %H:%M")
    )


def render_html(items: list[CollectedItem]) -> str:
    """SR-F-501~505. 전달 대상 기사로 HTML 본문을 만든다.

    열 구성은 SR-F-502대로 순번·제목·피드 소스·키워드·발행일시다.
    제목은 원문 링크로 연결한다 (SR-F-503).
    """
    rows = []
    for index, item in enumerate(items, start=1):
        title = escape(item.title) or "(제목 없음)"
        link = escape(item.link, quote=True)
        rows.append(
            f'<tr>'
            f'<td style="{_TD_CENTER}">{index}</td>'
            f'<td style="{_TD}">'
            f'<a href="{link}" style="color:#1a56c4;text-decoration:none;">{title}</a>'
            f"</td>"
            f'<td style="{_TD_NOWRAP}">{escape(item.site)}</td>'
            f'<td style="{_TD_NOWRAP}">{escape(item.keyword)}</td>'
            f'<td style="{_TD_NOWRAP}">{format_published(item)}</td>'
            f"</tr>"
        )

    return (
        '<div style="margin:0;padding:16px;background-color:#ffffff;'
        'font-family:\'Malgun Gothic\',AppleGothic,sans-serif;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'style="border-collapse:collapse;width:100%;max-width:900px;">'
        "<tr><td>"
        f'<p style="margin:0 0 12px 0;font-size:13px;color:#666666;">'
        f"신규 기사 {len(items)}건</p>"
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'style="border-collapse:collapse;width:100%;">'
        "<thead><tr>"
        f'<th style="{_TH}width:40px;">#</th>'
        f'<th style="{_TH}">제목</th>'
        f'<th style="{_TH}width:90px;">피드 소스</th>'
        f'<th style="{_TH}width:90px;">키워드</th>'
        f'<th style="{_TH}width:130px;">발행일시</th>'
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        '<p style="margin:12px 0 0 0;font-size:11px;color:#999999;">'
        "NewsFlow · 발행일시는 한국 시간</p>"
        "</td></tr></table></div>"
    )


def render_text(items: list[CollectedItem]) -> str:
    """HTML을 못 읽는 클라이언트를 위한 대체 본문."""
    lines = [f"신규 기사 {len(items)}건", ""]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. [{item.site}/{item.keyword}] {item.title}")
        lines.append(f"   {item.link}  ({format_published(item)})")
    return "\n".join(lines)


def build_message(
    *, subject: str, mail_to: str, mail_from: str, items: list[CollectedItem]
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("NewsFlow", mail_from))
    message["To"] = mail_to
    message.set_content(render_text(items))
    message.add_alternative(render_html(items), subtype="html")
    return message


def send_mail(
    *,
    subject: str,
    mail_to: str,
    items: list[CollectedItem],
    config: Settings | None = None,
    smtp_factory=None,
) -> None:
    """SR-F-506. 설정된 수신자에게 설정된 제목으로 발송한다.

    실패하면 EmailSendFailedError를 올린다 (SR-F-508, 부록 C.2 EMAIL_SEND_FAILED).
    smtp_factory는 테스트에서 SMTP 연결을 갈아끼우기 위한 것이다.
    """
    config = config or default_settings

    missing = [
        name
        for name, value in (
            ("SMTP_HOST", config.smtp_host),
            ("SMTP_USER", config.smtp_user),
            ("SMTP_PASSWORD", config.smtp_password),
            ("MAIL_FROM", config.mail_from),
        )
        if not value
    ]
    if missing:
        raise EmailSendFailedError(
            f".env에 값이 없다: {', '.join(missing)} (SR-N-301: 코드에 두지 않는다)"
        )

    # smtplib이 자격 증명을 ASCII로 인코딩한다. 한글이 섞여 있으면
    # UnicodeEncodeError가 나는데 원인을 짐작하기 어려워 미리 걸러낸다.
    for name, value in (("SMTP_USER", config.smtp_user), ("SMTP_PASSWORD", config.smtp_password)):
        if not value.isascii():
            raise EmailSendFailedError(
                f".env의 {name}에 ASCII가 아닌 문자가 있다. "
                ".env.example의 예시 문구를 실제 값으로 바꿨는지 확인할 것"
            )

    message = build_message(
        subject=subject,
        mail_to=mail_to,
        mail_from=config.mail_from,
        items=items,
    )

    try:
        with _connect(config, smtp_factory) as smtp:
            smtp.login(config.smtp_user, config.smtp_password)
            smtp.send_message(message)
    except EmailSendFailedError:
        raise
    except Exception as exc:  # noqa: BLE001 - 모든 발송 실패를 하나의 코드로 모은다
        raise EmailSendFailedError(f"메일 발송 실패: {exc}") from exc


def _connect(config: Settings, smtp_factory):
    """SR-I-203 / SR-N-303. 외부 SMTP 통신은 TLS로 감싼다."""
    if smtp_factory is not None:
        return smtp_factory(config)

    context = ssl.create_default_context()
    if config.smtp_port == 465:
        # 암시적 TLS
        return smtplib.SMTP_SSL(
            config.smtp_host,
            config.smtp_port,
            timeout=SMTP_TIMEOUT_SECONDS,
            context=context,
        )

    smtp = smtplib.SMTP(
        config.smtp_host, config.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
    )
    smtp.starttls(context=context)
    return smtp
