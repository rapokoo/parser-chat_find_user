"""
In-memory кэш watchlist'а.

Идея: на каждое сообщение/join-событие мы не должны ходить в SQLite —
это лишний I/O в хот-пасе. Вместо этого весь watchlist грузится в
обычный dict один раз при старте, и дальше проверка "это отслеживаемый
человек?" — это O(1) обращение к словарю в памяти (наносекунды).

reload() можно дергать вручную (например, по команде себе в Telegram
в будущем расширении), чтобы подхватить изменения без рестарта процесса.
"""

import logging

import db

log = logging.getLogger("watchlist_cache")


class WatchlistCache:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._data: dict[str, db.WatchlistEntry] = {}

    async def reload(self) -> int:
        self._data = await db.load_all_as_dict(self.db_path)
        log.info("Watchlist кэш загружен: %d записей", len(self._data))
        return len(self._data)

    def get(self, username: str) -> db.WatchlistEntry | None:
        """username может быть с @ или без, регистр не важен — нормализуем."""
        if not username:
            return None
        return self._data.get(db.normalize_username(username))

    def __len__(self) -> int:
        return len(self._data)
