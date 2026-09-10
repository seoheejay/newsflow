"""RSS 수집 (SR-F-301~310).

Celery에 묶여 있지 않은 순수 함수다. 각 단계를 독립적으로 검증할 수 있어야 한다는
SR-N-402를 따르고, 이후 작업 처리기가 collect()를 그대로 호출하면 된다.
"""

from __future__ import annotations

import calendar
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

import feedparser
import httpx

from app.services.link_normalize import link_hash
from app.services.url_template import build_collect_url, has_keyword_placeholder

# SR-F-307. 개별 요청의 응답 대기 상한.
DEFAULT_TIMEOUT_SECONDS = 15.0

# SR-F-306. 동시 HTTP 요청 수 상한.
MAX_CONCURRENCY = 3

# SR-I-202. 대상 사이트가 누구의 요청인지 알 수 있어야 한다.
USER_AGENT = "NewsFlow/0.1 (+https://github.com/seoheejay/newsflow)"

# SR-F-205로 키워드 없이 조회되는 소스의 keyword 값.
# Article.keyword는 필수(SRS 5.1)라 빈 문자열을 쓴다.
NO_KEYWORD = ""


@dataclass(frozen=True)
class CollectTarget:
    """키워드 × 피드 소스 조합 하나 (SR-F-301)."""

    url: str
    site: str
    sort_order: int
    keyword: str


@dataclass(frozen=True)
class CollectedItem:
    """수집된 항목 하나 (SR-F-303, 305)."""

    title: str
    link: str
    link_hash: str
    keyword: str
    site: str
    sort_order: int
    published_at: datetime | None  # SR-F-304: 알 수 없으면 None


@dataclass
class NodeLog:
    """주소별 처리 결과 (SR-F-308, SR-F-704). 부록 A.3 node_logs 형태."""

    site: str
    keyword: str
    count: int
    elapsed_ms: int
    error: str | None = None

    def to_dict(self) -> dict:
        data = {
            "site": self.site,
            "keyword": self.keyword,
            "count": self.count,
            "elapsed_ms": self.elapsed_ms,
        }
        if self.error:
            data["error"] = self.error
        return data


@dataclass
class CollectOutcome:
    items: list[CollectedItem] = field(default_factory=list)
    node_logs: list[NodeLog] = field(default_factory=list)

    @property
    def failed_count(self) -> int:
        return sum(1 for log in self.node_logs if log.error)

    @property
    def all_failed(self) -> bool:
        """SR-F-310. 주소가 하나라도 있고 전부 실패했으면 실행을 실패로 본다."""
        return bool(self.node_logs) and self.failed_count == len(self.node_logs)


def build_targets(
    keywords: list[str], feed_sources: list[tuple[str, str, int]]
) -> list[CollectTarget]:
    """SR-F-301. 키워드 N × 활성 피드 소스 M으로 최대 N×M개의 주소를 만든다.

    feed_sources는 (name, url_template, sort_order) 튜플이며 활성 소스만 넘겨야 한다
    (SR-F-207의 판정은 호출자가 한다).

    {keyword}가 없는 템플릿은 키워드 수와 무관하게 1회만 만든다 (SR-F-205).
    """
    targets: list[CollectTarget] = []
    for name, url_template, sort_order in feed_sources:
        if not has_keyword_placeholder(url_template):
            targets.append(
                CollectTarget(
                    url=url_template,
                    site=name,
                    sort_order=sort_order,
                    keyword=NO_KEYWORD,
                )
            )
            continue
        for keyword in keywords:
            targets.append(
                CollectTarget(
                    url=build_collect_url(url_template, keyword),
                    site=name,
                    sort_order=sort_order,
                    keyword=keyword,
                )
            )
    return targets


def _published_at(entry) -> datetime | None:
    """SR-F-303 + SR-F-304.

    feedparser가 RSS 2.0(RFC 822)과 Atom(RFC 3339)을 모두 UTC struct_time으로 준다.
    파싱하지 못하면 해당 속성이 없거나 None이므로 그대로 None을 돌려준다.
    """
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            epoch = calendar.timegm(parsed)
            # DB 컬럼이 naive DateTime이고 SR-D-203이 UTC 보관을 요구한다.
            return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(tzinfo=None)
    return None


def _parse_entries(
    target: CollectTarget, body: bytes, max_per_source: int
) -> list[CollectedItem]:
    feed = feedparser.parse(body)

    # feedparser는 관대해서 bozo가 서도 항목을 건지는 경우가 많다.
    # 항목이 하나도 없을 때만 파싱 실패로 본다 (SR-F-308).
    if feed.bozo and not feed.entries:
        raise ValueError(f"feed parse failed: {feed.bozo_exception}")

    items: list[CollectedItem] = []
    for entry in feed.entries:
        link = (getattr(entry, "link", "") or "").strip()
        title = (getattr(entry, "title", "") or "").strip()
        if not link:
            # 링크가 없으면 중복 판단도 전달도 불가능하다.
            continue
        items.append(
            CollectedItem(
                title=title,
                link=link,
                link_hash=link_hash(link),  # SR-F-401
                keyword=target.keyword,  # SR-F-305
                site=target.site,  # SR-F-305
                sort_order=target.sort_order,
                published_at=_published_at(entry),
            )
        )
        # SR-F-309. 주소별 수집 건수는 소스당 최대 건수를 넘지 않는다.
        if len(items) >= max_per_source:
            break
    return items


def _fetch_one(
    client: httpx.Client, target: CollectTarget, max_per_source: int, retries: int
) -> tuple[list[CollectedItem], NodeLog]:
    started = time.monotonic()
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response = client.get(target.url)  # SR-F-302
            response.raise_for_status()
            items = _parse_entries(target, response.content, max_per_source)
        except Exception as exc:  # noqa: BLE001 - 주소 하나의 실패가 전체를 멈추면 안 된다
            last_error = exc
            if attempt < retries:
                continue
        else:
            elapsed = int((time.monotonic() - started) * 1000)
            return items, NodeLog(
                site=target.site,
                keyword=target.keyword,
                count=len(items),
                elapsed_ms=elapsed,
            )

    # SR-F-308. 실패한 주소는 0건으로 처리하고 로그만 남긴다.
    elapsed = int((time.monotonic() - started) * 1000)
    return [], NodeLog(
        site=target.site,
        keyword=target.keyword,
        count=0,
        elapsed_ms=elapsed,
        error=_error_text(last_error),
    )


def _error_text(exc: Exception | None) -> str:
    if exc is None:
        return "unknown error"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"http {exc.response.status_code}"
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def collect(
    targets: list[CollectTarget],
    *,
    max_per_source: int,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_concurrency: int = MAX_CONCURRENCY,
    retries: int = 0,
    client: httpx.Client | None = None,
) -> CollectOutcome:
    """SR-F-302~310. 주소 목록을 받아 항목과 주소별 로그를 돌려준다.

    결과는 targets 순서를 유지한다. SR-F-404의 "최초 1건"이 동시 실행 순서에 따라
    달라지지 않도록 하기 위함이다.

    retries의 기본값은 0이다. SR-N-203(최대 3회 재시도)은 이번 범위 밖이고,
    15초 타임아웃(SR-F-307)과 곱해지면 12개 소스 30초(SR-N-101)를 넘긴다.
    """
    if not targets:
        return CollectOutcome()

    owns_client = client is None
    if client is None:
        client = httpx.Client(
            timeout=timeout,  # SR-F-307
            headers={"User-Agent": USER_AGENT},  # SR-I-202
            follow_redirects=True,
        )

    try:
        # SR-F-306. 워커 수가 곧 동시 요청 수 상한이다.
        with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
            results = list(
                pool.map(
                    lambda t: _fetch_one(client, t, max_per_source, retries),
                    targets,
                )
            )
    finally:
        if owns_client:
            client.close()

    outcome = CollectOutcome()
    for items, log in results:
        outcome.items.extend(items)
        outcome.node_logs.append(log)
    return outcome
