import os
import logging
import asyncio
import threading
import sys
import random
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# --- CONFIGURATION ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
PORT = int(os.environ.get("PORT", 8080))

if not TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN is not set in Environment Variables!")
    sys.exit(1)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- GAME DATA ---
FISH_TYPES = [
    {"name": "🐟 Common Minnow", "rarity": "Common", "chance": 60, "points": 10},
    {"name": "🐠 Tropical Clownfish", "rarity": "Uncommon", "chance": 25, "points": 25},
    {"name": "🐡 Pufferfish", "rarity": "Rare", "chance": 10, "points": 75},
    {"name": "🦈 Great White Shark", "rarity": "Legendary", "chance": 4, "points": 500},
    {"name": "🐙 Giant Squid", "rarity": "Mythical", "chance": 1, "points": 2000},
]

# Simple in-memory storage (Resets on restart)
user_data = {}

def get_user(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            "score": 0,
            "energy": 5,
            "last_regen": time.time(),
            "total_caught": 0
        }
    
    # Regenerate energy: 1 energy every 10 minutes
    user = user_data[user_id]
    now = time.time()
    elapsed = now - user["last_regen"]
    regen_amount = int(elapsed // 600)
    
    if regen_amount > 0:
        user["energy"] = min(5, user["energy"] + regen_amount)
        user["last_regen"] = now
        
    return user

# --- BOT LOGIC ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    text = (
        "🎣 *WELCOME TO FISH DASH* 🌊\n\n"
        "Cast your line and catch rare sea creatures!\n\n"
        f"🎒 *Your Stats:*\n"
        f"✨ Score: {user['score']}\n"
        f"🐟 Caught: {user['total_caught']}\n"
        f"⚡ Energy: {user['energy']}/5\n\n"
        "Use /fish to start catching!"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def fish_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if user["energy"] <= 0:
        await update.message.reply_text("🪫 *Out of Energy!*\nWait for your energy to refill (1 per 10 mins).", parse_mode='Markdown')
        return

    user["energy"] -= 1
    
    # Handle both message command and button callback
    if update.message:
        status_msg = await update.message.reply_text("🎣 Casting line... 🌊")
    else:
        status_msg = await update.callback_query.edit_message_text("🎣 Casting line... 🌊")
        
    await asyncio.sleep(2) # Visual suspense

    # Determine catch
    roll = random.randint(1, 100)
    cumulative = 0
    caught_fish = None

    for fish in sorted(FISH_TYPES, key=lambda x: x['chance']):
        cumulative += fish['chance']
        if roll <= cumulative:
            caught_fish = fish
            break
    
    if not caught_fish: # Fallback to common
        caught_fish = FISH_TYPES[0]

    user["score"] += caught_fish["points"]
    user["total_caught"] += 1

    result_text = (
        f"🎈 *YOU CAUGHT SOMETHING!* 🎈\n\n"
        f"Type: {caught_fish['name']}\n"
        f"Rarity: *{caught_fish['rarity']}*\n"
        f"Points: +{caught_fish['points']}\n\n"
        f"⚡ Energy Left: {user['energy']}/5\n"
        f"💰 Total Score: {user['score']}"
    )

    keyboard = [[InlineKeyboardButton("Fish Again! 🎣", callback_data="play_again")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await status_msg.edit_text(result_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(result_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "play_again":
        await fish_command(update, context)

# --- RENDER HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Fish Bot is running")
    def log_message(self, format, *args): return

def run_health_check():
    httpd = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    httpd.serve_forever()

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('fish', fish_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    async with application:
        await application.initialize()
        await application.start()
        
        # Ensure no conflict
        await application.bot.delete_webhook(drop_pending_updates=True)
        
        logger.info("Fish Catching Bot Started!")
        await application.updater.start_polling(drop_pending_updates=True)
        
        while True:
            await asyncio.sleep(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
