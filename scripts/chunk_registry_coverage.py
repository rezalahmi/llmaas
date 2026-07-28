"""Report P1 Chunk Registry coverage without reading or printing content."""

import argparse
import asyncio
import json
import os
from decimal import Decimal

import asyncpg

from app.repositories.chunk_repository import get_chunk_registry_coverage


def build_coverage_report(row) -> dict:
    report = {
        key: int(value) if isinstance(value, Decimal) else value
        for key, value in dict(row).items()
    }
    total_attachments = report["total_attachments"]
    report["attachment_coverage_percent"] = (
        round(float(report["complete_attachments"]) * 100 / total_attachments, 2)
        if total_attachments
        else 100.0
    )
    total_chunks = report["total_chunks"]
    report["fully_versioned_coverage_percent"] = (
        round(float(report["fully_versioned_chunks"]) * 100 / total_chunks, 2)
        if total_chunks
        else (100.0 if total_attachments == 0 else 0.0)
    )
    return report


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

    report = build_coverage_report(row)
    print(json.dumps(report, sort_keys=True))
    if report["attachment_coverage_percent"] < args.fail_under:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(run())
