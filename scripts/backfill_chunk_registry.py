"""Run the global P1.5 Chunk Registry backfill maintenance job."""

import argparse
import asyncio
import json
import os

import asyncpg

from app.services.chunk_registry_backfill_service import (
    BackfillOptions,
    run_chunk_registry_backfill,
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key-id", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--use-default-chunking", action="store_true")
    parser.add_argument("--default-chunk-size", type=int, default=800)
    parser.add_argument("--default-chunk-overlap", type=int, default=400)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


async def run():
    args = parse_args()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")
    options = BackfillOptions(
        api_key_id=args.api_key_id,
        dry_run=args.dry_run,
        use_default_chunking=args.use_default_chunking,
        default_chunk_size=args.default_chunk_size,
        default_chunk_overlap=args.default_chunk_overlap,
        concurrency=args.concurrency,
        page_size=args.page_size,
        limit=args.limit,
    )
    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=max(2, args.concurrency + 1),
    )
    try:
        summary = await run_chunk_registry_backfill(pool, options=options)
    finally:
        await pool.close()
    print(json.dumps(summary.to_dict(), sort_keys=True))
    if not options.dry_run and (summary.failed or summary.settings_unknown):
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(run())
