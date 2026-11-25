from sqlalchemy import Column, Integer, String, Text, DECIMAL, DateTime, Enum, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Category(Base):
    __tablename__ = 'categories'
    
    category_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(100), nullable=False)
    description = Column(Text)
    
    # Связь с меню
    menu_items = relationship("MenuItem", back_populates="category")


class MenuItem(Base):
    __tablename__ = 'menu_items'
    
    item_id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey('categories.category_id'), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text)
    price = Column(DECIMAL(10, 2), nullable=False)
    avg_prep_time_mins = Column(Integer)
    is_available = Column(Boolean, default=True)
    
    category = relationship("Category", back_populates="menu_items")
    order_items = relationship("OrderItem", back_populates="menu_item")


class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(150), nullable=False)
    identifier = Column(String(50))
    phone = Column(String(20))
    email = Column(String(100))
    role = Column(String(50))  # Или Enum, если используется в БД
    created_at = Column(DateTime)
    
    orders = relationship("Order", back_populates="user")


class Order(Base):
    __tablename__ = 'orders'
    
    order_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    status = Column(String(50))
    target_time = Column(DateTime)
    total_amount = Column(DECIMAL(10, 2))
    created_at = Column(DateTime)
    
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
    status_history = relationship("OrderStatusHistory", back_populates="order")


class OrderItem(Base):
    __tablename__ = 'order_items'
    
    order_item_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.order_id'), nullable=False)
    item_id = Column(Integer, ForeignKey('menu_items.item_id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    
    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem", back_populates="order_items")


class OrderStatusHistory(Base):
    __tablename__ = 'order_status_history'
    
    history_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.order_id'), nullable=False)
    status = Column(String(50), nullable=False)
    changed_at = Column(DateTime, nullable=False)
    
    order = relationship("Order", back_populates="status_history")