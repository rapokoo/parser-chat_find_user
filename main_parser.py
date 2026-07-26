"""
Часть 3: детект новых участников через нативные Telegram join-события
(ChatAction: user_joined / user_added) + сверка с in-memory кэшем watchlist.

Без Safeguard-специфичной логики — полагаемся только на серверные
события Telegram, они приходят раньше и не зависят от поведения
конкретного анти-спам бота в чате.

Запуск:
    python3 main_parser.py

В этой части алерты пока только логируются в консоль (Pushover и
дублирующее уведомление на второй аккаунт добавим в частях 4 и 5) —
но вся структура event handler'а уже финальная, в part 4/5 просто
допишем вызов send_pushover_alert() и send_telegram_notify() в
отмеченном месте.
"""

import asyncio
import logging
import os
import time

from dotenv import load_dotenv

load_dotenv()  # обязательно ДО импорта наших модулей, которые читают os.environ на этапе импорта

from telethon import TelegramClient, events, utils

import db
import pushover
from watchlist_cache import WatchlistCache

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("main_parser")

API_ID = int(os.environ["API_ID_READER"])
API_HASH = os.environ["API_HASH_READER"]
SESSION = os.environ.get("SESSION_READER", "session_reader")
DB_PATH = os.environ.get("DB_PATH", "watchlist.db")
TARGET_CHATS_RAW = os.environ.get("TARGET_CHATS", "")
TARGET_CHATS = [c.strip() for c in TARGET_CHATS_RAW.split(",") if c.strip()]

client = TelegramClient(SESSION, API_ID, API_HASH)
cache = WatchlistCache(DB_PATH)

# chat_id -> человекочитаемое название чата. Резолвится один раз при старте
# для всех TARGET_CHATS (см. main()), поэтому в хот-пасе это просто
# синхронный dict.get() без сетевых запросов. Если чат почему-то не
# оказался в кэше (например, слушаем все чаты аккаунта), резолвим
# лениво через event.get_chat() и кэшируем результат на будущее.
chat_titles: dict[int, str] = {}


def _extract_title(entity) -> str:
    return getattr(entity, "title", None) or getattr(entity, "username", None) or str(getattr(entity, "id", entity))


async def get_chat_title(chat_id: int, event=None) -> str:
    cached = chat_titles.get(chat_id)
    if cached is not None:
        return cached

    if event is None:
        return str(chat_id)

    try:
        entity = await event.get_chat()
    except Exception as e:  # не даём сбою резолвинга сломать обработку алерта
        log.warning("Не удалось резолвить название чата %s: %r", chat_id, e)
        return str(chat_id)

    title = _extract_title(entity)
    chat_titles[chat_id] = title
    return title


def _log_task_exception(task: asyncio.Task) -> None:
    """Коллбек для фоновых задач (напр. отправка Pushover), чтобы исключения
    не терялись молча — asyncio по умолчанию их просто проглатывает."""
    exc = task.exception() if not task.cancelled() else None
    if exc is not None:
        log.error("Фоновая задача завершилась с ошибкой: %r", exc)


async def handle_new_member(
    username: str | None,
    user_id: int,
    chat_id: int,
    t_event_received: float,
    chat_title: str,
) -> None:
    """
    Единая точка обработки нового участника, независимо от того,
    как он был извлечён (сейчас — только через ChatAction).
    """
    if not username:
        log.info("JOIN chat=%s (%s) user_id=%s — юзернейма нет, игнорируем", chat_title, chat_id, user_id)
        return

    entry = cache.get(username)
    elapsed_ms = round((time.perf_counter() - t_event_received) * 1000, 3)

    if entry is not None:
        # Fire-and-forget: не ждём завершения HTTP-запроса к Pushover, чтобы
        # не задерживать обработку следующих событий из очереди Telethon.
        task = asyncio.create_task(pushover.send_pushover_alert(entry, chat_id, chat_title))
        task.add_done_callback(_log_task_exception)

        # === ЗДЕСЬ в Части 5 добавим asyncio.create_task(send_telegram_notify(entry, chat_id, chat_title)) ===
        log.warning(
            "🚨 ALERT: watchlist-персона вступила в \"%s\" (chat=%s)! user_id=%s @%s "
            "(%s | %s | wallet=%s) | обработано за %sмс",
            chat_title, chat_id, user_id, entry.username, entry.name, entry.description,
            entry.wallet_ton or "-", elapsed_ms,
        )
    else:
        log.info(
            "JOIN chat=%s (%s) user_id=%s @%s — не в watchlist | обработано за %sмс",
            chat_title, chat_id, user_id, username, elapsed_ms,
        )


@client.on(events.ChatAction(chats=TARGET_CHATS or None))
async def on_chat_action(event):
    t0 = time.perf_counter()

    if not (event.user_joined or event.user_added):
        return  # не интересует (выход, смена фото чата и т.д.)

    user = await event.get_user()
    username = getattr(user, "username", None)
    user_id = getattr(user, "id", None)

    chat_title = await get_chat_title(event.chat_id, event)

    await handle_new_member(username, user_id, event.chat_id, t0, chat_title)


async def main() -> None:
    await db.init_db(DB_PATH)  # идемпотентно: CREATE TABLE IF NOT EXISTS — безопасно при повторных запусках
    await cache.reload()

    await client.start()
    me = await client.get_me()
    log.info("Авторизован как: %s (@%s, id=%s)", me.first_name, me.username, me.id)
    log.info("Watchlist: %d записей в памяти", len(cache))

    if not TARGET_CHATS:
        log.warning("TARGET_CHATS пуст — слушаю ВСЕ чаты. Задай TARGET_CHATS перед боевым запуском.")
    else:
        for chat_ref in TARGET_CHATS:
            try:
                entity = await client.get_entity(chat_ref)
            except Exception as e:
                log.error("Не удалось резолвить чат %r: %r — проверь TARGET_CHATS", chat_ref, e)
                continue
            cid = utils.get_peer_id(entity)
            chat_titles[cid] = _extract_title(entity)
        log.info("Слушаю чаты: %s", {cid: title for cid, title in chat_titles.items()})

    log.info("Готов, жду вступления новых участников...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
