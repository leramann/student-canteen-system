import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from models import Order
from history.generate_history import generate_orders_history

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "canteen_db")

DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)

@pytest.fixture(scope="module")
def session():
    db = SessionLocal()
    yield db
    db.close()

def test_history_coverage(session):
    orders = session.query(Order).all()
    if not orders:
        pytest.skip("База пуста")
    dates = [o.created_at for o in orders if o.created_at]
    delta = max(dates) - min(dates)
    assert delta.days >= 42, f"История покрывает {delta.days} дней, а нужно минимум 42!"

def test_lunch_peak(session):
    orders = session.query(Order).all()
    if not orders:
        pytest.skip("База пуста")
    lunch_orders = sum(1 for o in orders if o.created_at and 12 <= o.created_at.hour <= 14)
    total_orders = len(orders)
    assert lunch_orders > (total_orders * 0.4), "Нет выраженного обеденного пика!"

def test_idempotency(session):
    count_before = session.query(Order).count()
    generate_orders_history(session)
    count_after = session.query(Order).count()
    assert count_before == count_after, "Повторный запуск продублировал заказы!"