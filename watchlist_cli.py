"""
CLI для управления watchlist'ом (инфлюенсеры/медиа).

Примеры:
    python3 watchlist_cli.py add --name "Ivan Influencer" --username ivan_inf \\
        --description "Крипто-инфлюенсер, 100k подписчиков" --wallet "UQAbc123..."

    python3 watchlist_cli.py remove --username ivan_inf

    python3 watchlist_cli.py list
"""

import argparse
import asyncio
import os

from dotenv import load_dotenv

import db

load_dotenv()
DB_PATH = os.environ.get("DB_PATH", "watchlist.db")


async def cmd_add(args: argparse.Namespace) -> None:
    await db.init_db(DB_PATH)
    try:
        entry = await db.add_entry(
            DB_PATH,
            name=args.name,
            username=args.username,
            description=args.description or "",
            wallet_ton=args.wallet or "",
        )
    except ValueError as e:
        print(f"Ошибка: {e}")
        return
    print(f"Добавлено: {entry.name} (@{entry.username}) id={entry.id}")


async def cmd_remove(args: argparse.Namespace) -> None:
    await db.init_db(DB_PATH)
    removed = await db.remove_entry(DB_PATH, args.username)
    if removed:
        print(f"Удалено: @{db.normalize_username(args.username)}")
    else:
        print(f"Не найдено: @{db.normalize_username(args.username)}")


async def cmd_list(args: argparse.Namespace) -> None:
    await db.init_db(DB_PATH)
    entries = await db.list_entries(DB_PATH)
    if not entries:
        print("Watchlist пуст.")
        return
    print(f"Всего в watchlist: {len(entries)}\n")
    for e in entries:
        wallet = e.wallet_ton or "-"
        desc = e.description or "-"
        print(f"[{e.id}] {e.name} | @{e.username} | {desc} | wallet: {wallet} | added: {e.added_at}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Управление watchlist инфлюенсеров/медиа")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Добавить человека в watchlist")
    p_add.add_argument("--name", required=True, help="Имя (для себя)")
    p_add.add_argument("--username", required=True, help="Юзернейм в Telegram (с @ или без)")
    p_add.add_argument("--description", default="", help="Описание: кто это")
    p_add.add_argument("--wallet", default="", help="Адрес кошелька TON")
    p_add.set_defaults(func=cmd_add)

    p_remove = sub.add_parser("remove", help="Удалить человека из watchlist")
    p_remove.add_argument("--username", required=True, help="Юзернейм для удаления")
    p_remove.set_defaults(func=cmd_remove)

    p_list = sub.add_parser("list", help="Показать весь watchlist")
    p_list.set_defaults(func=cmd_list)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
