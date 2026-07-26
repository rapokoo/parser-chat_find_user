"""
Отправка алертов через Pushover с максимальным приоритетом (emergency, priority=2).

Emergency-приоритет:
    - Пробивает Quiet Hours / Do Not Disturb на устройстве.
    - Повторяет звук + вибро каждые `retry` секунд, пока не тапнешь по
      уведомлению (подтверждение) или пока не истечёт `expire` секунд.
    - Единственный уровень приоритета в Pushover, который требует retry/expire.

Документация: https://pushover.net/api#priority
"""

import logging
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("pushover")

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"

PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN", "")
PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY", "")
PUSHOVER_SOUND = os.environ.get("PUSHOVER_SOUND", "persistent")
PUSHOVER_RETRY = int(os.environ.get("PUSHOVER_RETRY", "30"))
PUSHOVER_EXPIRE = int(os.environ.get("PUSHOVER_EXPIRE", "1800"))

# Короткий таймаут — если Pushover тормозит, не хотим зависать в event loop'е.
REQUEST_TIMEOUT_SECONDS = 5.0

# Общий переиспользуемый клиент (держим keep-alive соединение, не пересоздаём
# TCP/TLS на каждый алерт — это тоже вопрос скорости).
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
    return _client


def build_message(entry, chat_id: int, chat_title: str | None = None) -> tuple[str, str]:
    """Возвращает (title, message) для Pushover."""
    chat_ref = chat_title or str(chat_id)
    title = f"🚨 {entry.name} вступил в \"{chat_ref}\""

    lines = [
        f"Юзернейм: @{entry.username}",
        f"Описание: {entry.description or '-'}",
        f"Кошелёк (TON): {entry.wallet_ton or '-'}",
        f"Чат: {chat_ref}",
    ]
    message = "\n".join(lines)
    return title, message


async def send_pushover_alert(entry, chat_id: int, chat_title: str | None = None) -> bool:
    """
    Отправляет emergency-алерт. Возвращает True при успехе, False при ошибке.
    Никогда не бросает исключение наружу — ошибка сети/Pushover не должна
    ронять основной event loop парсера.
    """
    if not PUSHOVER_TOKEN or not PUSHOVER_USER_KEY:
        log.error("PUSHOVER_TOKEN / PUSHOVER_USER_KEY не заданы в .env — алерт не отправлен")
        return False

    title, message = build_message(entry, chat_id, chat_title)

    payload = {
        "token": PUSHOVER_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "title": title,
        "message": message,
        "priority": 2,  # emergency — максимальный приоритет
        "retry": PUSHOVER_RETRY,
        "expire": PUSHOVER_EXPIRE,
        "sound": PUSHOVER_SOUND,
    }

    t0 = time.perf_counter()
    client = _get_client()

    try:
        response = await client.post(PUSHOVER_API_URL, data=payload)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    except httpx.RequestError as e:
        log.error("Pushover: сетевая ошибка при отправке алерта: %s", e)
        return False

    try:
        data = response.json()
    except ValueError:
        log.error("Pushover: не удалось распарсить ответ, status=%s body=%r", response.status_code, response.text[:300])
        return False

    if response.status_code == 200 and data.get("status") == 1:
        log.info(
            "Pushover: алерт по @%s отправлен успешно за %sмс (request_id=%s)",
            entry.username, elapsed_ms, data.get("request"),
        )
        return True

    log.error(
        "Pushover: ошибка отправки (status=%s): %s",
        response.status_code, data.get("errors", data),
    )
    return False


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
