# -*- coding: utf-8 -*-

import os
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Bot,
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
import psycopg2
from psycopg2 import sql

# --- Configuration Section ---
# These values are hardcoded as requested.
# Sensitive values (BOT_TOKEN, DATABASE_URL) are read from the environment.

OWNER_IDS = [7662192190, 6041119040]
SUPPORT_USERNAME = "OLDKASEB"
FORCED_JOIN_CHANNEL = "@RHINOSOUL_TM"
GROUP_INSTALL_LIMIT = 50

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Database Setup ---
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def setup_database():
    """Creates necessary tables if they don't exist."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                # Users table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        first_name VARCHAR(255),
                        username VARCHAR(255),
                        start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                # Groups table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS groups (
                        group_id BIGINT PRIMARY KEY,
                        title VARCHAR(255),
                        member_count INT,
                        owner_mention VARCHAR(255),
                        added_time TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                # Start message table
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

# --- Helper Functions ---

async def is_owner(user_id: int) -> bool:
    """Checks if a user is one of the owners."""
    return user_id in OWNER_IDS

async def check_channel_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if a user is a member of the mandatory channel."""
    try:
        member = await context.bot.get_chat_member(chat_id=FORCED_JOIN_CHANNEL, user_id=user_id)
        return member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.CREATOR]
    except Exception as e:
        logger.warning(f"Could not check channel membership for {user_id}: {e}")
        return False # Fail-safe

async def force_join_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """A middleware to enforce channel subscription. Returns True if check passes."""
    if update.effective_user:
        user_id = update.effective_user.id
        if await is_owner(user_id):
            return True # Owners bypass the check

        is_member = await check_channel_membership(user_id, context)
        if not is_member:
            keyboard = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{FORCED_JOIN_CHANNEL.lstrip('@')}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            text = f"❗️کاربر گرامی، برای استفاده از ربات ابتدا باید در کانال ما عضو شوید:\n\n{FORCED_JOIN_CHANNEL}\n\nپس از عضویت، دوباره تلاش کنید."
            if update.callback_query:
                await update.callback_query.answer(text, show_alert=True)
            else:
                await update.message.reply_text(text, reply_markup=reply_markup)
            return False
        return True
    return False

# --- User Commands ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command for new users."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.first_name}) started the bot.")

    # --- Database entry ---
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING;",
                (user.id, user.first_name, user.username)
            )
            conn.commit()
        conn.close()

    # --- Force Join Check ---
    if not await force_join_middleware(update, context):
        return

    # --- Welcome Message ---
    keyboard = [
        [InlineKeyboardButton("👤 ارتباط با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton("➕ افزودن ربات به گروه", url=f"https://t.me/{(await context.bot.get_me()).username}?startgroup=true")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Fetch custom start message
    custom_message_info = None
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT message_id, chat_id FROM start_message WHERE id = 1;")
            result = cur.fetchone()
            if result:
                custom_message_info = {"message_id": result[0], "chat_id": result[1]}
        conn.close()

    if custom_message_info:
        try:
            await context.bot.copy_message(
                chat_id=user.id,
                from_chat_id=custom_message_info["chat_id"],
                message_id=custom_message_info["message_id"],
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send custom start message: {e}. Sending default.")
            await update.message.reply_text("سلام! به ربات ما خوش آمدید.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("سلام! به ربات ما خوش آمدید.", reply_markup=reply_markup)


    # --- Report to Owner ---
    report_text = (
        f"✅ کاربر جدید ربات را استارت کرد:\n\n"
        f"👤 نام: {user.full_name}\n"
        f"🆔 شناسه: `{user.id}`\n"
        f"🔗 یوزرنیم: @{user.username if user.username else 'ندارد'}"
    )
    # Simple button to send a message, complex implementation deferred
    for owner_id in OWNER_IDS:
        try:
            await context.bot.send_message(chat_id=owner_id, text=report_text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send start report to owner {owner_id}: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the help message with a list of games."""
    if not await force_join_middleware(update, context):
        return
        
    help_text = """
    راهنمای ربات بازی 🎮

    در اینجا لیست بازی‌های موجود و دستورات مربوط به آن‌ها آمده است:

    **بازی‌های گروهی:**
    - `/hokm` - شروع بازی حکم
    - `/dooz @user` - شروع بازی دوز
    - `/hads_kalame` - شروع بازی حدس کلمه
    - `/hads_addad [min] [max]` - شروع بازی حدس عدد
    - `/type` - شروع بازی تایپ سرعتی
    - `/gharch` - شروع بازی قارچ (پیام ناشناس)
    - `/eteraf` - شروع بازی اعتراف (ناشناс)

    **قابلیت‌های دیگر:**
    - `/help` - نمایش همین راهنما
    - `/settings` - تنظیمات ربات در گروه (برای ادمین‌ها)

    برای شروع هر بازی، کافیست دستور آن را در گروه ارسال کنید.
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")


# --- Game Stubs (To be fully implemented) ---
# These are placeholders to show where the game logic would go.

async def game_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A placeholder for game commands that are not yet implemented."""
    if not await force_join_middleware(update, context):
        return
        
    command = update.message.text.split()[0]
    await update.message.reply_text(
        f"بازی `{command}` در حال حاضر در دست ساخت است. به زودی آماده خواهد شد!",
        parse_mode="Markdown"
    )

# --- Owner Commands ---

async def set_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets the custom welcome message for the bot."""
    user_id = update.effective_user.id
    if not await is_owner(user_id):
        return await update.message.reply_text("❌ این دستور فقط برای مالک ربات است.")

    if not update.message.reply_to_message:
        return await update.message.reply_text("لطفا این دستور را روی یک پیام ریپلای کنید.")

    replied_message = update.message.reply_to_message
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO start_message (id, message_id, chat_id) VALUES (1, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET message_id = EXCLUDED.message_id, chat_id = EXCLUDED.chat_id;",
                (replied_message.message_id, replied_message.chat_id)
            )
            conn.commit()
        conn.close()
        await update.message.reply_text("✅ پیام خوشامدگویی با موفقیت تنظیم شد.")
    else:
        await update.message.reply_text("⚠️ خطای دیتابیس. لطفا دوباره تلاش کنید.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends bot statistics to the owner."""
    user_id = update.effective_user.id
    if not await is_owner(user_id):
        return

    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users;")
            user_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM groups;")
            group_count = cur.fetchone()[0]
            cur.execute("SELECT SUM(member_count) FROM groups;")
            total_members_result = cur.fetchone()
            total_group_members = total_members_result[0] if total_members_result[0] else 0

        stats_text = (
            f"📊 **آمار ربات** 📊\n\n"
            f"👤 **تعداد کاربران:** {user_count}\n"
            f"👥 **تعداد گروه‌ها:** {group_count}\n"
            f"👨‍👩‍👧‍👦 **مجموع اعضای گروه‌ها:** {total_group_members}"
        )
        await update.message.reply_text(stats_text, parse_mode="Markdown")
        conn.close()
    else:
        await update.message.reply_text("⚠️ خطای دیتابیس.")

async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Makes the bot leave a group by its ID."""
    user_id = update.effective_user.id
    if not await is_owner(user_id):
        return
        
    if not context.args:
        return await update.message.reply_text("استفاده صحیح: `/leave <group_id>`")
    
    try:
        group_id = int(context.args[0])
        await context.bot.leave_chat(group_id)
        await update.message.reply_text(f"✅ با موفقیت از گروه `{group_id}` خارج شدم.")
        # Also remove from DB
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM groups WHERE group_id = %s;", (group_id,))
                conn.commit()
            conn.close()
    except (ValueError, IndexError):
        await update.message.reply_text("لطفا یک آیدی عددی معتبر وارد کنید.")
    except Exception as e:
        await update.message.reply_text(f"خطا در خروج از گروه: {e}")

async def grouplist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_owner(user_id):
        return
        
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT group_id, title, member_count, owner_mention FROM groups;")
            groups = cur.fetchall()
        conn.close()
        
        if not groups:
            return await update.message.reply_text("ربات در هیچ گروهی عضو نیست.")
            
        message = "📜 **لیست گروه‌ها:**\n\n"
        for i, group in enumerate(groups, 1):
            group_id, title, member_count, owner_mention = group
            message += (
                f"{i}. **{title}**\n"
                f"   - آیدی: `{group_id}`\n"
                f"   - اعضا: {member_count}\n"
                f"   - مالک: {owner_mention if owner_mention else 'نامشخص'}\n\n"
            )
            # Send in chunks to avoid message length limit
            if len(message) > 3500:
                await update.message.reply_text(message, parse_mode="Markdown")
                message = ""
        
        if message:
            await update.message.reply_text(message, parse_mode="Markdown")

    else:
        await update.message.reply_text("⚠️ خطای دیتابیس.")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str):
    """Generic broadcast function."""
    user_id = update.effective_user.id
    if not await is_owner(user_id):
        return await update.message.reply_text("❌ این دستور فقط برای مالک ربات است.")
    
    if not update.message.reply_to_message:
        return await update.message.reply_text("لطفا این دستور را روی یک پیام ریپلای کنید.")

    conn = get_db_connection()
    if not conn:
        return await update.message.reply_text("⚠️ خطای دیتابیس.")

    table = "users" if target == "users" else "groups"
    column = "user_id" if target == "users" else "group_id"
    
    with conn.cursor() as cur:
        cur.execute(f"SELECT {column} FROM {table};")
        targets = cur.fetchall()
    conn.close()

    if not targets:
        return await update.message.reply_text(f"هیچ هدفی برای ارسال یافت نشد.")

    sent_count = 0
    failed_count = 0
    
    status_message = await update.message.reply_text(f"⏳ در حال شروع ارسال همگانی به {len(targets)} {target}...")

    for (target_id,) in targets:
        try:
            await context.bot.forward_message(
                chat_id=target_id,
                from_chat_id=update.message.reply_to_message.chat.id,
                message_id=update.message.reply_to_message.message_id
            )
            sent_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"Broadcast failed for {target_id}: {e}")
        
        if (sent_count + failed_count) % 20 == 0: # Update status periodically
            await status_message.edit_text(
                f"⏳ در حال ارسال...\n✅ موفق: {sent_count}\n❌ ناموفق: {failed_count}"
            )

    await status_message.edit_text(
        f"🏁 ارسال همگانی به پایان رسید.\n\n"
        f"✅ موفق: {sent_count}\n"
        f"❌ ناموفق: {failed_count}"
    )

async def fwdusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await broadcast_command(update, context, target="users")

async def fwdgroups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await broadcast_command(update, context, target="groups")

# --- Chat Member Handler ---

async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tracks when the bot is added to or removed from a group."""
    result = update.chat_member
    if result is None:
        return

    chat = result.chat
    user = result.from_user
    new_status = result.new_chat_member.status
    old_status = result.old_chat_member.status
    
    is_bot = result.new_chat_member.user.id == context.bot.id

    if is_bot:
        if new_status == ChatMember.MEMBER and old_status != ChatMember.MEMBER:
            # Bot was added to the group
            logger.info(f"Bot was added to group {chat.id} by {user.id}")

            # Check group limit
            conn = get_db_connection()
            if not conn:
                await context.bot.send_message(chat.id, "خطای دیتابیس، لطفا بعدا امتحان کنید.")
                await context.bot.leave_chat(chat.id)
                return

            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM groups;")
                group_count = cur.fetchone()[0]
            
            if group_count >= GROUP_INSTALL_LIMIT:
                limit_message = (
                    f"⚠️ **ظرفیت نصب این ربات تکمیل شده است!** ⚠️\n\n"
                    f"متاسفانه در حال حاضر امکان فعال‌سازی ربات در گروه‌های جدید وجود ندارد. "
                    f"برای دریافت نسخه ۲ و اطلاعات بیشتر، لطفاً با پشتیبانی (@{SUPPORT_USERNAME}) در ارتباط باشید."
                )
                await context.bot.send_message(chat.id, limit_message, parse_mode="Markdown")
                await context.bot.leave_chat(chat.id)

                # Notify owner
                owner_report = (
                     f"🔔 **هشدار: سقف نصب ({GROUP_INSTALL_LIMIT} گروه) تکمیل شد!** 🔔\n\n"
                     f"ربات تلاش کرد به گروه جدید `{chat.title}` (ID: `{chat.id}`) اضافه شود اما به دلیل تکمیل ظرفیت، به صورت خودکار خارج شد."
                )
                for owner_id in OWNER_IDS:
                    await context.bot.send_message(owner_id, owner_report, parse_mode="Markdown")
                conn.close()
                return

            # Add group to DB
            try:
                member_count = await context.bot.get_chat_member_count(chat.id)
                owner = (await context.bot.get_chat_administrators(chat.id))[0].user
                owner_mention = owner.mention_markdown()
            except Exception:
                member_count = 0
                owner_mention = "نامشخص"

            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO groups (group_id, title, member_count, owner_mention) VALUES (%s, %s, %s, %s) ON CONFLICT (group_id) DO UPDATE SET title = EXCLUDED.title, member_count = EXCLUDED.member_count;",
                    (chat.id, chat.title, member_count, owner_mention)
                )
                conn.commit()
            conn.close()

            # Send welcome message and report to owner
            welcome_text = "سلام! 👋 من با موفقیت در گروه شما نصب شدم.\nبرای مشاهده لیست بازی‌ها از دستور /help استفاده کنید."
            await context.bot.send_message(chat.id, welcome_text)

            report_text = (
                f"➕ **ربات به گروه جدید اضافه شد:**\n\n"
                f"🌐 نام گروه: {chat.title}\n"
                f"🆔 آیدی گروه: `{chat.id}`\n"
                f"👥 تعداد اعضا: {member_count}\n\n"
                f"👤 **اضافه شده توسط:**\n"
                f"   - نام: {user.full_name}\n"
                f"   - یوزرنیم: @{user.username if user.username else 'ندارد'}\n"
                f"   - آیدی: `{user.id}`"
            )
            for owner_id in OWNER_IDS:
                await context.bot.send_message(owner_id, report_text, parse_mode="Markdown")

        elif new_status == ChatMember.LEFT:
            # Bot was removed from the group
            logger.info(f"Bot was removed from group {chat.id}")
            
            # Remove from DB
            conn = get_db_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM groups WHERE group_id = %s;", (chat.id,))
                    conn.commit()
                conn.close()

            # Report to owner
            report_text = (
                f"❌ **ربات از گروه زیر اخراج شد:**\n\n"
                f"🌐 نام گروه: {chat.title}\n"
                f"🆔 آیدی گروه: `{chat.id}`"
            )
            for owner_id in OWNER_IDS:
                await context.bot.send_message(owner_id, report_text, parse_mode="Markdown")

# --- Main Application ---
def main() -> None:
    """Start the bot."""
    # Run DB setup once at the start
    setup_database()

    # Create the Application and pass it your bot's token.
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN environment variable not set. Exiting.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # --- Register Handlers ---
    # User commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # Game command placeholders
    game_commands = ["hokm", "dooz", "hads_kalame", "hads_addad", "type", "gharch", "eteraf", "settings", "top"]
    for cmd in game_commands:
        application.add_handler(CommandHandler(cmd, game_placeholder))

    # Owner commands
    application.add_handler(CommandHandler("setstart", set_start_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("leave", leave_command))
    application.add_handler(CommandHandler("grouplist", grouplist_command))
    application.add_handler(CommandHandler("fwdusers", fwdusers_command))
    application.add_handler(CommandHandler("fwdgroups", fwdgroups_command))

    # Chat member handler for tracking groups
    application.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
