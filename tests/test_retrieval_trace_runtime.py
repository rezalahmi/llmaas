import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.routers.chat_router import stream_response
from app.schemas.file_search import (
    FileSearchResponse,
    RetrievalCandidateFact,
)
from app.services.retrieval_trace_service import build_retrieval_trace


def _runtime(status="completed", failure=None, reranking="completed"):
    stages = {
        "query_rewrite": {"status": "not_requested", "failure": None},
        "dense_retrieval": {"status": "completed", "failure": None},
        "filtering": {"status": "completed", "failure": None},
        "reranking": {
            "status": reranking,
            "failure": failure if reranking in {"failed", "degraded"} else None,
        },
        "context_selection": {"status": "completed", "failure": None},
    }
    return {
        "attempt_count": 1,
        "query_rewrite_count": 0,
        "latency_ms": 7,
        "retrieval_status": status,
        "retrieval_failure": failure,
        "stages": stages,
    }


def _trace(runtime=None):
    fact = RetrievalCandidateFact(
        source_id="tenant-file-1",
        chunk_ref="tenant-chunk-1",
        vector_store_id="vs-1",
        dense_distance=0.2,
        dense_rank=1,
        rerank_score=0.8,
        rerank_rank=1,
        selected=True,
    )
    response = FileSearchResponse(
        results=[],
        retrieval_facts=[fact],
        retrieval_runtime=runtime or _runtime(),
    )
    return build_retrieval_trace(
        fs_response=response,
        vector_store_ids=["vs-1"],
        generation_model="runtime-model:42",
        trace_id="ragtrace_runtime_test",
    ).model_dump(mode="json")


def test_runtime_trace_is_content_free_and_uses_request_model():
    trace = _trace()
    serialized = json.dumps(trace)

    assert trace["versions"]["generation_model"] == "runtime-model"
    assert trace["versions"]["generation_version"] == "42"
    assert trace["confidence"] == {
        "answer_confidence": None,
        "confidence_status": "not_supported",
        "confidence_method": None,
        "calibration_version": None,
    }
    for forbidden in ("query", "text", "content", "api_key", "exception"):
        assert f'"{forbidden}"' not in serialized.lower()


def test_degraded_reranker_trace_keeps_attribution_and_failure():
    trace = _trace(
        _runtime(
            status="degraded",
            failure="provider_error",
            reranking="degraded",
        )
    )

    assert trace["retrieval_status"] == "degraded"
    assert trace["retrieval_failure"] == "provider_error"
    assert trace["retrieved_sources"][0]["selected"] is True


@pytest.mark.asyncio
async def test_stream_emits_exactly_one_trace_after_created_before_delta():
    messages = [
        {
            "type": "message",
            "data": "event: response.created\ndata: {}\n\n",
        },
        {
            "type": "message",
            "data": (
                "event: response.output_text.delta\n"
                'data: {"delta":"hello"}\n\n'
            ),
        },
        {
            "type": "message",
            "data": (
                "event: response.usage\n"
                'data: {"total_tokens":0}\n\n'
            ),
        },
    ]

    async def listen():
        for message in messages:
            yield message

    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.close = AsyncMock()
    pubsub.listen.return_value = listen()
    redis = MagicMock()
    redis.pubsub.return_value = pubsub

    chunks = [
        chunk
        async for chunk in stream_response(
            redis,
            AsyncMock(),
            "key-1",
            "request-1",
            retrieval_trace=_trace(),
        )
    ]
    body = "".join(chunks)

    assert body.count("event: response.retrieval_trace") == 1
    assert body.index("event: response.created") < body.index(
        "event: response.retrieval_trace"
    )
    assert body.index("event: response.retrieval_trace") < body.index(
        "event: response.output_text.delta"
    )
