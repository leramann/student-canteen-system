from datetime import datetime
from typing import List, Dict, Optional


class WaitTimePredictor:
    def __init__(self):
        # Словарь для хранения среднего времени ожидания по часам: {час: среднее_в_минутах}
        self.hourly_averages: Dict[int, float] = {}
        self.global_average: float = 10.0  # Базовое время, если история пуста
        self.mae: Optional[float] = None

    def train(self, completed_orders: List[Dict]) -> float:
        """
        Обучает модель на истории выполненных заказов и считает метрику MAE.
        Ожидаемый формат элемента списка completed_orders:
        {'created_at': datetime, 'actual_wait_minutes': float}
        """
        if not completed_orders:
            self.mae = 0.0
            return self.mae

        # 1. Группируем время ожидания по часам дня
        hourly_data: Dict[int, List[float]] = {}
        all_times: List[float] = []

        for order in completed_orders:
            hour = order['created_at'].hour
            wait_time = float(order['actual_wait_minutes'])

            hourly_data.setdefault(hour, []).append(wait_time)
            all_times.append(wait_time)

        # 2. Считаем среднее для каждого часа и общее среднее
        self.global_average = sum(all_times) / len(all_times)
        for hour, times in hourly_data.items():
            self.hourly_averages[hour] = sum(times) / len(times)

        # 3. Вычисляем MAE (Mean Absolute Error) на исторических данных
        total_error = 0.0
        for order in completed_orders:
            predicted = self.predict(order['created_at'])
            actual = float(order['actual_wait_minutes'])
            total_error += abs(actual - predicted)

        self.mae = round(total_error / len(completed_orders), 2)
        return self.mae

    def predict(self, order_time: Optional[datetime] = None) -> int:
        """
        Возвращает прогноз времени ожидания в минутах (округленный до целого).
        """
        if order_time is None:
            order_time = datetime.now()

        hour = order_time.hour
        prediction = self.hourly_averages.get(hour, self.global_average)
        return max(1, round(prediction))

    def format_prediction(self, order_time: Optional[datetime] = None) -> str:
        """
        Возвращает строку в формате для демо: 'ожидание ~N мин'.
        """
        minutes = self.predict(order_time)
        return f"ожидание ~{minutes} мин"


async def get_ai_recommendation(query: str, menu_items: list[dict], cart: list[dict]) -> str:
    pass