"""AC-01 대조용 내보내기.

기존 n8n 워크플로 결과와 나란히 놓고 비교한다.

n8n 에는 저장소 대비 중복 제거(SR-F-405)가 없었으므로, 그 단계 **전**까지만
돌린 결과를 적는다. 즉 수집 → 실행 내 중복 제거(SR-F-404) → 정렬(SR-F-406).
저장도 발송도 하지 않는다.
"""

import sys
from pathlib import Path

from app.db import SessionLocal
from app.services import settings_store
from app.services.collector import build_targets, collect
from app.services.mailer import format_published, render_html
from app.services.pipeline import load_active_feed_sources
from app.services.processing import dedupe_within_run, sort_for_delivery

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "ac01-newsflow.txt")

with SessionLocal() as db:
    cfg = settings_store.load_settings(db)
    sources = load_active_feed_sources(db)

targets = build_targets(cfg.keywords, sources)  # SR-F-301
outcome = collect(targets, max_per_source=cfg.max_per_source)  # SR-F-302~309
deduped = dedupe_within_run(outcome.items)  # SR-F-404
items = sort_for_delivery(deduped)  # SR-F-406, 407

lines = [
    "NewsFlow 수집 결과 (AC-01 대조용)",
    "저장소 대비 중복 제거(SR-F-405) 전 단계. n8n 과 같은 조건으로 맞춘 것이다.",
    "=" * 70,
    f"키워드           : {', '.join(cfg.keywords)}",
    f"활성 피드 소스    : {', '.join(name for name, _, _ in sources)}",
    f"소스당 최대 건수  : {cfg.max_per_source}",
    f"수집 주소        : {len(targets)}개",
    "",
    "주소별 수집 건수",
    "-" * 70,
]
for log in outcome.node_logs:
    status = f"실패({log.error})" if log.error else f"{log.count}건"
    lines.append(f"  {log.site:<12} {log.keyword:<10} {status:<20} {log.elapsed_ms:>6}ms")

lines += [
    "-" * 70,
    f"수집 {len(outcome.items)}건 → 실행 내 중복 제거 후 {len(items)}건",
    "",
    "전달 순서 (SR-F-406: 키워드 → 소스 정렬 순서 → 발행일시 내림차순)",
    "=" * 70,
]
for i, item in enumerate(items, start=1):
    lines.append(f"{i:>3}. [{item.keyword}] [{item.site}] {format_published(item)}")
    lines.append(f"     {item.title}")
    lines.append(f"     {item.link}")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
if items:
    OUT.with_suffix(".html").write_text(render_html(items), encoding="utf-8")

print(f"작성: {OUT}  ({len(items)}건)")
if items:
    print(f"      {OUT.with_suffix('.html')}  (메일 본문과 같은 표)")
