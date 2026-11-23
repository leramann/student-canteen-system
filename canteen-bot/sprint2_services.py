"""Pure business rules for Sprint 2; no database or network access."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Any


ORDER_STATUSES = ("new", "accepted", "cooking", "ready", "picked_up", "cancelled")
ACTIVE_ORDER_STATUSES = ("new", "accepted", "cooking", "ready")
STATUS_TRANSITIONS = {
    "new": frozenset({"accepted", "cancelled"}),
    "accepted": frozenset({"cooking", "cancelled"}),
    "cooking": frozenset({"ready"}),
    "ready": frozenset({"picked_up"}),
    "picked_up": frozenset(),
    "cancelled": frozenset(),
}


class ValidationError(ValueError):
    """Raised when input violates a canteen business rule."""


def normalize_order_items(raw_items: Any) -> list[dict[str, int]]:
    """Validate and combine duplicate item IDs from an untrusted request."""
    if not isinstance(raw_items, list) or not raw_items or len(raw_items) > 50:
        raise ValidationError("Заказ должен содержать от 1 до 50 позиций")

    quantities: dict[int, int] = defaultdict(int)
    for row in raw_items:
        if not isinstance(row, Mapping):
            raise ValidationError("Некорректный формат позиции заказа")
        item_id = row.get("item_id", row.get("id"))
        quantity = row.get("quantity", row.get("qty", 1))
        if isinstance(item_id, bool) or not isinstance(item_id, int) or item_id <= 0:
            raise ValidationError("Некорректный идентификатор блюда")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 50:
            raise ValidationError("Количество должно быть от 1 до 50")
        quantities[item_id] += quantity
        if quantities[item_id] > 50:
            raise ValidationError("Для одного блюда можно заказать не более 50 порций")
    return [{"item_id": item_id, "quantity": quantity} for item_id, quantity in sorted(quantities.items())]


def calculate_total(items: Iterable[Mapping[str, Any]]) -> Decimal:
    """Calculate a total using server-fetched unit prices."""
    total = Decimal("0.00")
    for row in items:
        try:
            price = Decimal(str(row["price"]))
            quantity = int(row["quantity"])
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValidationError("Некорректная цена или количество") from exc
        if not price.is_finite() or price < 0 or quantity <= 0:
            raise ValidationError("Цена и количество должны быть положительными")
        total += price * quantity
    return total.quantize(Decimal("0.01"))


def allowed_next_statuses(current_status: str) -> tuple[str, ...]:
    """Return valid next statuses for the current order state."""
    if current_status not in STATUS_TRANSITIONS:
        raise ValidationError("Неизвестный текущий статус заказа")
    return tuple(status for status in ORDER_STATUSES if status in STATUS_TRANSITIONS[current_status])


def validate_status_transition(current_status: str, new_status: str) -> None:
    if new_status not in allowed_next_statuses(current_status):
        raise ValidationError(f"Недопустимая смена статуса: {current_status} → {new_status}")


def queue_position(active_orders_ahead: int) -> int:
    if isinstance(active_orders_ahead, bool) or not isinstance(active_orders_ahead, int) or active_orders_ahead < 0:
        raise ValidationError("Количество заказов в очереди некорректно")
    return active_orders_ahead + 1


def predict_wait_minutes(
    own_prep_minutes: int,
    active_orders_ahead: int,
    average_prep_minutes: int = 5,
) -> int:
    """Simple estimate: own preparation plus one average slot per order ahead."""
    values = (own_prep_minutes, active_orders_ahead, average_prep_minutes)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise ValidationError("Время приготовления и очередь должны быть неотрицательными числами")
    return max(1, own_prep_minutes + active_orders_ahead * average_prep_minutes)


def hourly_wait_averages(observations: Iterable[Mapping[str, Any]]) -> dict[int, float]:
    """Build average actual wait by hour (0..23) from {'hour', 'minutes'} rows."""
    buckets: dict[int, list[float]] = defaultdict(list)
    for row in observations:
        try:
            hour = int(row["hour"])
            minutes = float(row["minutes"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("Некорректная запись истории ожидания") from exc
        if not 0 <= hour <= 23 or minutes < 0:
            raise ValidationError("Час или время ожидания вне допустимого диапазона")
        buckets[hour].append(minutes)
    return {hour: sum(values) / len(values) for hour, values in buckets.items()}


def predict_for_hour(hourly_averages: Mapping[int, float], hour: int, fallback: float = 5.0) -> float:
    if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
        raise ValidationError("Час должен быть от 0 до 23")
    value = float(hourly_averages.get(hour, fallback))
    if value < 0:
        raise ValidationError("Прогноз не может быть отрицательным")
    return round(value, 1)


def mean_absolute_error(actual: Iterable[float], predicted: Iterable[float]) -> float:
    actual_values = [float(value) for value in actual]
    predicted_values = [float(value) for value in predicted]
    if not actual_values or len(actual_values) != len(predicted_values):
        raise ValidationError("Для MAE нужны одинаковые непустые ряды")
    return round(sum(abs(a - p) for a, p in zip(actual_values, predicted_values)) / len(actual_values), 3)


def validate_menu_payload(payload: Any) -> dict[str, Any]:
    """Normalize menu CRUD input; SQL execution remains parameterized in the API."""
    if not isinstance(payload, Mapping):
        raise ValidationError("Ожидался объект с данными блюда")
    name = str(payload.get("name", "")).strip()
    if not name or len(name) > 150:
        raise ValidationError("Название блюда обязательно и не должно превышать 150 символов")
    description = str(payload.get("description", "")).strip()
    if len(description) > 5000:
        raise ValidationError("Описание слишком длинное")
    try:
        price = Decimal(str(payload.get("price")))
        category_id = int(payload.get("category_id"))
        prep = int(payload.get("avg_prep_time_mins", 5))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValidationError("Цена, категория и время приготовления заданы неверно") from exc
    if not price.is_finite() or price <= 0 or price > Decimal("100000"):
        raise ValidationError("Цена должна быть больше 0 и не превышать 100000")
    if category_id <= 0 or not 1 <= prep <= 240:
        raise ValidationError("Категория или время приготовления вне диапазона")
    image_id = payload.get("image_url", payload.get("image_id"))
    image_id = str(image_id).strip() if image_id else None
    if image_id and len(image_id) > 255:
        raise ValidationError("Ссылка на изображение слишком длинная")
    return {
        "name": name,
        "description": description or None,
        "price": price.quantize(Decimal("0.01")),
        "category_id": category_id,
        "avg_prep_time_mins": prep,
        "image_id": image_id,
    }
