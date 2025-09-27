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
    ConversationHandler,
)
from telegram.constants import ParseMode
import psycopg2
from PIL import Image, ImageDraw, ImageFont

# --- پیکربندی اصلی ---
OWNER_IDS = [7662192190, 6041119040]
SUPPORT_USERNAME = "OLDKASEB"
FORCED_JOIN_CHANNEL = "@RHINOSOUL_TM"
GROUP_INSTALL_LIMIT = 50
INITIAL_LIVES = 6  # تعداد جان اولیه در بازی حدس کلمه

# --- لیست کلمات و جملات ---
WORD_LIST = ["فضاپیما", "کهکشان", "الگوریتم", "کتابخانه", "دانشگاه", "کامپیوتر", "اینترنت", "برنامه", "نویسی", "هوش", "مصنوعی", "یادگیری", "ماشین", "شبکه", "عصبی", "داده", "کاوی", "پایتون", "جاوا", "اسکریپت", "فناوری", "اطلاعات", "امنیت", "سایبری", "حمله", "ویروس", "بدافزار", "آنتی", "ویروس", "دیوار", "آتش", "رمزنگاری", "پروتکل", "اینترنت", "دامنه", "میزبانی", "وب", "سرور", "کلاینت", "پایگاه", "داده", "رابط", "کاربری", "تجربه", "کاربری", "طراحی", "گرافیک", "انیمیشن", "سه", "بعدی", "واقعیت", "مجازی", "افزوده", "بلاکچین", "ارز", "دیجیتال", "بیتکوین", "اتریوم", "قرارداد", "هوشمند", "متاورس", "اینترنت", "اشیاء", "رباتیک", "خودرو", "خودران", "پهپاد", "سنسور", "پردازش", "تصویر", "سیگنال", "مخابرات", "ماهواره", "فرکانس", "موج", "الکترومغناطیس", "فیزیک", "کوانتوم", "نسبیت", "انیشتین", "نیوتن", "گرانش", "سیاهچاله", "ستاره", "نوترونی", "انفجار", "بزرگ", "کیهان", "شناسی", "اختر", "فیزیک", "شیمی", "آلی", "معدنی", "تجزیه", "بیوشیمی", "ژنتیک", "سلول", "بافت", "ارگان", "متابولیسم", "فتوسنتز", "تنفس", "سلولی", "زیست", "شناسی", "میکروبیولوژی", "باکتری", "قارچ", "ویروس", "پزشکی", "داروسازی", "جراحی", "قلب", "مغز", "اعصاب", "روانشناسی", "جامعه", "شناسی", "اقتصاد", "بازار", "سرمایه", "بورس", "سهام", "تورم", "رکود", "رشد", "اقتصادی", "تولید", "ناخالص", "داخلی", "صادرات", "واردات", "تجارت", "بین", "الملل", "سیاست", "دموکراسی", "دیکتاتوری", "جمهوری", "پادشاهی", "انتخابات", "پارلمان", "دولت", "قوه", "قضائیه", "تاریخ", "باستان", "معاصر", "جنگ", "جهانی", "صلیبی", "رنسانس", "اصلاحات", "دینی", "انقلاب", "صنعتی", "فلسفه", "منطق", "اخلاق", "زیبایی", "شناسی", "افلاطون", "ارسطو", "سقراط", "دکارت", "کانت", "نیچه", "ادبیات", "شعر", "رمان", "داستان", "کوتاه", "نمایشنامه", "حافظ", "سعدی", "فردوسی", "مولانا", "خیام", "شکسپیر", "تولستوی", "داستایوفسکی", "هنر", "نقاشی", "مجسمه", "سازی", "معماری", "موسیقی", "سینما", "تئاتر", "عکاسی"]
TYPING_SENTENCES = ["در یک دهکده کوچک، مردی زندگی می‌کرد که به شجاعت و دانایی مشهور بود.", "فناوری بلاکچین پتانسیل ایجاد تحول در صنایع مختلف را دارد.", "یادگیری یک زبان برنامه نویسی جدید می‌تواند درهای جدیدی به روی شما باز کند.", "کتاب خواندن بهترین راه برای سفر به دنیاهای دیگر بدون ترک کردن خانه است.", "شب‌های پرستاره کویر منظره‌ای فراموش نشدنی را به نمایش می‌گذارند.", "تیم ما برای رسیدن به این موفقیت تلاش‌های شبانه روزی زیادی انجام داد.", "حفظ محیط زیست وظیفه تک تک ما برای نسل‌های آینده است.", "موفقیت در زندگی نیازمند تلاش، پشتکار و کمی شانس است.", "اینترنت اشیاء دنیایی را متصور می‌شود که همه چیز به هم متصل است.", "بزرگترین ماجراجویی که می‌توانی داشته باشی، زندگی کردن رویاهایت است.", "برای حل مسائل پیچیده، گاهی باید از زوایای مختلف به آنها نگاه کرد.", "تاریخ پر از درس‌هایی است که می‌توانیم برای ساختن آینده‌ای بهتر از آنها بیاموزیم.", "هوش مصنوعی به سرعت در حال تغییر چهره جهان ما است.", "یک دوست خوب، گنجی گرانبها در فراز و نشیب‌های زندگی است.", "سفر کردن به نقاط مختلف جهان، دیدگاه انسان را گسترش می‌دهد.", "ورزش منظم کلید اصلی برای داشتن بدنی سالم و روحی شاداب است.", "موسیقی زبان مشترک تمام انسان‌ها در سراسر کره زمین است.", "هیچگاه برای یادگیری و شروع یک مسیر جدید دیر نیست.", "احترام به عقاید دیگران، حتی اگر با آنها مخالف باشیم، نشانه بلوغ است.", "تغییر تنها پدیده ثابت در جهان هستی است؛ باید خود را با آن وفق دهیم.", "صبر و شکیبایی در برابر مشکلات، آنها را در نهایت حل شدنی می‌کند.", "خلاقیت یعنی دیدن چیزی که دیگران نمی‌بینند و انجام کاری که دیگران جراتش را ندارند.", "شادی واقعی در داشتن چیزهای زیاد نیست، بلکه در لذت بردن از چیزهایی است که داریم.", "صداقت و راستگویی سنگ بنای هر رابطه پایدار و موفقی است.", "کهکشان راه شیری تنها یکی از میلیاردها کهکشان موجود در کیهان است.", "برای ساختن یک ربات پیشرفته، به دانش برنامه نویسی و الکترونیک نیاز است.", "امنیت سایبری در دنیای دیجیتال امروز از اهمیت فوق العاده‌ای برخوردار است.", "هرگز قدرت یک ایده خوب را دست کم نگیر، می‌تواند دنیا را تغییر دهد.", "کار گروهی و همکاری می‌تواند منجر به نتایجی شگفت انگیز شود.", "شکست بخشی از مسیر موفقیت است، از آن درس بگیرید و دوباره تلاش کنید."]

# --- تنظیمات لاگ ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- مدیریت دیتابیس ---
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    try: return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def setup_database():
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, first_name VARCHAR(255), username VARCHAR(255), start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW());")
                cur.execute("CREATE TABLE IF NOT EXISTS groups (group_id BIGINT PRIMARY KEY, title VARCHAR(255), member_count INT, owner_mention VARCHAR(255), added_time TIMESTAMP WITH TIME ZONE DEFAULT NOW());")
                cur.execute("CREATE TABLE IF NOT EXISTS start_message (id INT PRIMARY KEY, message_id BIGINT, chat_id BIGINT);")
            conn.commit()
            logger.info("Database setup complete.")
        except Exception as e: logger.error(f"Database setup failed: {e}")
        finally: conn.close()

# --- توابع کمکی ---
async def is_owner(user_id: int) -> bool: return user_id in OWNER_IDS
async def is_group_admin(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if await is_owner(user_id): return True
    admins = await context.bot.get_chat_administrators(chat_id)
    return user_id in {admin.user.id for admin in admins}
def convert_persian_to_english_numbers(text: str) -> str:
    if not text: return ""
    return text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))

# --- مدیریت وضعیت بازی‌ها ---
active_games = {'guess_number': {}, 'dooz': {}, 'hangman': {}, 'typing': {}}

# --- منطق عضویت اجباری ---
async def force_join_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user: return False
    if await is_owner(user.id): return True
    try:
        member = await context.bot.get_chat_member(chat_id=FORCED_JOIN_CHANNEL, user_id=user.id)
        if member.status in ['member', 'administrator', 'creator']: return True
    except Exception as e:
        logger.warning(f"Could not check channel membership for {user.id}: {e}")
    
    keyboard = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{FORCED_JOIN_CHANNEL.lstrip('@')}")]]
    text = f"❗️{user.mention_html()}، برای استفاده از ربات ابتدا باید در کانال ما عضو شوی:\n\n{FORCED_JOIN_CHANNEL}"

    target_chat = update.effective_chat
    if update.callback_query:
        await update.callback_query.answer()
        await target_chat.send_message(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    elif update.message:
        await target_chat.send_message(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return False

# =================================================================
# ======================== GAME LOGIC START =======================
# =================================================================

# --------------------------- GAME: GUESS THE NUMBER (ConversationHandler) ---------------------------
SELECTING_RANGE, GUESSING = range(2)
async def hads_addad_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await force_join_middleware(update, context): return ConversationHandler.END
    chat, user = update.effective_chat, update.effective_user
    if not await is_group_admin(user.id, chat.id, context):
        await update.message.reply_text("❌ این بازی فقط توسط ادمین‌های گروه قابل شروع است.")
        return ConversationHandler.END
    if chat.id in active_games['guess_number']:
        await update.message.reply_text("یک بازی حدس عدد در این گروه فعال است.")
        return ConversationHandler.END
    await update.message.reply_text("بازه بازی را مشخص کنید. (مثال: `1-1000`)", parse_mode=ParseMode.MARKDOWN)
    return SELECTING_RANGE

async def receive_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat = update.effective_chat
    try:
        min_str, max_str = convert_persian_to_english_numbers(update.message.text).split('-')
        min_range, max_range = int(min_str.strip()), int(max_str.strip())
        if min_range >= max_range: raise ValueError
    except:
        await update.message.reply_text("فرمت اشتباه است. لطفا به این صورت وارد کنید: `عدد کوچک-عدد بزرگ`", parse_mode=ParseMode.MARKDOWN)
        return SELECTING_RANGE
    secret_number = random.randint(min_range, max_range)
    active_games['guess_number'][chat.id] = {"number": secret_number}
    await update.message.reply_text(f"🎲 **بازی حدس عدد شروع شد!** 🎲\n\nیک عدد بین **{min_range}** و **{max_range}** انتخاب کرده‌ام.", parse_mode=ParseMode.MARKDOWN)
    return GUESSING

async def handle_guess_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    if chat_id not in active_games['guess_number']: return ConversationHandler.END
    guess = int(convert_persian_to_english_numbers(update.message.text))
    secret_number = active_games['guess_number'][chat_id]['number']
    user = update.effective_user
    if guess < secret_number: await update.message.reply_text("بالاتر ⬆️")
    elif guess > secret_number: await update.message.reply_text("پایین‌تر ⬇️")
    else:
        await update.message.reply_text(f"🎉 **تبریک!** {user.mention_html()} برنده شد! 🎉\n\nعدد صحیح **{secret_number}** بود.", parse_mode=ParseMode.HTML)
        del active_games['guess_number'][chat_id]
        return ConversationHandler.END
    return GUESSING

async def cancel_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat.id in active_games['guess_number']: del active_games['guess_number'][update.effective_chat.id]
    await update.message.reply_text('بازی حدس عدد لغو شد.')
    return ConversationHandler.END

# --------------------------- GAME: DOOZ (TIC-TAC-TOE) ---------------------------
async def dooz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    if update.effective_chat.type == 'private': return await update.message.reply_text("این بازی فقط در گروه‌ها قابل اجراست.")
    
    challenger, challenged_user = update.effective_user, None
    if update.message.reply_to_message:
        challenged_user = update.message.reply_to_message.from_user
        if challenged_user.is_bot: return await update.message.reply_text("شما نمی‌توانید ربات‌ها را به بازی دعوت کنید!")
        if challenged_user.id == challenger.id: return await update.message.reply_text("شما نمی‌توانید خودتان را به بازی دعوت کنید!")
    elif context.args and context.args[0].startswith('@'):
        pass
    else:
        return await update.message.reply_text("برای دعوت، یا روی پیام یک نفر ریپلای کنید یا او را منشن کنید. (`/dooz @username`)")

    if challenged_user:
        challenged_mention = challenged_user.mention_html()
        cb_info = challenged_user.username if challenged_user.username else str(challenged_user.id)
    else:
        cb_info = context.args[0][1:]
        challenged_mention = f"کاربر @{cb_info}"

    text = f"{challenger.mention_html()} {challenged_mention} را به بازی دوز دعوت کرد!"
    keyboard = [[
        InlineKeyboardButton("✅ قبول", callback_data=f"dooz_accept_{challenger.id}_{cb_info}"),
        InlineKeyboardButton("❌ رد", callback_data=f"dooz_decline_{challenger.id}_{cb_info}")
    ]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def dooz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query, user = update.callback_query, update.effective_user
    if not await force_join_middleware(update, context): return
    
    data = query.data.split('_')
    action, p1_id, p2_info = data[1], int(data[2]), data[3]

    if action in ["accept", "decline"]:
        is_correct_user = (user.username == p2_info) or (str(user.id) == p2_info)
        if not is_correct_user: return await query.answer("این دعوت برای شما نیست!", show_alert=True)
        if user.id == p1_id and action == "accept": return await query.answer("شما نمی‌توانید دعوت خودتان را قبول کنید!", show_alert=True)
        
        p1_mention = (await context.bot.get_chat(p1_id)).mention_html()
        if action == "accept":
            chat_id = query.message.chat.id
            if chat_id in active_games['dooz']: return await query.edit_message_text("یک بازی دوز در این گروه فعال است.")
            active_games['dooz'][chat_id] = {"players": {p1_id: "❌", user.id: "⭕️"}, "board": [[" "]*3 for _ in range(3)], "turn": p1_id}
            text = f"بازی شروع شد!\n{p1_mention} (❌) vs {user.mention_html()} (⭕️)\n\nنوبت {p1_mention} است."
            keyboard = [[InlineKeyboardButton(" ", callback_data=f"dooz_move_{r*3+c}_{p1_id}_{user.id}") for c in range(3)] for r in range(3)]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        else: await query.edit_message_text(f"{user.mention_html()} دعوت {p1_mention} را رد کرد.", parse_mode=ParseMode.HTML)

    elif action == "move":
        chat_id, p1_id, p2_id = query.message.chat.id, int(data[3]), int(data[4])
        if chat_id not in active_games['dooz']: return await query.answer("این بازی تمام شده.", show_alert=True)
        
        game = active_games['dooz'][chat_id]
        if user.id not in [p1_id, p2_id]: return await query.answer("شما بازیکن این مسابقه نیستید!", show_alert=True)
        if user.id != game['turn']: return await query.answer("نوبت شما نیست!", show_alert=True)

        row, col = divmod(int(data[2]), 3)
        if game['board'][row][col] != " ": return await query.answer("این خانه پر شده!", show_alert=True)
        
        symbol = game['players'][user.id]
        game['board'][row][col] = symbol
        
        b = game['board']
        win = any(all(c==symbol for c in r) for r in b) or any(all(b[r][c]==symbol for r in range(3)) for c in range(3)) or all(b[i][i]==symbol for i in range(3)) or all(b[i][2-i]==symbol for i in range(3))
        winner = "draw" if all(c!=" " for r in b for c in r) and not win else user.id if win else None
        
        game['turn'] = p2_id if user.id == p1_id else p1_id
        keyboard = [[InlineKeyboardButton(c, callback_data=f"dooz_move_{r*3+i}_{p1_id}_{p2_id}") for i, c in enumerate(row)] for r, row in enumerate(b)]

        if winner:
            text = "بازی مساوی شد!" if winner=="draw" else f"بازی تمام شد! برنده: {user.mention_html()} 🏆"
            del active_games['dooz'][chat_id]
        else:
            text = f"نوبت {(await context.bot.get_chat(game['turn'])).mention_html()} است."
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    await query.answer()

# --------------------------- GAME: HADS KALAME (با جان جداگانه) ---------------------------
async def hads_kalame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    chat_id = update.effective_chat.id
    if chat_id in active_games['hangman']: return await update.message.reply_text("یک بازی حدس کلمه فعال است.")
    word = random.choice(WORD_LIST)
    active_games['hangman'][chat_id] = {"word": word, "display": ["_"] * len(word), "guessed_letters": set(), "players": {}}
    game = active_games['hangman'][chat_id]
    text = f"🕵️‍♂️ **حدس کلمه (رقابتی) شروع شد!**\n\nهر کاربر {INITIAL_LIVES} جان دارد.\nکلمه: `{' '.join(game['display'])}`"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_letter_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, user = update.effective_chat.id, update.effective_user
    if chat_id not in active_games['hangman']: return
    if not await force_join_middleware(update, context): return

    guess = update.message.text.strip()
    game = active_games['hangman'][chat_id]
    
    if user.id not in game['players']: game['players'][user.id] = INITIAL_LIVES
    if game['players'][user.id] == 0: return await update.message.reply_text(f"{user.mention_html()}، شما تمام جان‌های خود را از دست داده‌اید!", parse_mode=ParseMode.HTML)
    if guess in game['guessed_letters']: return

    game['guessed_letters'].add(guess)
    if guess in game['word']:
        for i, letter in enumerate(game['word']):
            if letter == guess: game['display'][i] = letter
        if "_" not in game['display']:
            await update.message.reply_text(f"✅ **{user.mention_html()}** برنده شد! کلمه صحیح `{game['word']}` بود.", parse_mode=ParseMode.MARKDOWN)
            del active_games['hangman'][chat_id]
        else:
            await update.message.reply_text(f"`{' '.join(game['display'])}`", parse_mode=ParseMode.MARKDOWN)
    else:
        game['players'][user.id] -= 1
        lives_left = game['players'][user.id]
        if lives_left > 0:
            await update.message.reply_text(f"اشتباه بود {user.mention_html()}! شما **{lives_left}** جان دیگر دارید.", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"{user.mention_html()} تمام جان‌های خود را از دست داد و از بازی حذف شد.", parse_mode=ParseMode.HTML)
            if all(lives == 0 for lives in game['players'].values()):
                await update.message.reply_text(f"☠️ همه باختید! کلمه صحیح `{game['word']}` بود.", parse_mode=ParseMode.MARKDOWN)
                del active_games['hangman'][chat_id]

# --------------------------- GAME: TYPE SPEED ---------------------------
def create_typing_image(text: str) -> io.BytesIO:
    try: font = ImageFont.truetype("Vazir.ttf", 24)
    except IOError: font = ImageFont.load_default()
    dummy_img, draw = Image.new('RGB', (1, 1)), ImageDraw.Draw(Image.new('RGB', (1, 1)))
    _, _, w, h = draw.textbbox((0, 0), text, font=font)
    img = Image.new('RGB', (w + 40, h + 40), color = (255, 255, 255))
    ImageDraw.Draw(img).text((20,20), text, fill=(0,0,0), font=font, align="right")
    bio = io.BytesIO()
    bio.name = 'image.jpeg'
    img.save(bio, 'JPEG')
    bio.seek(0)
    return bio

async def type_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    chat_id = update.effective_chat.id
    if chat_id in active_games['typing']: return await update.message.reply_text("یک بازی تایپ سرعتی فعال است.")
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
        await update.message.reply_text(f"🏆 {user.mention_html()} برنده شد!\nزمان: **{duration:.2f}** ثانیه", parse_mode=ParseMode.HTML)
        del active_games['typing'][chat_id]

# --------------------------- GAME: GHARCH & ETERAF ---------------------------
async def anonymous_game_starter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    command = update.message.text.split('/')[1]
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
    if 'anon_target_chat' not in user_data: return await update.message.reply_text("لطفا ابتدا از طریق دکمه‌ای که در گروه قرار دارد، بازی را شروع کنید.")
    
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

# --------------------------- PLACEHOLDERS & SETTINGS ---------------------------
async def placeholder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"قابلیت `{update.message.text.split()[0]}` در آینده اضافه خواهد شد.", parse_mode=ParseMode.MARKDOWN)

# =================================================================
# ================= OWNER & CORE COMMANDS START ===================
# =================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if context.args:
        try:
            payload = context.args[0]
            game_type, chat_id_str = payload.split('_')
            if game_type in ["gharch", "eteraf"]:
                context.user_data['anon_target_chat'] = {'id': int(chat_id_str), 'type': game_type}
                prompt = "پیام خود را برای ارسال ناشناس بنویسید..." if game_type == "gharch" else "اعتراف خود را بنویسید..."
                await update.message.reply_text(prompt)
                return
        except (ValueError, IndexError): pass

    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING;", (user.id, user.first_name, user.username))
            conn.commit()
        conn.close()
    
    if not await force_join_middleware(update, context): return

    keyboard = [[InlineKeyboardButton("👤 ارتباط با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME}")], [InlineKeyboardButton("➕ افزودن ربات به گروه", url=f"https://t.me/{(await context.bot.get_me()).username}?startgroup=true")]]
    await update.message.reply_text("سلام! به ربات ما خوش آمدید.", reply_markup=InlineKeyboardMarkup(keyboard))

    report_text = f"✅ کاربر جدید: {user.mention_html()} (ID: `{user.id}`)"
    for owner_id in OWNER_IDS:
        try: await context.bot.send_message(chat_id=owner_id, text=report_text, parse_mode=ParseMode.HTML)
        except: pass

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    help_text = "راهنمای ربات 🎮\n\n/hokm - بازی حکم (بزودی)\n/dooz @user - بازی دوز\n/hads_kalame - حدس کلمه\n/hads_addad - حدس عدد\n/type - تایپ سرعتی\n/gharch - پیام ناشناس\n/eteraf - اعتراف ناشناس"
    await update.message.reply_text(help_text)

# --- دستورات مالک ---
async def set_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    if not update.message.reply_to_message: return await update.message.reply_text("روی یک پیام ریپلای کنید.")
    msg = update.message.reply_to_message
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO start_message (id, message_id, chat_id) VALUES (1, %s, %s) ON CONFLICT (id) DO UPDATE SET message_id = EXCLUDED.message_id, chat_id = EXCLUDED.chat_id;", (msg.message_id, msg.chat_id))
            conn.commit()
        conn.close()
        await update.message.reply_text("✅ پیام خوشامدگویی تنظیم شد.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users;"); user_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM groups;"); group_count = cur.fetchone()[0]
            cur.execute("SELECT SUM(member_count) FROM groups;"); total_members = cur.fetchone()[0] or 0
        stats = f"📊 **آمار ربات**\n\n👤 کاربران: {user_count}\n👥 گروه‌ها: {group_count}\n👨‍👩‍👧‍👦 مجموع اعضا: {total_members}"
        await update.message.reply_text(stats, parse_mode=ParseMode.MARKDOWN)
        conn.close()

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str):
    if not await is_owner(update.effective_user.id): return
    if not update.message.reply_to_message: return await update.message.reply_text("روی یک پیام ریپلای کنید.")
    conn, table, column = get_db_connection(), "users" if target == "users" else "groups", "user_id" if target == "users" else "group_id"
    if not conn: return
    with conn.cursor() as cur: cur.execute(f"SELECT {column} FROM {table};"); targets = cur.fetchall()
    conn.close()
    if not targets: return await update.message.reply_text("هدفی یافت نشد.")
    
    sent, failed = 0, 0
    status_msg = await update.message.reply_text(f"⏳ در حال ارسال به {len(targets)} {target}...")
    for (target_id,) in targets:
        try:
            await context.bot.forward_message(chat_id=target_id, from_chat_id=update.message.reply_to_message.chat.id, message_id=update.message.reply_to_message.message_id)
            sent += 1
        except Exception as e:
            failed += 1
            logger.error(f"Broadcast failed for {target_id}: {e}")
    await status_msg.edit_text(f"🏁 ارسال تمام شد.\n\n✅ موفق: {sent}\n❌ ناموفق: {failed}")

async def fwdusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE): await broadcast_command(update, context, "users")
async def fwdgroups_command(update: Update, context: ContextTypes.DEFAULT_TYPE): await broadcast_command(update, context, "groups")

# --- مدیریت گروه ---
async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result, chat, user = update.chat_member, update.effective_chat, update.effective_user
    if not result: return
    
    is_bot = result.new_chat_member.user.id == context.bot.id
    if not is_bot: return

    if result.new_chat_member.status == 'member' and result.old_chat_member.status != 'member':
        conn = get_db_connection()
        if not conn: return
        with conn.cursor() as cur: cur.execute("SELECT COUNT(*) FROM groups;"); group_count = cur.fetchone()[0]
        
        if group_count >= GROUP_INSTALL_LIMIT:
            await chat.send_message(f"⚠️ ظرفیت نصب این ربات تکمیل شده است! لطفاً با پشتیبانی (@{SUPPORT_USERNAME}) تماس بگیرید.")
            await chat.leave()
            for owner_id in OWNER_IDS: await context.bot.send_message(owner_id, f"🔔 هشدار: سقف نصب ({GROUP_INSTALL_LIMIT}) تکمیل شد. ربات از گروه `{chat.title}` خارج شد.", parse_mode=ParseMode.MARKDOWN)
            return
        
        member_count = await chat.get_member_count()
        with conn.cursor() as cur: cur.execute("INSERT INTO groups (group_id, title, member_count) VALUES (%s, %s, %s) ON CONFLICT (group_id) DO NOTHING;", (chat.id, chat.title, member_count))
        conn.commit()
        conn.close()
        
        await chat.send_message("سلام! 👋 من با موفقیت نصب شدم.\nبرای مشاهده لیست بازی‌ها از دستور /help استفاده کنید.")
        report = f"➕ **ربات به گروه جدید اضافه شد:**\n\n🌐 نام: {chat.title}\n🆔: `{chat.id}`\n👥 اعضا: {member_count}\n\n👤 توسط: {user.mention_html()} (ID: `{user.id}`)"
        for owner_id in OWNER_IDS: await context.bot.send_message(owner_id, report, parse_mode=ParseMode.HTML)

    elif result.new_chat_member.status == 'left':
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur: cur.execute("DELETE FROM groups WHERE group_id = %s;", (chat.id,))
            conn.commit()
            conn.close()
        report = f"❌ **ربات از گروه زیر اخراج شد:**\n\n🌐 نام: {chat.title}\n🆔: `{chat.id}`"
        for owner_id in OWNER_IDS: await context.bot.send_message(owner_id, report, parse_mode=ParseMode.MARKDOWN)

# =================================================================
# ======================== MAIN FUNCTION ==========================
# =================================================================

def main() -> None:
    setup_database()
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN environment variable not set.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation Handler for Guess the Number
    guess_number_conv = ConversationHandler(
        entry_points=[CommandHandler("hads_addad", hads_addad_command)],
        states={
            SELECTING_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_range)],
            GUESSING: [MessageHandler(filters.Regex(r'^[\d۰-۹]+$'), handle_guess_conversation)],
        },
        fallbacks=[CommandHandler('cancel', cancel_game)],
        per_user=False, per_chat=True, per_message=False
    )
    application.add_handler(guess_number_conv)

    # Core Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # Game Start Commands
    application.add_handler(CommandHandler("dooz", dooz_command))
    application.add_handler(CommandHandler("hads_kalame", hads_kalame_command))
    application.add_handler(CommandHandler("type", type_command))
    application.add_handler(CommandHandler("gharch", anonymous_game_starter))
    application.add_handler(CommandHandler("eteraf", anonymous_game_starter))
    
    # Placeholders
    application.add_handler(CommandHandler("hokm", placeholder_command))
    application.add_handler(CommandHandler("top", placeholder_command))
    application.add_handler(CommandHandler("settings", placeholder_command))

    # Owner Commands
    application.add_handler(CommandHandler("setstart", set_start_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("fwdusers", fwdusers_command))
    application.add_handler(CommandHandler("fwdgroups", fwdgroups_command))

    # Callback Handlers
    application.add_handler(CallbackQueryHandler(dooz_callback, pattern=r'^dooz_'))

    # Message Handlers for Games (Order is important)
    application.add_handler(MessageHandler(filters.Regex(r'^[آ-ی]$') & filters.ChatType.GROUPS, handle_letter_guess))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_anonymous_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_typing_attempt))
    
    # Chat Member Handler
    application.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    
    logger.info("Bot is starting with FINAL logic...")
    application.run_polling()

if __name__ == "__main__":
    main()
