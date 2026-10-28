import asyncio
import logging
import sys
import pymysql
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["BOT_TOKEN"]

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "database": os.getenv("DB_NAME", "canteen_db"),
    "charset": "utf8mb4",
}


bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_name = message.from_user.first_name
    
    # Проверка соединения с базой данных
    db_status = "Успешно подключено к MySQL! 🟢"
    try:
        connection = pymysql.connect(**DB_CONFIG)
        connection.close()
    except Exception as e:
        db_status = f"Ошибка подключения к БД: {e} 🔴"

    await message.answer(
        f"Привет, {html.bold(user_name)}! 👋\n"
        f"Добро пожаловать в систему предзаказов нашей студенческой столовой.\n\n"
        f"Бэкенд запущен, бот на связи! 🚀\n"
        f"Статус БД: {db_status}"
    )

async def main() -> None:
    print("Бот запущен и ожидает сообщения...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")