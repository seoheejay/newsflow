"""수집 파이프라인 수동 실행 (SR-F-301~310, 401~407).

    poetry run python -m app.cli.collect
    poetry run python -m app.cli.collect --keyword AI --keyword 반도체
    poetry run python -m app.cli.collect --store          # 신규 기사를 저장한다

Celery는 아직 붙이지 않았다. 이 스크립트가 부록 B.1의 5~14단계를 그대로 돈다.
"""

from __future__ import annotations

import argparse
import sys

from app.db import SessionLocal
from app.services.collector import DEFAULT_TIMEOUT_SECONDS, MAX_CONCURRENCY
from app.services.pipeline import run_collection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.collect",
        description="RSS 수집과 중복 제거를 한 번 수행한다 (메일 발송은 하지 않는다).",
    )
    parser.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        metavar="말",
        help="DB의 키워드 대신 쓸 키워드. 여러 번 지정할 수 있다.",
    )
    parser.add_argument(
        "--max-per-source",
        type=int,
        metavar="N",
        help="주소별 최대 수집 건수 (SR-F-309). 기본값은 설정값.",
    )
    parser.add_argument(
        "--store",
        action="store_true",
        help="전달 대상을 저장한다 (SR-F-601). 두 번 실행하면 AC-04를 확인할 수 있다.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        metavar="초",
        help=f"개별 요청 대기 상한 (SR-F-307). 기본 {DEFAULT_TIMEOUT_SECONDS}.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=MAX_CONCURRENCY,
        metavar="N",
        help=f"동시 요청 수 (SR-F-306). 기본 {MAX_CONCURRENCY}.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=0,
        metavar="N",
        help="일시적 오류 재시도 횟수 (SR-N-203). 기본 0 — SR-N-101과 상충한다.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        metavar="N",
        help="출력할 전달 대상 기사 수. 기본 20.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    with SessionLocal() as db:
        result = run_collection(
            db,
            keywords=args.keywords,
            max_per_source=args.max_per_source,
            store=args.store,
            timeout=args.timeout,
            max_concurrency=args.concurrency,
            retries=args.retries,
        )

    if not result.targets:
        print("수집 주소가 없다. 키워드나 활성 피드 소스를 등록하고 다시 실행할 것.")
        print("  --keyword 로 키워드를 직접 넘길 수도 있다.")
        return 1

    print(f"\n주소 {len(result.targets)}개")
    print("-" * 72)
    for log in result.node_logs:
        keyword = log.keyword or "-"
        status = f"실패: {log.error}" if log.error else f"{log.count}건"
        print(f"  {log.site:<12} {keyword:<12} {status:<28} {log.elapsed_ms:>6}ms")

    print("-" * 72)
    print(f"  수집          {result.collected_count}건")
    print(f"  실행 내 중복 제거 후  {result.deduped_count}건   (SR-F-404)")
    print(f"  신규          {result.new_count}건   (SR-F-405)")
    if result.stored:
        print(f"  저장          {result.new_count}건   (SR-F-601)")
    elif result.new_count:
        print("  저장          안 함 — 저장하려면 --store")

    if result.failed:
        print("\n전체 주소 수집 실패. 실행을 실패로 처리한다 (SR-F-310).")
        return 2

    if result.new_items:
        print(f"\n전달 대상 (SR-F-406 정렬, 최대 {args.limit}건)")
        print("-" * 72)
        for item in result.new_items[: args.limit]:
            published = (
                item.published_at.strftime("%Y-%m-%d %H:%M") if item.published_at else "-"
            )
            print(f"  [{item.keyword or '-'}] {item.site:<10} {published:<17} {item.title[:40]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
