import asyncio
import json

from app.repositories.chunk_repository import (
    delete_chunk_inventory,
    replace_chunk_inventory,
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

    def transaction(self):
        return FakeTransaction()

    async def execute(self, query, *args):
        self.executions.append((query, args))
        return "DELETE 1"

    async def executemany(self, query, rows):
        self.batch = (query, list(rows))


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
                    "id": "file_1_0",
                    "chunk_index": 0,
                    "chunking_strategy": "recursive_character",
                    "chunking_version": "v1",
                    "embedding_version": "embed-v1",
                    "character_count": 12,
                    "token_count": 3,
                    "exact_hash": "a" * 64,
                    "metadata": {"page": 1},
                }
            ],
        )
    )

    assert len(pg.executions) == 1
    assert pg.executions[0][1] == ("vs_1", "file_1")
    assert pg.batch is not None
    _, rows = pg.batch
    assert len(rows) == 1
    assert rows[0][:5] == ("vs_1", "file_1_0", 7, "file_1", 0)
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
    assert pg.batch is None


def test_delete_chunk_inventory_scopes_delete_to_store_and_file():
    pg = FakeConnection()

    result = asyncio.run(
        delete_chunk_inventory(
            pg,
            vector_store_id="vs_1",
            file_id="file_1",
        )
    )

    assert result == "DELETE 1"
    assert pg.executions[0][1] == ("vs_1", "file_1")
