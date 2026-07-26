"""
Часть 1: тест подключения userbot'а (Telethon) и приёма событий из чата.

Запуск:
    python3 test_connection.py

При первом запуске Telethon спросит номер телефона, код из Telegram
и (если включена) пароль двухфакторки. После этого создастся файл
сессии (session_reader.session) — повторных запросов не будет.
"""

import logging
import os

from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("test_connection")

API_ID = int(os.environ["API_ID_READER"])
API_HASH = os.environ["API_HASH_READER"]
SESSION = os.environ.get("SESSION_READER", "session_reader")
TARGET_CHATS_RAW = os.environ.get("TARGET_CHATS", "")

# Поддерживаем и username чата (без @), и числовой id
TARGET_CHATS = [
    c.strip() for c in TARGET_CHATS_RAW.split(",") if c.strip()
]

client = TelegramClient(SESSION, API_ID, API_HASH)


@client.on(events.NewMessage(chats=TARGET_CHATS or None))
async def on_new_message(event):
    sender = await event.get_sender()
    username = getattr(sender, "username", None)
    text = (event.raw_text or "").replace("\n", " ")[:120]
    log.info(
        "MSG chat_id=%s from=%s(@%s) text=%r",
        event.chat_id, getattr(sender, "id", "?"), username, text,
    )


@client.on(events.ChatAction(chats=TARGET_CHATS or None))
async def on_chat_action(event):
    # Это событие сработает на нативный "N присоединился к группе"
    if event.user_joined or event.user_added:
        user = await event.get_user()
        username = getattr(user, "username", None)
        log.info(
            "JOIN(native) chat_id=%s user_id=%s username=%s",
            event.chat_id, getattr(user, "id", "?"), username,
        )


async def main():
    await client.start()
    me = await client.get_me()
    log.info("Успешно авторизован как: %s (@%s, id=%s)", me.first_name, me.username, me.id)

    if not TARGET_CHATS:
        log.warning(
            "TARGET_CHATS пуст — слушаю ВСЕ чаты аккаунта. "
            "Задай TARGET_CHATS в .env перед боевым запуском."
        )
    else:
        log.info("Слушаю чаты: %s", TARGET_CHATS)

    log.info("Жду сообщения... (Ctrl+C для выхода)")
    await client.run_until_disconnected()


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
