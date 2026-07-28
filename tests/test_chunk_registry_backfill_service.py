import asyncio

import pytest

from app.services.chunk_registry_backfill_service import (
    BackfillOptions,
    process_backfill_candidate,
    run_chunk_registry_backfill,
)


def candidate(**overrides):
    value = {
        "attachment_id": "vsf_1",
        "vector_store_id": "vs_1",
        "file_id": "file_1",
        "api_key_id": 7,
        "external_user_id": 70,
        "chunk_size": 800,
        "chunk_overlap": 200,
        "storage_path": "storage/files/file_1.txt",
        "filename": "file.txt",
        "ext": ".txt",
        "file_status": "ready",
    }
    value.update(overrides)
    return value


class FakeConnection:
    def __init__(self, fetch_pages=None, lock_available=True):
        self.executions = []
        self.fetch_pages = list(fetch_pages or [])
        self.lock_calls = []
        self.lock_available = lock_available

    async def execute(self, query, *args):
        self.executions.append((query, args))
        return "UPDATE 1"

    async def fetch(self, query, *args):
        self.executions.append((query, args))
        return self.fetch_pages.pop(0) if self.fetch_pages else []

    async def fetchval(self, query, *args):
        self.lock_calls.append((query, args))
        if "pg_try_advisory_lock" in query:
            return self.lock_available
        return True


class Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakePool:
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.acquires = 0
        self.workers = []

    def acquire(self):
        self.acquires += 1
        if self.acquires == 1:
            return Acquire(self.coordinator)
        worker = FakeConnection()
        self.workers.append(worker)
        return Acquire(worker)


def test_unknown_settings_are_not_guessed_or_ingested():
    pg = FakeConnection()
    calls = []

    async def ingest(**kwargs):
        calls.append(kwargs)

    status = asyncio.run(
        process_backfill_candidate(
            pg,
            candidate=candidate(chunk_size=None, chunk_overlap=None),
            options=BackfillOptions(),
            ingest=ingest,
        )
    )

    assert status == "settings_unknown"
    assert calls == []
    assert pg.executions[0][1] == (
        "vsf_1",
        7,
        "settings_unknown",
        "chunking_settings_not_recorded",
    )


def test_default_chunking_requires_explicit_opt_in():
    pg = FakeConnection()
    calls = []

    async def ingest(**kwargs):
        calls.append(kwargs)
        return {}

    status = asyncio.run(
        process_backfill_candidate(
            pg,
            candidate=candidate(chunk_size=None, chunk_overlap=None),
            options=BackfillOptions(
                use_default_chunking=True,
                default_chunk_size=900,
                default_chunk_overlap=100,
            ),
            ingest=ingest,
        )
    )

    assert status == "completed"
    assert calls[0]["chunk_size"] == 900
    assert calls[0]["chunk_overlap"] == 100


def test_failure_is_isolated_and_persisted_without_raw_error_text():
    pg = FakeConnection()

    async def ingest(**kwargs):
        raise RuntimeError("raw query and provider response must not persist")

    status = asyncio.run(
        process_backfill_candidate(
            pg,
            candidate=candidate(),
            options=BackfillOptions(),
            ingest=ingest,
        )
    )

    assert status == "failed"
    assert pg.executions[-1][1][-1] == "backfill_RuntimeError"
    assert "raw query" not in repr(pg.executions)


def test_dry_run_has_no_database_mutation():
    pg = FakeConnection()
    status = asyncio.run(
        process_backfill_candidate(
            pg,
            candidate=candidate(),
            options=BackfillOptions(dry_run=True),
        )
    )
    assert status == "would_process"
    assert pg.executions == []


def test_global_run_is_locked_paginated_and_resumable():
    coordinator = FakeConnection(fetch_pages=[[candidate()], []])
    pool = FakePool(coordinator)

    async def ingest(**kwargs):
        return {}

    summary = asyncio.run(
        run_chunk_registry_backfill(
            pool,
            options=BackfillOptions(page_size=10),
            ingest=ingest,
        )
    )

    assert summary.to_dict() == {
        "discovered": 1,
        "would_process": 0,
        "completed": 1,
        "failed": 0,
        "settings_unknown": 0,
    }
    assert "pg_try_advisory_lock" in coordinator.lock_calls[0][0]
    assert "pg_advisory_unlock" in coordinator.lock_calls[-1][0]
    fetches = [
        execution
        for execution in coordinator.executions
        if "WITH candidates AS" in execution[0]
    ]
    assert fetches[0][1] == (None, None, 10)
    assert fetches[1][1] == (None, "vsf_1", 10)


def test_invalid_backfill_options_are_rejected():
    with pytest.raises(ValueError, match="smaller"):
        BackfillOptions(
            default_chunk_size=800,
            default_chunk_overlap=800,
        ).validate()


def test_second_global_run_is_rejected_by_advisory_lock():
    pool = FakePool(FakeConnection(lock_available=False))
    with pytest.raises(RuntimeError, match="already running"):
        asyncio.run(
            run_chunk_registry_backfill(
                pool,
                options=BackfillOptions(dry_run=True),
            )
        )
