"""수집 파이프라인 통합 테스트 (부록 B.1의 5~14단계)와 AC-04."""

import httpx
from sqlalchemy.orm import Session

from app.constants import DEFAULT_USER_ID
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
