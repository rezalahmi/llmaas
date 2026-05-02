# tests\test_responses_stream.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_stream_response(client, patch_redis):

    async def msg_generator():
        yield {"type": "message", "data": json.dumps({"response": "Hi"})}
        yield {"type": "message", "data": "[DONE]"}

    pubsub_mock = MagicMock()  # ⛔️ اینجا AsyncMock غلطه
    pubsub_mock.subscribe = AsyncMock()
    pubsub_mock.listen.return_value = msg_generator()

    patch_redis.pubsub = MagicMock(return_value=pubsub_mock)  # ⛔️ مهم

    patch_redis.lpush = AsyncMock()

    patch_redis.get = AsyncMock(return_value=json.dumps({
        "user_id": "test-user",
        "rpm_limit": 60,
        "api_key": "test-key"
    }))

    # اگر rate_limit داری
    pipe_mock = MagicMock()
    pipe_mock.incrby.return_value = pipe_mock
    pipe_mock.expire.return_value = pipe_mock
    pipe_mock.execute = AsyncMock(return_value=(1, True))

    patch_redis.pipeline = MagicMock(return_value=pipe_mock)

    r = await client.post(
        "/v1/responses",
        json={"prompt": "hello", "stream": True},
        headers={"Authorization": "Bearer test-key"}
    )

    assert r.status_code == 200

    chunks = [chunk async for chunk in r.aiter_text()]

    assert any("Hi" in c for c in chunks)
    assert any("[DONE]" in c for c in chunks)