import asyncio
import os
import re
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import asyncpg

# ========== تنظیمات محیط ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
OWNER_IDS = [7662192190, 6041119040]
REQUIRED_CHANNEL = "@RHINOSOUL_TM"
SUPPORT_USERNAME = "@OLDKASEB"

if not BOT_TOKEN or not DATABASE_URL:
    raise RuntimeError("BOT_TOKEN و DATABASE_URL باید تنظیم شوند.")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
pool: asyncpg.Pool = None

# ========== دیتابیس ==========
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    score INT DEFAULT 0,
    daily_score INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS groups (
    id BIGINT PRIMARY KEY,
    title TEXT,
    owner_id BIGINT
);

CREATE TABLE IF NOT EXISTS games (
    id SERIAL PRIMARY KEY,
    group_id BIGINT REFERENCES groups(id) ON DELETE CASCADE,
    creator_id BIGINT,
    range_min INT,
    range_max INT,
    target_number INT,
    status TEXT CHECK (status IN ('waiting', 'active', 'finished')) DEFAULT 'waiting',
    announce_msg_id INT,
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
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute(CREATE_SQL)

# ========== کمک‌تابع‌ها ==========
def normalize_numbers(text: str) -> str:
    return text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))

async def upsert_user(u):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO UPDATE
            SET username=EXCLUDED.username, first_name=EXCLUDED.first_name
        """, u.id, u.username, u.first_name or "")

async def ensure_group(chat_id: int, title: str, owner_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO groups (id, title, owner_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title
        """, chat_id, title or "", owner_id)

async def is_member_required_channel(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False

async def send_join_request(message: Message | CallbackQuery):
    msg = message.message if isinstance(message, CallbackQuery) else message
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 عضویت در کانال", url=f"https://t.me/{REQUIRED_CHANNEL.removeprefix('@')}")],
        [InlineKeyboardButton(text="✅ عضو شدم", callback_data="check_membership")]
    ])
    await msg.reply(f"برای شرکت در بازی ابتدا عضو کانال {REQUIRED_CHANNEL} شوید.", reply_markup=kb)

# ========== کیبوردها ==========
def waiting_kb(game_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 منم بازی", callback_data=f"join_{game_id}")],
        [InlineKeyboardButton(text="▶️ شروع بازی", callback_data=f"start_{game_id}")],
        [InlineKeyboardButton(text="❌ بستن", callback_data=f"close_{game_id}")]
    ])

# ========== مدیریت پیام قبلی ==========
last_bot_messages = {}  # key = chat_id, value = message_id

async def delete_last_bot_message(chat_id: int):
    msg_id = last_bot_messages.get(chat_id)
    if msg_id:
        try:
            await bot.delete_message(chat_id, msg_id)
        except:
            pass

# ========== استارت PV ==========
@dp.message(F.chat.type == "private", F.text.lower() == "start")
async def start_pv(m: Message):
    await upsert_user(m.from_user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ افزودن به گروه", url=f"https://t.me/FindNumRS_Bot?startgroup=true")],
        [InlineKeyboardButton("🆘 تماس با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME.removeprefix('@')}")],
    ])
    text = f"""سلام {m.from_user.first_name} 👋

🎲 من ربات بازی گروهی «حدس عدد» هستم!

📢 برای بازی حتماً اعضای گروه باید عضو کانال {REQUIRED_CHANNEL} باشند.

تیم برنامه نویسی RHINOSOUL
توسعه ربات، سایت و اپلیکیشن برای هر گروه و کسب‌وکار

🎁 هر ماه کاربر امتیاز برتر هدیه دریافت می‌کند
سوالات خود را با پشتیبان مطرح کنید: {SUPPORT_USERNAME}
"""
    await m.answer(text, reply_markup=kb)

# ========== دکمه عضویت ==========
@dp.callback_query(F.data == "check_membership")
async def check_membership(c: CallbackQuery):
    if await is_member_required_channel(c.from_user.id):
        await c.answer("عضویت تایید شد ✅", show_alert=True)
    else:
        await c.answer("هنوز عضو کانال نیستی ❌", show_alert=True)

# ========== دکمه بستن ==========
@dp.callback_query(F.data.startswith("close_"))
async def close_panel(c: CallbackQuery):
    try:
        await bot.delete_message(c.message.chat.id, c.message.message_id)
    except:
        pass

# ========== حدس عدد ==========
@dp.message(F.chat.type.in_({"group", "supergroup"}), F.text.lower().contains("حدس عدد"))
async def handle_guess_word(m: Message):
    await upsert_user(m.from_user)
    await ensure_group(m.chat.id, m.chat.title or "", m.from_user.id)
    if not await is_member_required_channel(m.from_user.id):
        await send_join_request(m)
        return
    await delete_last_bot_message(m.chat.id)
    msg = await m.reply("🎯 لطفاً رنج بازی را وارد کنید (مثال: 1-1000 یا ۱-۱۰۰۰):")
    last_bot_messages[m.chat.id] = msg.message_id

    @dp.message(F.chat.id == m.chat.id)
    async def set_custom_range(r_msg: Message):
        text = normalize_numbers(r_msg.text)
        match = re.match(r"(\d+)[–-](\d+)", text)
        if not match:
            await r_msg.reply("❌ فرمت اشتباه است، دوباره وارد کنید (مثال: 1-1000).")
            return
        mn, mx = int(match[1]), int(match[2])
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO games (group_id, creator_id, range_min, range_max, status)
                VALUES ($1,$2,$3,$4,'waiting')
            """, m.chat.id, m.from_user.id, mn, mx)
            rec = await conn.fetchrow("SELECT id FROM games WHERE group_id=$1 AND status='waiting' ORDER BY id DESC LIMIT 1", m.chat.id)
            game_id = rec["id"]
        await bot.edit_message_text(
            chat_id=r_msg.chat.id,
            message_id=last_bot_messages[m.chat.id],
            text=f"🎯 بازی در حالت انتظار بازیکن است!\nرنج بازی: <b>{mn} تا {mx}</b>\nبرای شرکت حتما عضو {REQUIRED_CHANNEL} شوید.",
            reply_markup=waiting_kb(game_id),
            parse_mode="HTML"
        )
        dp.message_handlers.unregister(set_custom_range)

# ========== دکمه منم بازی ==========
@dp.callback_query(F.data.startswith("join_"))
async def join_game(c: CallbackQuery):
    game_id = int(c.data.split("_")[1])
    if not await is_member_required_channel(c.from_user.id):
        await c.answer("برای شرکت باید عضو کانال بشی ❌", show_alert=True)
        return
    await upsert_user(c.from_user)
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO participants (game_id, user_id)
            VALUES ($1,$2)
            ON CONFLICT DO NOTHING
        """, game_id, c.from_user.id)
    await c.answer("🎉 وارد بازی شدی عزیزم ✅", show_alert=True)

# ========== دکمه شروع بازی ==========
@dp.callback_query(F.data.startswith("start_"))
async def start_game_btn(c: CallbackQuery):
    game_id = int(c.data.split("_")[1])
    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM games WHERE id=$1", game_id)
    if not game or game["status"] != "waiting":
        await c.answer("بازی نامعتبر است ❌", show_alert=True)
        return
    if c.from_user.id != game["creator_id"]:
        await c.answer("فقط درخواست‌کننده می‌تواند بازی را شروع کند ❌", show_alert=True)
        return
    target = random.randint(int(game["range_min"]), int(game["range_max"]))
    await conn.execute("""
        UPDATE games SET target_number=$1, status='active', started_at=now()
        WHERE id=$2
    """, target, game_id)
    await c.message.edit_text(
        f"🎯 بازی شروع شد! عددی بین {game['range_min']} تا {game['range_max']} حدس بزنید.",
        reply_markup=None
    )
    await c.answer("بازی شروع شد ✅")

# ========== حدس عدد ==========
@dp.message(F.chat.type.in_({"group", "supergroup"}), F.text.regexp(r"^[۰-۹0-9]+$"))
async def guess_number(m: Message):
    num = int(normalize_numbers(m.text.strip()))
    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM games WHERE group_id=$1 AND status='active' ORDER BY id DESC LIMIT 1", m.chat.id)
        if not game:
            return
        is_participant = await conn.fetchval("SELECT 1 FROM participants WHERE game_id=$1 AND user_id=$2", game["id"], m.from_user.id)
        if not is_participant:
            return
        if num == game["target_number"]:
            await conn.execute("""
                UPDATE games SET status='finished', winner_id=$1, finished_at=now()
                WHERE id=$2
            """, m.from_user.id, game["id"])
            await conn.execute("UPDATE users SET score = score + 1, daily_score = daily_score + 1 WHERE id=$1", m.from_user.id)
            await m.reply(f"🎉 تبریک! <a href='tg://user?id={m.from_user.id}'>{m.from_user.first_name}</a> عدد {num} را درست حدس زد!", parse_mode="HTML")

# ========== نمایش آمار بازی ==========
@dp.message(F.chat.type.in_({"group", "supergroup"}), F.text.lower() == "امتیاز بازی")
async def show_scores(m: Message):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.id, u.first_name, u.score
            FROM users u
            JOIN participants p ON u.id = p.user_id
            JOIN games g ON g.id = p.game_id
            WHERE g.group_id=$1
            GROUP BY u.id
            ORDER BY u.score DESC
            LIMIT 10
        """, m.chat.id)
    if not rows:
        await m.reply("هنوز هیچ امتیازی ثبت نشده.")
        return
    lines = ["🏆 <b>جدول امتیاز</b>:"]
    for idx, row in enumerate(rows, 1):
        mention = f"<a href='tg://user?id={row['id']}'>{row['first_name']}</a>"
        lines.append(f"{idx}. {mention} — {row['score']} امتیاز")
    await m.reply("\n".join(lines), parse_mode="HTML")

# ========== تسک زمان‌بندی ==========
async def scheduled_tasks():
    while True:
        now = datetime.utcnow()
        next_day = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        seconds_until_midnight = (next_day - now).total_seconds()
        await asyncio.sleep(seconds_until_midnight + 5)
        async with pool.acquire() as conn:
            top10 = await conn.fetch("""
                SELECT id, first_name, daily_score FROM users
                ORDER BY daily_score DESC
                LIMIT 10
            """)
            for owner_id in OWNER_IDS:
                lines = ["📊 <b>۱۰ کاربر برتر امروز</b>:"]
                for idx, row in enumerate(top10,1):
                    lines.append(f"{idx}. <a href='tg://user?id={row['id']}'>{row['first_name']}</a> — {row['daily_score']} امتیاز")
                if top10:
                    await bot.send_message(owner_id, "\n".join(lines), parse_mode="HTML")
            await conn.execute("UPDATE users SET score = score + daily_score, daily_score = 0")
        if now.day == 1:
            async with pool.acquire() as conn:
                top_month = await conn.fetchrow("SELECT id, first_name, score FROM users ORDER BY score DESC LIMIT 1")
                for owner_id in OWNER_IDS:
                    if top_month:
                        await bot.send_message(owner_id, f"📊 <b>گزارش ریست ماهانه</b>\nکاربر برتر ماه قبل: <a href='tg://user?id={top_month['id']}'>{top_month['first_name']}</a> — {top_month['score']} امتیاز", parse_mode="HTML")
                await conn.execute("UPDATE users SET score = 0, daily_score = 0")

# ========== دستورات مالک ==========
@dp.message(F.from_user.id.in_(OWNER_IDS))
async def owner_commands(m: Message):
    text = m.text.lower()
    if text == "آمار ربات":
        async with pool.acquire() as conn:
            users = await conn.fetchval("SELECT COUNT(*) FROM users")
            groups = await conn.fetch("SELECT * FROM groups")
            games = await conn.fetchval("SELECT COUNT(*) FROM games")
        lines = [
            f"📊 آمار کلی ربات:",
            f"👤 کاربران: {users}",
            f"👥 گروه‌ها: {len(groups)}",
            f"🎮 بازی‌ها: {games}",
            "",
            "📋 لیست گروه‌ها:"
        ]
        for g in groups:
            owner = f"<a href='tg://user?id={g['owner_id']}'>مالک</a>"
            lines.append(f"• {g['title']} ({g['id']}) — {owner}")
        await m.reply("\n".join(lines), parse_mode="HTML")

    elif text.startswith("پیام همگانی "):
        msg_text = m.text[len("پیام همگانی "):].strip()
        async with pool.acquire() as conn:
            groups = await conn.fetch("SELECT id FROM groups")
            for g in groups:
                try:
                    await bot.send_message(g['id'], msg_text)
                except:
                    pass
        await m.reply("پیام به همه گروه‌ها ارسال شد ✅")

    elif text == "پینگ":
        start = datetime.utcnow()
        await m.reply("⏱ در حال بررسی...")
        end = datetime.utcnow()
        await m.reply(f"🏓 سرعت ربات: {(end-start).total_seconds()*1000:.2f} ms")

# ========== اجرای ربات ==========
async def main():
    await init_db()
    asyncio.create_task(scheduled_tasks())
    me = await bot.get_me()
    print(f"🤖 Logged in as @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
