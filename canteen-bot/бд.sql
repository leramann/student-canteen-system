CREATE DATABASE IF NOT EXISTS canteen_db;
USE canteen_db;

CREATE TABLE IF NOT EXISTS menu_items (
    item_id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT DEFAULT 1,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    is_available TINYINT(1) DEFAULT 1
);

INSERT INTO menu_items (name, description, price) VALUES
('Борщ', 'Классический с говядиной и сметаной', 150),
('Плов', 'Со свининой и морковью', 180),
('Котлета по-киевски', 'С картофельным пюре', 220),
('Компот', 'Из сухофруктов', 50);