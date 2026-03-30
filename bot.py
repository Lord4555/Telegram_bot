import os
import sqlite3
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import uuid

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
PRIVATE_CHANNEL_LINK = os.getenv("PRIVATE_CHANNEL_LINK")
REFERRALS_NEEDED = int(os.getenv("REFERRALS_NEEDED", "5"))

if not TOKEN or not CHANNEL_USERNAME or not PRIVATE_CHANNEL_LINK:
    raise ValueError("Missing required environment variables: BOT_TOKEN, CHANNEL_USERNAME, PRIVATE_CHANNEL_LINK")

DB_PATH = "referrals.db"


def init_db():
    """Initialize SQLite database"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            invite_link TEXT UNIQUE,
            referral_count INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0,
            rewarded INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id INTEGER,
            referee_id INTEGER,
            PRIMARY KEY (referrer_id, referee_id),
            FOREIGN KEY (referrer_id) REFERENCES users(user_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS one_time_links (
            link_id TEXT PRIMARY KEY,
            user_id INTEGER,
            base_link TEXT,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    con.commit()
    con.close()


def get_user(user_id):
    """Get user from database"""
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return row


def create_user(user_id, username):
    """Create new user with unique invite link"""
    invite_link = f"https://t.me/{os.getenv('BOT_USERNAME', 'your_bot')}?start={user_id}"
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(
            "INSERT INTO users (user_id, username, invite_link) VALUES (?, ?, ?)",
            (user_id, username, invite_link),
        )
        con.commit()
    except sqlite3.IntegrityError:
        pass
    con.close()
    return invite_link


def verify_user(user_id):
    """Mark user as verified"""
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE users SET verified=1 WHERE user_id=?", (user_id,))
    con.commit()
    con.close()


def increment_referral(referrer_id, referee_id):
    """Track referral and increment count"""
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(
            "INSERT INTO referrals (referrer_id, referee_id) VALUES (?, ?)",
            (referrer_id, referee_id),
        )
        count = con.execute(
            "UPDATE users SET referral_count = referral_count + 1 WHERE user_id=? RETURNING referral_count",
            (referrer_id,),
        ).fetchone()[0]
        con.commit()
    except sqlite3.IntegrityError:
        count = con.execute(
            "SELECT referral_count FROM users WHERE user_id=?", (referrer_id,)
        ).fetchone()[0]
    con.close()
    return count


def mark_rewarded(user_id):
    """Mark user as rewarded"""
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE users SET rewarded=1 WHERE user_id=?", (user_id,))
    con.commit()
    con.close()


def generate_one_time_link(user_id):
    """Generate a unique one-time link for a user"""
    unique_token = str(uuid.uuid4())
    base_link = PRIVATE_CHANNEL_LINK
    
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO one_time_links (link_id, user_id, base_link) VALUES (?, ?, ?)",
        (unique_token, user_id, base_link),
    )
    con.commit()
    con.close()
    
    return base_link, unique_token


def get_leaderboard(limit=10):
    """Get top referrers"""
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT username, referral_count FROM users WHERE verified=1 ORDER BY referral_count DESC LIMIT ?",
        (limit,),
    ).fetchall()
    con.close()
    return rows


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    args = context.args

    # Check if user was referred
    referrer_id = None
    if args:
        try:
            referrer_id = int(args[0])
        except ValueError:
            pass

    # Create or get user
    existing = get_user(user.id)
    if not existing:
        create_user(user.id, user.username or user.first_name)

    # If referred by someone, track it
    if referrer_id and referrer_id != user.id:
        user_data = get_user(user.id)
        referrer_data = get_user(referrer_id)
        if user_data and referrer_data:
            count = increment_referral(referrer_id, user.id)
            # Check if referrer reached target
            if count >= REFERRALS_NEEDED:
                referrer = get_user(referrer_id)
                if referrer[5] == 0:  # Not yet rewarded
                    mark_rewarded(referrer_id)
                    try:
                        base_link, link_token = generate_one_time_link(referrer_id)
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 CONGRATULATIONS! 🎉\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nYou've successfully invited {REFERRALS_NEEDED} people! 🚀\n\n✨ You've unlocked exclusive access!\n\n🔗 HERE'S YOUR REWARD LINK:\n\n{base_link}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n⏰ This link is ONE-TIME only\n⏳ Once you join, it expires\n\n🎁 Don't share this link - it's unique to you!",
                            parse_mode="Markdown",
                        )
                    except Exception as e:
                        pass

    user_data = get_user(user.id)
    
    if user_data[4] == 0:  # Not verified
        # Create channel link from username
        channel_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔗 Join Our Main Challenge",
                    url=channel_link,
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ Verify & Get Referral Link",
                    callback_data="verify",
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Welcome to our Reading Challenge 1.0\n\n"
            f"To join the challenge, you have to join my main channel and invite your 5 friends!",
            reply_markup=reply_markup,
        )
    else:
        # Already verified, show referral link
        invite_link = user_data[2]
        count = user_data[3]
        progress_bar = "🟩" * min(count, REFERRALS_NEEDED) + "⬜" * (REFERRALS_NEEDED - min(count, REFERRALS_NEEDED))
        
        keyboard = [
            [
                InlineKeyboardButton(" Progress", callback_data="show_progress"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎉 Welcome back! 👋\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📤 YOUR UNIQUE REFERRAL LINK\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{invite_link}\n\n"
            f"✨ How to use it:\n"
            f"1️⃣ Copy the link\n"
            f"2️⃣ Share with friends\n"
            f"3️⃣ They click to join\n"
            f"4️⃣ You get +1 referral\n\n"
            f"📊 Progress: {count}/{REFERRALS_NEEDED}\n{progress_bar}\n\n"
            f"💡 Invite {REFERRALS_NEEDED - count} more to unlock the exclusive reward!",
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )


async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle verification button click"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_data = get_user(user.id)

    if not user_data:
        create_user(user.id, user.username or user.first_name)
        user_data = get_user(user.id)

    # Mark as verified
    verify_user(user.id)
    
    # Get user data again
    user_data = get_user(user.id)
    invite_link = user_data[2]
    progress_bar = "🟩" * 0 + "⬜" * REFERRALS_NEEDED

    keyboard = [
        [
            InlineKeyboardButton(" Progress", callback_data="show_progress"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✅ Verified Successfully!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📤 YOUR UNIQUE REFERRAL LINK\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{invite_link}\n\n"
        f"✨ How to use it:\n"
        f"1️⃣ Copy the link\n"
        f"2️⃣ Share with friends\n"
        f"3️⃣ They click to join\n"
        f"4️⃣ You get +1 referral\n\n"
        f"📊 Progress: 0/{REFERRALS_NEEDED}\n{progress_bar}\n\n"
        f"💡 Invite {REFERRALS_NEEDED} friends to unlock the exclusive reward!",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )



async def show_progress_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle show progress button click"""
    query = update.callback_query

    user = query.from_user
    user_data = get_user(user.id)

    if not user_data:
        await query.answer("Use /start first!", show_alert=True)
        return

    count = user_data[3]
    rewarded = user_data[5]
    verified = user_data[4]
    bar = "🟩" * min(count, REFERRALS_NEEDED) + "⬜" * (REFERRALS_NEEDED - min(count, REFERRALS_NEEDED))

    if not verified:
        await query.answer("Please verify first!", show_alert=True)
        return

    if count >= REFERRALS_NEEDED and rewarded:
        status_msg = f"📊 Your Referral Progress\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{bar}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🎉 {count}/{REFERRALS_NEEDED} referrals\n✅ Reward Unlocked!\n\n🎁 Use /reward to claim your exclusive link!"
    elif count >= REFERRALS_NEEDED:
        status_msg = f"📊 Your Referral Progress\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{bar}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🎉 {count}/{REFERRALS_NEEDED} referrals\n⏳ Processing reward...\n\nCheck back in a moment!"
    else:
        remaining = REFERRALS_NEEDED - count
        status_msg = f"📊 Your Referral Progress\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{bar}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📈 {count}/{REFERRALS_NEEDED} referrals\n\n💡 {remaining} more to unlock the reward!\n\n✨ Keep sharing your link!"

    await query.answer()
    await query.edit_message_text(status_msg, parse_mode="Markdown")


async def how_to_use_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle how to use button click"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"📚 HOW TO USE THE READING CHALLENGE\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 YOUR MISSION:\n"
        f"Invite {REFERRALS_NEEDED} friends to join the Reading Challenge\n\n"
        f"📖 STEP BY STEP:\n"
        f"1️⃣ You have a unique referral link\n"
        f"2️⃣ Share it with friends (copy with Copy Link button)\n"
        f"3️⃣ Your friends click the link to join\n"
        f"4️⃣ They must join the channel: @MirzajonovI\n"
        f"5️⃣ Each friend = +1 referral for you\n\n"
        f"🏆 REWARD:\n"
        f"When you reach {REFERRALS_NEEDED} referrals:\n"
        f"✅ You unlock exclusive access\n"
        f"✅ Receive a one-time private link\n"
        f"✅ Access the VIP reading community\n\n"
        f"📊 TRACK YOUR PROGRESS:\n"
        f"• Use /progress to see how many you've invited\n"
        f"• Use /leaderboard to see top referrers\n"
        f"• Use /reward to claim your prize\n\n"
        f"💡 TIPS:\n"
        f"• Each person can only join once\n"
        f"• Your link is unique to you\n"
        f"• Share on social media, messages, anywhere!\n\n"
        f"❓ QUESTIONS?\n"
        f"• Use /help for all commands\n"
        f"• Use /start to see your link again",
        parse_mode="Markdown",
    )


async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show referral progress"""
    user = update.effective_user
    user_data = get_user(user.id)

    if not user_data:
        await update.message.reply_text("Use /start first to get your referral link!")
        return

    count = user_data[3]
    rewarded = user_data[5]
    verified = user_data[4]
    bar = "🟩" * min(count, REFERRALS_NEEDED) + "⬜" * (REFERRALS_NEEDED - min(count, REFERRALS_NEEDED))

    if not verified:
        await update.message.reply_text("⚠️ Please verify first! Use /start")
        return

    if count >= REFERRALS_NEEDED and rewarded:
        status_msg = f"📊 Your Referral Progress\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{bar}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🎉 {count}/{REFERRALS_NEEDED} referrals\n✅ Reward Unlocked!\n\n🎁 Use /reward to claim your exclusive link!"
    elif count >= REFERRALS_NEEDED:
        status_msg = f"📊 Your Referral Progress\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{bar}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🎉 {count}/{REFERRALS_NEEDED} referrals\n⏳ Processing reward...\n\nCheck back in a moment!"
    else:
        remaining = REFERRALS_NEEDED - count
        status_msg = f"📊 Your Referral Progress\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{bar}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📈 {count}/{REFERRALS_NEEDED} referrals\n\n💡 {remaining} more to unlock the reward!\n\n✨ Keep sharing your link!"

    await update.message.reply_text(status_msg, parse_mode="Markdown")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top referrers"""
    rows = get_leaderboard()
    if not rows:
        await update.message.reply_text("🏆 No referrals yet!")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 Top Referrers\n"]
    for i, (username, count) in enumerate(rows):
        prefix = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{prefix} @{username} — {count} referrals")

    await update.message.reply_text("\n".join(lines))


async def reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user their one-time reward link"""
    user = update.effective_user
    user_data = get_user(user.id)

    if not user_data:
        await update.message.reply_text("Use /start first to get started!")
        return

    _, _, _, count, _, rewarded = user_data

    if count < REFERRALS_NEEDED:
        await update.message.reply_text(
            f"❌ You haven't unlocked the reward yet!\n\n"
            f"Current progress: {count}/{REFERRALS_NEEDED} referrals\n\n"
            f"Keep inviting friends using your referral link!"
        )
        return

    if rewarded == 0:
        await update.message.reply_text("⏳ Generating your one-time link...")
        return

    # Get user's one-time links
    con = sqlite3.connect(DB_PATH)
    link = con.execute(
        "SELECT base_link, used FROM one_time_links WHERE user_id=? AND used=0 LIMIT 1",
        (user.id,),
    ).fetchone()
    con.close()

    if link:
        base_link, used_status = link
        await update.message.reply_text(
            f"🎉 Here's your exclusive one-time link:\n\n"
            f"`{base_link}`\n\n"
            f"⏰ This link expires after one use!\n\n"
            f"⚠️ Save it now - it can only be used once!"
        )
    else:
        await update.message.reply_text(
            "Your one-time reward link has already been used! 🎊\n\n"
            "You've successfully accessed the exclusive channel!"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help menu"""
    await update.message.reply_text(
        "📱 Available Commands:\n\n"
        "/start - Get your referral link\n"
        "/progress - Check your referral progress\n"
        "/leaderboard - View top referrers\n"
        "/reward - View your one-time reward link\n"
        "/help - Show this message"
    )


def main():
    """Main bot function"""
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("progress", progress))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("reward", reward))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify$"))
    app.add_handler(CallbackQueryHandler(show_progress_callback, pattern="^show_progress$"))

    print("🤖 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
