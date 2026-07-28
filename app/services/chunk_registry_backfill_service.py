"""Resumable, content-safe P1.5 Chunk Registry backfill orchestration."""

import asyncio
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable

from app.repositories.chunk_repository import (
    list_chunk_registry_backfill_candidates,
    mark_chunk_registry_backfill,
)


BACKFILL_ADVISORY_LOCK_KEY = 715_001_500


@dataclass(frozen=True)
class BackfillOptions:
    api_key_id: int | None = None
    dry_run: bool = False
    use_default_chunking: bool = False
    default_chunk_size: int = 800
    default_chunk_overlap: int = 400
    concurrency: int = 1
    page_size: int = 100
    limit: int | None = None

    def validate(self) -> "BackfillOptions":
        if self.concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if self.page_size < 1:
            raise ValueError("page_size must be at least 1")
        if self.limit is not None and self.limit < 1:
            raise ValueError("limit must be at least 1")
        if self.default_chunk_size < 1:
            raise ValueError("default_chunk_size must be positive")
        if not 0 <= self.default_chunk_overlap < self.default_chunk_size:
            raise ValueError(
                "default_chunk_overlap must be non-negative and smaller than "
                "default_chunk_size"
            )
        return self


@dataclass
class BackfillSummary:
    discovered: int = 0
    would_process: int = 0
    completed: int = 0
    failed: int = 0
    settings_unknown: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _chunking_settings(
    candidate: dict[str, Any],
    options: BackfillOptions,
) -> tuple[int, int] | None:
    size = candidate.get("chunk_size")
    overlap = candidate.get("chunk_overlap")
    if size is not None and overlap is not None:
        return int(size), int(overlap)
    if options.use_default_chunking:
        return options.default_chunk_size, options.default_chunk_overlap
    return None


async def process_backfill_candidate(
    pg,
    *,
    candidate: dict[str, Any],
    options: BackfillOptions,
    ingest: Callable[..., Awaitable[dict]] | None = None,
) -> str:
    """Process one attachment and return a non-sensitive terminal status."""
    settings = _chunking_settings(candidate, options)
    if settings is None:
        if not options.dry_run:
            await mark_chunk_registry_backfill(
                pg,
                attachment_id=candidate["attachment_id"],
                api_key_id=candidate["api_key_id"],
                status="settings_unknown",
                error="chunking_settings_not_recorded",
            )
        return "settings_unknown"

    if options.dry_run:
        return "would_process"

    await mark_chunk_registry_backfill(
        pg,
        attachment_id=candidate["attachment_id"],
        api_key_id=candidate["api_key_id"],
        status="running",
    )
    file_record = {
        "id": candidate["file_id"],
        "storage_path": candidate["storage_path"],
        "filename": candidate["filename"],
        "ext": candidate["ext"],
        "api_key_id": candidate["api_key_id"],
        "external_user_id": candidate["external_user_id"],
        "status": candidate["file_status"],
    }
    try:
        if ingest is None:
            from app.services.vector_store_file_service import (
                attach_file_to_vector_store,
            )

            ingest = attach_file_to_vector_store
        await ingest(
            pg=pg,
            vector_store_id=candidate["vector_store_id"],
            file_id=candidate["file_id"],
            file_record=file_record,
            chunk_size=settings[0],
            chunk_overlap=settings[1],
            batch_id=None,
        )
    except Exception as exc:
        # Store only the exception class. Raw provider/file text is not persisted.
        await mark_chunk_registry_backfill(
            pg,
            attachment_id=candidate["attachment_id"],
            api_key_id=candidate["api_key_id"],
            status="failed",
            error=f"backfill_{type(exc).__name__}",
        )
        return "failed"

    await mark_chunk_registry_backfill(
        pg,
        attachment_id=candidate["attachment_id"],
        api_key_id=candidate["api_key_id"],
        status="completed",
    )
    return "completed"


async def run_chunk_registry_backfill(
    pool,
    *,
    options: BackfillOptions,
    ingest: Callable[..., Awaitable[dict]] | None = None,
) -> BackfillSummary:
    options.validate()
    summary = BackfillSummary()
    semaphore = asyncio.Semaphore(options.concurrency)
    after_id = None

    async with pool.acquire() as coordinator:
        locked = await coordinator.fetchval(
            "SELECT pg_try_advisory_lock($1)",
            BACKFILL_ADVISORY_LOCK_KEY,
        )
        if not locked:
            raise RuntimeError("another chunk registry backfill is already running")

        try:
            while options.limit is None or summary.discovered < options.limit:
                remaining = (
                    options.page_size
                    if options.limit is None
                    else min(options.page_size, options.limit - summary.discovered)
                )
                rows = await list_chunk_registry_backfill_candidates(
                    coordinator,
                    api_key_id=options.api_key_id,
                    after_id=after_id,
                    limit=remaining,
                )
                if not rows:
                    break
                candidates = [dict(row) for row in rows]
                summary.discovered += len(candidates)
                after_id = candidates[-1]["attachment_id"]

                async def process(candidate):
                    async with semaphore:
                        if options.dry_run:
                            return await process_backfill_candidate(
                                coordinator,
                                candidate=candidate,
                                options=options,
                                ingest=ingest,
                            )
                        async with pool.acquire() as pg:
                            return await process_backfill_candidate(
                                pg,
                                candidate=candidate,
                                options=options,
                                ingest=ingest,
                            )

                statuses = await asyncio.gather(
                    *(process(candidate) for candidate in candidates)
                )
                for status in statuses:
                    setattr(summary, status, getattr(summary, status) + 1)
        finally:
            await coordinator.fetchval(
                "SELECT pg_advisory_unlock($1)",
                BACKFILL_ADVISORY_LOCK_KEY,
            )

    return summary
