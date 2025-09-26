import asyncio
import os
import random
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import asyncpg

# ========= تنظیمات =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@RHINOSOUL_TM")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@OLDKASEB")

if not BOT_TOKEN or not DATABASE_URL or OWNER_ID == 0:
    raise RuntimeError("ENV های BOT_TOKEN, DATABASE_URL, OWNER_ID باید تنظیم شوند.")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
pool: asyncpg.Pool = None

# ========= دیتابیس =========
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users (
  id BIGINT PRIMARY KEY,
  username TEXT,
  first_name TEXT
);

CREATE TABLE IF NOT EXISTS groups (
  id BIGINT PRIMARY KEY,
  title TEXT,
  charge_units INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS games (
  id SERIAL PRIMARY KEY,
  group_id BIGINT REFERENCES groups(id) ON DELETE CASCADE,
  creator_id BIGINT,
  range_min INT,
  range_max INT,
  target_number INT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  winner_id BIGINT,
  status TEXT CHECK (status IN ('pending','active','finished')) DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS game_participants (
  id SERIAL PRIMARY KEY,
  game_id INT REFERENCES games(id) ON DELETE CASCADE,
  user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(game_id, user_id)
);
"""

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute(CREATE_SQL)

async def upsert_user(u):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO UPDATE
            SET username=EXCLUDED.username, first_name=EXCLUDED.first_name
        """, u.id, u.username, u.first_name or "")

async def set_group_range(group_id: int, mn: int, mx: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO games (group_id, range_min, range_max, status)
            VALUES ($1,$2,$3,'pending')
        """, group_id, mn, mx)

async def get_pending_game(group_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM games WHERE group_id=$1 AND status='pending' ORDER BY id DESC LIMIT 1", group_id)

async def get_active_game(group_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM games WHERE group_id=$1 AND status='active' ORDER BY id DESC LIMIT 1", group_id)

async def create_active_game(group_id: int, creator_id: int, mn: int, mx: int, target: int) -> int:
    async with pool.acquire() as conn:
        rec = await conn.fetchrow("""
            INSERT INTO games (group_id, creator_id, range_min, range_max, target_number, started_at, status)
            VALUES ($1,$2,$3,$4,$5, now(), 'active')
            RETURNING id
        """, group_id, creator_id, mn, mx, target)
        return int(rec["id"])

async def finish_game(game_id: int, winner_id: int | None = None):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE games SET finished_at=now(), winner_id=$2, status='finished' WHERE id=$1", game_id, winner_id)

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
    await msg.reply(f"برای استفاده از ربات باید اول عضو کانال {REQUIRED_CHANNEL} بشی.", reply_markup=kb)

@dp.callback_query(F.data == "check_membership")
async def check_membership(c: CallbackQuery):
    ok = await is_member_required_channel(c.from_user.id)
    if ok:
        await c.answer("عضویت شما تایید شد ✅", show_alert=True)
        await c.message.reply("حالا می‌تونی به بازی بپیوندی. بنویس: «حدس عدد»")
    else:
        await c.answer("هنوز عضو کانال نیستی ❌", show_alert=True)

def main_panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 انتخاب رنج", callback_data="range")],
        [InlineKeyboardButton(text="🎲 شروع بازی", callback_data="start_game")],
    ])

def range_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1–10", callback_data="range_1_10")],
        [InlineKeyboardButton(text="10–100", callback_data="range_10_100")],
        [InlineKeyboardButton(text="100–500", callback_data="range_100_500")],
        [InlineKeyboardButton(text="100–1000", callback_data="range_100_1000")],
        [InlineKeyboardButton(text="1000–5000", callback_data="range_1000_5000")],
        [InlineKeyboardButton(text="سفارشی", callback_data="range_custom")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_main")]
    ])

@dp.message(F.text.lower() == "شروع")
async def start_private(m: Message):
    await upsert_user(m.from_user)
    await m.answer("سلام! برای شروع در گروه بنویس: «حدس عدد»")

@dp.message(F.chat.type.in_({"group","supergroup"}) & F.text.contains("حدس عدد"))
async def open_panel(m: Message):
    if not await is_member_required_channel(m.from_user.id):
        await send_join_request(m)
        return
    await m.reply("پنل بازی:", reply_markup=main_panel())

@dp.callback_query(F.data == "range")
async def pick_range(c: CallbackQuery):
    await c.message.edit_text("رنج عدد را انتخاب کنید:", reply_markup=range_kb())

@dp.callback_query(F.data == "back_main")
async def back_main(c: CallbackQuery):
    await c.message.edit_text("پنل بازی:", reply_markup=main_panel())

@dp.callback_query(F.data.startswith("range_"))
async def set_range_cb(c: CallbackQuery):
    _, mn, mx = c.data.split("_")
    mn, mx = int(mn), int(mx)
    await set_group_range(c.message.chat.id, mn, mx)
    await c.answer(f"رنج {mn}-{mx} تنظیم شد.")

@dp.callback_query(F.data == "start_game")
async def start_game(c: CallbackQuery):
    if not await is_member_required_channel(c.from_user.id):
        await send_join_request(c)
        return
    pending = await get_pending_game(c.message.chat.id)
    if not pending:
        await set_group_range(c.message.chat.id, 1, 10)
        pending = await get_pending_game(c.message.chat.id)
    mn, mx = int(pending["range_min"]), int(pending["range_max"])
    target = random.randint(mn, mx)
    game_id = await create_active_game(c.message.chat.id, c.from_user.id, mn, mx, target)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 منم بازی", callback_data=f"join_active_{game_id}")]
    ])
    await c.message.reply(f"بازی شروع شد! یک عدد بین {mn} تا {mx} حدس بزنید.", reply_markup=kb)

@dp.message(F.text.lower() == "اتمام بازی")
async def end_game(m: Message):
    game = await get_active_game(m.chat.id)
    if not game:
        await m.reply("هیچ بازی فعالی وجود ندارد.")
        return
    # فقط شروع‌کننده یا مالک
    if m.from_user.id != game["creator_id"] and m.from_user.id != OWNER_ID:
        await m.reply("فقط شروع‌کننده یا مالک می‌تواند بازی را تمام کند.")
        return
    await finish_game(game["id"])
    await m.reply("بازی به پایان رسید ❌")

# گرفتن حدس‌ها
@dp.message(F.chat.type.in_({"group","supergroup"}) & F.text.regexp(r"^\d+$"))
async def catch_guess(m: Message):
    game = await get_active_game(m.chat.id)
    if not game:
        return
    if not await is_member_required_channel(m.from_user.id):
        return
    num = int(m.text.strip())
    if num == int(game["target_number"]):
        await finish_game(game["id"], m.from_user.id)
        await m.reply(f"تبریک 🎉 <a href='tg://user?id={m.from_user.id}'>{m.from_user.first_name}</a> عدد {num} رو درست حدس زد!")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
