import asyncio
import os
import random
import re
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
import asyncpg

# ========= تنظیمات =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@RHINOSOUL_TM")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@OLDKASEB")
TZ_NAME = os.getenv("TZ", "Asia/Muscat")

if not BOT_TOKEN or not DATABASE_URL or OWNER_ID == 0:
    raise RuntimeError("ENV های BOT_TOKEN, DATABASE_URL, OWNER_ID باید تنظیم شوند.")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
pool: asyncpg.Pool = None
BOT_USERNAME: str | None = None

# ========= دیتابیس =========
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users (
  id BIGINT PRIMARY KEY,
  username TEXT,
  first_name TEXT,
  is_seller BOOLEAN DEFAULT FALSE,
  is_owner BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS groups (
  id BIGINT PRIMARY KEY,
  title TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  charge_units INT DEFAULT 0,
  installed_at TIMESTAMPTZ DEFAULT now()
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

CREATE INDEX IF NOT EXISTS idx_games_group_status ON games(group_id, status);

CREATE TABLE IF NOT EXISTS game_participants (
  id SERIAL PRIMARY KEY,
  game_id INT REFERENCES games(id) ON DELETE CASCADE,
  user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(game_id, user_id)
);

CREATE TABLE IF NOT EXISTS scores (
  id SERIAL PRIMARY KEY,
  group_id BIGINT REFERENCES groups(id) ON DELETE CASCADE,
  user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
  points INT DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(group_id, user_id)
);

CREATE TABLE IF NOT EXISTS wins (
  id SERIAL PRIMARY KEY,
  group_id BIGINT REFERENCES groups(id) ON DELETE CASCADE,
  user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
  game_id INT REFERENCES games(id) ON DELETE CASCADE,
  won_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wins_group_time ON wins(group_id, won_at);
"""

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute(CREATE_SQL)
        await conn.execute(
            "INSERT INTO users (id, is_owner) VALUES ($1, TRUE) ON CONFLICT (id) DO UPDATE SET is_owner=TRUE",
            OWNER_ID
        )

# ========= کمک‌تابع‌ها =========
async def upsert_user(u):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO UPDATE
            SET username=EXCLUDED.username, first_name=EXCLUDED.first_name
        """, u.id, u.username, u.first_name or "")

async def register_group(chat_id: int, title: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO groups (id, title) VALUES ($1, $2)
            ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, is_active=TRUE
        """, chat_id, title)

async def deactivate_group(chat_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE groups SET is_active=FALSE WHERE id=$1", chat_id)

async def count_active_groups() -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) AS c FROM groups WHERE is_active=TRUE")
        return int(row["c"])

async def can_join_new_group() -> bool:
    return (await count_active_groups()) < 50

async def get_charge_units(group_id: int) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT charge_units FROM groups WHERE id=$1", group_id)
        return int(row["charge_units"] or 0) if row else 0

async def set_charge_units(group_id: int, value: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE groups SET charge_units=$1 WHERE id=$2", value, group_id)

async def consume_unit(group_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT charge_units FROM groups WHERE id=$1", group_id)
        if not row or int(row["charge_units"] or 0) <= 0:
            return False
        await conn.execute("UPDATE groups SET charge_units=charge_units-1 WHERE id=$1", group_id)
        return True

async def set_group_range(group_id: int, mn: int, mx: int):
    async with pool.acquire() as conn:
        pending = await conn.fetchrow("""
            SELECT id FROM games WHERE group_id=$1 AND status='pending'
            ORDER BY id DESC LIMIT 1
        """, group_id)
        if pending:
            await conn.execute("UPDATE games SET range_min=$1, range_max=$2 WHERE id=$3", mn, mx, pending["id"])
        else:
            await conn.execute("""
                INSERT INTO games (group_id, range_min, range_max, status)
                VALUES ($1,$2,$3,'pending')
            """, group_id, mn, mx)

async def get_pending_game(group_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM games WHERE group_id=$1 AND status='pending'
            ORDER BY id DESC LIMIT 1
        """, group_id)

async def get_active_game(group_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM games WHERE group_id=$1 AND status='active'
            ORDER BY id DESC LIMIT 1
        """, group_id)

async def create_active_game(group_id: int, creator_id: int, mn: int, mx: int, target: int) -> int:
    async with pool.acquire() as conn:
        rec = await conn.fetchrow("""
            INSERT INTO games (group_id, creator_id, range_min, range_max, target_number, started_at, status)
            VALUES ($1,$2,$3,$4,$5, now(), 'active')
            RETURNING id
        """, group_id, creator_id, mn, mx, target)
        return int(rec["id"])

async def finish_game(game_id: int, winner_id: int | None):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE games SET finished_at=now(), winner_id=$2, status='finished'
            WHERE id=$1
        """, game_id, winner_id)

async def add_points_and_win(group_id: int, user_id: int, game_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO scores (group_id, user_id, points, updated_at)
            VALUES ($1,$2,1,now())
            ON CONFLICT (group_id, user_id) DO UPDATE
            SET points = scores.points + 1,
                updated_at = now()
        """, group_id, user_id)
        await conn.execute("""
            INSERT INTO wins (group_id, user_id, game_id)
            VALUES ($1,$2,$3)
        """, group_id, user_id, game_id)

async def get_top_period(group_id: int, period: str, limit: int = 10):
    # تبدیل TZ به offset ساده: Oman (GST) معمولاً UTC+4
    tz_offset_hours = 4
    now_utc = datetime.now(timezone.utc)
    now = now_utc + timedelta(hours=tz_offset_hours)
    if period == "daily":
        start_local = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)
    elif period == "weekly":
        # شروع هفته را یکشنبه در نظر می‌گیریم (قابل تغییر)
        weekday = now.weekday()  # Mon=0..Sun=6
        # اگر بخواهیم یکشنبه شروع: offset = (weekday+1) % 7
        offset_days = (weekday + 1) % 7
        start_local = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo) - timedelta(days=offset_days)
    elif period == "monthly":
        start_local = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
    else:
        start_local = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)
    start_utc = (start_local - timedelta(hours=tz_offset_hours)).astimezone(timezone.utc)

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT user_id, COUNT(*) AS wins_count
            FROM wins
            WHERE group_id=$1 AND won_at >= $2
            GROUP BY user_id
            ORDER BY wins_count DESC
            LIMIT $3
        """, group_id, start_utc, limit)
        return rows

async def reset_scores(group_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE scores SET points=0 WHERE group_id=$1", group_id)

async def is_owner(user_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT is_owner FROM users WHERE id=$1", user_id)
        return bool(row and row["is_owner"])

async def is_seller(user_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT is_seller FROM users WHERE id=$1", user_id)
        return bool(row and row["is_seller"])

async def is_owner_or_seller(user_id: int) -> bool:
    return (await is_owner(user_id)) or (await is_seller(user_id))

async def set_seller_flag(user_id: int, flag: bool):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (id, is_seller) VALUES ($1,$2)
            ON CONFLICT (id) DO UPDATE SET is_seller=$2
        """, user_id, flag)

async def resolve_user_id(text: str) -> int | None:
    text = text.strip()
    if text.isdigit():
        return int(text)
    if text.startswith("@"):
        # تلاش برای پیدا کردن از DB (باید قبلا تعامل داشته باشد)
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id FROM users WHERE username=$1", text.removeprefix("@"))
            return int(row["id"]) if row else None
    return None

# ========= عضویت اجباری =========
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

# ========= کیبوردها =========
def main_panel():
    buttons = [
        [InlineKeyboardButton(text="🎯 انتخاب رنج", callback_data="range")],
        [InlineKeyboardButton(text="👥 پیوستن به بازی", callback_data="join")],
        [InlineKeyboardButton(text="🎲 شروع بازی", callback_data="start_game")],
        [InlineKeyboardButton(text="🔁 بازی مجدد", callback_data="restart")],
        [InlineKeyboardButton(text="📊 پنل امتیاز", callback_data="open_scores")],
        [InlineKeyboardButton(text="🛠️ افزودن به گروه", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")] if BOT_USERNAME else [],
        [InlineKeyboardButton(text="🆘 ارتباط با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME.removeprefix('@')}")]
    ]
    # حذف خطوط خالی
    buttons = [row for row in buttons if row]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def range_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1–10", callback_data="range_1_10"),
         InlineKeyboardButton(text="1–50", callback_data="range_1_50")],
        [InlineKeyboardButton(text="1–100", callback_data="range_1_100"),
         InlineKeyboardButton(text="سفارشی", callback_data="range_custom")],
    ])

# ========= هندلرهای ورود/خروج گروه =========
@dp.message(F.new_chat_members)
async def on_added(m: Message):
    me = await bot.get_me()
    for u in m.new_chat_members:
        if u.id == me.id:
            if not await can_join_new_group():
                await m.reply("سقف نصب ربات تکمیل است (۵۰ گروه).")
                await bot.leave_chat(m.chat.id)
                return
            await register_group(m.chat.id, m.chat.title or "")
            await m.reply("ربات اضافه شد. برای شروع بنویسید: «حدس عدد»")
            return

@dp.message(F.left_chat_member)
async def on_left(m: Message):
    me = await bot.get_me()
    if m.left_chat_member.id == me.id:
        await deactivate_group(m.chat.id)

# ========= جریان اصلی بازی =========
@dp.message(Command("start"))
async def start(m: Message):
    global BOT_USERNAME
    await upsert_user(m.from_user)
    me = await bot.get_me()
    BOT_USERNAME = me.username
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠️ افزودن به گروه", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton(text="🆘 ارتباط با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME.removeprefix('@')}")]
    ])
    await m.answer("سلام! برای شروع در گروه بنویس: «حدس عدد»", reply_markup=kb)

@dp.message(F.chat.type.in_({"group","supergroup"}) & F.text.contains("حدس عدد"))
async def open_panel(m: Message):
    await upsert_user(m.from_user)
    if not await is_member_required_channel(m.from_user.id):
        await send_join_request(m)
        return
    await m.reply("پنل بازی:", reply_markup=main_panel())

@dp.callback_query(F.data == "range")
async def pick_range(c: CallbackQuery):
    await c.message.edit_text("رنج عدد را انتخاب کنید:", reply_markup=range_kb())

@dp.callback_query(F.data.startswith("range_"))
async def set_range_cb(c: CallbackQuery):
    if c.data == "range_custom":
        await c.message.reply("رنج سفارشی را با فرمت «min-max» بفرستید. مثال: 1-100")
        return
    _, mn, mx = c.data.split("_")
    mn, mx = int(mn), int(mx)
    await set_group_range(c.message.chat.id, mn, mx)
    await c.answer("رنج تنظیم شد.")
    await c.message.reply(f"رنج انتخاب شد: {mn} تا {mx}")

@dp.message(F.chat.type.in_({"group","supergroup"}) & F.text.regexp(r"^\s*\d+\s*-\s*\d+\s*$"))
async def custom_range_from_group(m: Message):
    # اجازه رنج سفارشی با پیام: "min-max"
    if not await is_member_required_channel(m.from_user.id):
        await send_join_request(m)
        return
    s = m.text.strip()
    mn, mx = map(int, re.findall(r"\d+", s))
    if mn >= mx:
        await m.reply("حداقل باید از حداکثر کوچک‌تر باشد.")
        return
    await set_group_range(m.chat.id, mn, mx)
    await m.reply(f"رنج سفارشی ثبت شد: {mn}-{mx}")

@dp.callback_query(F.data == "join")
async def join_game(c: CallbackQuery):
    if not await is_member_required_channel(c.from_user.id):
        await send_join_request(c)
        return
    pending = await get_pending_game(c.message.chat.id)
    if not pending:
        await set_group_range(c.message.chat.id, 1, 10)
        pending = await get_pending_game(c.message.chat.id)
    async with pool.acquire() as conn:
        await upsert_user(c.from_user)
        await conn.execute("""
            INSERT INTO game_participants (game_id, user_id)
            VALUES ($1, $2)
            ON CONFLICT (game_id, user_id) DO NOTHING
        """, pending["id"], c.from_user.id)
    await c.answer("به بازی پیوستید.", show_alert=False)

@dp.callback_query(F.data == "start_game")
async def start_game(c: CallbackQuery):
    if not await is_member_required_channel(c.from_user.id):
        await send_join_request(c)
        return
    units = await get_charge_units(c.message.chat.id)
    if units <= 0:
        await c.answer("گروه شما شارژ ندارد. از مالک/فروشنده بخواهید شارژ کند.", show_alert=True)
        return
    pending = await get_pending_game(c.message.chat.id)
    if not pending or not pending["range_min"] or not pending["range_max"]:
        await set_group_range(c.message.chat.id, 1, 10)
        pending = await get_pending_game(c.message.chat.id)
    mn, mx = int(pending["range_min"]), int(pending["range_max"])
    target = random.randint(mn, mx)
    if not await consume_unit(c.message.chat.id):
        await c.answer("شارژ کافی نیست.", show_alert=True)
        return
    game_id = await create_active_game(c.message.chat.id, c.from_user.id, mn, mx, target)
    await c.message.reply(f"بازی شروع شد! یک عدد بین {mn} تا {mx} حدس بزنید.\nعضویت اجباری: {REQUIRED_CHANNEL}")

@dp.message(F.chat.type.in_({"group","supergroup"}) & F.text.regexp(r"^\d+$"))
async def catch_guess(m: Message):
    game = await get_active_game(m.chat.id)
    if not game:
        return
    if not await is_member_required_channel(m.from_user.id):
        # عضو نیست؛ امتیاز نمی‌گیرد و پیام نادیده گرفته می‌شود
        return
    num = int(m.text.strip())
    if num == int(game["target_number"]):
        await upsert_user(m.from_user)
        await finish_game(int(game["id"]), m.from_user.id)
        await add_points_and_win(m.chat.id, m.from_user.id, int(game["id"]))
        await m.reply(f"تبریک <a href='tg://user?id={m.from_user.id}'>{m.from_user.first_name}</a>! عدد برنده {num} بود. 🎉")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔁 بازی مجدد", callback_data="restart")],
            [InlineKeyboardButton(text="🔒 بستن پنل", callback_data="close_panel")],
        ])
        await m.reply("می‌خوای دوباره بازی کنیم؟", reply_markup=kb)

@dp.callback_query(F.data == "restart")
async def restart_cb(c: CallbackQuery):
    active = await get_active_game(c.message.chat.id)
    if active:
        await c.answer("بازی فعلی هنوز فعال است.", show_alert=True)
        return
    await set_group_range(c.message.chat.id, 1, 10)
    await c.message.reply("بازی آماده‌ست. رنج را انتخاب کنید و شرکت‌کنندگان بپیوندند.", reply_markup=main_panel())

@dp.callback_query(F.data == "close_panel")
async def close_panel(c: CallbackQuery):
    await c.message.edit_text("پنل بسته شد.")

# ========= امتیازها =========
def scores_panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 روزانه", callback_data="score_daily"),
         InlineKeyboardButton(text="📆 هفتگی", callback_data="score_weekly"),
         InlineKeyboardButton(text="🗓️ ماهانه", callback_data="score_monthly")],
        [InlineKeyboardButton(text="♻️ ریست امتیاز", callback_data="score_reset")]
    ])

@dp.callback_query(F.data == "open_scores")
async def open_scores_panel(c: CallbackQuery):
    await c.message.reply("پنل امتیاز:", reply_markup=scores_panel())

@dp.callback_query(F.data.startswith("score_"))
async def handle_scores(c: CallbackQuery):
    kind = c.data.removeprefix("score_")
    if kind in ("daily","weekly","monthly"):
        rows = await get_top_period(c.message.chat.id, kind, limit=10)
        if not rows:
            await c.message.reply("هنوز امتیازی ثبت نشده.")
            return
        lines = []
        for idx, r in enumerate(rows, start=1):
            lines.append(f"{idx}. <a href='tg://user?id={r['user_id']}'>{r['user_id']}</a> — {r['wins_count']} برد")
        await c.message.reply(f"رتبه‌بندی {('روزانه' if kind=='daily' else 'هفتگی' if kind=='weekly' else 'ماهانه')}:\n" + "\n".join(lines))
    elif kind == "reset":
        await reset_scores(c.message.chat.id)
        await c.message.reply("امتیازهای گروه ریست شد.")
    else:
        await c.answer("نامشخص.", show_alert=True)

# ========= شارژ و خروج =========
@dp.message(F.chat.type.in_({"group","supergroup"}) & F.text.lower().startswith("شارژ بازی"))
async def charge_cmd(m: Message):
    if not await is_owner_or_seller(m.from_user.id):
        return
    parts = m.text.split()
    if len(parts) < 3:
        await m.reply("فرمت درست: «شارژ بازی +1» یا «شارژ بازی 0»")
        return
    try:
        value = int(parts[2].replace("+",""))
    except:
        await m.reply("عدد نامعتبر.")
        return
    await register_group(m.chat.id, m.chat.title or "")
    await set_charge_units(m.chat.id, value)
    await m.reply(f"شارژ بازی گروه تنظیم شد: {value}")

@dp.message(F.chat.type.in_({"group","supergroup"}) & F.text == "خروج بازی")
async def leave_group(m: Message):
    if not await is_owner_or_seller(m.from_user.id):
        return
    await m.reply("خدانگهدار 👋")
    await bot.leave_chat(m.chat.id)

# ========= مالک و سودو =========
@dp.message(F.text.startswith("سودو بازی"))
async def set_sudo(m: Message):
    if not await is_owner(m.from_user.id):
        return
    parts = m.text.split(maxsplit=2)
    if len(parts) < 3:
        await m.reply("فرمت: «سودو بازی @یوزرنیم» یا «سودو بازی user_id»")
        return
    target = parts[2].strip()
    user_id = await resolve_user_id(target)
    if not user_id:
        await m.reply("کاربر پیدا نشد. باید قبلاً با ربات تعامل داشته باشد یا user_id بدهید.")
        return
    await set_seller_flag(user_id, True)
    await m.reply(f"کاربر {target} به‌عنوان فروشنده اضافه شد.")

@dp.message(F.text.startswith("حذف سودو بازی"))
async def unset_sudo(m: Message):
    if not await is_owner(m.from_user.id):
        return
    parts = m.text.split(maxsplit=2)
    if len(parts) < 3:
        await m.reply("فرمت: «حذف سودو بازی @یوزرنیم» یا «حذف سودو بازی user_id»")
        return
    target = parts[2].strip()
    user_id = await resolve_user_id(target)
    if not user_id:
        await m.reply("کاربر پیدا نشد.")
        return
    await set_seller_flag(user_id, False)
    await m.reply(f"فروشنده {target} حذف شد.")

# ========= اجرای ربات =========
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
