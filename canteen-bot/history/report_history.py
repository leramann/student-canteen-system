import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from models import Order

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "canteen_db")

DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)

def print_history_report():
    session = SessionLocal()
    try:
        orders = session.query(Order).all()
        if not orders:
            print("История заказов пуста.")
            return

        dates = [o.created_at for o in orders if o.created_at]
        min_date = min(dates).strftime('%Y-%m-%d')
        max_date = max(dates).strftime('%Y-%m-%d')
        
        print("=" * 50)
        print(f"📊 ОТЧЕТ ПО ИСТОРИИ ЗАКАЗОВ (AI/Data)")
        print("=" * 50)
        print(f"📅 Период: с {min_date} по {max_date}")
        print(f"📦 Всего строк (заказов): {len(orders)}")
        print("-" * 50)
        print("⏰ Загрузка по часам (Топ-5 пиковых часов):")
        
        hours_count = {}
        for o in orders:
            if o.created_at:
                h = o.created_at.hour
                hours_count[h] = hours_count.get(h, 0) + 1
                
        sorted_hours = sorted(hours_count.items(), key=lambda x: x[1], reverse=True)
        for hour, count in sorted_hours[:5]:
            print(f"  {hour:02d}:00 - {hour:02d}:59 : {count} заказов")
        print("=" * 50)

    finally:
        session.close()

if __name__ == "__main__":
    print_history_report()