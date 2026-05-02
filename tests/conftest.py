# tests\conftest.py
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


import app.main
print("REAL generate_task PATH:", app.main.generate_task)
print("MODULE:", app.main.generate_task.__module__)


import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from app.main import app, get_redis
import pytest_asyncio
from app.auth import get_api_key


@pytest.fixture(autouse=True)
def mock_rate_limit():
    with patch("app.main.check_rate_limit") as m:
        m.return_value = None
        yield

@pytest.fixture(autouse=True)
def override_auth():
    from app.auth import get_api_key

    async def fake_user():
        return {
            "user_id": "test-user",
            "rpm_limit": 100,
        }

    app.dependency_overrides[get_api_key] = fake_user
    yield
    app.dependency_overrides.pop(get_api_key, None)
    

@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def patch_redis():
    mock_redis = AsyncMock()

    async def override_get_redis():
        return mock_redis

    # ❌ clear نکن
    app.dependency_overrides[get_redis] = override_get_redis

    yield mock_redis

    # فقط همون override خودت رو پاک کن
    app.dependency_overrides.pop(get_redis, None)

@pytest.fixture(autouse=True)
def mock_token_counter():
    """جلوگیری از خطای نبودن فایل tiktoken در تست‌ها"""
    with patch("app.main.count_tokens") as mocked:
        mocked.return_value = 10  # یک عدد فرضی
        yield mocked

@pytest.fixture
def patch_celery():
    mock_result = MagicMock()
    mock_result.id = "test-task-id"
    mock_result.get.return_value = {
        "response": "hello world",
        "input_tokens": 10,
        "output_tokens": 20,
    }

    with patch("app.main.generate_task") as mock_generate:
        mock_generate.delay.return_value = mock_result
        yield mock_generate


