"""
Слой работы с SQLite-базой watchlist'а.

Таблица watchlist:
    id            INTEGER PRIMARY KEY
    name          TEXT    -- имя человека (для себя, для памяти)
    username      TEXT    -- юзернейм в Telegram, БЕЗ @, в нижнем регистре, UNIQUE
    description   TEXT    -- кто это: инфлюенсер / медиа / whatever
    wallet_ton    TEXT    -- адрес кошелька TON (может быть пустым)
    added_at      TEXT    -- ISO timestamp

Юзернейм всегда хранится в нижнем регистре и без @ — Telegram username
регистронезависимый, поэтому сравнение тоже должно быть регистронезависимым.
Нормализация делается один раз здесь (normalize_username), остальной код
всегда должен ходить через эту функцию перед любым сравнением/вставкой.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    username     TEXT NOT NULL,
    description  TEXT DEFAULT '',
    wallet_ton   TEXT DEFAULT '',
    added_at     TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_username ON watchlist(username);
"""


@dataclass
class WatchlistEntry:
    id: int
    name: str
    username: str
    description: str
    wallet_ton: str
    added_at: str


def normalize_username(raw: str) -> str:
    """Убирает @, пробелы, приводит к нижнему регистру."""
    return raw.strip().lstrip("@").lower()


async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def add_entry(
    db_path: str,
    name: str,
    username: str,
    description: str = "",
    wallet_ton: str = "",
) -> WatchlistEntry:
    uname = normalize_username(username)
    if not uname:
        raise ValueError("Юзернейм не может быть пустым")

    added_at = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(db_path) as db:
        try:
            cursor = await db.execute(
                "INSERT INTO watchlist (name, username, description, wallet_ton, added_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, uname, description, wallet_ton, added_at),
            )
            await db.commit()
        except aiosqlite.IntegrityError as e:
            raise ValueError(f"Юзернейм @{uname} уже есть в watchlist") from e

        return WatchlistEntry(
            id=cursor.lastrowid,
            name=name,
            username=uname,
            description=description,
            wallet_ton=wallet_ton,
            added_at=added_at,
        )


async def remove_entry(db_path: str, username: str) -> bool:
    """Возвращает True, если запись была найдена и удалена."""
    uname = normalize_username(username)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("DELETE FROM watchlist WHERE username = ?", (uname,))
        await db.commit()
        return cursor.rowcount > 0


async def get_entry(db_path: str, username: str) -> Optional[WatchlistEntry]:
    uname = normalize_username(username)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM watchlist WHERE username = ?", (uname,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return WatchlistEntry(**dict(row))


async def list_entries(db_path: str) -> list[WatchlistEntry]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM watchlist ORDER BY added_at DESC")
        rows = await cursor.fetchall()
        return [WatchlistEntry(**dict(row)) for row in rows]


async def load_all_as_dict(db_path: str) -> dict[str, WatchlistEntry]:
    """
    Грузит весь watchlist в память одним запросом.
    Используется основным парсером при старте (и при ручном reload)
    для построения быстрого in-memory индекса username -> WatchlistEntry.
    """
    entries = await list_entries(db_path)
    return {e.username: e for e in entries}
