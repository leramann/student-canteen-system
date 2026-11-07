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
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT item_id as id, category_id as category, name, description, price, "
                "NULL as image_url, NULL as calories FROM menu_items WHERE is_available = 1"
            )
            items = cur.fetchall()
            for item in items:
                item['price'] = float(item['price'])
            return items
    finally:
        conn.close()


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




async def create_order_handler(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        user_id = data.get("user_id")
        items = data.get("items", [])

        if not user_id or not items:
            return web.json_response({"error": "user_id and items are required"}, status=400)

        conn = pymysql.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
                if not cur.fetchone():
                    return web.json_response({"error": "User not found"}, status=404)

                total_amount = 0.0
                validated_items = []

                for item_info in items:
                    item_id = item_info.get("item_id")
                    quantity = item_info.get("quantity", 1)

                    cur.execute("SELECT item_id, price, is_available FROM menu_items WHERE item_id = %s", (item_id,))
                    db_item = cur.fetchone()

                    if not db_item or not db_item["is_available"]:
                        return web.json_response({"error": f"Item {item_id} not found or unavailable"}, status=400)

                    unit_price = float(db_item["price"])
                    total_amount += unit_price * quantity
                    
                    validated_items.append({
                        "item_id": item_id,
                        "quantity": quantity,
                        "unit_price": unit_price
                    })

                cur.execute(
                    "INSERT INTO orders (user_id, status, total_amount, target_time, created_at) "
                    "VALUES (%s, 'new', %s, NOW() + INTERVAL 30 MINUTE, NOW())",
                    (user_id, total_amount)
                )
                order_id = cur.lastrowid

                for v_item in validated_items:
                    cur.execute(
                        "INSERT INTO order_items (order_id, item_id, quantity, unit_price) "
                        "VALUES (%s, %s, %s, %s)",
                        (order_id, v_item["item_id"], v_item["quantity"], v_item["unit_price"])
                    )

                conn.commit()
                return web.json_response({
                    "success": True,
                    "order_id": order_id,
                    "status": "new",
                    "total_amount": total_amount
                }, status=201)

        except Exception as db_err:
            conn.rollback()
            raise db_err
        finally:
            conn.close()

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def get_user_orders_handler(request: web.Request) -> web.Response:
    try:
        user_id = request.rel_url.query.get("user_id")
        if not user_id:
            return web.json_response({"error": "user_id query parameter is required"}, status=400)

        conn = pymysql.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT order_id, status, total_amount, target_time, created_at "
                    "FROM orders WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,)
                )
                orders = cur.fetchall()

                for order in orders:
                    order['total_amount'] = float(order['total_amount'])
                    if order.get('target_time'):
                        order['target_time'] = order['target_time'].strftime('%Y-%m-%d %H:%M:%S')
                    if order.get('created_at'):
                        order['created_at'] = order['created_at'].strftime('%Y-%m-%d %H:%M:%S')

                    cur.execute(
                        "SELECT oi.item_id, m.name, oi.quantity, oi.unit_price "
                        "FROM order_items oi "
                        "JOIN menu_items m ON oi.item_id = m.item_id "
                        "WHERE oi.order_id = %s",
                        (order['order_id'],)
                    )
                    items = cur.fetchall()
                    for item in items:
                        item['unit_price'] = float(item['unit_price'])
                    
                    order['items'] = items

                return web.json_response({"orders": orders}, status=200)

        finally:
            conn.close()

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def update_order_status_handler(request: web.Request) -> web.Response:
    try:
        order_id = request.match_info.get("order_id")
        data = await request.json()
        new_status = data.get("status")

        valid_statuses = ['new', 'accepted', 'cooking', 'ready', 'picked_up', 'cancelled']
        if new_status not in valid_statuses:
            return web.json_response({
                "error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            }, status=400)

        conn = pymysql.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT order_id, status FROM orders WHERE order_id = %s", (order_id,))
                order = cur.fetchone()
                if not order:
                    return web.json_response({"error": "Order not found"}, status=404)

                cur.execute(
                    "UPDATE orders SET status = %s WHERE order_id = %s",
                    (new_status, order_id)
                )
                conn.commit()

                return web.json_response({
                    "success": True,
                    "order_id": int(order_id),
                    "old_status": order['status'],
                    "new_status": new_status
                }, status=200)

        finally:
            conn.close()

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/api/menu", menu_handler)
    app.router.add_post("/api/ai/recommend", ai_handler)
    app.router.add_post("/api/orders", create_order_handler)
    app.router.add_get("/api/orders", get_user_orders_handler)
    app.router.add_patch("/api/orders/{order_id}/status", update_order_status_handler)
    app.router.add_static("/static/", FRONTEND_DIR)
    app.router.add_get("/health", health_handler)
    return app


if __name__ == '__main__':
    web.run_app(create_app(), host='127.0.0.1', port=8084)