
import pytest
from aiohttp.test_utils import TestClient, TestServer

import web_server


@pytest.mark.asyncio
async def test_menu_returns_items(monkeypatch):
    # Подменяем запрос к базе данных тестовыми данными
    def fake_fetch_menu():
        return [
            {
                "id": 1,
                "category": "Напитки",
                "category_id": 1,
                "name": "Чай",
                "description": "Черный чай",
                "price": 100.0,
                "image_url": None,
                "avg_prep_time_mins": 5,
                "is_available": True
            }
        ]

    monkeypatch.setattr(
        web_server,
        "fetch_menu_from_db",
        fake_fetch_menu
    )

    client = TestClient(TestServer(web_server.create_app()))
    await client.start_server()

    try:
        response = await client.get("/api/menu")

        assert response.status == 200

        data = await response.json()

        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Чай"
        assert data["items"][0]["price"] == 100.0

    finally:
        await client.close()

@pytest.mark.asyncio
async def test_menu_returns_error_when_database_fails(monkeypatch):
    # Имитируем ошибку подключения к базе данных
    def fake_fetch_menu():
        raise web_server.pymysql.OperationalError("Database unavailable")

    monkeypatch.setattr(
        web_server,
        "fetch_menu_from_db",
        fake_fetch_menu
    )

    client = TestClient(TestServer(web_server.create_app()))
    await client.start_server()

    try:
        response = await client.get("/api/menu")

        assert response.status == 503
        assert "меню" in await response.text()

    finally:
        await client.close()
