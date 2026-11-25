from datetime import datetime
from ai_service import WaitTimePredictor


def test_empty_history_prediction():
    """Если история заказов пуста, модель возвращает базовое время (10 мин) и MAE = 0.0."""
    predictor = WaitTimePredictor()
    mae = predictor.train([])

    assert mae == 0.0
    assert predictor.predict(datetime(2026, 11, 25, 12, 0)) == 10
    assert predictor.format_prediction(datetime(2026, 11, 25, 12, 0)) == "ожидание ~10 мин"


def test_hourly_prediction_and_mae():
    """Проверка расчета среднего времени по часам и точности метрики MAE."""
    predictor = WaitTimePredictor()
    history = [
        {"created_at": datetime(2026, 11, 24, 12, 10), "actual_wait_minutes": 14.0},
        {"created_at": datetime(2026, 11, 24, 12, 45), "actual_wait_minutes": 16.0},
        {"created_at": datetime(2026, 11, 24, 15, 20), "actual_wait_minutes": 5.0},
    ]

    mae = predictor.train(history)

    # Для 12 часов среднее (14 + 16) / 2 = 15.0 -> ошибка для каждого заказа 1.0
    # Для 15 часов среднее 5.0 -> ошибка 0.0
    # Итого MAE = (1.0 + 1.0 + 0.0) / 3 = 0.67
    assert mae == 0.67
    assert predictor.predict(datetime(2026, 11, 25, 12, 30)) == 15
    assert predictor.predict(datetime(2026, 11, 25, 15, 0)) == 5


def test_fallback_to_global_average():
    """Если для конкретного часа нет данных, используется общее среднее время."""
    predictor = WaitTimePredictor()
    history = [
        {"created_at": datetime(2026, 11, 24, 10, 0), "actual_wait_minutes": 8.0},
        {"created_at": datetime(2026, 11, 24, 14, 0), "actual_wait_minutes": 12.0},
    ]
    predictor.train(history)

    # Данных за 18 часов нет, поэтому должно вернуться общее среднее (8 + 12) / 2 = 10
    assert predictor.predict(datetime(2026, 11, 25, 18, 0)) == 10


def test_format_output_for_demo():
    """Проверка формата вывода строки для интерфейса и демо."""
    predictor = WaitTimePredictor()
    predictor.train([
        {"created_at": datetime(2026, 11, 25, 13, 15), "actual_wait_minutes": 12.0}
    ])

    result = predictor.format_prediction(datetime(2026, 11, 25, 13, 40))
    assert result == "ожидание ~12 мин"
