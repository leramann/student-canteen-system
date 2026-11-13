import os
import pymysql
from aiohttp import web
from pathlib import Path
from ai_service import get_ai_recommendation

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "database": os.getenv("DB_NAME", "canteen_db"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

FRONTEND_DIR = Path(__file__).parent / "frontend"


def fetch_menu_from_db():
    return [
        {"id": 1, "category": "Первые блюда", "name": "Борщ", "description": "Классический с говядиной", "price": 150, "image_url": "", "calories": 320},
        {"id": 2, "category": "Первые блюда", "name": "Суп-лапша", "description": "Куриный бульон", "price": 120, "image_url": "", "calories": 210},
        {"id": 3, "category": "Вторые блюда", "name": "Плов", "description": "Со свининой и морковью", "price": 180, "image_url": "", "calories": 420},
        {"id": 4, "category": "Вторые блюда", "name": "Котлета по-киевски", "description": "С картофельным пюре", "price": 220, "image_url": "", "calories": 480},
        {"id": 5, "category": "Напитки", "name": "Компот", "description": "Из сухофруктов", "price": 50, "image_url": "", "calories": 90},
        {"id": 6, "category": "Десерты", "name": "Сырники", "description": "Со сгущёнкой", "price": 130, "image_url": "", "calories": 340},
    ]


async def index_handler(request: web.Request) -> web.Response:
    return web.FileResponse(FRONTEND_DIR / "index.html")


async def menu_handler(request: web.Request) -> web.Response:
    try:
        items = fetch_menu_from_db()
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)
    return web.json_response({"items": items})


async def ai_handler(request: web.Request) -> web.Response:
    data = await request.json()
    query = data.get("query", "")
    cart = data.get("cart", [])
    try:
        items = fetch_menu_from_db()
        answer = await get_ai_recommendation(query, items, cart)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)
    return web.json_response({"answer": answer})

async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "message": "Server is running"})


def create_app() -> web.Application:
    app = web.Application()  # <--- ВОТ ЭТА СТРОЧКА ДОЛЖНА БЫТЬ ОБЯЗАТЕЛЬНО!
    app.router.add_get("/", index_handler)
    app.router.add_get("/api/menu", menu_handler)
    app.router.add_post("/api/ai/recommend", ai_handler)
    app.router.add_static("/static/", FRONTEND_DIR)
    app.router.add_get("/health", health_handler)
    return app