FROM python:3.12-slim

WORKDIR /app

# Сначала только requirements — чтобы Docker кэшировал слой с зависимостями
# и не переустанавливал их при каждом изменении кода.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY db.py watchlist_cache.py watchlist_cli.py pushover.py main_parser.py ./

# session-файл и watchlist.db НЕ копируются в образ — это runtime-состояние,
# оно должно жить в volume (./data), а не быть запечённым в image.
# .env тоже не копируется — передаётся через env_file в docker-compose.yml,
# чтобы секреты не осели в слоях образа.

CMD ["python3", "main_parser.py"]
