import os
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from models import Base, Category, MenuItem, User, Order, OrderItem
from history.generate_history import generate_orders_history

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "canteen_db")

DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"🔧 Подключаемся к базе данных MySQL...")
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)

def seed_database():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    try:
        print("🌱 Начинаем наполнение базы данных (seed)...")

        categories_data = ["Супы", "Основные блюда", "Салаты", "Напитки", "Выпечка"]
        categories = {}
        for cat_title in categories_data:
            cat = session.query(Category).filter_by(title=cat_title).first()
            if not cat:
                cat = Category(title=cat_title, description=f"Категория {cat_title}")
                session.add(cat)
                session.commit()
            categories[cat_title] = cat

        menu_items_data = [
            {"name": "Борщ украинский", "category": "Супы", "price": 180.0, "desc": "Классический"},
            {"name": "Суп куриный", "category": "Супы", "price": 140.0, "desc": "Домашний"},
            {"name": "Солянка", "category": "Супы", "price": 210.0, "desc": "Мясной"},
            {"name": "Плов", "category": "Основные блюда", "price": 250.0, "desc": "С мясом"},
            {"name": "Котлета", "category": "Основные блюда", "price": 230.0, "desc": "По-киевски"},
            {"name": "Пюре", "category": "Основные блюда", "price": 90.0, "desc": "Нежное"},
            {"name": "Рыба", "category": "Основные блюда", "price": 270.0, "desc": "Под сыром"},
            {"name": "Гречка", "category": "Основные блюда", "price": 70.0, "desc": "Отварная"},
            {"name": "Оливье", "category": "Салаты", "price": 130.0, "desc": "Классический"},
            {"name": "Цезарь", "category": "Салаты", "price": 220.0, "desc": "С курицей"},
            {"name": "Капуста", "category": "Салаты", "price": 80.0, "desc": "Витаминный"},
            {"name": "Компот", "category": "Напитки", "price": 50.0, "desc": "Сладкий"},
            {"name": "Чай", "category": "Напитки", "price": 40.0, "desc": "Горячий"},
            {"name": "Морс", "category": "Напитки", "price": 60.0, "desc": "Клюквенный"},
            {"name": "Пирожок", "category": "Выпечка", "price": 75.0, "desc": "С яблоком"},
            {"name": "Булочка", "category": "Выпечка", "price": 85.0, "desc": "С корицей"}
        ]

        menu_objects = []
        for item_data in menu_items_data:
            existing_item = session.query(MenuItem).filter_by(name=item_data["name"]).first()
            if not existing_item:
                item = MenuItem(
                    name=item_data["name"],
                    category_id=categories[item_data["category"]].category_id,
                    price=item_data["price"],
                    description=item_data["desc"],
                    avg_prep_time_mins=15,
                    is_available=True
                )
                session.add(item)
                session.commit()
                menu_objects.append(item)
            else:
                menu_objects.append(existing_item)

        users_data = [
            {"identifier": "sofia_kal", "full_name": "Софья Калмыкова", "role": "student"},
            {"identifier": "mann_v", "full_name": "Манн В.", "role": "student"},
            {"identifier": "pichugina_k", "full_name": "Пичугина К.", "role": "student"},
            {"identifier": "antonova_m", "full_name": "Антонова М.", "role": "student"},
            {"identifier": "student_canteen", "full_name": "Иван Студент", "role": "student"}
        ]

        user_objects = []
        for u_data in users_data:
            user = session.query(User).filter_by(identifier=u_data["identifier"]).first()
            if not user:
                user = User(
                    full_name=u_data["full_name"],
                    identifier=u_data["identifier"],
                    role=u_data["role"],
                    created_at=datetime.datetime.utcnow()
                )
                session.add(user)
                session.commit()
                user_objects.append(user)
            else:
                user_objects.append(user)

        # Вызов генератора истории (Ваша часть)
        print("🤖 Передаем управление генератору истории...")
        generate_orders_history(session)

        print("🚀 База данных успешно заполнена и готова к работе!")

    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка при сидировании БД: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    seed_database()