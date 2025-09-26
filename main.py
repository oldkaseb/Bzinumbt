import asyncio
import os
import random
import re
from typing import List
from aiogram.filters.command import Command

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import asyncpg

# ========== تنظیمات محیط ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@YourChannel")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@SupportUser")

if not BOT_TOKEN or not DATABASE_URL or OWNER_ID == 0 or not REQUIRED_CHANNEL:
    raise RuntimeError("ENV ها باید تنظیم شوند.")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
pool: asyncpg.Pool = None

# ========== ساختار دیتابیس ==========
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
# ========== راه‌اندازی دیتابیس ==========
async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute(CREATE_SQL)

# ========== کمک‌تابع‌ها ==========
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
def range_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1–10", callback_data="range_1_10")],
        [InlineKeyboardButton(text="10–100", callback_data="range_10_100")],
        [InlineKeyboardButton(text="100–500", callback_data="range_100_500")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_main")]
    ])

def waiting_kb(game_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 منم بازی", callback_data=f"join_{game_id}")],
        [InlineKeyboardButton(text="▶️ شروع بازی", callback_data=f"start_{game_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_main")]
    ])

# ========== مدیریت پیام قبلی ربات ==========
last_bot_messages = {}  # key = group_id, value = message_id

async def delete_last_bot_message(chat_id: int):
    msg_id = last_bot_messages.get(chat_id)
    if msg_id:
        try:
            await bot.delete_message(chat_id, msg_id)
        except:
            pass

# ========== هندل پیام «حدس عدد» ==========
@dp.message(F.chat.type.in_({"group", "supergroup"}) & F.text.lower().contains("حدس عدد"))
async def handle_guess_word(m: Message):
    await upsert_user(m.from_user)
    await ensure_group(m.chat.id, m.chat.title or "", m.from_user.id)

    if not await is_member_required_channel(m.from_user.id):
        await send_join_request(m)
        return

    await delete_last_bot_message(m.chat.id)
    msg = await m.reply("رنج بازی را انتخاب کنید:", reply_markup=range_kb())
    last_bot_messages[m.chat.id] = msg.message_id

# ========== انتخاب رنج ==========
@dp.callback_query(F.data.startswith("range_"))
async def handle_range(c: CallbackQuery):
    if not await is_member_required_channel(c.from_user.id):
        await send_join_request(c)
        return

    data = c.data.split("_")
    mn, mx = int(data[1]), int(data[2])

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO games (group_id, creator_id, range_min, range_max, status)
            VALUES ($1,$2,$3,$4,'waiting')
        """, c.message.chat.id, c.from_user.id, mn, mx)

        rec = await conn.fetchrow("SELECT id FROM games WHERE group_id=$1 AND status='waiting' ORDER BY id DESC LIMIT 1", c.message.chat.id)
        game_id = rec["id"]

    await delete_last_bot_message(c.message.chat.id)

    text = f"""🎯 بازی در حالت انتظار بازیکن است!
رنج بازی: <b>{mn} تا {mx}</b>
برای شرکت در بازی ابتدا عضو {REQUIRED_CHANNEL} شوید.
سپس روی "منم بازی" کلیک کنید.
"""
    msg = await c.message.answer(text, reply_markup=waiting_kb(game_id))
    last_bot_messages[c.message.chat.id] = msg.message_id

# ========== دکمه عضویت دوباره ==========
@dp.callback_query(F.data == "check_membership")
async def check_membership(c: CallbackQuery):
    if await is_member_required_channel(c.from_user.id):
        await c.answer("عضویت تایید شد ✅", show_alert=True)
    else:
        await c.answer("هنوز عضو کانال نیستی ❌", show_alert=True)

# ========== دکمه «منم بازی» ==========
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

        game = await conn.fetchrow("SELECT * FROM games WHERE id=$1", game_id)
        users = await conn.fetch("SELECT user_id FROM participants WHERE game_id=$1", game_id)

    player_list = "\n".join(
        [f"{i+1}. <a href='tg://user?id={u['user_id']}'>کاربر</a>" for i, u in enumerate(users)]
    )

    txt = f"""🎯 بازی در حالت انتظار بازیکن است!
رنج بازی: <b>{game['range_min']} تا {game['range_max']}</b>

شرکت‌کنندگان:
{player_list}
"""
    try:
        await bot.edit_message_text(
            chat_id=c.message.chat.id,
            message_id=game['announce_msg_id'] or last_bot_messages.get(c.message.chat.id),
            text=txt,
            reply_markup=waiting_kb(game_id),
            parse_mode="HTML"
        )
    except:
        pass

    await c.answer("به بازی اضافه شدی ✅", show_alert=False)

# ========== دکمه «شروع بازی» ==========
@dp.callback_query(F.data.startswith("start_"))
async def start_game_btn(c: CallbackQuery):
    game_id = int(c.data.split("_")[1])
    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM games WHERE id=$1", game_id)

    if not game or game["status"] != "waiting":
        await c.answer("بازی نامعتبر است ❌", show_alert=True)
        return

    if c.from_user.id != game["creator_id"]:
        await c.answer("فقط درخواست‌کننده می‌تونه بازی رو شروع کنه ❌", show_alert=True)
        return

    target = random.randint(int(game["range_min"]), int(game["range_max"]))

    async with pool.acquire() as conn:
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
@dp.message(F.chat.type.in_({"group", "supergroup"}) & F.text.regexp(r"^\d+$"))
async def guess_number(m: Message):
    num = int(m.text.strip())

    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM games WHERE group_id=$1 AND status='active' ORDER BY id DESC LIMIT 1", m.chat.id)
        if not game:
            return
        if num == game["target_number"]:
            await conn.execute("""
                UPDATE games SET status='finished', winner_id=$1, finished_at=now()
                WHERE id=$2
            """, m.from_user.id, game["id"])

            await conn.execute("""
                UPDATE users SET score = score + 1 WHERE id=$1
            """, m.from_user.id)

            await m.reply(f"🎉 تبریک! <a href='tg://user?id={m.from_user.id}'>{m.from_user.first_name}</a> عدد {num} را درست حدس زد!", parse_mode="HTML")

@dp.message(F.chat.type.in_({"group", "supergroup"}) & F.text.lower() == "امتیاز بازی")
async def show_scores(m: Message):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.id, u.first_name, u.username, u.score
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
        name = row["first_name"] or "کاربر"
        mention = f"<a href='tg://user?id={row['id']}'>{name}</a>"
        lines.append(f"{idx}. {mention} — {row['score']} امتیاز")

    await m.reply("\n".join(lines), parse_mode="HTML")

@dp.message(F.chat.type.in_({"group", "supergroup"}) & F.text.lower() == "ریست آمار بازی")
async def reset_scores(m: Message):
    member = await bot.get_chat_member(m.chat.id, m.from_user.id)
    is_admin = member.status in ("creator", "owner")
    if m.from_user.id != OWNER_ID and not is_admin:
        await m.reply("این دستور فقط برای مالک گروه یا مالک ربات است.")
        return

    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE users SET score = 0
            WHERE id IN (
                SELECT user_id FROM participants
                JOIN games ON participants.game_id = games.id
                WHERE games.group_id = $1
            )
        """, m.chat.id)

    await m.reply("✅ آمار بازی صفر شد.")

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

@dp.message(F.chat.type == "private", F.text.lower() == "شروع")
async def start_pv(m: Message):
    await upsert_user(m.from_user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ افزودن به گروه", url=f"https://t.me/{(await bot.me()).username}?startgroup=true")],
        [InlineKeyboardButton("🆘 تماس با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME.removeprefix('@')}")],
    ])
    await m.answer(f"""سلام {m.from_user.first_name} 👋

من یه ربات بازی گروهی هستم 🎲
با ارسال «حدس عدد» در گروه، یک بازی ساده و هیجان‌انگیز راه بنداز!

📢 اول مطمئن شو اعضا توی کانال {REQUIRED_CHANNEL} عضو هستن.
""", reply_markup=kb)

@dp.message(F.chat.type == "private", F.from_user.id == OWNER_ID, F.text.lower() == "آمار ربات")
async def bot_stats(m: Message):
    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        groups = await conn.fetch("SELECT * FROM groups")
        games = await conn.fetchval("SELECT COUNT(*) FROM games")
    
    lines = [f"📊 آمار کلی ربات:",
             f"👤 کاربران: {users}",
             f"👥 گروه‌ها: {len(groups)}",
             f"🎮 بازی‌ها: {games}",
             "",
             "📋 لیست گروه‌ها:"]
    
    for g in groups:
        owner = f"<a href='tg://user?id={g['owner_id']}'>مالک</a>"
        lines.append(f"• {g['title']} ({g['id']}) — {owner}")

    await m.answer("\n".join(lines), parse_mode="HTML")

@dp.message(Command("start"))
async def handle_start_command(m: Message):
    await start_pv(m)  # همون تابعی که برای پیام «شروع» در PV داریم

async def main():
    await init_db()
    me = await bot.get_me()
    print(f"🤖 Logged in as @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
