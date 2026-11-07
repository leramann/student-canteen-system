import random
import datetime
from models import Order, OrderItem, User, MenuItem

def generate_orders_history(session):
    print("🧠 [AI/Data] Генерация истории заказов за 8 недель...")

    # 1. Очищаем старые заказы, чтобы не было дублей при повторном запуске
    session.query(OrderItem).delete()
    session.query(Order).delete()
    session.commit()

    users = session.query(User).all()
    menu_items = session.query(MenuItem).all()

    if not users or not menu_items:
        print("❌ Нет пользователей или меню. Сначала создайте их.")
        return

    rnd = random.Random(42) # Детерминированность
    statuses = ['new', 'accepted', 'cooking', 'ready', 'picked_up', 'cancelled']
    
    now = datetime.datetime.utcnow()
    start_date = now - datetime.timedelta(weeks=8)
    
    total_orders = 0
    current_date = start_date

    while current_date <= now:
        is_weekend = current_date.weekday() >= 5
        
        # В выходные меньше заказов, в будни больше
        orders_today = rnd.randint(10, 15) if is_weekend else rnd.randint(35, 50)
        
        for _ in range(orders_today):
            # Пик в обед (12:00 - 14:00) - 60% заказов
            if rnd.random() < 0.6:
                hour = rnd.randint(12, 14)
            else:
                hour = rnd.choice([9, 10, 11, 15, 16, 17, 18])
                
            minute = rnd.randint(0, 59)
            order_time = current_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            order_dishes = rnd.sample(menu_items, k=rnd.randint(1, 3))
            total = sum(float(dish.price) for dish in order_dishes)
            
            order = Order(
                user_id=rnd.choice(users).user_id,
                status=rnd.choice(statuses),
                total_amount=total,
                target_time=order_time + datetime.timedelta(minutes=30),
                created_at=order_time
            )
            session.add(order)
            session.flush() 

            for dish in order_dishes:
                order_item = OrderItem(
                    order_id=order.order_id,
                    item_id=dish.item_id,
                    quantity=1,
                    unit_price=dish.price
                )
                session.add(order_item)
            
            total_orders += 1
        current_date += datetime.timedelta(days=1)
        
    session.commit()
    print(f"✅ Успешно сгенерировано {total_orders} заказов!")