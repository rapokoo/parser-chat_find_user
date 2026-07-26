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

## ⚙️ Настройка окружения

Перед запуском создайте файл `.env` и заполните своими данными:

\`\`\`env
# === Аккаунт №1 (читающий чаты userbot) ===
API_ID_READER=       # ID приложения с my.telegram.org
API_HASH_READER=     # Hash приложения с my.telegram.org
SESSION_READER=      # Имя файла сессии (например: session_reader)

# === Pushover (уведомления) ===
PUSHOVER_TOKEN=      # Токен приложения Pushover
PUSHOVER_USER_KEY=   # User Key вашего аккаунта Pushover

# Звук уведомления (список: https://pushover.net/api#sounds)
PUSHOVER_SOUND=persistent

# Как часто (в секундах) повторять звук/вибро, пока не подтвердишь. Минимум 30.
PUSHOVER_RETRY=30

# Через сколько секунд Pushover перестанет напоминать, если не подтвердил (макс. 10800)
PUSHOVER_EXPIRE=1800

# Список отслеживаемых чатов (через запятую: username или ID)
TARGET_CHATS=

# Путь к SQLite базе watchlist'а
DB_PATH=watchlist.db
\`\`\`

## Важно

`.env` и `*.session` содержат чувствительные данные (API-ключи, авторизованная сессия аккаунта) — никогда не коммитятся (см. `.gitignore`), передаются только напрямую на сервер.
