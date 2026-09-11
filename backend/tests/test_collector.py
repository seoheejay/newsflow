"""수집 단위 테스트 (SR-F-301~310).

httpx.MockTransport로 네트워크 없이 돈다.
"""

import threading
import time

import httpx
import pytest

from app.services.collector import (
    DEFAULT_RETRIES,
    NO_KEYWORD,
    CollectTarget,
    build_targets,
    collect,
)

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title>
  <item>
    <title>첫 기사</title>
    <link>https://example.com/1</link>
    <pubDate>Tue, 08 Sep 2026 05:12:00 GMT</pubDate>
  </item>
  <item>
    <title>둘째 기사</title>
    <link>https://example.com/2</link>
    <pubDate>Tue, 08 Sep 2026 06:30:00 GMT</pubDate>
  </item>
</channel></rss>
"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>t</title>
  <entry>
    <title>Atom 기사</title>
    <link href="https://example.com/atom/1"/>
    <updated>2026-09-08T07:00:00Z</updated>
  </entry>
</feed>
"""

NO_DATE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title>
  <item><title>날짜 없음</title><link>https://example.com/nodate</link></item>
</channel></rss>
"""


def _target(url: str, site: str = "구글", keyword: str = "AI", order: int = 1):
    return CollectTarget(url=url, site=site, sort_order=order, keyword=keyword)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# --------------------------------------------------------------------- 301, 205


def test_SR_F_301_builds_n_times_m_targets() -> None:
    targets = build_targets(
        ["AI", "반도체"],
        [("구글", "https://g.com/rss?q={keyword}", 1), ("네이버", "https://n.com/rss?q={keyword}", 2)],
    )
    assert len(targets) == 4
    assert {t.site for t in targets} == {"구글", "네이버"}
    assert {t.keyword for t in targets} == {"AI", "반도체"}


def test_SR_F_301_target_url_has_keyword_substituted() -> None:
    targets = build_targets(["반도체"], [("구글", "https://g.com/rss?q={keyword}", 1)])
    assert targets[0].url == "https://g.com/rss?q=%EB%B0%98%EB%8F%84%EC%B2%B4"


def test_SR_F_205_template_without_placeholder_is_collected_once() -> None:
    targets = build_targets(
        ["AI", "반도체", "백엔드"], [("공지", "https://x.com/rss", 1)]
    )
    assert len(targets) == 1
    assert targets[0].keyword == NO_KEYWORD


# ------------------------------------------------------------------ 302~305


def test_SR_F_302_303_parses_rss_title_link_published() -> None:
    client = _client(lambda req: httpx.Response(200, content=RSS.encode()))
    out = collect([_target("https://g.com/rss")], max_per_source=10, client=client)

    assert [i.title for i in out.items] == ["첫 기사", "둘째 기사"]
    assert out.items[0].link == "https://example.com/1"
    assert out.items[0].published_at.isoformat() == "2026-09-08T05:12:00"


def test_SR_I_201_parses_atom_as_well_as_rss() -> None:
    client = _client(lambda req: httpx.Response(200, content=ATOM.encode()))
    out = collect([_target("https://g.com/atom")], max_per_source=10, client=client)

    assert [i.title for i in out.items] == ["Atom 기사"]
    assert out.items[0].published_at.isoformat() == "2026-09-08T07:00:00"


def test_SR_F_304_missing_published_date_keeps_item_with_none() -> None:
    client = _client(lambda req: httpx.Response(200, content=NO_DATE_RSS.encode()))
    out = collect([_target("https://g.com/rss")], max_per_source=10, client=client)

    assert len(out.items) == 1
    assert out.items[0].published_at is None


def test_SR_F_305_items_carry_keyword_and_site() -> None:
    client = _client(lambda req: httpx.Response(200, content=RSS.encode()))
    out = collect(
        [_target("https://g.com/rss", site="지디넷", keyword="반도체")],
        max_per_source=10,
        client=client,
    )
    assert {(i.keyword, i.site) for i in out.items} == {("반도체", "지디넷")}


def test_SR_I_202_sends_identifiable_user_agent() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("user-agent")
        return httpx.Response(200, content=RSS.encode())

    # client를 직접 주지 않아야 collect()가 User-Agent를 붙인다.
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, headers={"User-Agent": "NewsFlow/0.1 (+test)"})
    collect([_target("https://g.com/rss")], max_per_source=10, client=client)
    assert "NewsFlow" in seen["ua"]


# ---------------------------------------------------------------------- 306, 307


def test_SR_F_306_concurrent_requests_never_exceed_three() -> None:
    lock = threading.Lock()
    active = 0
    peak = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return httpx.Response(200, content=RSS.encode())

    targets = [_target(f"https://g.com/rss?{i}") for i in range(12)]
    collect(targets, max_per_source=10, client=_client(handler))

    assert peak <= 3, f"동시 요청이 {peak}개까지 올랐다"


def test_SR_F_307_timeout_is_recorded_as_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    out = collect([_target("https://g.com/rss")], max_per_source=10, client=_client(handler))

    assert out.items == []
    assert out.node_logs[0].error == "timeout"
    assert out.node_logs[0].count == 0


# ---------------------------------------------------------------------- 308~310


def test_SR_F_308_one_bad_target_does_not_stop_the_others() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "bad" in str(request.url):
            return httpx.Response(500)
        return httpx.Response(200, content=RSS.encode())

    targets = [
        _target("https://g.com/rss", site="구글"),
        _target("https://bad.com/rss", site="지디넷"),
        _target("https://n.com/rss", site="네이버"),
    ]
    out = collect(targets, max_per_source=10, client=_client(handler))

    assert len(out.items) == 4  # 정상 2개 소스 × 2건
    failed = [log for log in out.node_logs if log.error]
    assert len(failed) == 1
    assert failed[0].site == "지디넷"
    assert failed[0].error == "http 500"
    assert out.all_failed is False


def test_SR_F_308_malformed_feed_is_recorded_as_failure() -> None:
    client = _client(lambda req: httpx.Response(200, content=b"<<< not a feed"))
    out = collect([_target("https://g.com/rss")], max_per_source=10, client=client)

    assert out.items == []
    assert out.node_logs[0].error is not None


def test_SR_F_309_per_target_count_is_capped(  # noqa: D103
) -> None:
    client = _client(lambda req: httpx.Response(200, content=RSS.encode()))
    out = collect([_target("https://g.com/rss")], max_per_source=1, client=client)

    assert len(out.items) == 1


def test_SR_F_310_all_targets_failing_marks_run_failed() -> None:
    client = _client(lambda req: httpx.Response(503))
    targets = [_target("https://a.com/rss"), _target("https://b.com/rss")]
    out = collect(targets, max_per_source=10, client=client)

    assert out.all_failed is True
    assert out.failed_count == 2


def test_SR_F_310_partial_failure_is_not_a_failed_run() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "bad" in str(request.url):
            return httpx.Response(503)
        return httpx.Response(200, content=RSS.encode())

    out = collect(
        [_target("https://bad.com/rss"), _target("https://ok.com/rss")],
        max_per_source=10,
        client=_client(handler),
    )
    assert out.all_failed is False


def test_SR_F_310_no_targets_is_not_a_failed_run() -> None:
    out = collect([], max_per_source=10)
    assert out.all_failed is False
    assert out.items == []


# ------------------------------------------------------------------------ 기타


def test_SR_F_704_node_log_shape_matches_appendix_a3() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "bad" in str(request.url):
            raise httpx.TimeoutException("t", request=request)
        return httpx.Response(200, content=RSS.encode())

    out = collect(
        [_target("https://ok.com/rss"), _target("https://bad.com/rss", site="지디넷")],
        max_per_source=10,
        client=_client(handler),
    )
    ok, bad = (log.to_dict() for log in out.node_logs)

    assert set(ok) == {"site", "keyword", "count", "elapsed_ms"}
    assert set(bad) == {"site", "keyword", "count", "elapsed_ms", "error"}
    assert bad["error"] == "timeout"


def test_SR_F_404_collect_preserves_target_order() -> None:
    # "최초 1건"이 결정적이려면 결과 순서가 targets 순서와 같아야 한다.
    def handler(request: httpx.Request) -> httpx.Response:
        time.sleep(0.03 if "slow" in str(request.url) else 0)
        return httpx.Response(200, content=RSS.encode())

    targets = [
        _target("https://slow.com/rss", site="느림"),
        _target("https://fast.com/rss", site="빠름"),
    ]
    out = collect(targets, max_per_source=10, client=_client(handler))

    assert [log.site for log in out.node_logs] == ["느림", "빠름"]
    assert out.items[0].site == "느림"


def test_SR_N_203_connect_error_is_retried_up_to_three_attempts() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        raise httpx.ConnectError("boom", request=request)

    collect([_target("https://g.com/rss")], max_per_source=10, client=_client(handler))
    assert attempts["n"] == 1 + DEFAULT_RETRIES  # 최초 1회 + 재시도 2회


def test_SR_N_203_transient_failure_recovers_on_retry() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise httpx.ConnectError("일시적", request=request)
        return httpx.Response(200, content=RSS.encode())

    out = collect(
        [_target("https://g.com/rss")], max_per_source=10, client=_client(handler)
    )

    assert attempts["n"] == 2
    assert len(out.items) == 2
    assert out.node_logs[0].error is None  # 복구됐으므로 실패가 아니다


def test_SR_N_203_timeout_is_not_retried() -> None:
    """SR-F-307(15초) × 3회 = 45초라 SR-N-101(30초)을 넘긴다. TBD-04의 해소."""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        raise httpx.TimeoutException("timed out", request=request)

    collect([_target("https://g.com/rss")], max_per_source=10, client=_client(handler))
    assert attempts["n"] == 1


@pytest.mark.parametrize("status", [404, 500, 503])
def test_SR_N_203_http_errors_are_not_retried(status: int) -> None:
    # 다시 걸어도 같은 답이 온다.
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(status)

    collect([_target("https://g.com/rss")], max_per_source=10, client=_client(handler))
    assert attempts["n"] == 1


def test_SR_N_203_parse_failure_is_not_retried() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(200, content=b"<<< not a feed")

    collect([_target("https://g.com/rss")], max_per_source=10, client=_client(handler))
    assert attempts["n"] == 1


def test_SR_N_203_retries_can_be_disabled() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        raise httpx.ConnectError("boom", request=request)

    collect(
        [_target("https://g.com/rss")],
        max_per_source=10,
        retries=0,
        client=_client(handler),
    )
    assert attempts["n"] == 1
