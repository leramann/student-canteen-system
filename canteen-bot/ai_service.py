async def get_ai_recommendation(query: str, menu_items: list[dict], cart: list[dict]) -> str:
    """
    ЭТО ТОЧКА ИНТЕГРАЦИИ ИИ. Отдаю этот файл МАШЕ с ИИ.
    Она должна заменить тело функции на вызов реальной модели.
    """
    names = ", ".join(i["name"] for i in menu_items[:5])
    return f"(заглушка) Скоро здесь будет ИИ. Сейчас в меню есть: {names}"