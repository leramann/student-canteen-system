import os
import random
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from models import Base, Category, MenuItem, User, Order, OrderItem

# Надежно загружаем переменные из .env файла
load_dotenv()

# Считываем параметры подключения из окружения с дефолтными значениями
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "canteen_db")

# Защита: проверяем, что пароль вообще задан в .env
if not DB_PASSWORD:
    raise ValueError(
        "❌ Ошибка: Не найден параметр DB_PASSWORD в файле .env! "
        "Убедись, что файл .env создан и содержит корректные доступы."
    )

# Динамически собираем безопасную строку подключения
DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"🔧 Подключаемся к базе данных...")
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)

def seed_database():
    # Создаем таблицы, если их еще нет
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    try:
        print("🌱 Начинаем наполнение базы данных (seed)...")

        # 1. Категории (используем title)
        categories_data = ["Супы", "Основные блюда", "Салаты", "Напитки", "Выпечка"]
        categories = {}
        for cat_title in categories_data:
            cat = session.query(Category).filter_by(title=cat_title).first()
            if not cat:
                cat = Category(title=cat_title, description=f"Категория {cat_title}")
                session.add(cat)
                session.commit()
            categories[cat_title] = cat

        # 2. Меню (15+ позиций)
        menu_items_data = [
            {"name": "Борщ украинский", "category": "Супы", "price": 180.0, "desc": "Классический борщ со сметаной"},
            {"name": "Суп куриный с лапшой", "category": "Супы", "price": 140.0, "desc": "Домашний куриный суп"},
            {"name": "Солянка сборная", "category": "Супы", "price": 210.0, "desc": "Наваристый мясной суп"},
            {"name": "Плов с говядиной", "category": "Основные блюда", "price": 250.0, "desc": "Ароматный рис с мясом и специями"},
            {"name": "Котлета по-киевски", "category": "Основные блюда", "price": 230.0, "desc": "Нежная котлета с зелёным маслом"},
            {"name": "Пюре картофельное", "category": "Основные блюда", "price": 90.0, "desc": "Нежное картофельное пюре с маслом"},
            {"name": "Рыба запеченная под сыром", "category": "Основные блюда", "price": 270.0, "desc": "Филе белой рыбы с сырной корочкой"},
            {"name": "Гречка отварная", "category": "Основные блюда", "price": 70.0, "desc": "Рассыпчатая гречневая каша"},
            {"name": "Салат «Оливье»", "category": "Салаты", "price": 130.0, "desc": "Традиционный праздничный салат"},
            {"name": "Салат «Цезарь с курицей»", "category": "Салаты", "price": 220.0, "desc": "Свежий салат с соусом и сухариками"},
            {"name": "Витаминный из капусты", "category": "Салаты", "price": 80.0, "desc": "Легкий капустный салат с морковью"},
            {"name": "Компот из сухофруктов", "category": "Напитки", "price": 50.0, "desc": "Домашний сладкий компот"},
            {"name": "Чай черный / зеленый", "category": "Напитки", "price": 40.0, "desc": "Классический горячий чай"},
            {"name": "Морс клюквенный", "category": "Напитки", "price": 60.0, "desc": "Освежающий ягодный морс"},
            {"name": "Пирожок с яблоком", "category": "Выпечка", "price": 75.0, "desc": "Свежая сдоба с фруктовой начинкой"},
            {"name": "Булочка с корицей", "category": "Выпечка", "price": 85.0, "desc": "Ароматная булочка в глазури"}
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

        # 3. Пользователи (используем identifier и full_name)
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

        # 4. Заказы (с учетом имен колонок order_id, user_id, item_id, total_amount)
        existing_orders_count = session.query(Order).count()
        if existing_orders_count < 20:
            statuses = ['new', 'accepted', 'cooking', 'ready', 'picked_up', 'cancelled']
            
            for i in range(25):
                random_user = random.choice(user_objects)
                order_dishes = random.sample(menu_objects, k=random.randint(1, 3))
                
                total = sum(dish.price for dish in order_dishes)
                order = Order(
                    user_id=random_user.user_id,
                    status=random.choice(statuses),
                    total_amount=total,
                    target_time=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
                    created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=random.randint(1, 168))
                )
                session.add(order)
                session.commit()

                for dish in order_dishes:
                    order_item = OrderItem(
                        order_id=order.order_id,
                        item_id=dish.item_id,
                        quantity=1,
                        unit_price=dish.price
                    )
                    session.add(order_item)
                session.commit()
            print("✅ Успешно создано 25 тестовых заказов!")
        else:
            print("ℹ️ Заказы уже существуют, пропускаем генерацию.")

        print("🚀 База данных успешно заполнена и готова к работе!")

    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка при сидировании БД: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    seed_database()