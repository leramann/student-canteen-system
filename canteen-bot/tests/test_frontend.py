
import pytest
from aiohttp.test_utils import TestClient, TestServer

from web_server import create_app


@pytest.mark.asyncio
async def test_main_page_returns_html():
    client = TestClient(TestServer(create_app()))
    await client.start_server()

    try:
        response = await client.get("/")

        assert response.status == 200

        html = await response.text()

        assert "<html" in html.lower()

    finally:
        await client.close()


@pytest.mark.asyncio
async def test_javascript_file_is_available():
    client = TestClient(TestServer(create_app()))
    await client.start_server()

    try:
        response = await client.get("/static/app.js")

        assert response.status == 200

        javascript = await response.text()

        assert len(javascript) > 0

    finally:
        await client.close()
