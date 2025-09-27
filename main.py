import asyncio
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime, timedelta
import re
import os

# ====================== CONFIG ======================
API_TOKEN = os.getenv("BOT_TOKEN")  # متغیر محیطی ریلوی برای توکن ربات
DB_URI = os.getenv("DATABASE_URL")   # متغیر محیطی ریلوی برای دیتابیس PostgreSQL
CHANNEL_ID = "@RHINOSOUL_TM"
SUPPORT = "@OLDKASEB"
OWNER_IDS = [7662192190, 6041119040]

# ====================== DATABASE ======================
class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(dsn=DB_URI)

    async def execute(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

db = Database()

# ====================== FSM ======================
class GuessGame(StatesGroup):
    waiting_for_range = State()
    playing = State()

# ====================== BOT INIT ======================
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ====================== HELPERS ======================
def to_english_numbers(text: str) -> str:
    persian_numbers = "۰۱۲۳۴۵۶۷۸۹"
    english_numbers = "0123456789"
    for p, e in zip(persian_numbers, english_numbers):
        text = text.replace(p, e)
    return text

async def is_channel_member(user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status != "left"
    except:
        return False

async def get_admin_ids(chat_id: int):
    admins = await bot.get_chat_administrators(chat_id)
    return [admin.user.id for admin in admins]

async def add_user(user_id: int, username: str):
    await db.execute("""
        INSERT INTO users(user_id, username)
        VALUES($1, $2)
        ON CONFLICT (user_id) DO UPDATE SET username=$2
    """, user_id, username or "")

async def update_score(user_id: int, score: int):
    await db.execute("""
        UPDATE users
        SET total_score = total_score + $1,
            daily_score = daily_score + $1,
            monthly_score = monthly_score + $1
        WHERE user_id = $2
    """, score, user_id)

# ====================== TABLE INIT ======================
async def init_tables():
    await db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        total_score INT DEFAULT 0,
        daily_score INT DEFAULT 0,
        monthly_score INT DEFAULT 0
    );
    """)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS games (
        game_id SERIAL PRIMARY KEY,
        group_id BIGINT,
        creator_id BIGINT,
        target_number INT,
        start_time TIMESTAMP,
        end_time TIMESTAMP
    );
    """)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS participants (
        game_id INT REFERENCES games(game_id),
        user_id BIGINT REFERENCES users(user_id),
        score INT DEFAULT 0,
        PRIMARY KEY(game_id,user_id)
    );
    """)

# ====================== PRIVATE HANDLERS ======================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ افزودن به گروه", url=f"https://t.me/FindNumRS_Bot?startgroup=true")],
        [InlineKeyboardButton("🆘 تماس با پشتیبان", url=f"https://t.me/{SUPPORT[1:]}")]
    ])
    await message.answer(
        f"سلام 😎\nمن ربات FindNumRS_Bot هستم!\nبا من می‌تونی در گروه‌ها عدد حدس بزنی و امتیاز جمع کنی.\n"
        "برای کاربر برتر ماهانه هدیه داریم 🎁\n\n"
        f"کانال تیم: {CHANNEL_ID}\n"
        f"پشتیبان: {SUPPORT}",
        reply_markup=kb
    )

# ====================== GROUP GAME ======================
active_games = {}  # {group_id: {"creator": id, "target": num, "participants": set()}}

@dp.message(lambda m: m.text and m.text.startswith("حدس عدد"))
async def start_guess_game(message: types.Message, state: FSMContext):
    admins = await get_admin_ids(message.chat.id)
    if message.from_user.id not in admins:
        await message.reply("❌ فقط ادمین‌ها می‌توانند بازی را شروع کنند.")
        return
    await message.reply("🎮 لطفا بازه بازی را به صورت min-max وارد کنید (مثلا 1-1000):")
    await state.set_state(GuessGame.waiting_for_range)
    await state.update_data(creator=message.from_user.id)

@dp.message(GuessGame.waiting_for_range)
async def set_game_range(message: types.Message, state: FSMContext):
    text = to_english_numbers(message.text)
    match = re.match(r"(\d+)-(\d+)", text)
    if not match:
        await message.reply("❌ فرمت اشتباه است. لطفا به صورت min-max وارد کنید.")
        return
    min_val, max_val = int(match.group(1)), int(match.group(2))
    target = int(min_val + (max_val - min_val) * asyncio.random.random())
    data = await state.get_data()
    group_id = message.chat.id
    active_games[group_id] = {"creator": data["creator"], "target": target, "participants": set(), "range": (min_val, max_val)}
    await db.execute("INSERT INTO games(group_id, creator_id, target_number, start_time) VALUES($1,$2,$3,$4)",
                     group_id, data["creator"], target, datetime.now())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🎮 منم بازی", callback_data="join_game")],
        [InlineKeyboardButton("▶️ شروع بازی", callback_data="begin_game")],
        [InlineKeyboardButton("❌ بستن", callback_data="close_game")]
    ])
    await message.reply(f"بازی آماده شد! بازه: {min_val} تا {max_val}\nشرکت‌کنندگان باید عضو {CHANNEL_ID} باشند.", reply_markup=kb)
    await state.clear()

# ====================== CALLBACK HANDLERS ======================
@dp.callback_query(lambda c: c.data == "join_game")
async def join_game_cb(callback: types.CallbackQuery):
    group_id = callback.message.chat.id
    user_id = callback.from_user.id
    username = callback.from_user.username
    if not await is_channel_member(user_id):
        await callback.answer("❌ لطفا ابتدا عضو کانال شوید.", show_alert=True)
        return
    active_games[group_id]["participants"].add(user_id)
    await add_user(user_id, username)
    await callback.answer("✅ وارد بازی شدی عزیزم!")

@dp.callback_query(lambda c: c.data == "begin_game")
async def begin_game_cb(callback: types.CallbackQuery):
    group_id = callback.message.chat.id
    if callback.from_user.id != active_games[group_id]["creator"]:
        await callback.answer("❌ فقط سازنده بازی می‌تواند شروع کند.", show_alert=True)
        return
    min_val, max_val = active_games[group_id]["range"]
    await callback.message.edit_text(f"🎉 بازی شروع شد! بازه: {min_val}-{max_val}\nعدد را حدس بزنید.")

@dp.callback_query(lambda c: c.data == "close_game")
async def close_game_cb(callback: types.CallbackQuery):
    group_id = callback.message.chat.id
    if callback.from_user.id != active_games[group_id]["creator"]:
        await callback.answer("❌ فقط سازنده بازی می‌تواند ببندد.", show_alert=True)
        return
    del active_games[group_id]
    await callback.message.edit_text("❌ بازی بسته شد.")

# ====================== GUESS HANDLER ======================
@dp.message(lambda m: m.chat.id in active_games)
async def guess_number(message: types.Message):
    group_id = message.chat.id
    user_id = message.from_user.id
    if user_id not in active_games[group_id]["participants"]:
        return
    try:
        guess = int(to_english_numbers(message.text))
    except:
        return
    target = active_games[group_id]["target"]
    if guess == target:
        await update_score(user_id, 1)
        await message.reply(f"🎉 تبریک {message.from_user.mention()}! عدد درست بود.\nامتیاز +1")
        del active_games[group_id]
    elif guess < target:
        await message.reply("🔼 عدد بزرگ‌تر است!")
    else:
        await message.reply("🔽 عدد کوچک‌تر است!")

# ====================== SHOW TOP SCORES ======================
@dp.message(Command("امتیاز_بازی"))
async def show_top_scores(message: types.Message):
    rows = await db.fetch("SELECT username, total_score FROM users ORDER BY total_score DESC LIMIT 10")
    text = "🏆 ۱۰ نفر برتر:\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. @{row['username']} - {row['total_score']} امتیاز\n"
    await message.reply(text)

# ====================== STARTUP ======================
async def main():
    await db.connect()
    await init_tables()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
