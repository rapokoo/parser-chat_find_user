# Telegram Memecoin Chat Parser

Userbot на Telethon, который мониторит вступления новых участников в Telegram-чатах (мемкоин-комьюнити) и присылает мгновенный алерт через Pushover, если зашедший юзернейм есть в watchlist (инфлюенсеры/медиа).

## Возможности

- Детект вступления через нативные Telegram join-события (без зависимости от анти-спам ботов вроде Safeguard)
- Watchlist на SQLite: имя, юзернейм, описание, TON-кошелёк — управление через CLI
- In-memory кэш watchlist для проверки за микросекунды, без похода в БД на каждое событие
- Алерты через Pushover с emergency-приоритетом (retry/expire, пробивает Quiet Hours)
- Название чата — и в консольном логе, и в самом уведомлении
- Docker Compose для деплоя, systemd как альтернатива

## Стек

Python 3.12, Telethon, aiosqlite, httpx, python-dotenv.

## Структура

```
main_parser.py       — основной event loop, детект + алерты
db.py                 — слой работы с SQLite (watchlist)
watchlist_cache.py    — in-memory кэш watchlist
watchlist_cli.py      — CLI для управления watchlist (add/remove/list)
pushover.py           — интеграция с Pushover
test_connection.py    — тестовый скрипт для проверки подключения userbot'а
```

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить API_ID/API_HASH с my.telegram.org, TARGET_CHATS, Pushover-токены
```

Первый запуск (интерактивная авторизация userbot'а — телефон + код):
```bash
python3 main_parser.py
```

## Управление watchlist

```bash
python3 watchlist_cli.py add --name "Имя" --username юзернейм --description "Описание" --wallet "TON-адрес"
python3 watchlist_cli.py list
python3 watchlist_cli.py remove --username юзернейм
```

После изменения watchlist — перезапустить процесс (кэш грузится при старте).

## Деплой

- Через systemd — см. `DEPLOYMENT.md`
- Через Docker — см. `DOCKER.md`

## Важно

`.env` и `*.session` содержат чувствительные данные (API-ключи, авторизованная сессия аккаунта) — никогда не коммитятся (см. `.gitignore`), передаются только напрямую на сервер.
