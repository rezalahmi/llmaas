import httpx
import pytest

from app.services import reranker_service
from app.services.reranker_service import RerankerOutcome


class _AsyncClient:
    def __init__(self, post):
        self.post = post

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


@pytest.mark.asyncio
async def test_reranker_timeout_is_explicit_fallback(monkeypatch):
    async def post(*_, **__):
        raise httpx.ReadTimeout("provider details must not enter trace")

    monkeypatch.setattr(
        reranker_service.httpx,
        "AsyncClient",
        lambda: _AsyncClient(post),
    )
    candidates = [{"text": "private chunk"}]

    result = await reranker_service.rerank_results_with_status("private query", candidates)

    assert result.outcome == RerankerOutcome.FAILED_FALLBACK
    assert result.failure == "timeout"
    assert result.results is candidates


@pytest.mark.asyncio
async def test_reranker_provider_error_is_explicit_fallback(monkeypatch):
    async def post(*_, **__):
        raise httpx.ConnectError("secret provider response")

    monkeypatch.setattr(
        reranker_service.httpx,
        "AsyncClient",
        lambda: _AsyncClient(post),
    )
    candidates = [{"text": "private chunk"}]

    result = await reranker_service.rerank_results_with_status("private query", candidates)

    assert result.outcome == RerankerOutcome.FAILED_FALLBACK
    assert result.failure == "provider_error"
    assert "secret provider response" not in result.failure


@pytest.mark.asyncio
async def test_reranker_empty_provider_result_is_not_confused_with_failure(
    monkeypatch,
):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": []}

    async def post(*_, **__):
        return Response()

    monkeypatch.setattr(
        reranker_service.httpx,
        "AsyncClient",
        lambda: _AsyncClient(post),
    )

    result = await reranker_service.rerank_results_with_status(
        "query", [{"text": "chunk"}]
    )

    assert result.outcome == RerankerOutcome.ELIMINATED_ALL
    assert result.results == []
