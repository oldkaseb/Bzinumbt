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
import arabic_reshaper
from bidi.algorithm import get_display

# --- پیکربندی اصلی ---
OWNER_IDS = [7662192190, 6041119040]
SUPPORT_USERNAME = "OLDKASEB"
FORCED_JOIN_CHANNEL = "@RHINOSOUL_TM"
GROUP_INSTALL_LIMIT = 50
INITIAL_LIVES = 6
# --- تعریف حالت‌های مکالعه برای بازی قارچ ---
ASKING_GOD_USERNAME, CONFIRMING_GOD = range(2)
# --- لیست کلمات و جملات ---
WORD_LIST = ["فضاپیما", "کهکشان", "الگوریتم", "کتابخانه", "دانشگاه", "کامپیوتر", "اینترنت", "برنامه", "نویسی", "هوش", "مصنوعی", "یادگیری", "ماشین", "شبکه", "عصبی", "داده", "کاوی", "پایتون", "جاوا", "اسکریپت", "فناوری", "اطلاعات", "امنیت", "سایبری", "حمله", "ویروس", "بدافزار", "آنتی", "ویروس", "دیوار", "آتش", "رمزنگاری", "پروتکل", "اینترنت", "دامنه", "میزبانی", "وب", "سرور", "کلاینت", "پایگاه", "داده", "رابط", "کاربری", "تجربه", "کاربری", "طراحی", "گرافیک", "انیمیشن", "سه", "بعدی", "واقعیت", "مجازی", "افزوده", "بلاکچین", "ارز", "دیجیتال", "بیتکوین", "اتریوم", "قرارداد", "هوشمند", "متاورس", "اینترنت", "اشیاء", "رباتیک", "خودرو", "خودران", "پهپاد", "سنسور", "پردازش", "تصویر", "سیگنال", "مخابرات", "ماهواره", "فرکانس", "موج", "الکترومغناطیس", "فیزیک", "کوانتوم", "نسبیت", "انیشتین", "نیوتن", "گرانش", "سیاهچاله", "ستاره", "نوترونی", "انفجار", "بزرگ", "کیهان", "شناسی", "اختر", "فیزیک", "شیمی", "آلی", "معدنی", "تجزیه", "بیوشیمی", "ژنتیک", "سلول", "بافت", "ارگان", "متابولیسم", "فتوسنتز", "تنفس", "سلولی", "زیست", "شناسی", "میکروبیولوژی", "باکتری", "قارچ", "ویروس", "پزشکی", "داروسازی", "جراحی", "قلب", "مغز", "اعصاب", "روانشناسی", "جامعه", "شناسی", "اقتصاد", "بازار", "سرمایه", "بورس", "سهام", "تورم", "رکود", "رشد", "اقتصادی", "تولید", "ناخالص", "داخلی", "صادرات", "واردات", "تجارت", "بین", "ملل", "سیاست", "دموکراسی", "دیکتاتوری", "جمهوری", "پادشاهی", "انتخابات", "پارلمان", "دولت", "قوه", "قضائیه", "تاریخ", "باستان", "معاصر", "جنگ", "جهانی", "صلیبی", "رنسانس", "اصلاحات", "دینی", "انقلاب", "صنعتی", "فلسفه", "منطق", "اخلاق", "زیبایی", "شناسی", "افلاطون", "ارسطو", "سقراط", "دکارت", "کانت", "نیچه", "ادبیات", "شعر", "رمان", "داستان", "کوتاه", "نمایشنامه", "حافظ", "سعدی", "فردوسی", "مولانا", "خیام", "شکسپیر", "تولستوی", "داستایوفسکی", "هنر", "نقاشی", "مجسمه", "سازی", "معماری", "موسیقی", "سینما", "تئاتر", "عکاسی"]
TYPING_SENTENCES = ["در یک دهکده کوچک مردی زندگی میکرد که به شجاعت و دانایی مشهور بود", "فناوری بلاکچین پتانسیل ایجاد تحول در صنایع مختلف را دارد", "یادگیری یک زبان برنامه نویسی جدید میتواند درهای جدیدی به روی شما باز کند", "کتاب خواندن بهترین راه برای سفر به دنیاهای دیگر بدون ترک کردن خانه است", "شب های پرستاره کویر منظره ای فراموش نشدنی را به نمایش میگذارند", "تیم ما برای رسیدن به این موفقیت تلاش های شبانه روزی زیادی انجام داد", "حفظ محیط زیست وظیفه تک تک ما برای نسل های آینده است", "موفقیت در زندگی نیازمند تلاش پشتکار و کمی شانس است", "اینترنت اشیاء دنیایی را متصور میشود که همه چیز به هم متصل است", "بزرگترین ماجراجویی که میتوانی داشته باشی زندگی کردن رویاهایت است", "برای حل مسائل پیچیده گاهی باید از زوایای مختلف به آنها نگاه کرد", "تاریخ پر از درس هایی است که می‌توانیم برای ساختن آینده ای بهتر از آنها بیاموزیم", "هوش مصنوعی به سرعت در حال تغییر چهره جهان ما است", "یک دوست خوب گنجی گرانبها در فراز و نشیب های زندگی است", "سفر کردن به نقاط مختلف جهان دیدگاه انسان را گسترش میدهد", "ورزش منظم کلید اصلی برای داشتن بدنی سالم و روحی شاداب است", "موسیقی زبان مشترک تمام انسان ها در سراسر کره زمین است", "هیچگاه برای یادگیری و شروع یک مسیر جدید دیر نیست", "احترام به عقاید دیگران حتی اگر با آنها مخالف باشیم نشانه بلوغ است", "تغییر تنها پدیده ثابت در جهان هستی است باید خود را با آن وفق دهیم", "صبر و شکیبایی در برابر مشکلات آنها را در نهایت حل شدنی میکند", "خلاقیت یعنی دیدن چیزی که دیگران نمیبینند و انجام کاری که دیگران جراتش را ندارند", "شادی واقعی در داشتن چیزهای زیاد نیست بلکه در لذت بردن از چیزهایی است که داریم", "صداقت و راستگویی سنگ بنای هر رابطه پایدار و موفقی است", "کهکشان راه شیری تنها یکی از میلیاردها کهکشان موجود در کیهان است", "برای ساختن یک ربات پیشرفته به دانش برنامه نویسی و الکترونیک نیاز است", "امنیت سایبری در دنیای دیجیتال امروز از اهمیت فوق العاده ای برخوردار است", "هرگز قدرت یک ایده خوب را دست کم نگیر میتواند دنیا را تغییر دهد", "کار گروهی و همکاری می‌تواند منجر به نتایجی شگفت انگیز شود", "شکست بخشی از مسیر موفقیت است از آن درس بگیرید و دوباره تلاش کنید"]

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
                cur.execute("CREATE TABLE IF NOT EXISTS groups (group_id BIGINT PRIMARY KEY, title VARCHAR(255), member_count INT, added_time TIMESTAMP WITH TIME ZONE DEFAULT NOW());")
                cur.execute("CREATE TABLE IF NOT EXISTS start_message (id INT PRIMARY KEY, message_id BIGINT, chat_id BIGINT);")
                cur.execute("CREATE TABLE IF NOT EXISTS banned_users (user_id BIGINT PRIMARY KEY);")
                cur.execute("CREATE TABLE IF NOT EXISTS banned_groups (group_id BIGINT PRIMARY KEY);")
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
active_games = {'guess_number': {}, 'dooz': {}, 'hangman': {}, 'typing': {}, 'hokm': {}}

# --- منطق عضویت اجباری و بن ---
async def pre_command_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    if not user: return False

    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM banned_users WHERE user_id = %s;", (user.id,))
            if cur.fetchone(): return False
            if chat.type != 'private':
                cur.execute("SELECT 1 FROM banned_groups WHERE group_id = %s;", (chat.id,))
                if cur.fetchone(): 
                    try: await context.bot.leave_chat(chat.id)
                    except: pass
                    return False
        conn.close()
    
    return await force_join_middleware(update, context)

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

# --------------------------- GAME: HOKM (نسخه نهایی) ---------------------------
# ======================= GAME: HOKM (نسخه نهایی با دکمه‌های شیشه‌ای) =======================

# --- توابع کمکی برای بازی حکم ---
def create_deck():
    """یک دسته کارت مرتب شده ۵۲تایی ایجاد و آن را بُر می‌زند."""
    suits = ['S', 'H', 'D', 'C']  # Spades, Hearts, Diamonds, Clubs
    ranks = list(range(2, 15))  # 2-10, J(11), Q(12), K(13), A(14)
    deck = [f"{s}{r}" for s in suits for r in ranks]
    random.shuffle(deck)
    return deck

def card_to_persian(card):
    """کارت را به فرمت فارسی با ایموجی تبدیل می‌کند."""
    if not card: return "🃏"
    suits = {'S': '♠️', 'H': '♥️', 'D': '♦️', 'C': '♣️'}
    ranks = {11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
    suit, rank = card[0], int(card[1:])
    # نمایش رنک کارت یا حرف معادل آن
    rank_display = str(ranks.get(rank, rank))
    return f"{suits[suit]} {rank_display}"

def get_card_value(card, hokm_suit, trick_suit):
    """ارزش عددی یک کارت را برای مقایسه و تعیین برنده دست محاسبه می‌کند."""
    suit, rank = card[0], int(card[1:])
    value = rank
    if suit == hokm_suit:
        value += 200  # کارت‌های حکم بالاترین ارزش را دارند
    elif suit == trick_suit:
        value += 100  # کارت‌های خال زمین ارزش بیشتری از سایر خال‌ها دارند
    return value

# --- تابع اصلی برای ساخت رابط کاربری (صفحه بازی) ---
# ======================= این تابع را جایگزین کنید =======================
# ======================= فقط این تابع را جایگزین کنید =======================
# ======================= این تابع را جایگزین کنید =======================
async def render_hokm_board(game: dict, context: ContextTypes.DEFAULT_TYPE):
    """
    این تابع صفحه بازی (متن و دکمه‌ها) را بر اساس وضعیت فعلی بازی برای همه تولید می‌کند.
    """
    game_id = game['message_id']
    keyboard = []
    
    # --- بخش نمایش بازیکنان و کارت‌های روی میز ---
    if game['mode'] == '4p':
        p_names = [p['name'] for p in game['players']]
        team_a_text = f"🔴 تیم A: {p_names[0]} و {p_names[2]}"
        team_b_text = f"🔵 تیم B: {p_names[1]} و {p_names[3]}"
        
        table_cards = ["➖"]*4
        for play in game.get('current_trick', []):
            player_index = next((i for i, p in enumerate(game['players']) if p['id'] == play['player_id']), -1)
            if player_index != -1:
                table_cards[player_index] = card_to_persian(play['card'])

        board_layout = [
            [InlineKeyboardButton(team_a_text, callback_data=f"hokm_noop_{game_id}")],
            [InlineKeyboardButton(team_b_text, callback_data=f"hokm_noop_{game_id}")],
            [InlineKeyboardButton("بازیکن", callback_data=f"hokm_noop_{game_id}"), InlineKeyboardButton("کارت بازی شده", callback_data=f"hokm_noop_{game_id}")],
            [InlineKeyboardButton(p_names[0], callback_data=f"hokm_noop_{game_id}"), InlineKeyboardButton(table_cards[0], callback_data=f"hokm_noop_{game_id}")],
            [InlineKeyboardButton(p_names[1], callback_data=f"hokm_noop_{game_id}"), InlineKeyboardButton(table_cards[1], callback_data=f"hokm_noop_{game_id}")],
            [InlineKeyboardButton(p_names[2], callback_data=f"hokm_noop_{game_id}"), InlineKeyboardButton(table_cards[2], callback_data=f"hokm_noop_{game_id}")],
            [InlineKeyboardButton(p_names[3], callback_data=f"hokm_noop_{game_id}"), InlineKeyboardButton(table_cards[3], callback_data=f"hokm_noop_{game_id}")],
        ]
        keyboard.extend(board_layout)
    else: # <<<--- بخش جدید برای حالت دو نفره --->>>
        p_names = [p['name'] for p in game['players']]
        p1_card = card_to_persian(game['current_trick'][0]['card']) if len(game.get('current_trick', [])) > 0 else "➖"
        p2_card = card_to_persian(game['current_trick'][1]['card']) if len(game.get('current_trick', [])) > 1 else "➖"

        board_layout = [
            [InlineKeyboardButton(f"{p_names[0]}", callback_data=f"hokm_noop_{game_id}"), InlineKeyboardButton(p1_card, callback_data=f"hokm_noop_{game_id}")],
            [InlineKeyboardButton(f"{p_names[1]}", callback_data=f"hokm_noop_{game_id}"), InlineKeyboardButton(p2_card, callback_data=f"hokm_noop_{game_id}")],
        ]
        keyboard.extend(board_layout)

    # --- بخش نمایش وضعیت و امتیازات ---
    hokm_suit_fa = card_to_persian(f"{game['hokm_suit']}2")[0] if game.get('hokm_suit') else '❓'
    hakem_name = game.get('hakem_name', '...')
    
    if game['mode'] == '4p':
        trick_score_text = f"دست: 🔴 {game['trick_scores']['A']} - {game['trick_scores']['B']} 🔵"
        game_score_text = f"امتیاز کل: 🔴 {game['game_scores']['A']} - {game['game_scores']['B']} 🔵"
    else: # <<<--- بخش جدید برای حالت دو نفره --->>>
        p_ids = [p['id'] for p in game['players']]
        trick_score_text = f"دست: {p_names[0]} {game['trick_scores'][p_ids[0]]} - {game['trick_scores'][p_ids[1]]} {p_names[1]}"
        game_score_text = f"امتیاز کل: {p_names[0]} {game['game_scores'][p_ids[0]]} - {game['game_scores'][p_ids[1]]} {p_names[1]}"


    keyboard.append([InlineKeyboardButton(f"حاکم: {hakem_name}", callback_data=f"hokm_noop_{game_id}"), InlineKeyboardButton(f"حکم: {hokm_suit_fa}", callback_data=f"hokm_noop_{game_id}")])
    keyboard.append([InlineKeyboardButton(trick_score_text, callback_data=f"hokm_noop_{game_id}")])
    keyboard.append([InlineKeyboardButton(game_score_text, callback_data=f"hokm_noop_{game_id}")])

    # --- بخش دکمه‌های کنترلی ---
    keyboard.append([InlineKeyboardButton("🃏 نمایش دست من (خصوصی)", callback_data=f"hokm_showhand_{game_id}")])

    # --- نمایش دکمه‌های مربوط به وضعیت فعلی بازی ---
    if game['status'] == 'hakem_choosing':
        suit_map = {'♠️': 'S', '♥️': 'H', '♦️': 'D', '♣️': 'C'}
        choose_buttons = [InlineKeyboardButton(emoji, callback_data=f"hokm_choose_{game_id}_{char}") for emoji, char in suit_map.items()]
        keyboard.append(choose_buttons)
    elif game['status'] == 'playing':
        current_turn_player_id = game['players'][game['turn_index']]['id']
        player_hand = game['hands'][current_turn_player_id]
        card_buttons = [InlineKeyboardButton(str(i + 1), callback_data=f"hokm_play_{game_id}_{i}") for i in range(len(player_hand))]
        for i in range(0, len(card_buttons), 7):
            keyboard.append(card_buttons[i:i+7])
    
    return InlineKeyboardMarkup(keyboard)

# --- تابع مدیریت دستور اولیه بازی ---
async def hokm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور اولیه برای شروع بازی و انتخاب حالت ۲ یا ۴ نفره."""
    if not await pre_command_check(update, context): return
    if update.effective_chat.type == 'private':
        await update.message.reply_text("بازی حکم فقط در گروه‌ها قابل اجراست.")
        return

    keyboard = [
        [
            InlineKeyboardButton("😎 ۲ نفره", callback_data="hokm_start_2p"),
            InlineKeyboardButton("👨‍👩‍👧‍👦 ۴ نفره", callback_data="hokm_start_4p")
        ]
    ]
    await update.message.reply_text("حالت بازی حکم را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- تابع اصلی برای مدیریت تمام تعاملات بازی ---
# ======================= فقط این تابع را جایگزین کنید =======================
# ======================= این تابع را هم جایگزین کنید =======================
# ======================= این تابع را هم جایگزین کنید =======================
async def hokm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id
    
    if not await pre_command_check(update, context):
        await query.answer(); return
        
    data = query.data.split('_'); action = data[1]

    if action == "start":
        await query.answer(); mode = data[2]; max_players = 4 if mode == '4p' else 2
        if chat_id not in active_games['hokm']: active_games['hokm'][chat_id] = {}
        msg = await query.edit_message_text(f"بازی حکم {max_players} نفره! منتظر ورود بازیکنان...")
        game_id = msg.message_id
        active_games['hokm'][chat_id][game_id] = {"status": "joining", "mode": mode, "players": [{'id': user.id, 'name': user.first_name}], "message_id": game_id}
        keyboard = [[InlineKeyboardButton(f"Join Game (1/{max_players})", callback_data=f"hokm_join_{game_id}")]]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard)); return

    game_id = int(data[2])
    if chat_id not in active_games['hokm'] or game_id not in active_games['hokm'][chat_id]:
        await query.answer("این بازی دیگر فعال نیست.", show_alert=True)
        try: await query.edit_message_text("این بازی تمام شده است.")
        except: pass
        return
    
    game = active_games['hokm'][chat_id][game_id]

    if action == "join":
        if any(p['id'] == user.id for p in game['players']): return await query.answer("شما قبلاً به بازی پیوسته‌اید!", show_alert=True)
        max_players = 4 if game['mode'] == '4p' else 2
        if len(game['players']) >= max_players: return await query.answer("ظرفیت بازی تکمیل است.", show_alert=True)
        
        await query.answer(); game['players'].append({'id': user.id, 'name': user.first_name})
        num_players = len(game['players'])

        if num_players < max_players:
            keyboard = [[InlineKeyboardButton(f"Join Game ({num_players}/{max_players})", callback_data=f"hokm_join_{game_id}")]]
            await query.edit_message_text(f"بازی حکم (ID: {game_id})\nبازیکنان وارد شده: {num_players}/{max_players}", reply_markup=InlineKeyboardMarkup(keyboard))
        else: # <<<--- منطق جدید برای شروع بازی --- >>>
            p_ids = [p['id'] for p in game['players']]
            game.update({
                "status": "dealing_first_5", "deck": create_deck(), "hands": {pid: [] for pid in p_ids},
                "hakem_id": None, "hakem_name": None, "turn_index": 0, "hokm_suit": None, "current_trick": [],
                "trick_scores": {'A': 0, 'B': 0} if game['mode'] == '4p' else {p_ids[0]: 0, p_ids[1]: 0},
                "game_scores": game.get('game_scores', {'A': 0, 'B': 0} if game['mode'] == '4p' else {p_ids[0]: 0, p_ids[1]: 0})
            })

            for _ in range(5):
                for p in game['players']: game['hands'][p['id']].append(game['deck'].pop(0))
            
            hakem_p = next((p for p in game['players'] if 'S14' in game['hands'][p['id']]), game['players'][0])
            game.update({"hakem_id": hakem_p['id'], "hakem_name": hakem_p['name'], "status": 'hakem_choosing'})
            
            reply_markup = await render_hokm_board(game, context)
            await query.edit_message_text(f"بازیکنان کامل شدند!\nحاکم: **{game['hakem_name']}**\n\nحاکم عزیز، بر اساس ۵ کارت اول خود، حکم را انتخاب کنید.", reply_markup=reply_markup)

    elif action == "choose":
        if user.id != game.get('hakem_id'): return await query.answer("شما حاکم نیستید!", show_alert=True)
        await query.answer(); game['hokm_suit'] = data[3]
        for p in game['players']:
            while len(game['hands'][p['id']]) < 13: game['hands'][p['id']].append(game['deck'].pop(0))
        game['status'] = 'playing'
        game['turn_index'] = next(i for i, p in enumerate(game['players']) if p['id'] == game['hakem_id'])
        turn_player_name = game['players'][game['turn_index']]['name']
        reply_markup = await render_hokm_board(game, context)
        await query.edit_message_text(f"بازی شروع شد! حکم: **{card_to_persian(game['hokm_suit']+'2')[0]}**\n\nنوبت **{turn_player_name}** است.", reply_markup=reply_markup)

    elif action == "showhand":
        if not any(p['id'] == user.id for p in game['players']): return await query.answer("شما بازیکن این مسابقه نیستید!", show_alert=True)
        hand = sorted(game['hands'][user.id])
        hand_str = "\n".join([f"{i+1}. {card_to_persian(c)}" for i, c in enumerate(hand)]) or "شما کارتی در دست ندارید."
        await query.answer(f"دست شما:\n{hand_str}", show_alert=True)

    elif action == "play":
        if user.id != game['players'][game['turn_index']]['id']: return await query.answer("نوبت شما نیست!", show_alert=True)
        card_index = int(data[3]); hand = sorted(game['hands'][user.id])
        if not (0 <= card_index < len(hand)): return await query.answer("شماره کارت نامعتبر است.", show_alert=True)
        
        card_played = hand[card_index]
        if game['current_trick']:
            trick_suit = game['current_trick'][0]['card'][0]
            if any(c.startswith(trick_suit) for c in hand) and not card_played.startswith(trick_suit):
                return await query.answer(f"شما باید از خال زمین ({card_to_persian(trick_suit+'2')[0]}) بازی کنید!", show_alert=True)

        await query.answer(); game['hands'][user.id].remove(card_played)
        game['current_trick'].append({'player_id': user.id, 'card': card_played})

        num_players = len(game['players'])
        if len(game['current_trick']) == num_players:
            trick_suit = game['current_trick'][0]['card'][0]
            winner_id = max(game['current_trick'], key=lambda p: get_card_value(p['card'], game['hokm_suit'], trick_suit))['player_id']
            
            # --- منطق جدید برای آپدیت امتیاز ---
            if game['mode'] == '4p':
                winner_team = 'A' if winner_id in [game['players'][0]['id'], game['players'][2]['id']] else 'B'
                game['trick_scores'][winner_team] += 1
                round_over = game['trick_scores']['A'] == 7 or game['trick_scores']['B'] == 7
            else: # 2p
                game['trick_scores'][winner_id] += 1
                round_over = any(score == 7 for score in game['trick_scores'].values())

            game['turn_index'] = next(i for i, p in enumerate(game['players']) if p['id'] == winner_id)
            game['current_trick'] = []
            
            if round_over:
                # --- منطق جدید برای پایان دست ---
                if game['mode'] == '4p':
                    winning_team_name = 'A' if game['trick_scores']['A'] == 7 else 'B'
                    game['game_scores'][winning_team_name] += 1
                    winner_display_name = f"تیم {winning_team_name}"
                    game_over = game['game_scores'][winning_team_name] == 7
                else: # 2p
                    winner_display_name = next(p['name'] for p in game['players'] if p['id'] == winner_id)
                    game['game_scores'][winner_id] += 1
                    game_over = game['game_scores'][winner_id] == 7

                if game_over:
                    await query.edit_message_text(f"🏆 **بازی تمام شد!** 🏆\n\nبرنده نهایی: **{winner_display_name}**")
                    del active_games['hokm'][chat_id][game_id]; return
                
                # --- منطق جدید برای حاکم بعدی ---
                current_hakem_index = next(i for i, p in enumerate(game['players']) if p['id'] == game['hakem_id'])
                if game['mode'] == '4p':
                    hakem_team = 'A' if game['hakem_id'] in [game['players'][0]['id'], game['players'][2]['id']] else 'B'
                    next_hakem_index = current_hakem_index if winning_team_name == hakem_team else (current_hakem_index + 1) % 4
                else: # 2p (حاکمیت همیشه می‌چرخد)
                    next_hakem_index = (current_hakem_index + 1) % 2
                
                # ریست کردن وضعیت برای دست جدید
                p_ids = [p['id'] for p in game['players']]
                game.update({ "status": "dealing_first_5", "deck": create_deck(), "hands": {pid: [] for pid in p_ids},
                              "trick_scores": {'A': 0, 'B': 0} if game['mode'] == '4p' else {p_ids[0]: 0, p_ids[1]: 0} })
                for _ in range(5):
                    for p in game['players']: game['hands'][p['id']].append(game['deck'].pop(0))
                game['hakem_id'] = game['players'][next_hakem_index]['id']
                game['hakem_name'] = game['players'][next_hakem_index]['name']
                game['status'] = 'hakem_choosing'

                reply_markup = await render_hokm_board(game, context)
                await query.edit_message_text(f"دست تمام شد! برنده: **{winner_display_name}**\n\nحاکم جدید: **{game['hakem_name']}**\nمنتظر انتخاب حکم...", reply_markup=reply_markup)
            
            else: # اگر دست تمام نشده
                turn_player_name = game['players'][game['turn_index']]['name']
                reply_markup = await render_hokm_board(game, context)
                await query.edit_message_text(f"حکم: **{card_to_persian(game['hokm_suit']+'2')[0]}**\n\nنوبت **{turn_player_name}** است.", reply_markup=reply_markup)
        
        else: # اگر هنوز همه بازی نکرده‌اند
            game['turn_index'] = (game['turn_index'] + 1) % num_players
            turn_player_name = game['players'][game['turn_index']]['name']
            reply_markup = await render_hokm_board(game, context)
            await query.edit_message_text(f"حکم: **{card_to_persian(game['hokm_suit']+'2')[0]}**\n\nنوبت **{turn_player_name}** است.", reply_markup=reply_markup)
            
    elif action == "noop":
        await query.answer()

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
    query, user = update.callback_query, query.from_user
    await query.answer()
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
            await update.message.reply_text(f"✅ **{user.mention_html()}** برنده شد! کلمه صحیح `{game['word']}` بود.", parse_mode=ParseMode.HTML)
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
            if all(lives == 0 for lives in game['players'].values() if lives is not None):
                await update.message.reply_text(f"☠️ همه باختید! کلمه صحیح `{game['word']}` بود.", parse_mode=ParseMode.MARKDOWN)
                del active_games['hangman'][chat_id]

# --------------------------- GAME: GHARCH & ETERAF ---------------------------
# ======================= GAME: GHARCH (نسخه جدید با گاد) =======================

# --- مرحله اول: شروع بازی و درخواست یوزرنیم گاد ---
# ======================= این دو تابع را به طور کامل جایگزین کنید =======================

# --- مرحله اول: شروع بازی، ارسال پیام اولیه و ذخیره آیدی آن ---
async def gharch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """شروع فرآیند بازی قارچ و ورود به حالت مکالمه."""
    if not await pre_command_check(update, context): return ConversationHandler.END
    if update.effective_chat.type == 'private':
        await update.message.reply_text("این بازی فقط در گروه‌ها قابل اجراست.")
        return ConversationHandler.END
        
    if not await is_group_admin(update.effective_user.id, update.effective_chat.id, context):
        await update.message.reply_text("❌ فقط ادمین‌های گروه می‌توانند این بازی را شروع کنند.")
        return ConversationHandler.END
    
    # ذخیره آیدی ادمین شروع کننده
    context.chat_data['starter_admin_id'] = update.effective_user.id
    
    # <<<--- تغییر اصلی: ارسال پیام و ذخیره آیدی آن --->>>
    sent_message = await update.message.reply_text(
        "🍄 **شروع بازی قارچ**\n\n"
        "لطفاً یوزرنیم گاد بازی را ارسال کنید (مثال: @GodUsername)."
    )
    context.chat_data['gharch_setup_message_id'] = sent_message.message_id
    
    return ASKING_GOD_USERNAME

# --- مرحله دوم: دریافت یوزرنیم، حذف پیام ادمین و ویرایش پیام اصلی ---
async def receive_god_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دریافت یوزرنیم گاد، حذف پیام و ویرایش پیام اولیه."""
    god_username = update.message.text.strip()
    if not god_username.startswith('@'):
        await update.message.reply_text("فرمت اشتباه است. لطفاً یوزرنیم را با @ ارسال کنید.", quote=True)
        return ASKING_GOD_USERNAME

    context.chat_data['god_username'] = god_username
    starter_admin_id = context.chat_data['starter_admin_id']
    setup_message_id = context.chat_data.get('gharch_setup_message_id')

    # <<<--- تغییر اصلی: حذف پیام حاوی یوزرنیم --->>>
    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete admin's username message: {e}")

    if not setup_message_id:
        await context.bot.send_message(update.effective_chat.id, "خطایی در یافتن پیام اصلی رخ داد. لطفاً بازی را با /cancel لغو و مجدداً شروع کنید.")
        return ConversationHandler.END

    keyboard = [[
        InlineKeyboardButton("✅ تایید می‌کنم", callback_data=f"gharch_confirm_god_{starter_admin_id}")
    ]]
    
    # <<<--- تغییر اصلی: ویرایش پیام اولیه به جای ارسال پیام جدید --->>>
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=setup_message_id,
        text=(
            f"{god_username} عزیز،\n"
            f"شما به عنوان گاد بازی قارچ انتخاب شدید. لطفاً برای شروع بازی، این مسئولیت را تایید کنید.\n\n"
            f"⚠️ **نکته:** برای دریافت گزارش‌ها، باید ربات را استارت کرده باشید. /start"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return CONFIRMING_GOD

# --- مرحله سوم: تایید نهایی گاد و شروع بازی ---
async def confirm_god(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """گاد بازی را تایید کرده و بازی رسماً شروع می‌شود."""
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id
    
    starter_admin_id = int(query.data.split('_')[3])
    god_username = context.chat_data.get('god_username', '').lstrip('@')

    # چک می‌کنیم که فرد درستی دکمه را فشار داده باشد
    if user.username.lower() != god_username.lower():
        await query.answer("این درخواست برای شما نیست!", show_alert=True)
        return CONFIRMING_GOD

    await query.answer("شما به عنوان گاد تایید شدید!")
    
    # ذخیره اطلاعات گاد
    god_id = user.id
    active_gharch_games[chat_id] = {'god_id': god_id, 'god_username': f"@{god_username}"}

    # ارسال و پین کردن پیام اصلی بازی
    bot_username = (await context.bot.get_me()).username
    game_message_text = (
        "**بازی قارچ 🍄 شروع شد!**\n\n"
        "روی دکمه زیر کلیک کن و حرف دلت رو بنویس تا به صورت ناشناس در گروه ظاهر بشه!\n\n"
        f"*(فقط گاد بازی، {active_gharch_games[chat_id]['god_username']}، از هویت ارسال‌کننده مطلع خواهد شد.)*"
    )
    keyboard = [[InlineKeyboardButton("🍄 ارسال پیام ناشناس", url=f"https://t.me/{bot_username}?start=gharch_{chat_id}")]]
    
    game_message = await query.message.reply_text(
        game_message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        await context.bot.pin_chat_message(chat_id, game_message.message_id)
        active_gharch_games[chat_id]['pinned_message_id'] = game_message.message_id
    except Exception as e:
        logger.error(f"Failed to pin message in gharch game: {e}")

    await query.edit_message_text(f"بازی قارچ با موفقیت توسط گاد (@{god_username}) شروع شد!")
    return ConversationHandler.END

# --- تابع برای لغو کردن فرآیند ---
async def cancel_gharch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """لغو فرآیند ساخت بازی قارچ."""
    await update.message.reply_text("فرآیند ساخت بازی قارچ لغو شد.")
    return ConversationHandler.END

async def eteraf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    chat_id, bot_username = update.effective_chat.id, (await context.bot.get_me()).username
    starter_message = await update.message.reply_text("یک موضوع اعتراف جدید شروع شد. برای ارسال اعتراف ناشناس (که به این پیام ریپلای می‌شود)، از دکمه زیر استفاده کنید.")
    keyboard = [[InlineKeyboardButton("🤫 ارسال اعتراف", url=f"https://t.me/{bot_username}?start=eteraf_{chat_id}_{starter_message.message_id}")]]
    await starter_message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

# ======================= این تابع را جایگزین کنید =======================
async def handle_anonymous_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    if 'anon_target_chat' not in user_data:
        return await update.message.reply_text("لطفاً ابتدا از طریق دکمه‌ای که در گروه قرار دارد، فرآیند را شروع کنید.")
    
    # استخراج اطلاعات لازم از user_data
    target_info = user_data['anon_target_chat']
    target_chat_id = target_info['id']
    game_type = target_info['type']
    message_text = update.message.text

    try:
        # --- منطق جدید برای بازی قارچ ---
        if game_type == "gharch":
            if target_chat_id in active_gharch_games:
                sender = update.effective_user
                god_info = active_gharch_games[target_chat_id]
                god_id = god_info['god_id']

                # ۱. ارسال پیام ناشناس به گروه
                await context.bot.send_message(
                    chat_id=target_chat_id,
                    text=f"#پیام_ناشناس 🍄\n\n{message_text}"
                )
                await update.message.reply_text("✅ پیام شما با موفقیت به صورت ناشناس در گروه ارسال شد.")

                # ۲. ساخت و ارسال گزارش به گاد
                report_text = (
                    f"📝 **گزارش پیام ناشناس جدید**\n\n"
                    f"👤 **ارسال کننده:**\n"
                    f"- نام: {sender.mention_html()}\n"
                    f"- یوزرنیم: @{sender.username}\n"
                    f"- آیدی: `{sender.id}`\n\n"
                    f"📜 **متن پیام:**\n"
                    f"{message_text}"
                )
                await context.bot.send_message(chat_id=god_id, text=report_text, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text("این بازی قارچ دیگر فعال نیست یا منقضی شده است.")

        # --- منطق قدیمی برای بازی اعتراف ---
        elif game_type == "eteraf":
            reply_to_id = target_info.get('reply_to')
            header = "#اعتراف_ناشناس 🤫"
            await context.bot.send_message(
                chat_id=target_chat_id,
                text=f"{header}\n\n{message_text}",
                reply_to_message_id=reply_to_id
            )
            await update.message.reply_text("✅ اعتراف شما با موفقیت به صورت ناشناس در گروه ارسال شد.")
        
        # --- می‌توانید بازی‌های ناشناس دیگر را در آینده اینجا اضافه کنید ---
        else:
            await update.message.reply_text("نوع بازی ناشناس مشخص نیست.")

    except Exception as e:
        await update.message.reply_text(f"⚠️ ارسال پیام با خطا مواجه شد: {e}")
        logger.error(f"Error in handle_anonymous_message for game {game_type}: {e}")
    finally:
        # در هر صورت، اطلاعات از حافظه موقت کاربر پاک می‌شود
        if 'anon_target_chat' in context.user_data:
            del context.user_data['anon_target_chat']

# --------------------------- GAME: TYPE SPEED (با اصلاح عکس) ---------------------------
def create_typing_image(text: str) -> io.BytesIO:
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    try:
        font = ImageFont.truetype("Vazir.ttf", 24)
    except IOError:
        logger.warning("Vazir.ttf font not found. Falling back to default.")
        font = ImageFont.load_default()
    
    dummy_img, draw = Image.new('RGB', (1, 1)), ImageDraw.Draw(Image.new('RGB', (1, 1)))
    _, _, w, h = draw.textbbox((0, 0), bidi_text, font=font)
    img = Image.new('RGB', (w + 40, h + 40), color=(255, 255, 255))
    ImageDraw.Draw(img).text((20, 20), bidi_text, fill=(0, 0, 0), font=font)
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
    
    # <<<--- اینجا تغییر اصلی است --->>>
    user_input = update.message.text.strip()
    
    if user_input == game['sentence']:
        duration = (datetime.now() - game['start_time']).total_seconds()
        user = update.effective_user
        await update.message.reply_text(f"🏆 {user.mention_html()} برنده شد!\nزمان: **{duration:.2f}** ثانیه", parse_mode=ParseMode.HTML)
        del active_games['typing'][chat_id]

# ... (بازی‌های قارچ و اعتراف)

# =================================================================
# ================= OWNER & CORE COMMANDS START ===================
# =================================================================
# --------------------------- PLACEHOLDERS & SETTINGS ---------------------------
async def placeholder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles commands that are not yet implemented."""
    if not await pre_command_check(update, context): return
    await update.message.reply_text(f"قابلیت `{update.message.text.split()[0]}` در آینده اضافه خواهد شد.", parse_mode=ParseMode.MARKDOWN)

# ======================= این تابع را جایگزین کنید =======================
# ======================= این تابع را به طور کامل جایگزین کنید =======================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    # --- بخش ۱: مدیریت لینک‌های ورودی (Deep Linking) ---
    if context.args:
        try:
            payload = context.args[0]
            parts = payload.split('_')
            game_type, target_chat_id = parts[0], int(parts[1])

            if game_type == "gharch":
                if target_chat_id in active_gharch_games:
                    god_username = active_gharch_games[target_chat_id]['god_username']
                    context.user_data['anon_target_chat'] = {'id': target_chat_id, 'type': game_type}
                    prompt = f"پیام خود را برای ارسال ناشناس بنویسید...\n\nتوجه: فقط گاد بازی ({god_username}) هویت شما را خواهد دید."
                    await update.message.reply_text(prompt)
                    return
                else:
                    await update.message.reply_text("این بازی قارچ دیگر فعال نیست."); return
            
            elif game_type == "eteraf":
                context.user_data['anon_target_chat'] = {'id': target_chat_id, 'type': game_type}
                if len(parts) > 2:
                    context.user_data['anon_target_chat']['reply_to'] = int(parts[2])
                prompt = "اعتراف خود را بنویسید تا به صورت ناشناس در گروه ارسال شود..."
                await update.message.reply_text(prompt)
                return

        except (ValueError, IndexError):
            pass # اگر payload معتبر نبود، به بخش استارت معمولی می‌رود

    # --- بخش ۲: منطق استارت معمولی ---
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur: 
            cur.execute("INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING;", (user.id, user.first_name, user.username))
            conn.commit()
    
    if not await force_join_middleware(update, context):
        if conn: conn.close()
        return

    # --- بخش ۳: ارسال پیام خوشامدگویی (سفارشی یا پیش‌فرض) ---
    keyboard = [
        [InlineKeyboardButton("➕ افزودن ربات به گروه", url=f"https://t.me/{(await context.bot.get_me()).username}?startgroup=true")],
        [InlineKeyboardButton("👤 ارتباط با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    custom_welcome_sent = False
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT message_id, chat_id FROM start_message WHERE id = 1;")
                start_msg_data = cur.fetchone()
                if start_msg_data:
                    message_id, from_chat_id = start_msg_data
                    await context.bot.copy_message(chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id, reply_markup=reply_markup)
                    custom_welcome_sent = True
        except Exception as e:
            logger.error(f"Could not send custom start message in PV: {e}")
        finally:
            conn.close()

    if not custom_welcome_sent:
        await update.message.reply_text("سلام! به ربات ما خوش آمدید.", reply_markup=reply_markup)
    
    # ارسال گزارش به ادمین‌ها
    report_text = f"✅ کاربر جدید: {user.mention_html()} (ID: `{user.id}`)"
    for owner_id in OWNER_IDS:
        try:
            await context.bot.send_message(chat_id=owner_id, text=report_text, parse_mode=ParseMode.HTML)
        except:
            pass

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_middleware(update, context): return
    help_text = "راهنمای ربات 🎮\n\n/hokm - بازی حکم\n/dooz @user - بازی دوز\n/hads_kalame - حدس کلمه\n/hads_addad - حدس عدد\n/type - تایپ سرعتی\n/gharch - پیام ناشناس\n/eteraf - اعتراف ناشناس"
    await update.message.reply_text(help_text)

# --- دستورات مالک (کامل شده) ---
async def set_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    if not update.message.reply_to_message: return await update.message.reply_text("روی یک پیام ریپلای کنید.")
    msg = update.message.reply_to_message
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur: cur.execute("INSERT INTO start_message (id, message_id, chat_id) VALUES (1, %s, %s) ON CONFLICT (id) DO UPDATE SET message_id = EXCLUDED.message_id, chat_id = EXCLUDED.chat_id;", (msg.message_id, msg.chat_id)); conn.commit()
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

async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("استفاده: /leave <group_id>")
    try:
        group_id = int(context.args[0])
        await context.bot.leave_chat(group_id)
        await update.message.reply_text(f"✅ با موفقیت از گروه `{group_id}` خارج شدم.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")

async def grouplist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT group_id, title, member_count FROM groups;")
            groups = cur.fetchall()
        conn.close()
        if not groups: return await update.message.reply_text("ربات در هیچ گروهی عضو نیست.")
        message = "📜 **لیست گروه‌ها:**\n\n"
        for i, (group_id, title, member_count) in enumerate(groups, 1):
            message += f"{i}. **{title}**\n   - ID: `{group_id}`\n   - اعضا: {member_count}\n\n"
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("استفاده: /join <group_id>")
    try:
        group_id = int(context.args[0])
        link = await context.bot.create_chat_invite_link(group_id, member_limit=30)
        await update.message.reply_text(f"لینک ورود شما:\n{link.invite_link}")
    except Exception as e:
        await update.message.reply_text(f"خطا در ساخت لینک (شاید ربات ادمین نباشد): {e}")

async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("استفاده: /ban_user <user_id>")
    try:
        user_id = int(context.args[0])
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur: cur.execute("INSERT INTO banned_users (user_id) VALUES (%s) ON CONFLICT DO NOTHING;", (user_id,))
            conn.commit(); conn.close()
            await update.message.reply_text(f"کاربر `{user_id}` با موفقیت مسدود شد.", parse_mode=ParseMode.MARKDOWN)
    except: await update.message.reply_text("آیدی نامعتبر است.")

async def unban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("استفاده: /unban_user <user_id>")
    try:
        user_id = int(context.args[0])
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur: cur.execute("DELETE FROM banned_users WHERE user_id = %s;", (user_id,))
            conn.commit(); conn.close()
            await update.message.reply_text(f"کاربر `{user_id}` با موفقیت از مسدودیت خارج شد.", parse_mode=ParseMode.MARKDOWN)
    except: await update.message.reply_text("آیدی نامعتبر است.")

async def ban_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bans a group from using the bot."""
    if not await is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("استفاده صحیح: /ban_group <group_id>")
    
    try:
        group_id = int(context.args[0])
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO banned_groups (group_id) VALUES (%s) ON CONFLICT DO NOTHING;", (group_id,))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"گروه `{group_id}` با موفقیت مسدود شد.", parse_mode=ParseMode.MARKDOWN)
            
            # Bot leaves the group after banning it
            try:
                await context.bot.leave_chat(group_id)
            except Exception as e:
                logger.warning(f"Could not leave the banned group {group_id}: {e}")

    except (ValueError, IndexError):
        await update.message.reply_text("لطفا یک آیدی عددی معتبر برای گروه وارد کنید.")

async def unban_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unbans a group."""
    if not await is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("استفاده صحیح: /unban_group <group_id>")

    try:
        group_id = int(context.args[0])
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM banned_groups WHERE group_id = %s;", (group_id,))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"گروه `{group_id}` با موفقیت از مسدودیت خارج شد.", parse_mode=ParseMode.MARKDOWN)
    except (ValueError, IndexError):
        await update.message.reply_text("لطفا یک آیدی عددی معتبر برای گروه وارد کنید.")

# ======================= این تابع را نیز جایگزین کنید =======================
async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = update.chat_member
    if not result: return

    chat = result.chat
    user = result.from_user # کاربری که ربات را اضافه کرده
    
    # مطمئن می‌شویم که تغییر وضعیت مربوط به ربات ماست
    if result.new_chat_member.user.id != context.bot.id:
        return

    # --- وقتی ربات به گروه اضافه می‌شود ---
    if result.new_chat_member.status == 'member' and result.old_chat_member.status != 'member':
        conn = get_db_connection()
        if not conn: return
        
        # <<<--- شروع بخش اضافه‌شده: چک کردن محدودیت نصب --->>>
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM groups;")
                group_count = cur.fetchone()[0]
            
            if group_count >= GROUP_INSTALL_LIMIT:
                await chat.send_message(f"⚠️ ظرفیت نصب این ربات تکمیل شده است! لطفاً با پشتیبانی (@{SUPPORT_USERNAME}) تماس بگیرید.")
                await context.bot.leave_chat(chat.id)
                for owner_id in OWNER_IDS:
                    await context.bot.send_message(owner_id, f"🔔 هشدار: سقف نصب ({GROUP_INSTALL_LIMIT}) تکمیل شد. ربات از گروه `{chat.title}` خارج شد.", parse_mode=ParseMode.MARKDOWN)
                conn.close()
                return
        except Exception as e:
            logger.error(f"Could not check group install limit: {e}")
        # <<<--- پایان بخش اضافه‌شده --->>>

        member_count = await chat.get_member_count()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO groups (group_id, title, member_count) VALUES (%s, %s, %s) ON CONFLICT (group_id) DO UPDATE SET title = EXCLUDED.title, member_count = EXCLUDED.member_count;", (chat.id, chat.title, member_count))
            conn.commit()

        custom_welcome_sent = False
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT message_id, chat_id FROM start_message WHERE id = 1;")
                start_msg_data = cur.fetchone()
                if start_msg_data:
                    message_id, from_chat_id = start_msg_data
                    await context.bot.copy_message(chat_id=chat.id, from_chat_id=from_chat_id, message_id=message_id)
                    custom_welcome_sent = True
        except Exception as e:
            logger.error(f"Could not send custom start message: {e}")

        if not custom_welcome_sent:
            await chat.send_message("سلام! 👋 من با موفقیت نصب شدم.\nبرای مشاهده لیست بازی‌ها از دستور /help استفاده کنید.")
        
        conn.close()
        
        report = f"➕ **ربات به گروه جدید اضافه شد:**\n\n🌐 نام: {chat.title}\n🆔: `{chat.id}`\n👥 اعضا: {member_count}\n\n👤 توسط: {user.mention_html()} (ID: `{user.id}`)"
        for owner_id in OWNER_IDS:
            try: await context.bot.send_message(owner_id, report, parse_mode=ParseMode.HTML)
            except: pass

    # --- وقتی ربات از گروه حذف می‌شود ---
    elif result.new_chat_member.status == 'left':
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM groups WHERE group_id = %s;", (chat.id,))
                conn.commit()
            conn.close()
        report = f"❌ **ربات از گروه زیر اخراج شد:**\n\n🌐 نام: {chat.title}\n🆔: `{chat.id}`"
        for owner_id in OWNER_IDS:
            try: await context.bot.send_message(owner_id, report, parse_mode=ParseMode.MARKDOWN)
            except: pass
                
# =================================================================
# ======================== MAIN FUNCTION ==========================
# =================================================================

# ======================= این تابع را نیز به طور کامل جایگزین کنید =======================
def main() -> None:
    """Start the bot."""
    setup_database()
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN environment variable not set.")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    
    # --- اولویت ۱: Conversation Handlers ---
    # این‌ها باید اول ثبت شوند تا پیام‌ها را قبل از handler های عمومی دریافت کنند.
    
    gharch_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("gharch", gharch_command)],
        states={
            ASKING_GOD_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_god_username)],
            CONFIRMING_GOD: [CallbackQueryHandler(confirm_god, pattern=r'^gharch_confirm_god_')],
        },
        fallbacks=[CommandHandler('cancel', cancel_gharch)],
        per_user=False, per_chat=True,
    )
    application.add_handler(gharch_conv_handler)
    
    guess_number_conv = ConversationHandler(
        entry_points=[CommandHandler("hads_addad", hads_addad_command)],
        states={
            SELECTING_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_range)],
            GUESSING: [MessageHandler(filters.Regex(r'^[\d۰-۹]+$'), handle_guess_conversation)],
        },
        fallbacks=[CommandHandler('cancel', cancel_game)],
        per_user=False, per_chat=True
    )
    application.add_handler(guess_number_conv)

    # --- اولویت ۲: Command Handlers (تمام دستورات) ---
    # دستورات اصلی
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # دستورات بازی
    application.add_handler(CommandHandler("hokm", hokm_command))
    application.add_handler(CommandHandler("dooz", dooz_command))
    application.add_handler(CommandHandler("hads_kalame", hads_kalame_command))
    application.add_handler(CommandHandler("type", type_command))
    application.add_handler(CommandHandler("eteraf", eteraf_command))
    
    # دستورات جایگزین (Placeholder)
    application.add_handler(CommandHandler("top", placeholder_command))
    application.add_handler(CommandHandler("settings", placeholder_command))

    # دستورات مالک ربات
    application.add_handler(CommandHandler("setstart", set_start_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("fwdusers", fwdusers_command))
    application.add_handler(CommandHandler("fwdgroups", fwdgroups_command))
    application.add_handler(CommandHandler("leave", leave_command))
    application.add_handler(CommandHandler("grouplist", grouplist_command))
    application.add_handler(CommandHandler("join", join_command))
    application.add_handler(CommandHandler("ban_user", ban_user_command))
    application.add_handler(CommandHandler("unban_user", unban_user_command))
    application.add_handler(CommandHandler("ban_group", ban_group_command))
    application.add_handler(CommandHandler("unban_group", unban_group_command))

    # --- اولویت ۳: CallbackQuery Handlers ---
    application.add_handler(CallbackQueryHandler(hokm_callback, pattern=r'^hokm_'))
    application.add_handler(CallbackQueryHandler(dooz_callback, pattern=r'^dooz_'))
    # CallbackQuery برای بازی قارچ در ConversationHandler آن مدیریت می‌شود

    # --- اولویت ۴: Message Handlers (عمومی) ---
    # این‌ها باید تقریباً در آخر باشند تا در کار بقیه دخالت نکنند
    application.add_handler(MessageHandler(filters.Regex(r'^[آ-ی]$') & filters.ChatType.GROUPS, handle_letter_guess))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_anonymous_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_typing_attempt))
    
    # --- اولویت ۵: سایر Handler ها ---
    application.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    
    logger.info("Bot is starting with final and corrected logic...")
    application.run_polling()

if __name__ == "__main__":
    main()
