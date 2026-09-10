"""수집 파이프라인 통합 테스트 (부록 B.1의 5~14단계)와 AC-04."""

import httpx
from sqlalchemy.orm import Session

from app.constants import DEFAULT_USER_ID
from app.errors import EmailSendFailedError
from app.models import Article, FeedSource, Keyword, Setting
from app.services.link_normalize import link_hash
from app.services.pipeline import DEFAULT_MAX_PER_SOURCE, run_collection
from app.services.processing import select_new_items
from tests.test_processing import _item

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title>
  <item><title>기사 A</title><link>https://example.com/a</link>
    <pubDate>Tue, 08 Sep 2026 05:00:00 GMT</pubDate></item>
  <item><title>기사 B</title><link>https://example.com/b?utm_source=x</link>
    <pubDate>Tue, 08 Sep 2026 06:00:00 GMT</pubDate></item>
</channel></rss>
"""

SOURCE_ID = "01FFFFFFFFFFFFFFFFFFFFFFFF"


def _seed(db: Session, *, is_active: bool = True) -> None:
    db.add(
        Keyword(
            id="01KKKKKKKKKKKKKKKKKKKKKKKK", value="AI", user_id=DEFAULT_USER_ID
        )
    )
    db.add(
        FeedSource(
            id=SOURCE_ID,
            name="구글",
            url_template="https://g.com/rss?q={keyword}",
            sort_order=1,
            is_active=is_active,
            user_id=DEFAULT_USER_ID,
        )
    )
    db.commit()


def _rss_client() -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, content=RSS.encode())
        )
    )


def _failing_client(status: int = 500) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(status))
    )


# ----------------------------------------------------------------- 조회 단계


def test_SR_F_207_inactive_feed_source_is_not_collected(db_session: Session) -> None:
    _seed(db_session, is_active=False)
    assert run_collection(db_session, client=_rss_client()).targets == []


def test_SR_F_301_no_keywords_produces_no_targets(db_session: Session) -> None:
    _seed(db_session)
    db_session.query(Keyword).delete()
    db_session.commit()

    assert run_collection(db_session, client=_rss_client()).targets == []


def test_SR_F_105_max_per_source_comes_from_setting(db_session: Session) -> None:
    _seed(db_session)
    db_session.add(
        Setting(
            id="01SSSSSSSSSSSSSSSSSSSSSSSS",
            mail_subject="오늘의 뉴스",
            mail_to="me@example.com",
            max_per_source=1,
            user_id=DEFAULT_USER_ID,
        )
    )
    db_session.commit()

    result = run_collection(db_session, client=_rss_client())
    assert result.collected_count == 1  # 피드에 2건이 있지만 설정이 1이다


def test_SR_F_105_falls_back_to_default_when_no_setting_row(
    db_session: Session,
) -> None:
    _seed(db_session)
    # 설정 CRUD(SR-F-1xx)가 아직 없어 행이 없을 수 있다.
    result = run_collection(db_session, client=_rss_client())
    assert result.collected_count == 2
    assert DEFAULT_MAX_PER_SOURCE == 10


def test_pipeline_keyword_override_replaces_db_keywords(db_session: Session) -> None:
    _seed(db_session)
    result = run_collection(
        db_session, keywords=["반도체", "백엔드"], client=_rss_client()
    )
    assert {t.keyword for t in result.targets} == {"반도체", "백엔드"}


# --------------------------------------------------------------------- AC-04


def test_AC_04_second_run_delivers_only_new_articles(db_session: Session) -> None:
    """연속 2회 실행 시 두 번째에는 신규 기사만 전달된다 — 본 릴리스의 핵심."""
    _seed(db_session)

    first = run_collection(db_session, store=True, client=_rss_client())
    assert first.collected_count == 2
    assert first.new_count == 2
    assert first.stored is True

    second = run_collection(db_session, store=True, client=_rss_client())
    assert second.collected_count == 2  # 같은 피드를 다시 읽었고
    assert second.new_count == 0  # 전달 대상은 없다 (SR-F-405)


def test_SR_NFR_03_repeat_runs_do_not_duplicate_stored_articles(
    db_session: Session,
) -> None:
    _seed(db_session)
    run_collection(db_session, store=True, client=_rss_client())
    run_collection(db_session, store=True, client=_rss_client())

    assert db_session.query(Article).count() == 2


def test_SR_F_405_tracking_param_variants_count_as_already_delivered(
    db_session: Session,
) -> None:
    _seed(db_session)
    run_collection(db_session, store=True, client=_rss_client())

    # 저장된 기사 B의 링크에는 utm_source가 붙어 있었다. 정규화 해시가 같으므로
    # 파라미터만 다른 같은 기사는 신규가 아니다.
    assert select_new_items(db_session, [_item("https://example.com/b?utm_source=z")]) == []


def test_SR_F_601_store_is_opt_in(db_session: Session) -> None:
    _seed(db_session)
    result = run_collection(db_session, client=_rss_client())

    assert result.new_count == 2
    assert result.stored is False
    assert db_session.query(Article).count() == 0


def test_SR_F_601_stored_rows_carry_hash_and_user(db_session: Session) -> None:
    _seed(db_session)
    run_collection(db_session, store=True, client=_rss_client())

    row = db_session.query(Article).filter_by(link="https://example.com/a").one()
    assert row.link_hash == link_hash("https://example.com/a")
    assert row.user_id == DEFAULT_USER_ID
    assert row.site == "구글"
    assert row.keyword == "AI"


# ----------------------------------------------------------------- 실패 처리


def test_SR_F_310_run_stops_when_every_target_fails(db_session: Session) -> None:
    _seed(db_session)
    result = run_collection(db_session, client=_failing_client())

    assert result.failed is True
    assert result.new_count == 0
    assert result.node_logs and all(log.error for log in result.node_logs)


def test_SR_F_310_failed_run_stores_nothing(db_session: Session) -> None:
    _seed(db_session)
    run_collection(db_session, store=True, client=_failing_client())

    assert db_session.query(Article).count() == 0


# ----------------------------------------------------------------- 메일 발송


class _Sender:
    """mailer.send_mail 대체."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    def __call__(self, *, subject, mail_to, items):
        self.calls.append({"subject": subject, "mail_to": mail_to, "items": items})
        if self.error:
            raise self.error


def _seed_setting(db: Session, *, mail_to: str = "me@example.com") -> None:
    db.add(
        Setting(
            id="01SSSSSSSSSSSSSSSSSSSSSSSS",
            mail_subject="오늘의 뉴스",
            mail_to=mail_to,
            max_per_source=10,
            user_id=DEFAULT_USER_ID,
        )
    )
    db.commit()


def test_SR_F_506_sends_to_configured_recipient_with_configured_subject(
    db_session: Session,
) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    sender = _Sender()

    result = run_collection(
        db_session, send=True, mail_sender=sender, client=_rss_client()
    )

    assert result.sent is True
    assert len(sender.calls) == 1
    assert sender.calls[0]["mail_to"] == "me@example.com"
    assert sender.calls[0]["subject"] == "오늘의 뉴스"
    assert len(sender.calls[0]["items"]) == 2


def test_SR_F_506_cli_arguments_override_the_setting(db_session: Session) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    sender = _Sender()

    run_collection(
        db_session,
        send=True,
        mail_to="other@example.com",
        mail_subject="임시 제목",
        mail_sender=sender,
        client=_rss_client(),
    )

    assert sender.calls[0]["mail_to"] == "other@example.com"
    assert sender.calls[0]["subject"] == "임시 제목"


def test_SR_F_506_missing_recipient_fails_the_run(db_session: Session) -> None:
    _seed(db_session)  # Setting 행이 없다
    sender = _Sender()

    result = run_collection(
        db_session, send=True, mail_sender=sender, client=_rss_client()
    )

    assert result.failed is True
    assert result.sent is False
    assert sender.calls == []
    assert "수신자" in result.error


def test_SR_F_507_no_new_articles_skips_send_and_succeeds(
    db_session: Session,
) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    sender = _Sender()

    # 1회차로 전부 저장하면 2회차의 신규는 0건이다.
    run_collection(db_session, store=True, client=_rss_client())
    result = run_collection(
        db_session, send=True, mail_sender=sender, client=_rss_client()
    )

    assert result.new_count == 0
    assert sender.calls == []  # 발송하지 않는다
    assert result.sent is False
    assert result.failed is False  # success로 끝난다
    assert result.error is None


def test_SR_F_508_send_failure_fails_the_run_and_records_the_reason(
    db_session: Session,
) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    sender = _Sender(error=EmailSendFailedError("SMTP 인증 실패"))

    result = run_collection(
        db_session, send=True, mail_sender=sender, client=_rss_client()
    )

    assert result.failed is True
    assert result.sent is False
    assert result.error == "SMTP 인증 실패"


def test_SR_F_508_send_failure_does_not_undo_storage(db_session: Session) -> None:
    # 저장은 발송보다 앞선다(부록 B.1 13단계 → 16단계). 발송이 실패해도
    # 저장된 기사는 남고, 다음 실행에서 다시 전달되지 않는다.
    _seed(db_session)
    _seed_setting(db_session)
    sender = _Sender(error=EmailSendFailedError("SMTP 실패"))

    run_collection(
        db_session, store=True, send=True, mail_sender=sender, client=_rss_client()
    )

    assert db_session.query(Article).count() == 2


def test_send_is_opt_in(db_session: Session) -> None:
    _seed(db_session)
    _seed_setting(db_session)
    sender = _Sender()

    result = run_collection(db_session, mail_sender=sender, client=_rss_client())

    assert sender.calls == []
    assert result.sent is False
