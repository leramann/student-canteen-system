
import pytest
from aiohttp.test_utils import TestClient, TestServer

from web_server import create_app


@pytest.mark.asyncio
async def test_health_returns_ok():
    client = TestClient(TestServer(create_app()))

    await client.start_server()

    try:
        response = await client.get("/health")

        assert response.status == 200

        data = await response.json()

        assert data == {
            "status": "ok",
            "message": "Server is running"
        }

    finally:
        await client.close()
