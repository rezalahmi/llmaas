# tests\test_responses_non_stream.py
import pytest
import json

@pytest.mark.asyncio
async def test_responses_non_stream(client, patch_celery):

    r = await client.post(
        "/v1/responses",
        json={"prompt": "hello", "stream": False},
        headers={"Authorization": "Bearer test-key"}
    )

    assert r.status_code == 200

    data = r.json()
    assert data["output"][0]["content"][0]["text"] == "hello world"

    patch_celery.delay.assert_called_once()