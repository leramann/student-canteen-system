import asyncio
import logging
import sys
import os
from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton,
)

from web_server import create_app

TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"]
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_name = message.from_user.first_name

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🍽 Открыть меню",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    ]])

    await message.answer(
        f"Привет, {user_name}! 👋\n"
        f"Добро пожаловать в систему предзаказов нашей столовой.\n\n"
        f"Жми кнопку ниже — откроется меню.",
        reply_markup=kb,
    )


async def main() -> None:
    from aiohttp import web

    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_HOST, WEB_PORT)
    await site.start()
    print(f"Сайт успешно запущен: http://localhost:{WEB_PORT}")
    print("Бот запущен и ожидает сообщения...")

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")