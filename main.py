#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
rhinosoul_bot.py
یک فایل واحد شامل تمام قابلیت‌هایی که خواسته بودی:
- /start در پیوی (با اسلش)، بقیه دستورات بدون اسلش
- دو مالک (پیش‌فرض)، آمار، لیست گروه‌ها، پینگ، پیام همگانی
- بازی "حدس عدد" با انتخاب رنج، منم بازی، شروع و اتمام بازی
- پذیرش اعداد فارسی و انگلیسی
- عضویت اجباری در کانال
- حذف پیام قبلی ربات برای تمیزی گروه
- گزارش روزانه 10 نفر برتر برای مالکان
- نوتیف هنگام اضافه شدن گروه جدید
"""

import os
import asyncio
import random
import time
import re
from typing import Optional, Dict

import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatMember,
)
from aiogram.filters.command import Command

# --------------------- تنظیمات محیط ---------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# دو مالک پیش‌فرض (مقدار دقیقی که گفتی):
DEFAULT_OWNER_IDS = "7662192190,6041119040"
OWNER_IDS = [int(x) for x in os.getenv("OWNER_IDS", DEFAULT_OWNER_IDS).split(",") if x.strip()]

# یوزرنیم‌ها / کانال‌ها (مقادیر پیش‌فرض بر اساس مشخصات تو)
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@RHINOSOUL_TM")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@OLDKASEB")
BOT_USERNAME = os.getenv("BOT_USERNAME", "FindNumRS_Bot")  # بدون @

if not BOT_TOKEN or not DATABASE_URL or not OWNER_IDS:
    raise RuntimeError("ENV ها باید تنظیم شوند: BOT_TOKEN, DATABASE_URL, OWNER_IDS")

# --------------------- راه‌اندازی بات و دیتابیس ---------------------
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
pool: Optional[asyncpg.Pool] = None

# نگهداری پیام‌های آخر ربات برای هر چت تا پاک بشن (برای تمیزی)
last_bot_messages: Dict[int, int] = {}  # chat_id -> message_id

# --------------------- SQL ساختار دیتابیس ---------------------
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    score INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS groups (
    id BIGINT PRIMARY KEY,
    title TEXT,
    owner_id BIGINT,
    added_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS games (
    id SERIAL PRIMARY KEY,
    group_id BIGINT REFERENCES groups(id) ON DELETE CASCADE,
    creator_id BIGINT,
    range_min INT,
    range_max INT,
    target_number INT,
    status TEXT CHECK (status IN ('waiting', 'active', 'finished')) DEFAULT 'waiting',
    announce_msg_id BIGINT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    winner_id BIGINT
);

CREATE TABLE IF NOT EXISTS participants (
    game_id INT,
    user_id BIGINT,
    PRIMARY KEY (game_id, user_id)
);
"""

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    async with pool.acquire() as conn:
        await conn.execute(CREATE_SQL)

# --------------------- یوتیلیتی‌ها ---------------------
# تبدیل اعداد فارسی به انگلیسی
FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
def normalize_number_text(s: str) -> str:
    return s.translate(FA_TO_EN).strip()

async def upsert_user(u):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO UPDATE
            SET username=EXCLUDED.username, first_name=EXCLUDED.first_name
            """,
            u.id, getattr(u, "username", "") or "", getattr(u, "first_name", "") or "",
        )

async def ensure_group(chat_id: int, title: str, owner_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO groups (id, title, owner_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title
            """,
            chat_id, title or "", owner_id,
        )

async def is_member_required_channel(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

def start_private_kb(bot_username: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ افزودن به گروه", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("🆘 تماس با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME.removeprefix('@')}")]
    ])

def range_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1–10", callback_data="range_1_10")],
        [InlineKeyboardButton(text="10–100", callback_data="range_10_100")],
        [InlineKeyboardButton(text="100–500", callback_data="range_100_500")],
        [InlineKeyboardButton(text="1000–9000", callback_data="range_1000_9000")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_main")]
    ])

def waiting_kb(game_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 منم بازی", callback_data=f"join_{game_id}")],
        [InlineKeyboardButton(text="▶️ شروع بازی", callback_data=f"start_{game_id}")],
        [InlineKeyboardButton(text="⏹️ اتمام بازی", callback_data=f"stop_{game_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_main")]
    ])

async def delete_last_bot_message(chat_id: int):
    mid = last_bot_messages.get(chat_id)
    if mid:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass

def format_mention(user_id: int, name: str):
    return f"<a href='tg://user?id={user_id}'>{name}</a>"

def parse_range_callback(data: str):
    # data like "range_1_10"
    parts = data.split("_")
    if len(parts) == 3:
        try:
            mn = int(parts[1]); mx = int(parts[2])
            return mn, mx
        except:
            return None
    return None

# --------------------- متن معرفی تیم و ربات (خواناتر شده) ---------------------
TEAM_INTRO = (
    "تیم برنامه‌نویسی و خدمات مجازی RHINOSOUL\n\n"
    "توسعه ربات، سایت و اپلیکیشن برای افراد، گروه‌ها و کسب‌وکارها — صفر تا صد هر سرویس."
)

BOT_INTRO = (
    "🎁 این ربات هدیه‌ای از تیم RHINOSOUL به شماست!\n\n"
    "اضافه‌سازی ساده: ربات را به گروهتان اضافه کنید و با نوشتن «حدس عدد» بازی را آغاز کنید.\n"
    "هر ماه تیم ما به نفر اول جایزه‌ای اهدا می‌کند — شاید آن نفر شما باشید! 🏆\n\n"
    "اگر سؤال یا مشکلی داشتی، راحت از پشتیبان کمک بگیر: "
    f"{SUPPORT_USERNAME}\n\n"
    "با آرزوی لحظات شاد و رقابتی 🤝"
)

# --------------------- هندلرها ---------------------

# /start فقط در پیوی — معرفی خوانا، دکمه‌های افزودن به گروه و تماس با پشتیبان
@dp.message(F.chat.type == "private", F.text == "/start")
async def start_pv(m: Message):
    await upsert_user(m.from_user)
    kb = start_private_kb(BOT_USERNAME)
    text = (
        f"سلام {m.from_user.first_name or 'دوست'} 👋\n\n"
        f"{TEAM_INTRO}\n\n"
        f"{BOT_INTRO}\n\n"
        f"📢 کانال تیم: {REQUIRED_CHANNEL}\n"
        f"🆘 پشتیبان: {SUPPORT_USERNAME}"
    )
    await m.answer(text, reply_markup=kb)

# وقتی کسی در گروه بنویسه "حدس عدد" (حساس به حروف کوچک/بزرگ)
@dp.message(F.chat.type.in_({"group", "supergroup"}), F.text.regexp(r"(?i)حدس عدد"))
async def handle_guess_word(m: Message):
    # ثبت کاربر و گروه
    await upsert_user(m.from_user)
    try:
        chat = await bot.get_chat(m.chat.id)
        owner_id = getattr(chat, "id", 0)
    except:
        owner_id = 0
    await ensure_group(m.chat.id, m.chat.title or "", owner_id)

    if not await is_member_required_channel(m.from_user.id):
        # دعوت به عضویت کانال
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 عضویت در کانال", url=f"https://t.me/{REQUIRED_CHANNEL.removeprefix('@')}")],
            [InlineKeyboardButton(text="✅ عضو شدم", callback_data="check_membership")]
        ])
        await delete_last_bot_message(m.chat.id)
        msg = await m.reply(f"⚠️ برای شرکت در بازی ابتدا عضو کانال {REQUIRED_CHANNEL} شوید.", reply_markup=kb)
        last_bot_messages[m.chat.id] = msg.message_id
        return

    # پاک کردن پیام قبلی ربات و ارسال انتخاب رنج
    await delete_last_bot_message(m.chat.id)
    msg = await m.reply("🎯 رنج بازی را انتخاب کنید:", reply_markup=range_kb())
    last_bot_messages[m.chat.id] = msg.message_id

# callback: چک عضویت کانال
@dp.callback_query(F.data == "check_membership")
async def check_membership_cb(c: CallbackQuery):
    if await is_member_required_channel(c.from_user.id):
        await c.answer("عضویت تایید شد ✅", show_alert=True)
    else:
        await c.answer("هنوز عضو کانال نیستید ❌", show_alert=True)

# انتخاب رنج (ایجاد بازی در حالت waiting)
@dp.callback_query(F.data.startswith("range_"))
async def handle_range(c: CallbackQuery):
    if not await is_member_required_channel(c.from_user.id):
        await c.answer("برای شرکت باید عضو کانال شوید ❌", show_alert=True)
        return

    rng = parse_range_callback(c.data)
    if not rng:
        await c.answer("رنج نامعتبر ❌", show_alert=True)
        return
    mn, mx = rng

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO games (group_id, creator_id, range_min, range_max, status)
            VALUES ($1,$2,$3,$4,'waiting')
            """,
            c.message.chat.id, c.from_user.id, mn, mx,
        )
        rec = await conn.fetchrow(
            "SELECT id FROM games WHERE group_id=$1 AND status='waiting' ORDER BY id DESC LIMIT 1",
            c.message.chat.id,
        )
        game_id = rec["id"]

    await delete_last_bot_message(c.message.chat.id)
    text = (
        f"🎯 بازی در حالت انتظار بازیکن است!\n"
        f"رنج بازی: <b>{mn} تا {mx}</b>\n\n"
        f"برای شرکت در بازی ابتدا عضو کانال {REQUIRED_CHANNEL} شوید.\n"
        f"سپس روی «🎮 منم بازی» کلیک کنید."
    )
    msg = await c.message.answer(text, reply_markup=waiting_kb(game_id), parse_mode="HTML")
    last_bot_messages[c.message.chat.id] = msg.message_id

# دکمه "منم بازی"
@dp.callback_query(F.data.startswith("join_"))
async def join_game(c: CallbackQuery):
    try:
        game_id = int(c.data.split("_")[1])
    except:
        await c.answer("بازی نامعتبر ❌", show_alert=True)
        return

    if not await is_member_required_channel(c.from_user.id):
        await c.answer("برای شرکت باید عضو کانال شوید ❌", show_alert=True)
        return

    await upsert_user(c.from_user)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO participants (game_id, user_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
            game_id, c.from_user.id,
        )
        game = await conn.fetchrow("SELECT * FROM games WHERE id=$1", game_id)
        users = await conn.fetch("SELECT user_id FROM participants WHERE game_id=$1", game_id)

    player_list = "\n".join([f"{i+1}. <a href='tg://user?id={u['user_id']}'>کاربر</a>" for i, u in enumerate(users)])
    txt = (
        f"🎯 بازی در حالت انتظار بازیکن است!\n"
        f"رنج بازی: <b>{game['range_min']} تا {game['range_max']}</b>\n\n"
        f"شرکت‌کنندگان:\n{player_list}"
    )
    try:
        # ویرایش پیام اطلاع‌رسانی (اگر announce_msg_id ذخیره شده باشد از آن استفاده کن)
        target_mid = game["announce_msg_id"] or last_bot_messages.get(c.message.chat.id)
        await bot.edit_message_text(chat_id=c.message.chat.id, message_id=target_mid, text=txt, reply_markup=waiting_kb(game_id), parse_mode="HTML")
    except Exception:
        pass

    await c.answer("به بازی اضافه شدی ✅", show_alert=False)

# دکمه شروع بازی (فقط سازنده بازی)
@dp.callback_query(F.data.startswith("start_"))
async def start_game_btn(c: CallbackQuery):
    try:
        game_id = int(c.data.split("_")[1])
    except:
        await c.answer("خطا ❌", show_alert=True)
        return

    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM games WHERE id=$1", game_id)

    if not game or game["status"] != "waiting":
        await c.answer("بازی نامعتبر است ❌", show_alert=True)
        return

    if c.from_user.id != game["creator_id"]:
        await c.answer("فقط درخواست‌کننده می‌تواند بازی را شروع کند ❌", show_alert=True)
        return

    target = random.randint(int(game["range_min"]), int(game["range_max"]))
    async with pool.acquire() as conn:
        await conn.execute("UPDATE games SET target_number=$1, status='active', started_at=now() WHERE id=$2", target, game_id)

    try:
        await c.message.edit_text(f"🎯 بازی شروع شد! عددی بین {game['range_min']} تا {game['range_max']} حدس بزنید.", reply_markup=None)
    except:
        pass
    await c.answer("بازی شروع شد ✅")

# دکمه اتمام بازی (فقط سازنده)
@dp.callback_query(F.data.startswith("stop_"))
async def stop_game_btn(c: CallbackQuery):
    try:
        game_id = int(c.data.split("_")[1])
    except:
        await c.answer("خطا ❌", show_alert=True)
        return

    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM games WHERE id=$1", game_id)
    if not game:
        await c.answer("بازی نامعتبر است ❌", show_alert=True)
        return
    if c.from_user.id != game["creator_id"]:
        await c.answer("فقط درخواست‌کننده می‌تواند بازی را متوقف کند ❌", show_alert=True)
        return

    async with pool.acquire() as conn:
        await conn.execute("UPDATE games SET status='finished', finished_at=now() WHERE id=$1", game_id)

    try:
        await c.message.edit_text("⏹️ بازی توسط درخواست‌کننده متوقف شد.", reply_markup=None)
    except:
        pass
    await c.answer("بازی متوقف شد ✅")

# دریافت عدد (فارسی یا انگلیسی) در حین بازی
@dp.message(F.chat.type.in_({"group", "supergroup"}), F.text.regexp(r"^[\d۰-۹]+$"))
async def guess_number(m: Message):
    text_norm = normalize_number_text(m.text.strip())
    try:
        num = int(text_norm)
    except:
        return

    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM games WHERE group_id=$1 AND status='active' ORDER BY id DESC LIMIT 1", m.chat.id)
        if not game:
            return

        if num == game["target_number"]:
            await conn.execute("UPDATE games SET status='finished', winner_id=$1, finished_at=now() WHERE id=$2", m.from_user.id, game["id"])
            await conn.execute("UPDATE users SET score = score + 1 WHERE id=$1", m.from_user.id)

            await m.reply(
                f"🎉 تبریک! {format_mention(m.from_user.id, m.from_user.first_name or 'کاربر')} عدد {m.text} را درست حدس زد! امتیاز شما اضافه شد ✅",
                parse_mode="HTML"
            )

            # گزارش نتیجه سریع به مالکان
            try:
                winnerscore = await pool.fetchval("SELECT score FROM users WHERE id=$1", m.from_user.id)
                for owner in OWNER_IDS:
                    try:
                        await bot.send_message(owner, f"🏆 بازی در گروه {m.chat.title or m.chat.id} تمام شد.\nبرنده: {format_mention(m.from_user.id, m.from_user.first_name or 'کاربر')}\nامتیاز فعلی: {winnerscore}", parse_mode="HTML")
                    except:
                        pass
            except:
                pass

# نمایش امتیازات بازی (10 نفر برتر آن گروه)
@dp.message(F.chat.type.in_({"group", "supergroup"}) & F.text.lower() == "امتیاز بازی")
async def show_scores(m: Message):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.id, u.first_name, u.username, u.score
            FROM users u
            JOIN participants p ON u.id = p.user_id
            JOIN games g ON g.id = p.game_id
            WHERE g.group_id=$1
            GROUP BY u.id
            ORDER BY u.score DESC
            LIMIT 10
            """,
            m.chat.id,
        )

    if not rows:
        await m.reply("هنوز هیچ امتیازی ثبت نشده.")
        return

    lines = ["🏆 <b>جدول امتیاز</b>:"]
    for idx, row in enumerate(rows, 1):
        name = row["first_name"] or "کاربر"
        mention = f"<a href='tg://user?id={row['id']}'>{name}</a>"
        lines.append(f"{idx}. {mention} — {row['score']} امتیاز")

    await m.reply("\n".join(lines), parse_mode="HTML")

# ریست آمار بازی (مالک ربات یا ادمین گروه)
@dp.message(F.text.lower() == "ریست آمار بازی")
async def reset_scores(m: Message):
    is_bot_owner = m.from_user.id in OWNER_IDS
    is_group_admin = False
    try:
        if m.chat.type in ("group", "supergroup"):
            member = await bot.get_chat_member(m.chat.id, m.from_user.id)
            is_group_admin = member.status in ("administrator", "creator")
    except:
        is_group_admin = False

    if not (is_bot_owner or is_group_admin):
        await m.reply("این دستور فقط برای مالک ربات یا ادمین/مالک گروه است.")
        return

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users SET score = 0
            WHERE id IN (
                SELECT user_id FROM participants
                JOIN games ON participants.game_id = games.id
                WHERE games.group_id = $1
            )
            """,
            m.chat.id,
        )

    await m.reply("✅ آمار بازی صفر شد.")

# راهنما
@dp.message(F.text.lower() == "راهنما")
async def help_cmd(m: Message):
    txt = (
        "📘 راهنمای ربات RHINOSOUL — حدس عدد\n\n"
        "• در گروه بنویسید: «حدس عدد» — ربات رنج را از شما می‌خواهد.\n"
        "• بعد از انتخاب رنج، پیام انتظار ساخته می‌شود. همه با کلیک روی «منم بازی» وارد می‌شوند.\n"
        "• شروع بازی را فقط درخواست‌کننده می‌تواند بزند.\n"
        "• هر کس عدد را درست حدس بزند برنده می‌شود و امتیازش ثبت می‌شود.\n\n"
        "دستورات (بدون /):\n"
        "• امتیاز بازی — نمایش جدول امتیازها\n"
        "• ریست آمار بازی — فقط برای مالک ربات یا ادمین/مالک گروه\n"
        "• راهنما — همین پیام\n"
    )
    await m.reply(txt)

# --------------------- دستورات مالک (در PV یا در گروه) ---------------------

# آمار ربات — کار می‌کند هر جا که مالک پیام بده
@dp.message(F.from_user.id.in_(OWNER_IDS) & F.text.lower() == "آمار ربات")
async def bot_stats(m: Message):
    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        groups = await conn.fetch("SELECT * FROM groups")
        games = await conn.fetchval("SELECT COUNT(*) FROM games")

    lines = [
        f"📊 آمار کلی ربات:",
        f"👤 کاربران ثبت‌شده: {users}",
        f"👥 گروه‌ها: {len(groups)}",
        f"🎮 بازی‌ها: {games}",
        "",
        "📋 لیست گروه‌ها:",
    ]
    for g in groups:
        owner = format_mention(g["owner_id"], "مالک")
        lines.append(f"• {g['title'] or 'بدون عنوان'} — آیدی: `{g['id']}` — {owner}")

    await m.reply("\n".join(lines), parse_mode="HTML")

# لیست گروه ها (مجزا)
@dp.message(F.from_user.id.in_(OWNER_IDS) & F.text.lower() == "لیست گروه ها")
async def list_groups(m: Message):
    async with pool.acquire() as conn:
        groups = await conn.fetch("SELECT * FROM groups ORDER BY added_at DESC")
    if not groups:
        await m.reply("هیچ گروهی ثبت نشده.")
        return
    out = ["📋 لیست گروه‌ها:"]
    for g in groups:
        out.append(f"{g['title'] or 'بدون عنوان'}\nآیدی: `{g['id']}` — مالک: {format_mention(g['owner_id'], 'مالک')}\n")
    await m.reply("\n".join(out), parse_mode="HTML")

# پینگ دقیق
@dp.message(F.from_user.id.in_(OWNER_IDS) & F.text.lower() == "پینگ")
async def ping_cmd(m: Message):
    t0 = time.perf_counter()
    msg = await m.reply("🏓 درحال بررسی...")
    t1 = time.perf_counter()
    rtt_ms = (t1 - t0) * 1000
    await msg.edit_text(f"🏓 Pong! RTT: {rtt_ms:.0f} ms")

# پیام همگانی — فرمت: "پیام همگانی متن ..." یا ریپلای به یک پیام و نوشتن "پیام همگانی"
@dp.message(F.from_user.id.in_(OWNER_IDS) & F.text.lower().startswith("پیام همگانی"))
async def broadcast_forward(m: Message):
    async with pool.acquire() as conn:
        groups = await conn.fetch("SELECT id FROM groups")
    if not groups:
        await m.reply("هیچ گروهی برای ارسال ثبت نشده.")
        return

    payload = m.text[len("پیام همگانی"):].strip()
    sent = 0
    for g in groups:
        try:
            if payload:
                await bot.send_message(g["id"], f"📢 پیام از مالک:\n\n{payload}")
            elif m.reply_to_message:
                await bot.forward_message(g["id"], m.chat.id, m.reply_to_message.message_id)
            sent += 1
        except Exception:
            pass
    await m.reply(f"✅ ارسال تقریبی انجام شد به {sent} گروه.")

# --------------------- گزارش روزانه و نوتیف‌ها ---------------------
async def daily_report_task():
    # گزارش روزانه 10 نفر برتر و ارسال به مالکان
    while True:
        try:
            async with pool.acquire() as conn:
                top = await conn.fetch("SELECT id, first_name, score FROM users ORDER BY score DESC LIMIT 10")
            if top:
                lines = ["📣 گزارش روزانه امتیازات — 10 نفر برتر:"]
                for i, r in enumerate(top, 1):
                    lines.append(f"{i}. {format_mention(r['id'], r['first_name'] or 'کاربر')} — {r['score']} امتیاز")
                text = "\n".join(lines)
                for owner in OWNER_IDS:
                    try:
                        await bot.send_message(owner, text, parse_mode="HTML")
                    except:
                        pass
        except Exception:
            pass
        # صبر 24 ساعت (86400 ثانیه)
        await asyncio.sleep(24 * 60 * 60)

async def notify_owner_new_group(group_id: int, title: str):
    text = f"📥 گروه جدید ثبت شد:\n{title or 'بدون عنوان'}\nآیدی: `{group_id}`"
    for owner in OWNER_IDS:
        try:
            await bot.send_message(owner, text, parse_mode="HTML")
        except:
            pass

# --------------------- مدیریت ورود ربات به گروه / شناسایی ادمین‌ها ---------------------
@dp.my_chat_member()
async def on_my_chat_member_update(m):
    # وقتی ربات به گروه اضافه میشه، ثبت گروه و اطلاع مالک
    try:
        chat = await bot.get_chat(m.chat.id)
        await ensure_group(m.chat.id, chat.title or "", 0)
        await notify_owner_new_group(m.chat.id, chat.title or "")
    except:
        pass

# دستور پیکربندی دستی برای شناسایی مجدد مقام داران گروه
@dp.message(F.chat.type.in_(["group", "supergroup"]) & F.text.lower() == "پیکربندی")
async def reconfigure_group(m: Message):
    try:
        member = await bot.get_chat_member(m.chat.id, m.from_user.id)
        if member.status not in ("creator", "administrator"):
            await m.reply("فقط ادمین‌ها می‌توانند پیکربندی را اجرا کنند.")
            return
    except:
        await m.reply("خطا در بررسی دسترسی‌ها.")
        return

    try:
        chat = await bot.get_chat(m.chat.id)
        await ensure_group(m.chat.id, chat.title or "", m.from_user.id)
        await m.reply("✅ پیکربندی و ثبت مجدد اطلاعات گروه انجام شد.")
    except Exception:
        await m.reply("خطا در پیکربندی. لطفاً بعداً تلاش کنید.")

# --------------------- راه‌اندازی اصلی ---------------------
async def on_startup():
    await init_db()
    me = await bot.get_me()
    print(f"🤖 Logged in as @{me.username}")
    # اگر خواستی، میتوانیم BOT_USERNAME را از get_me آپدیت کنیم (ولی از مقدار ENV استفاده می‌کنیم)
    # start background tasks
    asyncio.create_task(daily_report_task())

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down...")
