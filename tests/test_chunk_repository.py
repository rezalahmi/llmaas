import asyncio
import json

from app.repositories.chunk_repository import (
    delete_chunk_inventory,
    get_chunk_registry_coverage,
    list_chunk_registry_backfill_candidates,
    mark_chunk_registry_backfill,
    replace_chunk_inventory,
    resolve_chunk_ref,
)


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeConnection:
    def __init__(self):
        self.executions = []
        self.batch = None
        self.fetchrow_result = None
        self.fetch_result = []

    def transaction(self):
        return FakeTransaction()

    async def execute(self, query, *args):
        self.executions.append((query, args))
        return "DELETE 1"

    async def executemany(self, query, rows):
        self.batch = (query, list(rows))

    async def fetchrow(self, query, *args):
        self.executions.append((query, args))
        return self.fetchrow_result

    async def fetch(self, query, *args):
        self.executions.append((query, args))
        return self.fetch_result


def test_replace_chunk_inventory_replaces_file_rows_atomically():
    pg = FakeConnection()

    asyncio.run(
        replace_chunk_inventory(
            pg,
            api_key_id=7,
            vector_store_id="vs_1",
            file_id="file_1",
            chunks=[
                {
                    "id": "chk_abc",
                    "chunk_ref": "chk_abc",
                    "chunk_index": 0,
                    "chunking_strategy": "recursive_character",
                    "chunking_version": "v1",
                    "embedding_model": "embed-model",
                    "embedding_version": "embed-v1",
                    "reranker_model": "rerank-model",
                    "reranker_version": "rerank-v1",
                    "generation_model": "generation-model",
                    "generation_version": "generation-v1",
                    "vector_index_provider": "chroma",
                    "vector_index_version": "chroma-v1",
                    "character_count": 12,
                    "token_count": 3,
                    "exact_hash": "a" * 64,
                    "metadata": {"page": 1},
                }
            ],
        )
    )

    assert len(pg.executions) == 1
    assert pg.executions[0][1] == (7, "vs_1", "file_1", ["chk_abc"])
    assert pg.batch is not None
    query, rows = pg.batch
    assert "ON CONFLICT (api_key_id, vector_store_id, chunk_ref)" in query
    assert "'registered'" in query
    assert len(rows) == 1
    assert rows[0][:6] == ("vs_1", "chk_abc", "chk_abc", 7, "file_1", 0)
    assert json.loads(rows[0][-1]) == {"page": 1}


def test_replace_with_empty_inventory_only_deletes_existing_rows():
    pg = FakeConnection()

    asyncio.run(
        replace_chunk_inventory(
            pg,
            api_key_id=7,
            vector_store_id="vs_1",
            file_id="file_1",
            chunks=[],
        )
    )

    assert len(pg.executions) == 1
    assert pg.executions[0][1] == (7, "vs_1", "file_1", [])
    assert pg.batch is None


def test_delete_chunk_inventory_scopes_delete_to_store_and_file():
    pg = FakeConnection()

    result = asyncio.run(
        delete_chunk_inventory(
            pg,
            api_key_id=7,
            vector_store_id="vs_1",
            file_id="file_1",
        )
    )

    assert result == "DELETE 1"
    assert pg.executions[0][1] == (7, "vs_1", "file_1")


def test_resolve_chunk_ref_is_tenant_scoped():
    pg = FakeConnection()
    pg.fetchrow_result = {"chunk_ref": "chk_abc"}

    row = asyncio.run(resolve_chunk_ref(pg, api_key_id=7, chunk_ref="chk_abc"))

    assert row == {"chunk_ref": "chk_abc"}
    query, args = pg.executions[0]
    assert "api_key_id = $1" in query
    assert args == (7, "chk_abc")


def test_registry_coverage_can_be_scoped_to_tenant():
    pg = FakeConnection()
    pg.fetchrow_result = {
        "total_attachments": 2,
        "complete_attachments": 1,
        "missing_registry_attachments": 1,
        "total_chunks": 3,
        "registered_chunks": 2,
        "unresolved_chunks": 1,
        "fully_versioned_chunks": 2,
    }

    row = asyncio.run(get_chunk_registry_coverage(pg, api_key_id=7))

    assert row["unresolved_chunks"] == 1
    assert "vector_store_files" in pg.executions[0][0]
    assert "chunk_count = 0" in pg.executions[0][0]
    assert pg.executions[0][1] == (7,)


def test_backfill_candidates_are_tenant_scoped_and_keyset_paginated():
    pg = FakeConnection()
    pg.fetch_result = [{"attachment_id": "vsf_2"}]

    rows = asyncio.run(
        list_chunk_registry_backfill_candidates(
            pg,
            api_key_id=7,
            after_id="vsf_1",
            limit=50,
        )
    )

    assert rows == [{"attachment_id": "vsf_2"}]
    query, args = pg.executions[0]
    assert "vs.api_key_id = vsf.api_key_id" in query
    assert "f.api_key_id = vsf.api_key_id" in query
    assert "ORDER BY attachment_id" in query
    assert args == (7, "vsf_1", 50)


def test_mark_backfill_status_is_tenant_scoped():
    pg = FakeConnection()

    asyncio.run(
        mark_chunk_registry_backfill(
            pg,
            attachment_id="vsf_1",
            api_key_id=7,
            status="failed",
            error="backfill_TimeoutError",
        )
    )

    query, args = pg.executions[0]
    assert "api_key_id = $2" in query
    assert args == ("vsf_1", 7, "failed", "backfill_TimeoutError")
