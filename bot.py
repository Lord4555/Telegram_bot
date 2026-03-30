import os
import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ChatMemberHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN", "8745088680:AAFWQX27bp9U8YiSYcsUSqoXINHRpAskexA")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@MirzajonovI")
REWARD_LINK = os.getenv("REWARD_LINK", "https://t.me/+6M50i5FH2M43YWIy")
REFERRALS_NEEDED = 5

DB_PATH = "referrals.db"

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, invite_link TEXT, count INTEGER DEFAULT 0, rewarded INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS link_map (invite_link TEXT PRIMARY KEY, user_id INTEGER)""")
    con.commit()
    con.close()

def get_user(user_id):
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return row

def upsert_user(user_id, username, invite_link):
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT INTO users (user_id, username, invite_link, count, rewarded) VALUES (?,?,?,0,0) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username", (user_id, username, invite_link))
    con.execute("INSERT OR IGNORE INTO link_map (invite_link, user_id) VALUES (?,?)", (invite_link, user_id))
    con.commit()
    con.close()

def get_owner_by_link(invite_link):
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT user_id FROM link_map WHERE invite_link=?", (invite_link,)).fetchone()
    con.close()
    return row[0] if row else None

def increment_count(user_id):
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE users SET count=count+1 WHERE user_id=?", (user_id,))
    con.commit()
    row = con.execute("SELECT count, rewarded FROM users WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return row

def mark_rewarded(user_id):
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE users SET rewarded=1 WHERE user_id=?", (user_id,))
    con.commit()
    con.close()

def get_leaderboard(limit=10):
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT username, count FROM users ORDER BY count DESC LIMIT ?", (limit,)).fetchall()
    con.close()
    return rows

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing = get_user(user.id)
    if existing and existing[2]:
        link = existing[2]
        count = existing[3]
        await update.message.reply_text(f"👋 Welcome back, {user.first_name}!\n\nYour referral link:\n{link}\n\nProgress: {count}/{REFERRALS_NEEDED} referrals")
        return
    try:
        invite = await context.bot.create_chat_invite_link(chat_id=CHANNEL_USERNAME, name=str(user.id), creates_join_request=False)
        link = invite.invite_link
    except Exception:
        await update.message.reply_text("⚠️ Could not create an invite link. Make sure the bot is an admin in the channel.")
        return
    upsert_user(user.id, user.username or user.first_name, link)
    await update.message.reply_text(f"👋 Hey {user.first_name}! Here's your unique referral link:\n\n{link}\n\nInvite {REFERRALS_NEEDED} friends to unlock your reward!\nCheck your progress anytime with /progress")

async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    row = get_user(user.id)
    if not row:
        await update.message.reply_text("Use /start first to get your referral link!")
        return
    _, _, link, count, rewarded = row
    bar = "🟩" * min(count, REFERRALS_NEEDED) + "⬜" * (REFERRALS_NEEDED - min(count, REFERRALS_NEEDED))
    status = "✅ Reward unlocked!" if rewarded else f"{count}/{REFERRALS_NEEDED} referrals"
    await update.message.reply_text(f"📊 Your Referral Progress\n\n{bar}\n{status}\n\nYour link:\n{link}")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_leaderboard()
    if not rows:
        await update.message.reply_text("No referrals yet!")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 Top Referrers\n"]
    for i, (username, count) in enumerate(rows):
        prefix = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{prefix} @{username} — {count} referrals")
    await update.message.reply_text("\n".join(lines))

async def track_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    if old_status in ("member", "administrator", "creator"):
        return
    if new_status not in ("member", "administrator"):
        return
    invite_link_obj = result.invite_link
    if not invite_link_obj:
        return
    link = invite_link_obj.invite_link
    owner_id = get_owner_by_link(link)
    if not owner_id:
        return
    count, rewarded = increment_count(owner_id)
    try:
        await context.bot.send_message(chat_id=owner_id, text=f"✅ Someone joined using your link!\nProgress: {count}/{REFERRALS_NEEDED}")
        if count >= REFERRALS_NEEDED and not rewarded:
            mark_rewarded(owner_id)
            await context.bot.send_message(chat_id=owner_id, text=f"🎉 Congratulations! You've invited {REFERRALS_NEEDED} people!\n\nHere is your reward:\n{REWARD_LINK}")
    except Exception:
        pass

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("progress", progress))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(ChatMemberHandler(track_join, ChatMemberHandler.CHAT_MEMBER))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
