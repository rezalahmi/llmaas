"""Report P1 Chunk Registry coverage without reading or printing content."""

import argparse
import asyncio
import json
import os

import asyncpg

from app.repositories.chunk_repository import get_chunk_registry_coverage


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key-id", type=int)
    parser.add_argument(
        "--fail-under",
        type=float,
        default=100.0,
        help="Exit non-zero when registered coverage percentage is below this.",
    )
    return parser.parse_args()


async def run():
    args = parse_args()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")
    pg = await asyncpg.connect(dsn)
    try:
        row = await get_chunk_registry_coverage(
            pg,
            api_key_id=args.api_key_id,
        )
    finally:
        await pg.close()

    report = dict(row)
    total = report["total_chunks"]
    report["registered_coverage_percent"] = (
        round(report["registered_chunks"] * 100 / total, 2) if total else 100.0
    )
    report["fully_versioned_coverage_percent"] = (
        round(report["fully_versioned_chunks"] * 100 / total, 2)
        if total
        else 100.0
    )
    print(json.dumps(report, sort_keys=True))
    if report["registered_coverage_percent"] < args.fail_under:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(run())
