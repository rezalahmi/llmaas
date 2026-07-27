import asyncio
import json

from app.services.idempotency_service import (
    IdempotencyClaim,
    canonical_json_hash,
    claim_idempotency,
    complete_idempotency,
)


class FakeConnection:
    def __init__(self, rows):
        self.rows = list(rows)
        self.executions = []

    async def fetchrow(self, query, *args):
        self.executions.append(("fetchrow", query, args))
        return self.rows.pop(0)

    async def execute(self, query, *args):
        self.executions.append(("execute", query, args))
        return "UPDATE 1"


def test_canonical_json_hash_ignores_object_key_order():
    first = canonical_json_hash(
        method="POST",
        route="/vector_stores/",
        payload={"name": "docs", "metadata": {"b": 2, "a": 1}},
        api_key_id=7,
    )
    second = canonical_json_hash(
        method="post",
        route="/vector_stores/",
        payload={"metadata": {"a": 1, "b": 2}, "name": "docs"},
        api_key_id=7,
    )

    assert first == second


def test_first_request_claims_key():
    pg = FakeConnection(
        [{"status": "started", "response_status": None, "response_body": None, "request_hash": "hash"}]
    )

    result = asyncio.run(
        claim_idempotency(
            pg,
            api_key_id=7,
            operation="create_vector_store",
            key="crawl-1",
            request_hash="hash",
        )
    )

    assert isinstance(result, IdempotencyClaim)


def test_completed_request_replays_stored_status_and_body():
    pg = FakeConnection(
        [
            None,
            {
                "status": "completed",
                "response_status": 200,
                "response_body": json.dumps({"id": "vs_123"}),
                "request_hash": "hash",
            },
        ]
    )

    response = asyncio.run(
        claim_idempotency(
            pg,
            api_key_id=7,
            operation="create_vector_store",
            key="crawl-1",
            request_hash="hash",
        )
    )

    assert response.status_code == 200
    assert json.loads(response.body) == {"id": "vs_123"}


def test_reused_key_with_different_payload_returns_409():
    pg = FakeConnection(
        [
            None,
            {
                "status": "completed",
                "response_status": 200,
                "response_body": {"id": "vs_123"},
                "request_hash": "old-hash",
            },
        ]
    )

    response = asyncio.run(
        claim_idempotency(
            pg,
            api_key_id=7,
            operation="create_vector_store",
            key="crawl-1",
            request_hash="new-hash",
        )
    )

    assert response.status_code == 409
    assert json.loads(response.body)["error"]["code"] == "idempotency_key_reused"


def test_concurrent_request_returns_retry_after():
    pg = FakeConnection(
        [
            None,
            {
                "status": "started",
                "response_status": None,
                "response_body": None,
                "request_hash": "hash",
            },
        ]
    )

    response = asyncio.run(
        claim_idempotency(
            pg,
            api_key_id=7,
            operation="upload_file",
            key="crawl-1",
            request_hash="hash",
        )
    )

    assert response.status_code == 409
    assert response.headers["retry-after"] == "2"
    assert json.loads(response.body)["error"]["code"] == "idempotency_request_in_progress"


def test_completion_persists_response_and_resource():
    pg = FakeConnection([])
    claim = IdempotencyClaim(7, "upload_file", "crawl-1", "hash")

    asyncio.run(
        complete_idempotency(
            pg,
            claim,
            response_status=200,
            response_body={"file_id": "file_123"},
            resource_type="file",
            resource_id="file_123",
        )
    )

    _, _, args = pg.executions[0]
    assert args[4] == 200
    assert json.loads(args[5]) == {"file_id": "file_123"}
    assert args[6:] == ("file", "file_123")
