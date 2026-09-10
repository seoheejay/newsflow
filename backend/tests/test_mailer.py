"""메일 본문 생성과 발송 (SR-F-501~506, 508)."""

import re
from datetime import datetime

import pytest

from app.config import Settings
from app.errors import EmailSendFailedError
from app.services.collector import NO_KEYWORD, CollectedItem
from app.services.link_normalize import link_hash
from app.services.mailer import (
    build_message,
    format_published,
    render_html,
    render_text,
    send_mail,
)


def _item(
    *,
    title: str = "기사 제목",
    link: str = "https://example.com/1",
    keyword: str = "AI",
    site: str = "구글",
    order: int = 1,
    published: datetime | None = datetime(2026, 9, 8, 5, 12),
) -> CollectedItem:
    return CollectedItem(
        title=title,
        link=link,
        link_hash=link_hash(link),
        keyword=keyword,
        site=site,
        sort_order=order,
        published_at=published,
    )


def _config(**overrides) -> Settings:
    values = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_user": "sender@example.com",
        "smtp_password": "secret",
        "mail_from": "sender@example.com",
    }
    values.update(overrides)
    return Settings(**values)


class FakeSMTP:
    """smtplib 대체. 연결 방식과 보낸 메시지를 기록한다."""

    def __init__(self) -> None:
        self.logged_in: tuple[str, str] | None = None
        self.sent = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, message):
        self.sent.append(message)


# ---------------------------------------------------------------- 502, 503, 505


def test_SR_F_502_table_has_the_five_required_columns() -> None:
    html = render_html([_item()])
    # <thead>에 걸리지 않도록 <th 뒤에 공백을 요구한다.
    headers = re.findall(r"<th\s[^>]*>(.*?)</th>", html)

    assert headers == ["#", "제목", "피드 소스", "키워드", "발행일시"]


def test_SR_F_502_rows_are_numbered_from_one() -> None:
    html = render_html([_item(link="https://e.com/1"), _item(link="https://e.com/2")])
    cells = re.findall(r'<td style="[^"]*text-align:center[^"]*">(\d+)</td>', html)

    assert cells == ["1", "2"]


def test_SR_F_503_title_links_to_the_article() -> None:
    html = render_html([_item(title="제목", link="https://example.com/news/1")])
    assert '<a href="https://example.com/news/1"' in html
    assert ">제목</a>" in html


def test_SR_F_505_uses_inline_styles_only() -> None:
    html = render_html([_item()])

    assert "<style" not in html.lower()
    assert "stylesheet" not in html.lower()
    assert "<link" not in html.lower()
    assert 'style="' in html


def test_SR_F_505_avoids_layout_css_email_clients_break_on() -> None:
    html = render_html([_item()]).lower()

    assert "display:flex" not in html
    assert "display:grid" not in html
    assert "position:absolute" not in html
    assert "<table" in html  # table 레이아웃을 쓴다


def test_SR_F_501_escapes_html_in_titles() -> None:
    html = render_html([_item(title='<script>alert("x")</script>')])

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_SR_F_501_empty_title_has_a_placeholder() -> None:
    assert "(제목 없음)" in render_html([_item(title="")])


# --------------------------------------------------------------------- 504


def test_SR_F_504_published_at_is_shown_in_kst() -> None:
    # 보관은 UTC(SR-D-203), 표시는 Asia/Seoul(SR-F-504). +9시간.
    assert format_published(_item(published=datetime(2026, 9, 8, 5, 12))) == (
        "2026-09-08 14:12"
    )


def test_SR_F_504_kst_conversion_can_cross_the_date_line() -> None:
    assert format_published(_item(published=datetime(2026, 9, 8, 16, 0))) == (
        "2026-09-09 01:00"
    )


def test_SR_F_304_missing_published_shows_a_dash() -> None:
    assert format_published(_item(published=None)) == "-"


def test_SR_F_504_html_contains_the_converted_time() -> None:
    html = render_html([_item(published=datetime(2026, 9, 8, 5, 12))])
    assert "2026-09-08 14:12" in html


# --------------------------------------------------------------------- 키워드


def test_SR_F_205_no_keyword_source_shows_the_stored_value() -> None:
    # 저장값과 표시값이 같아야 한다. 표시 단계에서 변환하지 않는다.
    html = render_html([_item(keyword=NO_KEYWORD)])
    assert NO_KEYWORD == "(전체)"
    assert "(전체)" in html


# --------------------------------------------------------------------- 메시지


def test_SR_F_506_message_carries_subject_recipient_and_sender() -> None:
    message = build_message(
        subject="오늘의 뉴스",
        mail_to="me@example.com",
        mail_from="bot@example.com",
        items=[_item()],
    )

    assert message["Subject"] == "오늘의 뉴스"
    assert message["To"] == "me@example.com"
    assert "bot@example.com" in message["From"]


def test_SR_F_501_message_is_multipart_with_html_and_text() -> None:
    message = build_message(
        subject="s", mail_to="a@b.com", mail_from="c@d.com", items=[_item()]
    )
    types = {part.get_content_type() for part in message.walk()}

    assert "text/html" in types
    assert "text/plain" in types


def test_render_text_alternative_lists_links() -> None:
    text = render_text([_item(title="제목", link="https://e.com/1")])
    assert "제목" in text
    assert "https://e.com/1" in text


# ------------------------------------------------------------- 발송 / 508


def test_SR_I_203_send_logs_in_and_sends_over_the_injected_connection() -> None:
    smtp = FakeSMTP()
    send_mail(
        subject="오늘의 뉴스",
        mail_to="me@example.com",
        items=[_item()],
        config=_config(),
        smtp_factory=lambda cfg: smtp,
    )

    assert smtp.logged_in == ("sender@example.com", "secret")
    assert len(smtp.sent) == 1
    assert smtp.sent[0]["To"] == "me@example.com"
    assert smtp.closed is True


@pytest.mark.parametrize(
    "missing", ["smtp_host", "smtp_user", "smtp_password", "mail_from"]
)
def test_SR_N_301_missing_credentials_fail_with_email_send_failed(
    missing: str,
) -> None:
    with pytest.raises(EmailSendFailedError) as caught:
        send_mail(
            subject="s",
            mail_to="me@example.com",
            items=[_item()],
            config=_config(**{missing: None}),
            smtp_factory=lambda cfg: FakeSMTP(),
        )
    assert caught.value.code == "EMAIL_SEND_FAILED"
    assert missing.upper() in caught.value.message


@pytest.mark.parametrize("field", ["smtp_user", "smtp_password"])
def test_SR_F_508_non_ascii_credentials_give_an_actionable_message(
    field: str,
) -> None:
    # .env.example의 예시 문구를 그대로 둔 경우. smtplib이 내는
    # UnicodeEncodeError는 원인을 짐작하기 어려워 미리 걸러낸다.
    with pytest.raises(EmailSendFailedError) as caught:
        send_mail(
            subject="s",
            mail_to="me@example.com",
            items=[_item()],
            config=_config(**{field: "앱비밀번호16자리"}),
            smtp_factory=lambda cfg: FakeSMTP(),
        )

    assert field.upper() in caught.value.message
    assert "ASCII" in caught.value.message


def test_SR_F_508_smtp_error_becomes_email_send_failed() -> None:
    def boom(cfg):
        raise OSError("connection refused")

    with pytest.raises(EmailSendFailedError) as caught:
        send_mail(
            subject="s",
            mail_to="me@example.com",
            items=[_item()],
            config=_config(),
            smtp_factory=boom,
        )

    assert caught.value.code == "EMAIL_SEND_FAILED"
    assert caught.value.status_code == 500
    assert "connection refused" in caught.value.message
