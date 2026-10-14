import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ---- SOZLAMALAR ----
TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
TZ = timezone(timedelta(hours=5))

logging.basicConfig(level=logging.INFO)

# ---- BAZA ----
DB_PATH = os.getenv("DB_PATH", "messages.db")
db = sqlite3.connect(DB_PATH)
db.create_function("py_lower", 1, lambda s: s.lower() if s else s)
db.execute(
    """CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER, chat_title TEXT,
        user_id INTEGER, username TEXT, full_name TEXT,
        text TEXT, ts INTEGER, is_question INTEGER
    )"""
)
db.commit()

bot = Bot(TOKEN)
dp = Dispatcher()
waiting_search = False


def fmt(row):
    ts, name, text = row
    t = datetime.fromtimestamp(ts, TZ).strftime("%d.%m %H:%M")
    return f"[{t}] {name}: {text}"


async def reply_long(msg: Message, text: str):
    if not text:
        text = "Hech narsa topilmadi."
    for i in range(0, len(text), 4000):
        await msg.answer(text[i : i + 4000])


def menu():
    rows = [
        [InlineKeyboardButton(text="📩 Oxirgi xabarlar", callback_data="last")],
        [InlineKeyboardButton(text="📅 Bugungi xabarlar", callback_data="today")],
        [InlineKeyboardButton(text="❓ Savollar", callback_data="q")],
        [InlineKeyboardButton(text="👤 Talaba bo'yicha", callback_data="students")],
        [InlineKeyboardButton(text="🔎 So'z bo'yicha qidirish", callback_data="search")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def fetch(where="", params=(), limit=20):
    sql = "SELECT ts, full_name, text FROM messages "
    if where:
        sql += "WHERE " + where + " "
    sql += "ORDER BY ts DESC LIMIT ?"
    rows = db.execute(sql, (*params, limit)).fetchall()
    return "\n\n".join(fmt(r) for r in reversed(rows))


# ---- GURUH: jim saqlaydi ----
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def save_group_message(m: Message):
    text = m.text or m.caption
    if not text and m.content_type != "text":
        text = f"<{m.content_type}>"
    if not text or not m.from_user or m.from_user.is_bot:
        return
    u = m.from_user
    db.execute(
        "INSERT INTO messages (chat_id, chat_title, user_id, username, full_name, text, ts, is_question) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            m.chat.id, m.chat.title, u.id, u.username, u.full_name,
            text, int(m.date.timestamp()), 1 if "?" in text else 0,
        ),
    )
    db.commit()


# ---- SHAXSIY CHAT ----
@dp.message(
