# Telegram Referral Bot

A modern Telegram bot for managing referrals with button-based verification.

## Features

🔐 **Button Verification** - Users verify channel membership with one click
🔗 **Unique Referral Links** - Each user gets a personal referral link
📊 **Progress Tracking** - Visual progress bars showing referral count
🏆 **Leaderboard** - Real-time ranking of top referrers
🎉 **Auto Rewards** - Automatic reward notifications when target reached
💾 **SQLite Database** - Persistent user and referral data

## Prerequisites

- Python 3.8+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Bot must be admin in your channel

## Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
```

Edit `.env` with your values:
```env
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
BOT_USERNAME=your_bot_username
CHANNEL_USERNAME=@your_channel_name
PRIVATE_CHANNEL_LINK=https://t.me/+AbCdEfG123456789
REFERRALS_NEEDED=5
```

### 3. Make Bot Admin
Add your bot as admin in your Telegram channel (needed to verify members).

### 4. Run Locally
```bash
python3 bot.py
```

## How It Works

1. User sends `/start`
2. Bot shows verification button
3. User clicks button to verify membership in the public channel
4. User receives unique referral link
5. When referring 5 friends who join via link → one-time reward link is automatically sent
6. Reward link can only be used once and expires after joining
7. Check progress with `/progress` and `/leaderboard`

## One-Time Reward Links

Each user who reaches the referral target gets a unique, one-time-use invite link to the private reward channel:
- 🆔 Each link is unique per user
- ⏰ Once used/joined, the link expires (tracked in database)
- 🔐 Links are sent automatically when reward is unlocked
- 🔗 Users can view their link anytime with `/reward` command

**Note:** For full one-time enforcement, consider adding a web proxy that redirects and tracks link usage before passing to Telegram.

## Deployment

### Render.com
1. Push to GitHub
2. Connect repo to Render
3. Set environment variables in dashboard
4. Deploy with `render.yaml` config

### Heroku
```bash
heroku config:set BOT_TOKEN=your_token
heroku config:set BOT_USERNAME=your_bot
heroku config:set CHANNEL_USERNAME=@your_channel
heroku config:set PRIVATE_CHANNEL_LINK=https://t.me/+your_link

git push heroku main
```

## Commands

- `/start` - Get referral link (with verification)
- `/progress` - Check referral count
- `/reward` - View your one-time reward link
- `/leaderboard` - View top referrers
- `/help` - Show all commands

## Database

Three tables in SQLite:
- `users` - User info, referral links, counts, and reward status
- `referrals` - Tracks which user referred which new member
- `one_time_links` - Tracks unique one-time reward links (unique per user, marked as used after joining)

## Security

⚠️ Never commit `.env` file with real credentials
- Add `.env` to `.gitignore`
- Use environment variables for deployment
- Bot token should only be in `.env`
