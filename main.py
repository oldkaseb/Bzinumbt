import os
import asyncio
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import re

# ====================== CONFIG ======================
API_TOKEN = os.getenv("BOT_TOKEN")
DB_URI = os.getenv("DATABASE_URL")
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
    waiting_custom_range = State()

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
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardmarkup(text="➕ افزودن به گروه", url="https://t.me/FindNumRS_Bot?startgroup=true")],
            [InlineKeyboardmarkup(text="🆘 تماس با پشتیبان", url=f"https://t.me/{SUPPORT[1:]}")]
        ]
    )
    await message.answer(
        f"سلام 😎\nمن ربات FindNumRS_Bot هستم!\nبا من می‌تونی در گروه‌ها عدد حدس بزنی و امتیاز جمع کنی.\n"
        "برای کاربر برتر ماهانه هدیه داریم 🎁\n\n"
        f"کانال تیم: {CHANNEL_ID}\n"
        f"پشتیبان: {SUPPORT}",
        reply_markup=kb
    )

# ====================== GROUP GAME ======================
active_games = {}  # {group_id: {"creator": id, "target": num, "participants": set(), "range": tuple}}

RANGES = [
    (1, 10), (1, 50), (1, 100), (1, 200), (1, 500),
    (1, 1000), (1, 2000), (1, 5000), (1, 10000), (1, 20000)
]

def range_panel():
    kb = InlineKeyboardMarkup(row_width=2)
    for r in RANGES:
        kb.insert(InlineKeyboardmarkup(f"{r[0]}-{r[1]}", callback_data=f"range_{r[0]}_{r[1]}"))
    kb.add(
        InlineKeyboardmarkup("🎯 رنج سفارشی", callback_data="custom_range"),
        InlineKeyboardmarkup("❌ بستن", callback_data="close_panel")
    )
    return kb

@dp.message(Command("start_game"))
async def start_guess_game(message: types.Message, state: FSMContext):
    admins = await get_admin_ids(message.chat.id)
    if message.from_user.id not in admins:
        await message.reply("❌ فقط ادمین‌ها می‌توانند بازی را شروع کنند.")
        return
    await message.reply("🎮 لطفا بازه بازی را انتخاب کنید:", reply_markup=range_panel())

# ====================== CALLBACK HANDLERS ======================
@dp.callback_query(lambda c: c.data.startswith("range_"))
async def range_selected(cb: types.CallbackQuery):
    group_id = cb.message.chat.id
    parts = cb.data.split("_")
    min_val, max_val = int(parts[1]), int(parts[2])
    target = random.randint(min_val, max_val)
    active_games[group_id] = {"creator": cb.from_user.id, "target": target, "participants": set(), "range": (min_val, max_val)}
    await db.execute("INSERT INTO games(group_id, creator_id, target_number, start_time) VALUES($1,$2,$3,$4)",
                     group_id, cb.from_user.id, target, datetime.now())
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardmarkup("🎮 منم بازی", callback_data="join_game"))
    kb.add(InlineKeyboardmarkup("▶️ شروع بازی", callback_data="begin_game"))
    kb.add(InlineKeyboardmarkup("❌ بستن", callback_data="close_game"))
    await cb.message.edit_text(f"🎉 بازی آماده شد! بازه: {min_val}-{max_val}\nشرکت‌کنندگان وارد شوند:", reply_markup=kb)
    await cb.answer()

@dp.callback_query(lambda c: c.data == "custom_range")
async def custom_range_cb(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.edit_text("لطفا رنج دلخواه را به صورت min-max وارد کنید (مثال: 1-1000)")
    await state.set_state(GuessGame.waiting_custom_range)
    await state.update_data(creator=cb.from_user.id)
    await cb.answer()

@dp.message(GuessGame.waiting_custom_range)
async def custom_range_input(message: types.Message, state: FSMContext):
    text = to_english_numbers(message.text)
    match = re.match(r"(\d+)-(\d+)", text)
    if not match:
        await message.reply("❌ فرمت اشتباه است. لطفا به صورت min-max وارد کنید.")
        return
    min_val, max_val = int(match.group(1)), int(match.group(2))
    target = random.randint(min_val, max_val)
    group_id = message.chat.id
    data = await state.get_data()
    active_games[group_id] = {"creator": data["creator"], "target": target, "participants": set(), "range": (min_val, max_val)}
    await db.execute("INSERT INTO games(group_id, creator_id, target_number, start_time) VALUES($1,$2,$3,$4)",
                     group_id, data["creator"], target, datetime.now())
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardmarkup("🎮 منم بازی", callback_data="join_game"))
    kb.add(InlineKeyboardmarkup("▶️ شروع بازی", callback_data="begin_game"))
    kb.add(InlineKeyboardmarkup("❌ بستن", callback_data="close_game"))
    await message.reply(f"🎉 بازی آماده شد! بازه: {min_val}-{max_val}", reply_markup=kb)
    await state.clear()

@dp.callback_query(lambda c: c.data == "close_panel")
async def close_panel_cb(cb: types.CallbackQuery):
    await cb.message.delete()
    await cb.answer("پنل بسته شد ✅")

# ====================== PARTICIPANTS ======================
@dp.callback_query(lambda c: c.data == "join_game")
async def join_game_cb(cb: types.CallbackQuery):
    group_id = cb.message.chat.id
    user_id = cb.from_user.id
    username = cb.from_user.username
    if not await is_channel_member(user_id):
        await cb.answer("❌ لطفا ابتدا عضو کانال شوید.", show_alert=True)
        return
    active_games[group_id]["participants"].add(user_id)
    await add_user(user_id, username)
    await cb.answer("✅ وارد بازی شدی عزیزم!")

@dp.callback_query(lambda c: c.data == "begin_game")
async def begin_game_cb(cb: types.CallbackQuery):
    group_id = cb.message.chat.id
    if cb.from_user.id != active_games[group_id]["creator"]:
        await cb.answer("❌ فقط سازنده بازی می‌تواند شروع کند.", show_alert=True)
        return
    min_val, max_val = active_games[group_id]["range"]
    await cb.message.edit_text(f"🎉 بازی شروع شد! بازه: {min_val}-{max_val}\nعدد را حدس بزنید.")
    await cb.answer()

@dp.callback_query(lambda c: c.data == "close_game")
async def close_game_cb(cb: types.CallbackQuery):
    group_id = cb.message.chat.id
    if cb.from_user.id != active_games[group_id]["creator"]:
        await cb.answer("❌ فقط سازنده بازی می‌تواند ببندد.", show_alert=True)
        return
    del active_games[group_id]
    await cb.message.edit_text("❌ بازی بسته شد.")

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
@dp.message(Command("top_scores"))
async def show_top_scores(message: types.Message):
    rows = await db.fetch("SELECT username, total_score FROM users ORDER BY total_score DESC LIMIT 10")
    text = "🏆 ۱۰ نفر برتر:\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. @{row['username']} - {row['total_score']} امتیاز\n"
    await message.reply(text)

# ====================== DAILY & MONTHLY RESET ======================
async def daily_reset_task():
    while True:
        now = datetime.now()
        next_run = datetime.combine(now.date(), datetime.min.time()) + timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        # ریست روزانه
        await db.execute("UPDATE users SET daily_score = 0")
        # گزارش روزانه
        top_users = await db.fetch("SELECT username, daily_score FROM users ORDER BY daily_score DESC LIMIT 10")
        text = "📊 گزارش روزانه بازی‌ها:\n"
        if top_users:
            for i, row in enumerate(top_users, 1):
                text += f"{i}. @{row['username']} - {row['daily_score']} امتیاز\n"
        else:
            text += "هیچ بازی‌ای انجام نشده است.\n"
        for owner_id in OWNER_IDS:
            try:
                await bot.send_message(owner_id, text)
            except:
                pass

        # ریست ماهانه اگر روز اول ماه باشد
        if now.day == 1:
            top_month = await db.fetchrow("SELECT username, monthly_score FROM users ORDER BY monthly_score DESC LIMIT 1")
            if top_month:
                for owner_id in OWNER_IDS:
                    await bot.send_message(owner_id, f"🏆 کاربر برتر ماه قبل: @{top_month['username']} - {top_month['monthly_score']} امتیاز")
            await db.execute("UPDATE users SET monthly_score = 0")

# ====================== STARTUP ======================
async def main():
    await db.connect()
    await init_tables()
    asyncio.create_task(daily_reset_task())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
