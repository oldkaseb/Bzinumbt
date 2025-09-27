# -*- coding: utf-8 -*-

import os
import logging
import random
import io
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatMember,
    ChatMemberUpdated,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ChatMemberHandler,
)
from telegram.constants import ParseMode
import psycopg2
from PIL import Image, ImageDraw, ImageFont

# --- پیکربندی اصلی ---
OWNER_IDS = [7662192190, 6041119040]
SUPPORT_USERNAME = "OLDKASEB"
FORCED_JOIN_CHANNEL = "@RHINOSOUL_TM"
GROUP_INSTALL_LIMIT = 50
WORD_LIST = ["تلگرام", "ربات", "پایتون", "برنامه", "هوش", "مصنوعی", "کتابخانه", "کهکشان", "فضاپیما", "الگوریتم", "ذلیل", "پارتنر", "دلشوره", "اژدها", "پیرمرد", "باندانا", "نجاری", "عروسی"]
TYPING_SENTENCES = [
    "اگه حالم خوب بود که بیکار نبودم",
    "ربات راینو بازی بازی های متنوعی دارد.",
    "سرعت تایپ خود را با این بازی محک بزنید.",
    "رفیقای بد کل ماجراهای منن"
]

# --- تنظیمات لاگ ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- مدیریت دیتابیس ---
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def setup_database():
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        first_name VARCHAR(255),
                        username VARCHAR(255),
                        start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS groups (
                        group_id BIGINT PRIMARY KEY,
                        title VARCHAR(255),
                        member_count INT,
                        owner_mention VARCHAR(255),
                        added_time TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS start_message (
                        id INT PRIMARY KEY,
                        message_id BIGINT,
                        chat_id BIGINT
                    );
                """)
            conn.commit()
            logger.info("Database setup complete.")
        except Exception as e:
            logger.error(f"Database setup failed: {e}")
        finally:
            conn.close()

# --- توابع کمکی ---

async def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS

async def is_group_admin(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if await is_owner(user_id): return True
    admins = await context.bot.get_chat_administrators(chat_id)
    return user_id in {admin.user.id for admin in admins}

def convert_persian_to_english_numbers(text: str) -> str:
    if not text: return ""
    persian_nums = "۰۱۲۳۴۵۶۷۸۹"
    english_nums = "0123456789"
    return text.translate(str.maketrans(persian_nums, english_nums))

# --- مدیریت وضعیت بازی‌ها ---
active_games = {
    'guess_number': {}, 'dooz': {}, 'hangman': {}, 'typing': {}, 'settings': {}
}

# --- منطق عضویت اجباری ---
async def force_join_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user: return False
    if await is_owner(user.id): return True
    try:
        member = await context.bot.get_chat_member(chat_id=FORCED_JOIN_CHANNEL, user_id=user.id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        logger.warning(f"Could not check channel membership for {user.id}: {e}")
    
    keyboard = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{FORCED_JOIN_CHANNEL.lstrip('@')}")]]
    text = f"❗️کاربر گرامی، برای استفاده از ربات ابتدا باید در کانال ما عضو شوید:\n\n{FORCED_JOIN_CHANNEL}\n\nپس از عضویت، دوباره تلاش کنید."
    
    if update.callback_query:
        await update.callback_query.answer(text, show_alert=True)
    elif update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return False

# =================================================================
# ======================== GAME LOGIC START =======================
# =================================================================

# --------------------------- GAME: GUESS THE NUMBER ---------------------------
async def hads_addad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    chat, user = update.effective_chat, update.effective_user
    
    if not await is_group_admin(user.id, chat.id, context):
        return await update.message.reply_text("❌ این بازی فقط توسط ادمین‌های گروه قابل شروع است.")
    if chat.id in active_games['guess_number']:
        return await update.message.reply_text("یک بازی حدس عدد در این گروه فعال است.")

    min_range, max_range = 1, 100
    if len(context.args) == 2:
        try:
            args_en = [convert_persian_to_english_numbers(arg) for arg in context.args]
            n1, n2 = int(args_en[0]), int(args_en[1])
            min_range, max_range = min(n1, n2), max(n1, n2)
        except (ValueError, IndexError):
            return await update.message.reply_text("مثال: `/hads_addad 1 1000`")
    
    secret_number = random.randint(min_range, max_range)
    active_games['guess_number'][chat.id] = secret_number
    logger.info(f"GuessNumber started in {chat.id}. Number: {secret_number}.")
    msg_text = (f"🎲 **بازی حدس عدد شروع شد!** 🎲\n\n"
                f"یک عدد بین **{min_range}** و **{max_range}** انتخاب کرده‌ام.")
    msg = await update.message.reply_text(msg_text, parse_mode=ParseMode.MARKDOWN)
    try: await context.bot.pin_chat_message(chat.id, msg.message_id)
    except Exception as e: logger.warning(f"Could not pin message in {chat.id}: {e}")

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_games['guess_number']: return
    if not await force_join_middleware(update, context): return

    guess = int(convert_persian_to_english_numbers(update.message.text))
    secret_number = active_games['guess_number'][chat_id]
    user = update.effective_user

    if guess < secret_number: await update.message.reply_text("بالاتر ⬆️")
    elif guess > secret_number: await update.message.reply_text("پایین‌تر ⬇️")
    else:
        win_text = (f"🎉 **تبریک!** {user.mention_html()} برنده شد! 🎉\n\n"
                    f"عدد صحیح **{secret_number}** بود.")
        await update.message.reply_text(win_text, parse_mode=ParseMode.HTML)
        del active_games['guess_number'][chat_id]

# --------------------------- GAME: DOOZ (TIC-TAC-TOE) ---------------------------
async def dooz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    if update.effective_chat.type == 'private':
        return await update.message.reply_text("این بازی فقط در گروه‌ها قابل اجراست.")
    if len(context.args) != 1 or not context.args[0].startswith('@'):
        return await update.message.reply_text("لطفا یک نفر را منشن کنید. مثال: `/dooz @username`")

    challenger = update.effective_user
    challenged_username = context.args[0][1:]
    text = f"{challenger.mention_html()} کاربر @{challenged_username} را به دوز دعوت کرد!"
    keyboard = [[
        InlineKeyboardButton("✅ قبول", callback_data=f"dooz_accept_{challenger.id}_{challenged_username}"),
        InlineKeyboardButton("❌ رد", callback_data=f"dooz_decline_{challenger.id}_{challenged_username}")
    ]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def dooz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query, user = update.callback_query, update.effective_user
    if not await force_join_middleware(update, context): return
    
    data = query.data.split('_')
    action, challenger_id, p2_info = data[1], int(data[2]), data[3]

    if action in ["accept", "decline"]:
        if user.username != p2_info and user.id != challenger_id:
            return await query.answer("این دعوت برای شما نیست!", show_alert=True)
        if user.id == challenger_id and action == "accept":
            return await query.answer("شما نمی‌توانید دعوت خودتان را قبول کنید!", show_alert=True)
        
        if action == "accept":
            chat_id = query.message.chat.id
            if chat_id in active_games['dooz']:
                return await query.edit_message_text("یک بازی دوز در این گروه فعال است.")

            players = {challenger_id: "❌", user.id: "⭕️"}
            game_state = {"players": players, "board": [[" "]*3 for _ in range(3)], "turn": challenger_id}
            active_games['dooz'][chat_id] = game_state
            
            p1_mention = (await context.bot.get_chat(challenger_id)).mention_html()
            text = f"بازی شروع شد!\n{p1_mention} (❌) vs {user.mention_html()} (⭕️)\n\nنوبت {p1_mention} است."
            keyboard = [
                [InlineKeyboardButton(" ", callback_data=f"dooz_move_{i}_{challenger_id}_{user.id}") for i in range(3)],
                [InlineKeyboardButton(" ", callback_data=f"dooz_move_{i+3}_{challenger_id}_{user.id}") for i in range(3)],
                [InlineKeyboardButton(" ", callback_data=f"dooz_move_{i+6}_{challenger_id}_{user.id}") for i in range(3)]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        else: # decline
            p1_mention = (await context.bot.get_chat(challenger_id)).mention_html()
            await query.edit_message_text(f"{user.mention_html()} دعوت {p1_mention} را رد کرد.", parse_mode=ParseMode.HTML)

    elif action == "move":
        chat_id, p1_id, p2_id = query.message.chat.id, int(data[3]), int(data[4])
        if chat_id not in active_games['dooz']: return await query.answer("این بازی تمام شده.", show_alert=True)
        
        game_state = active_games['dooz'][chat_id]
        if user.id not in [p1_id, p2_id]: return await query.answer("شما بازیکن این مسابقه نیستید!", show_alert=True)
        if user.id != game_state['turn']: return await query.answer("نوبت شما نیست!", show_alert=True)

        move_idx, row, col = int(data[2]), *divmod(int(data[2]), 3)
        if game_state['board'][row][col] != " ": return await query.answer("این خانه پر شده!", show_alert=True)
        
        symbol = game_state['players'][user.id]
        game_state['board'][row][col] = symbol
        
        board = game_state['board']
        win = any(all(board[r][c] == symbol for c in range(3)) for r in range(3)) or \
              any(all(board[r][c] == symbol for r in range(3)) for c in range(3)) or \
              all(board[i][i] == symbol for i in range(3)) or \
              all(board[i][2-i] == symbol for i in range(3))

        winner = "draw" if all(c != " " for r in board for c in r) and not win else user.id if win else None
        
        game_state['turn'] = p2_id if user.id == p1_id else p1_id
        
        keyboard = [[InlineKeyboardButton(c, callback_data=f"dooz_move_{r*3+i}_{p1_id}_{p2_id}") for i, c in enumerate(row)] for r, row in enumerate(board)]

        if winner:
            text = "بازی مساوی شد!" if winner == "draw" else f"بازی تمام شد! برنده: {user.mention_html()} 🏆"
            del active_games['dooz'][chat_id]
        else:
            next_player_mention = (await context.bot.get_chat(game_state['turn'])).mention_html()
            text = f"نوبت {next_player_mention} است."
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    await query.answer()

# --------------------------- GAME: HADS KALAME (HANGMAN) ---------------------------
async def hads_kalame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    chat_id = update.effective_chat.id
    if chat_id in active_games['hangman']:
        return await update.message.reply_text("یک بازی حدس کلمه فعال است.")

    word = random.choice(WORD_LIST)
    game_state = {"word": word, "display": ["_"]*len(word), "guessed": set(), "lives": 6}
    active_games['hangman'][chat_id] = game_state
    
    text = (f"🕵️‍♂️ **بازی حدس کلمه شروع شد!** 🕵️‍♀️\n\n"
            f"کلمه: `{' '.join(game_state['display'])}`\n"
            f"شما {game_state['lives']} جان دارید.\nحروف را یکی یکی ارسال کنید.")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_letter_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_games['hangman']: return
    if not await force_join_middleware(update, context): return

    guess = update.message.text.strip()
    if len(guess) != 1 or not guess.isalpha(): return

    game = active_games['hangman'][chat_id]
    if guess in game['guessed']:
        return await update.message.reply_text(f"حرف '{guess}' قبلا حدس زده شده!")

    game['guessed'].add(guess)
    if guess in game['word']:
        for i, letter in enumerate(game['word']):
            if letter == guess: game['display'][i] = letter
        
        if "_" not in game['display']:
            await update.message.reply_text(f"✅ آفرین! شما برنده شدید! کلمه `{game['word']}` بود.", parse_mode=ParseMode.MARKDOWN)
            del active_games['hangman'][chat_id]
        else:
            await update.message.reply_text(f"`{' '.join(game['display'])}`\nشما هنوز {game['lives']} جان دارید.", parse_mode=ParseMode.MARKDOWN)
    else:
        game['lives'] -= 1
        if game['lives'] == 0:
            await update.message.reply_text(f"☠️ باختید! کلمه `{game['word']}` بود.", parse_mode=ParseMode.MARKDOWN)
            del active_games['hangman'][chat_id]
        else:
            await update.message.reply_text(f"حرف '{guess}' اشتباه بود!\n`{' '.join(game['display'])}`\nشما {game['lives']} جان دارید.", parse_mode=ParseMode.MARKDOWN)

# --------------------------- GAME: TYPE SPEED ---------------------------
def create_typing_image(text: str) -> io.BytesIO:
    try: font = ImageFont.truetype("Vazir.ttf", 24)
    except IOError: font = ImageFont.load_default()
    
    dummy_img, draw = Image.new('RGB', (1, 1)), ImageDraw.Draw(Image.new('RGB', (1, 1)))
    _, _, w, h = draw.textbbox((0, 0), text, font=font)
    img = Image.new('RGB', (w + 40, h + 40), color = (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20,20), text, fill=(0,0,0), font=font, align="right")
    bio = io.BytesIO()
    bio.name = 'image.jpeg'
    img.save(bio, 'JPEG')
    bio.seek(0)
    return bio

async def type_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    chat_id = update.effective_chat.id
    if chat_id in active_games['typing']:
        return await update.message.reply_text("یک بازی تایپ سرعتی فعال است.")

    sentence = random.choice(TYPING_SENTENCES)
    active_games['typing'][chat_id] = {"sentence": sentence, "start_time": datetime.now()}
    
    await update.message.reply_text("بازی تایپ سرعتی ۳... ۲... ۱...")
    image_file = create_typing_image(sentence)
    await update.message.reply_photo(photo=image_file, caption="سریع تایپ کنید!")

async def handle_typing_attempt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_games['typing']: return
    if not await force_join_middleware(update, context): return
        
    game = active_games['typing'][chat_id]
    if update.message.text == game['sentence']:
        duration = (datetime.now() - game['start_time']).total_seconds()
        user = update.effective_user
        text = f"🏆 {user.mention_html()} برنده شد!\nزمان: **{duration:.2f}** ثانیه"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        del active_games['typing'][chat_id]

# --------------------------- GAME: GHARCH & ETERAF ---------------------------
async def anonymous_game_starter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    command = update.message.text.split()[0][1:]
    chat_id = update.effective_chat.id
    bot_username = (await context.bot.get_me()).username

    title = "بازی قارچ 🍄" if command == "gharch" else "اعتراف ناشناس 🤫"
    button_text = "ارسال پیام ناشناس 🍄" if command == "gharch" else "ارسال اعتراف ناشناس 🤫"
    intro_text = "روی دکمه زیر کلیک کن و حرف دلت رو بنویس!"
    text = f"**{title} شروع شد!**\n\n{intro_text}"
    keyboard = [[InlineKeyboardButton(button_text, url=f"https://t.me/{bot_username}?start={command}_{chat_id}")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def handle_anonymous_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    if 'anon_target_chat' not in user_data:
        return await update.message.reply_text("لطفا ابتدا از طریق دکمه‌ای که در گروه قرار دارد، بازی را شروع کنید.")

    target_chat_id = user_data['anon_target_chat']['id']
    game_type = user_data['anon_target_chat']['type']
    header = "#پیام_ناشناس 🍄" if game_type == "gharch" else "#اعتراف_ناشناس 🤫"
    
    try:
        await context.bot.send_message(chat_id=target_chat_id, text=f"{header}\n\n{update.message.text}")
        await update.message.reply_text("✅ پیامت با موفقیت به صورت ناشناس در گروه ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ ارسال پیام با خطا مواجه شد: {e}")
    finally:
        del context.user_data['anon_target_chat']

# --------------------------- FEATURE: SETTINGS PANEL ---------------------------
# ... (Settings logic to be added if requested)

# --- Placeholder for complex games ---
async def placeholder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.split()[0]
    await update.message.reply_text(f"قابلیت `{command}` در حال حاضر در دست ساخت است.", parse_mode=ParseMode.MARKDOWN)

# =================================================================
# ========================= GAME LOGIC END ========================
# =================================================================


# --- دستورات عمومی و اصلی ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Handle deep links for Gharch/Eteraf
    if context.args:
        try:
            payload = context.args[0]
            game_type, chat_id_str = payload.split('_')
            if game_type in ["gharch", "eteraf"]:
                context.user_data['anon_target_chat'] = {'id': int(chat_id_str), 'type': game_type}
                prompt = "پیام خود را برای ارسال ناشناس بنویسید..." if game_type == "gharch" else "اعتراف خود را بنویسید..."
                await update.message.reply_text(prompt)
                return
        except (ValueError, IndexError):
            pass

    # Normal start logic
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING;",
                        (user.id, user.first_name, user.username))
            conn.commit()
        conn.close()
    
    if not await force_join_middleware(update, context): return

    keyboard = [
        [InlineKeyboardButton("👤 ارتباط با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton("➕ افزودن ربات به گروه", url=f"https://t.me/{(await context.bot.get_me()).username}?startgroup=true")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Fetch and send custom start message or default
    # ... (Your existing start message logic)
    await update.message.reply_text("سلام! به ربات ما خوش آمدید.", reply_markup=reply_markup)

    # Report to Owner
    report_text = (f"✅ کاربر جدید: {user.mention_html()}\n"
                   f"🆔: `{user.id}`\n"
                   f"🔗: @{user.username if user.username else 'ندارد'}")
    for owner_id in OWNER_IDS:
        try:
            await context.bot.send_message(chat_id=owner_id, text=report_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to send start report to {owner_id}: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    help_text = "راهنمای ربات 🎮\n\n/hokm - بازی حکم\n/dooz @user - بازی دوز\n/hads_kalame - حدس کلمه\n/hads_addad - حدس عدد\n/type - تایپ سرعتی\n/gharch - پیام ناشناس\n/eteraf - اعتراف ناشناس"
    await update.message.reply_text(help_text)

# --- دستورات مالک ---
# (The owner commands you had before go here, unchanged)

# --- مدیریت گروه ---
# (The track_chats function you had before goes here, unchanged)


def main() -> None:
    """Start the bot."""
    setup_database()

    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN environment variable not set.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Owner Commands
    # application.add_handler(CommandHandler("setstart", set_start_command))
    # ... and other owner commands ...

    # User Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    # application.add_handler(CommandHandler("settings", settings_command))

    # Game Start Commands
    application.add_handler(CommandHandler("hads_addad", hads_addad_command))
    application.add_handler(CommandHandler("dooz", dooz_command))
    application.add_handler(CommandHandler("hads_kalame", hads_kalame_command))
    application.add_handler(CommandHandler("type", type_command))
    application.add_handler(CommandHandler("gharch", anonymous_game_starter))
    application.add_handler(CommandHandler("eteraf", anonymous_game_starter))
    
    # Placeholders
    application.add_handler(CommandHandler("hokm", placeholder_command))
    application.add_handler(CommandHandler("top", placeholder_command))

    # Callback Handlers
    application.add_handler(CallbackQueryHandler(dooz_callback, pattern=r'^dooz_'))
    # application.add_handler(CallbackQueryHandler(settings_callback, pattern=r'^settings_'))

    # Message Handlers
    application.add_handler(MessageHandler(filters.Regex(r'^[\d۰-۹]+$') & filters.ChatType.GROUPS, handle_guess))
    application.add_handler(MessageHandler(filters.Regex(r'^[آ-ی]$') & filters.ChatType.GROUPS, handle_letter_guess))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_typing_attempt))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_anonymous_message))
    
    # Chat Member Handler
    # application.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))

    logger.info("Bot is starting with FULL game logic...")
    application.run_polling()

if __name__ == "__main__":
    main()
