import pytest

from sprint2_services import (
    ValidationError,
    allowed_next_statuses,
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


def test_normalize_items_accepts_one_position():
    assert normalize_order_items([{"id": 4, "qty": 2}]) == [{"item_id": 4, "quantity": 2}]


def test_normalize_items_combines_duplicates():
    assert normalize_order_items([{"id": 2}, {"item_id": 2, "quantity": 3}]) == [
        {"item_id": 2, "quantity": 4}
    ]


@pytest.mark.parametrize("items", [None, [], "bad", [{}], [{"id": 1, "quantity": True}]])
def test_normalize_items_rejects_invalid_payload(items):
    with pytest.raises(ValidationError):
        normalize_order_items(items)


def test_normalize_items_limits_quantity():
    with pytest.raises(ValidationError):
        normalize_order_items([{"id": 1, "quantity": 51}])


def test_total_uses_server_prices_and_decimal_math():
    assert calculate_total([{"price": "12.50", "quantity": 2}, {"price": "3", "quantity": 1}]) == 28


@pytest.mark.parametrize("row", [[{"price": -1, "quantity": 1}], [{"price": "NaN", "quantity": 1}]])
def test_total_rejects_invalid_prices(row):
    with pytest.raises(ValidationError):
        calculate_total(row)


def test_allowed_statuses_follow_workflow():
    assert allowed_next_statuses("new") == ("accepted", "cancelled")
    assert allowed_next_statuses("ready") == ("picked_up",)


@pytest.mark.parametrize("status", ["picked_up", "cancelled"])
def test_terminal_statuses_have_no_next_step(status):
    assert allowed_next_statuses(status) == ()


def test_status_transition_rejects_skipping_steps():
    with pytest.raises(ValidationError):
        validate_status_transition("new", "ready")


def test_status_transition_allows_next_step():
    validate_status_transition("accepted", "cooking")


def test_queue_position_is_one_based():
    assert queue_position(0) == 1
    assert queue_position(4) == 5


def test_queue_position_rejects_negative_count():
    with pytest.raises(ValidationError):
        queue_position(-1)


def test_wait_prediction_includes_orders_ahead():
    assert predict_wait_minutes(8, 3, 5) == 23


def test_hourly_average_and_prediction():
    averages = hourly_wait_averages([{"hour": 12, "minutes": 10}, {"hour": 12, "minutes": 20}])
    assert averages == {12: 15}
    assert predict_for_hour(averages, 12) == 15


def test_forecast_uses_fallback_for_unseen_hour():
    assert predict_for_hour({}, 8, 7.5) == 7.5


def test_forecast_rejects_invalid_hour():
    with pytest.raises(ValidationError):
        predict_for_hour({}, 24)


def test_mae_calculates_mean_absolute_error():
    assert mean_absolute_error([10, 20], [13, 18]) == 2.5


def test_mae_requires_equal_nonempty_sequences():
    with pytest.raises(ValidationError):
        mean_absolute_error([1], [])


def test_menu_payload_normalizes_fields():
    item = validate_menu_payload({"name": "  Суп  ", "price": "125.50", "category_id": "2"})
    assert item["name"] == "Суп"
    assert str(item["price"]) == "125.50"
    assert item["avg_prep_time_mins"] == 5


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "price": 20, "category_id": 1},
        {"name": "Суп", "price": 0, "category_id": 1},
        {"name": "Суп", "price": 20, "category_id": 0},
        {"name": "Суп", "price": 20, "category_id": 1, "avg_prep_time_mins": 241},
    ],
)
def test_menu_payload_rejects_invalid_fields(payload):
    with pytest.raises(ValidationError):
        validate_menu_payload(payload)
