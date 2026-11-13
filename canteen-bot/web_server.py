import os
import pymysql
from aiohttp import web
from pathlib import Path
from ai_service import get_ai_recommendation

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "canteen_db"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

FRONTEND_DIR = Path(__file__).parent / "frontend"

def fetch_menu_from_db():
    # Заглушка с картинками для сервера
    return [
        {"id": 1, "category": "Первые блюда", "name": "Борщ", "description": "Классический с говядиной", "price": 150, "image_url": "https://images.unsplash.com/photo-1621644835763-e6c4a63ec7ea?w=200&h=200&fit=crop", "calories": 320},
        {"id": 2, "category": "Первые блюда", "name": "Суп-лапша", "description": "Куриный бульон", "price": 120, "image_url": "https://images.unsplash.com/photo-1547592180-85f173990554?w=200&h=200&fit=crop", "calories": 210},
        {"id": 3, "category": "Вторые блюда", "name": "Плов", "description": "Со свининой и морковью", "price": 180, "image_url": "https://images.unsplash.com/photo-1512058564366-18510be2db19?w=200&h=200&fit=crop", "calories": 420},
        {"id": 4, "category": "Вторые блюда", "name": "Котлета по-киевски", "description": "С картофельным пюре", "price": 220, "image_url": "https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?w=200&h=200&fit=crop", "calories": 480},
        {"id": 5, "category": "Напитки", "name": "Компот", "description": "Из сухофруктов", "price": 50, "image_url": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=200&h=200&fit=crop", "calories": 90},
        {"id": 6, "category": "Десерты", "name": "Сырники", "description": "Со сгущёнкой", "price": 130, "image_url": "https://images.unsplash.com/photo-1498837167922-ddd27525d352?w=200&h=200&fit=crop", "calories": 340},
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

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/api/menu", menu_handler)
    app.router.add_post("/api/ai/recommend", ai_handler)
    app.router.add_static("/static/", FRONTEND_DIR)
    return app