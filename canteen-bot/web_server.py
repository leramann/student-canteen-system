"""MySQL API for the student canteen Mini App."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qsl

import pymysql
from aiohttp import web
from dotenv import load_dotenv

from ai_service import get_ai_recommendation
from sprint2_services import (
    ACTIVE_ORDER_STATUSES,
    ValidationError,
    calculate_total,
    hourly_wait_averages,
    mean_absolute_error,
    normalize_order_items,
    predict_for_hour,
    predict_wait_minutes,
    queue_position,
    validate_menu_payload,
    validate_status_transition,
)

load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "canteen_db"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "connect_timeout": 5,
    "read_timeout": 10,
    "write_timeout": 10,
}
ACTIVE_SQL = ",".join(["%s"] * len(ACTIVE_ORDER_STATUSES))


def _db_connect():
    return pymysql.connect(**DB_CONFIG)


def _decimal_json(value):
    return float(value) if isinstance(value, Decimal) else value


def fetch_menu_from_db(available_only: bool = False) -> list[dict]:
    where = "WHERE mi.is_available = 1" if available_only else ""
    with _db_connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"""SELECT mi.item_id AS id, mi.category_id, c.title AS category, mi.name,
                       mi.description, mi.price, mi.avg_prep_time_mins,
                       mi.is_available, mi.image_id AS image_url
                FROM menu_items mi
                JOIN categories c ON c.category_id = mi.category_id
                {where}
                ORDER BY c.category_id, mi.name"""
        )
        rows = cursor.fetchall()
    for row in rows:
        row["price"] = float(row["price"])
        row["avg_prep_time_mins"] = int(row["avg_prep_time_mins"] or 5)
        row["is_available"] = bool(row["is_available"])
    return rows


def verify_telegram_init_data(init_data: str) -> dict:
    """Verify Telegram WebApp initData and return its authenticated user object."""
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        raise web.HTTPServiceUnavailable(text="BOT_TOKEN is not configured")
    if not init_data or len(init_data) > 16_384:
        raise web.HTTPUnauthorized(text="Откройте приложение из Telegram")
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        fields = dict(pairs)
    except ValueError as exc:
        raise web.HTTPUnauthorized(text="Некорректные данные Telegram") from exc
    if len(fields) != len(pairs):
        raise web.HTTPUnauthorized(text="Повторяющиеся поля Telegram initData")
    received_hash = fields.pop("hash", "")
    if len(received_hash) != 64:
        raise web.HTTPUnauthorized(text="Подпись Telegram отсутствует")
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise web.HTTPUnauthorized(text="Подпись Telegram не прошла проверку")
    try:
        auth_date = int(fields["auth_date"])
        telegram_user = json.loads(fields["user"])
        telegram_id = int(telegram_user["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise web.HTTPUnauthorized(text="В initData нет пользователя или даты авторизации") from exc
    now = int(time.time())
    if auth_date > now + 60 or now - auth_date > 86_400:
        raise web.HTTPUnauthorized(text="Срок действия Telegram initData истёк")
    if telegram_id <= 0:
        raise web.HTTPUnauthorized(text="Некорректный Telegram user ID")
    telegram_user["id"] = telegram_id
    return telegram_user


def _init_data_from_request(request: web.Request, payload: dict | None = None) -> str:
    return request.headers.get("X-Telegram-Init-Data", (payload or {}).get("init_data", ""))


def _get_app_user(cursor, telegram_user: dict) -> dict:
    """Map verified Telegram ID to the existing users.identifier column."""
    telegram_id = str(telegram_user["id"])
    configured_role = _configured_demo_role(telegram_id)
    cursor.execute(
        "SELECT user_id, full_name, role FROM users WHERE identifier = %s LIMIT 1",
        (telegram_id,),
    )
    user = cursor.fetchone()
    if user:
        # Privileged roles are granted only by server-side Telegram-ID allowlists.
        # Never accept a role supplied by the browser.
        if configured_role and user["role"] != configured_role:
            cursor.execute(
                "UPDATE users SET role = %s WHERE user_id = %s",
                (configured_role, user["user_id"]),
            )
            user["role"] = configured_role
        return user
    first = str(telegram_user.get("first_name", "")).strip()
    last = str(telegram_user.get("last_name", "")).strip()
    full_name = " ".join(part for part in (first, last) if part) or "Пользователь Telegram"
    cursor.execute(
        "INSERT IGNORE INTO users (full_name, identifier, role) VALUES (%s, %s, %s)",
        (full_name[:150], telegram_id, configured_role or "student"),
    )
    cursor.execute(
        "SELECT user_id, full_name, role FROM users WHERE identifier = %s LIMIT 1",
        (telegram_id,),
    )
    user = cursor.fetchone()
    if not user:
        raise web.HTTPInternalServerError(text="Не удалось создать профиль пользователя")
    return user


def _configured_demo_role(telegram_id: str) -> str | None:
    """Return a privileged role only for IDs explicitly configured by the owner."""
    staff_ids = {value.strip() for value in os.getenv("STAFF_TELEGRAM_IDS", "").split(",") if value.strip()}
    admin_ids = {value.strip() for value in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if value.strip()}
    if telegram_id in admin_ids:
        return "admin"
    if telegram_id in staff_ids:
        return "staff"
    return None


def _authenticated_user(request: web.Request, payload: dict | None = None) -> dict:
    telegram_user = verify_telegram_init_data(_init_data_from_request(request, payload))
    try:
        with _db_connect() as conn, conn.cursor() as cursor:
            user = _get_app_user(cursor, telegram_user)
            conn.commit()
    except pymysql.MySQLError as exc:
        logger.exception("Ошибка поиска пользователя Telegram в MySQL")
        raise web.HTTPServiceUnavailable(text="База данных временно недоступна") from exc
    return {**user, "telegram_id": telegram_user["id"]}


def _require_role(user: dict, *roles: str) -> None:
    if user.get("role") not in roles:
        raise web.HTTPForbidden(text="Недостаточно прав для этого действия")


async def _read_json(request: web.Request) -> dict:
    try:
        payload = await request.json()
    except (json.JSONDecodeError, web.HTTPBadRequest) as exc:
        raise web.HTTPBadRequest(text="Некорректный JSON") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Ожидался JSON-объект")
    return payload


async def index_handler(request: web.Request) -> web.StreamResponse:
    return web.FileResponse(FRONTEND_DIR / "index.html")


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "message": "Server is running"})


async def menu_handler(request: web.Request) -> web.Response:
    try:
        # Keep unavailable dishes visible so students see why they cannot order them.
        return web.json_response({"items": fetch_menu_from_db()})
    except pymysql.MySQLError as exc:
        logger.exception("Ошибка загрузки меню")
        raise web.HTTPServiceUnavailable(text="Не удалось подключиться к меню") from exc


async def current_user_handler(request: web.Request) -> web.Response:
    user = _authenticated_user(request)
    return web.json_response({"user": user})


async def create_order_handler(request: web.Request) -> web.Response:
    payload = await _read_json(request)
    user = _authenticated_user(request, payload)
    _require_role(user, "student")
    try:
        requested_items = normalize_order_items(payload.get("items"))
    except ValidationError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    try:
        result = _place_order(int(user["user_id"]), requested_items)
    except LookupError as exc:
        raise web.HTTPConflict(text=str(exc)) from exc
    return web.json_response({"order": result}, status=201)


def _place_order(user_id: int, requested_items: list[dict[str, int]]) -> dict:
    ids = [row["item_id"] for row in requested_items]
    placeholders = ",".join(["%s"] * len(ids))
    conn = _db_connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""SELECT item_id, name, price, avg_prep_time_mins, is_available
                    FROM menu_items WHERE item_id IN ({placeholders}) FOR UPDATE""",
                ids,
            )
            menu_rows = {int(row["item_id"]): row for row in cursor.fetchall()}
            if len(menu_rows) != len(ids):
                raise LookupError("Одно или несколько блюд больше не существуют")
            line_items = []
            prep_minutes = 0
            for requested in requested_items:
                menu_item = menu_rows[requested["item_id"]]
                if not menu_item["is_available"]:
                    raise LookupError(f"Блюдо «{menu_item['name']}» сейчас недоступно")
                line = {
                    "item_id": requested["item_id"],
                    "quantity": requested["quantity"],
                    "price": menu_item["price"],
                    "name": menu_item["name"],
                }
                line_items.append(line)
                prep_minutes += int(menu_item["avg_prep_time_mins"] or 5) * line["quantity"]
            total = calculate_total(line_items)
            cursor.execute(
                f"SELECT COUNT(*) AS n FROM orders WHERE status IN ({ACTIVE_SQL})",
                ACTIVE_ORDER_STATUSES,
            )
            active_before = int(cursor.fetchone()["n"])
            position = queue_position(active_before + 1)
            wait = predict_wait_minutes(prep_minutes, active_before)
            cursor.execute(
                "INSERT INTO orders (user_id, status, total_amount) VALUES (%s, 'new', %s)",
                (user_id, total),
            )
            order_id = int(cursor.lastrowid)
            cursor.executemany(
                "INSERT INTO order_items (order_id, item_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                [
                    (order_id, row["item_id"], row["quantity"], row["price"])
                    for row in line_items
                ],
            )
            cursor.execute(
                "INSERT INTO order_status_history (order_id, status) VALUES (%s, 'new')",
                (order_id,),
            )
        conn.commit()
        return {
            "order_id": order_id,
            "status": "new",
            "total_amount": float(total),
            "queue_number": position,
            "estimated_wait_minutes": wait,
            "items": [
                {"item_id": row["item_id"], "name": row["name"], "quantity": row["quantity"],
                 "unit_price": float(row["price"]), "line_total": float(row["price"] * row["quantity"])}
                for row in line_items
            ],
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _orders_for_user(user_id: int, *, active_only: bool = False, all_orders: bool = False) -> list[dict]:
    conditions = []
    params: list = []
    if not all_orders:
        if active_only:
            conditions.append(f"o.status IN ({ACTIVE_SQL})")
            params.extend(ACTIVE_ORDER_STATUSES)
        else:
            conditions.append("o.user_id = %s")
            params.append(user_id)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with _db_connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"""SELECT o.order_id, o.user_id, u.full_name AS customer_name,
                       o.status, o.target_time, o.total_amount, o.created_at
                FROM orders o JOIN users u ON u.user_id=o.user_id{where}
                ORDER BY o.created_at DESC, o.order_id DESC LIMIT 200""",
            params,
        )
        orders = cursor.fetchall()
        if not orders:
            return []
        order_ids = [int(order["order_id"]) for order in orders]
        marks = ",".join(["%s"] * len(order_ids))
        cursor.execute(
            f"""SELECT oi.order_id, oi.item_id, mi.name, oi.quantity, oi.unit_price
                FROM order_items oi JOIN menu_items mi ON mi.item_id = oi.item_id
                WHERE oi.order_id IN ({marks}) ORDER BY oi.order_item_id""",
            order_ids,
        )
        items_by_order: dict[int, list[dict]] = {order_id: [] for order_id in order_ids}
        for item in cursor.fetchall():
            items_by_order[int(item["order_id"])].append({
                "item_id": int(item["item_id"]),
                "name": item["name"],
                "quantity": int(item["quantity"]),
                "unit_price": float(item["unit_price"]),
                "line_total": float(item["unit_price"] * item["quantity"]),
            })
    for order in orders:
        order["order_id"] = int(order["order_id"])
        order["user_id"] = int(order["user_id"])
        order["total_amount"] = float(order["total_amount"] or 0)
        order["created_at"] = order["created_at"].isoformat() if order["created_at"] else None
        order["target_time"] = order["target_time"].isoformat() if order["target_time"] else None
        order["items"] = items_by_order[order["order_id"]]
    return orders


async def my_orders_handler(request: web.Request) -> web.Response:
    user = _authenticated_user(request)
    _require_role(user, "student", "staff", "admin")
    try:
        return web.json_response({"orders": _orders_for_user(int(user["user_id"]))})
    except pymysql.MySQLError as exc:
        logger.exception("Ошибка загрузки истории заказов")
        raise web.HTTPServiceUnavailable(text="Не удалось загрузить заказы") from exc


async def repeat_order_handler(request: web.Request) -> web.Response:
    user = _authenticated_user(request)
    _require_role(user, "student")
    try:
        source_id = int(request.match_info["order_id"])
        with _db_connect() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT item_id, quantity FROM order_items WHERE order_id = %s "
                "AND order_id IN (SELECT order_id FROM orders WHERE order_id = %s AND user_id = %s)",
                (source_id, source_id, int(user["user_id"])),
            )
            rows = cursor.fetchall()
        if not rows:
            raise web.HTTPNotFound(text="Заказ не найден")
        requested = normalize_order_items([
            {"item_id": int(row["item_id"]), "quantity": int(row["quantity"])} for row in rows
        ])
        result = _place_order(int(user["user_id"]), requested)
    except ValueError as exc:
        raise web.HTTPBadRequest(text="Некорректный номер заказа") from exc
    except LookupError as exc:
        raise web.HTTPConflict(text=str(exc)) from exc
    return web.json_response({"order": result}, status=201)


async def staff_orders_handler(request: web.Request) -> web.Response:
    user = _authenticated_user(request)
    _require_role(user, "staff", "admin")
    try:
        orders = _orders_for_user(int(user["user_id"]), active_only=True)
        return web.json_response({"orders": orders})
    except pymysql.MySQLError as exc:
        logger.exception("Ошибка загрузки очереди сотрудника")
        raise web.HTTPServiceUnavailable(text="Не удалось загрузить очередь") from exc


async def admin_orders_handler(request: web.Request) -> web.Response:
    user = _authenticated_user(request)
    _require_role(user, "admin")
    try:
        return web.json_response({"orders": _orders_for_user(int(user["user_id"]), all_orders=True)})
    except pymysql.MySQLError as exc:
        logger.exception("Ошибка загрузки всех заказов")
        raise web.HTTPServiceUnavailable(text="Не удалось загрузить заказы") from exc


async def update_order_status_handler(request: web.Request) -> web.Response:
    user = _authenticated_user(request)
    _require_role(user, "staff", "admin")
    payload = await _read_json(request)
    new_status = payload.get("status")
    if not isinstance(new_status, str):
        raise web.HTTPBadRequest(text="Укажите новый статус")
    try:
        order_id = int(request.match_info["order_id"])
    except ValueError as exc:
        raise web.HTTPBadRequest(text="Некорректный номер заказа") from exc
    conn = _db_connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT status FROM orders WHERE order_id = %s FOR UPDATE", (order_id,))
            row = cursor.fetchone()
            if not row:
                raise web.HTTPNotFound(text="Заказ не найден")
            try:
                validate_status_transition(row["status"], new_status)
            except ValidationError as exc:
                raise web.HTTPConflict(text=str(exc)) from exc
            cursor.execute(
                "UPDATE orders SET status = %s WHERE order_id = %s AND status = %s",
                (new_status, order_id, row["status"]),
            )
            if cursor.rowcount != 1:
                raise web.HTTPConflict(text="Статус уже изменён другим сотрудником")
            cursor.execute(
                "INSERT INTO order_status_history (order_id, status) VALUES (%s, %s)",
                (order_id, new_status),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return web.json_response({"order_id": order_id, "status": new_status})


async def admin_menu_handler(request: web.Request) -> web.Response:
    user = _authenticated_user(request)
    _require_role(user, "admin")
    try:
        return web.json_response({"items": fetch_menu_from_db(available_only=False)})
    except pymysql.MySQLError as exc:
        logger.exception("Ошибка загрузки меню для администратора")
        raise web.HTTPServiceUnavailable(text="Не удалось загрузить меню") from exc


async def create_menu_item_handler(request: web.Request) -> web.Response:
    user = _authenticated_user(request)
    _require_role(user, "admin")
    try:
        data = validate_menu_payload(await _read_json(request))
    except ValidationError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    with _db_connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO menu_items (category_id, name, description, price, avg_prep_time_mins, is_available, image_id) "
            "VALUES (%s, %s, %s, %s, %s, 1, %s)",
            (data["category_id"], data["name"], data["description"], data["price"],
             data["avg_prep_time_mins"], data["image_id"]),
        )
        item_id = int(cursor.lastrowid)
        conn.commit()
    return web.json_response({"item_id": item_id}, status=201)


async def update_menu_item_handler(request: web.Request) -> web.Response:
    user = _authenticated_user(request)
    _require_role(user, "admin")
    try:
        item_id = int(request.match_info["item_id"])
        payload = await _read_json(request)
        data = validate_menu_payload(payload)
    except (ValueError, ValidationError) as exc:
        raise web.HTTPBadRequest(text=str(exc) or "Некорректный ID блюда") from exc
    availability = payload.get("is_available", True)
    if not isinstance(availability, bool):
        raise web.HTTPBadRequest(text="is_available должен быть true или false")
    with _db_connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE menu_items SET category_id=%s, name=%s, description=%s, price=%s, "
            "avg_prep_time_mins=%s, image_id=%s, is_available=%s WHERE item_id=%s",
            (data["category_id"], data["name"], data["description"], data["price"],
             data["avg_prep_time_mins"], data["image_id"], int(availability), item_id),
        )
        if cursor.rowcount == 0:
            cursor.execute("SELECT item_id FROM menu_items WHERE item_id=%s", (item_id,))
            if not cursor.fetchone():
                raise web.HTTPNotFound(text="Блюдо не найдено")
        conn.commit()
    return web.json_response({"item_id": item_id, "is_available": availability})


async def delete_menu_item_handler(request: web.Request) -> web.Response:
    user = _authenticated_user(request)
    _require_role(user, "admin")
    try:
        item_id = int(request.match_info["item_id"])
    except ValueError as exc:
        raise web.HTTPBadRequest(text="Некорректный ID блюда") from exc
    try:
        with _db_connect() as conn, conn.cursor() as cursor:
            cursor.execute("DELETE FROM menu_items WHERE item_id=%s", (item_id,))
            if cursor.rowcount == 0:
                raise web.HTTPNotFound(text="Блюдо не найдено")
            conn.commit()
    except pymysql.err.IntegrityError as exc:
        raise web.HTTPConflict(text="Блюдо есть в заказах; снимите его с продажи") from exc
    return web.json_response({"deleted": True, "item_id": item_id})


async def queue_forecast_handler(request: web.Request) -> web.Response:
    user = _authenticated_user(request)
    _require_role(user, "staff", "admin")
    with _db_connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            """SELECT HOUR(o.created_at) AS hour,
                      TIMESTAMPDIFF(MINUTE, o.created_at, h.changed_at) AS minutes
               FROM orders o JOIN order_status_history h ON h.order_id=o.order_id
               WHERE h.status='ready' AND h.changed_at IS NOT NULL
                 AND TIMESTAMPDIFF(MINUTE, o.created_at, h.changed_at) >= 0
               ORDER BY o.created_at DESC LIMIT 1000"""
        )
        observations = cursor.fetchall()
    rows = [{"hour": int(r["hour"]), "minutes": float(r["minutes"])} for r in observations]
    averages = hourly_wait_averages(rows)
    current_hour = datetime.now().hour
    baseline = sum(row["minutes"] for row in rows) / len(rows) if rows else 5.0
    prediction = predict_for_hour(averages, current_hour, baseline)
    # Leave-one-out error: each historical order is compared with the mean of
    # other orders in the same hour, falling back to all remaining observations.
    actual, predicted = [], []
    for index, row in enumerate(rows):
        others = rows[:index] + rows[index + 1:]
        same_hour = [other["minutes"] for other in others if other["hour"] == row["hour"]]
        comparison = same_hour or [other["minutes"] for other in others]
        if comparison:
            actual.append(row["minutes"])
            predicted.append(sum(comparison) / len(comparison))
    return web.json_response({
        "hour": current_hour,
        "estimated_wait_minutes": prediction,
        "training_samples": len(rows),
        "mae_minutes": mean_absolute_error(actual, predicted) if actual else None,
        "hourly_averages": {str(hour): round(value, 1) for hour, value in averages.items()},
    })


async def ai_handler(request: web.Request) -> web.Response:
    payload = await _read_json(request)
    query = str(payload.get("query", ""))[:500]
    cart = payload.get("cart", [])
    try:
        answer = await get_ai_recommendation(query, fetch_menu_from_db(available_only=True), cart)
    except Exception as exc:
        logger.exception("Ошибка AI-рекомендации")
        raise web.HTTPServiceUnavailable(text="Рекомендации временно недоступны") from exc
    return web.json_response({"answer": answer})


@web.middleware
async def api_errors(request: web.Request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except pymysql.MySQLError as exc:
        logger.exception("Ошибка MySQL в %s %s", request.method, request.path)
        raise web.HTTPServiceUnavailable(text="База данных временно недоступна") from exc


def create_app() -> web.Application:
    app = web.Application(client_max_size=1_048_576, middlewares=[api_errors])
    app.router.add_get("/", index_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/api/menu", menu_handler)
    app.router.add_post("/api/ai/recommend", ai_handler)
    app.router.add_get("/api/me", current_user_handler)
    app.router.add_post("/api/orders", create_order_handler)
    app.router.add_get("/api/my/orders", my_orders_handler)
    app.router.add_post("/api/my/orders/{order_id}/repeat", repeat_order_handler)
    app.router.add_get("/api/staff/orders", staff_orders_handler)
    app.router.add_patch("/api/staff/orders/{order_id}/status", update_order_status_handler)
    app.router.add_get("/api/staff/queue/forecast", queue_forecast_handler)
    app.router.add_get("/api/admin/orders", admin_orders_handler)
    app.router.add_get("/api/admin/menu", admin_menu_handler)
    app.router.add_post("/api/admin/menu", create_menu_item_handler)
    app.router.add_patch("/api/admin/menu/{item_id}", update_menu_item_handler)
    app.router.add_delete("/api/admin/menu/{item_id}", delete_menu_item_handler)
    app.router.add_static("/static/", FRONTEND_DIR)
    return app
