import os
import logging
import asyncio
import threading
import sys
import time
import tempfile
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import openai

# --- CONFIGURATION ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
PORT = int(os.environ.get("PORT", 8080))

if not TOKEN or not OPENAI_API_KEY:
    print("ERROR: BOT_TOKEN or OPENAI_API_KEY is not set!")
    sys.exit(1)

# Initialize OpenAI
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- GAME DATA (Famous Players) ---
PLAYERS = [
    {"name": "Lionel Messi", "image": "https://upload.wikimedia.org/wikipedia/commons/c/c1/Lionel_Messi_20180626.jpg"},
    {"name": "Cristiano Ronaldo", "image": "https://upload.wikimedia.org/wikipedia/commons/8/8c/Cristiano_Ronaldo_2018.jpg"},
    {"name": "Neymar", "image": "https://upload.wikimedia.org/wikipedia/commons/b/bc/Bra-Cr0_%287%29.jpg"},
    {"name": "Kylian Mbappe", "image": "https://upload.wikimedia.org/wikipedia/commons/5/57/Kylian_Mbapp%C3%A9_2018.jpg"},
    {"name": "Erling Haaland", "image": "https://upload.wikimedia.org/wikipedia/commons/0/07/Erling_Haaland_2023_%28cropped%29.jpg"},
    {"name": "Zinedine Zidane", "image": "https://upload.wikimedia.org/wikipedia/commons/f/f3/Zinedine_Zidane_by_Tasnim_01.jpg"},
    {"name": "Ronaldinho", "image": "https://upload.wikimedia.org/wikipedia/commons/e/e8/Ronaldinho_11feb2007.jpg"}
]

# In-memory storage
user_sessions = {}

def get_session(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "battery_end": 0,
            "attempts": 0,
            "current_player": None,
            "state": "IDLE"
        }
    return user_sessions[user_id]

def get_masked_name(name):
    """Creates a hint like L_____ M____"""
    parts = name.split()
    masked_parts = []
    for part in parts:
        masked_parts.append(part[0] + "_" * (len(part) - 1))
    return " ".join(masked_parts)

# --- BOT LOGIC ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ *Football Star Challenge* ⚽\n\n"
        "1. I show a player and a name hint.\n"
        "2. You **Type** the full name.\n"
        "3. You **Speak** the name to win!\n\n"
        "⚠️ *Rules:*\n"
        "• 2 chances per player.\n"
        "• 2-hour recharge if you fail.\n\n"
        "Type /play to start!"
    )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = get_session(user_id)

    if time.time() < session["battery_end"]:
        remaining = int((session["battery_end"] - time.time()) // 60)
        return await update.message.reply_text(f"🪫 *Battery Low!* Recharging... {remaining} mins left.")

    player = random.choice(PLAYERS)
    session["current_player"] = player
    session["attempts"] = 0
    session["state"] = "WAITING_TEXT"

    hint = get_masked_name(player["name"])
    await update.message.reply_photo(
        photo=player["image"],
        caption=f"Guess this legend!\n\nHint: `{hint}`\n\n⌨️ *Type the full name:*",
        parse_mode='Markdown'
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = get_session(user_id)

    if session["state"] != "WAITING_TEXT":
        return

    user_guess = update.message.text.lower().strip()
    correct_name = session["current_player"]["name"].lower()

    if correct_name in user_guess:
        session["state"] = "WAITING_VOICE"
        await update.message.reply_text(
            f"🎯 *Great!* Now send a **Voice Note** saying '{session['current_player']['name']}' to confirm!",
            parse_mode='Markdown'
        )
    else:
        session["attempts"] += 1
        if session["attempts"] < 2:
            await update.message.reply_text("❌ *Wrong name!* Try one more time... ⌨️")
        else:
            session["battery_end"] = time.time() + 7200
            session["state"] = "IDLE"
            await update.message.reply_text(f"❌ *Failed!* It was {session['current_player']['name']}. 🪫 Battery empty. Wait 2 hours.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = get_session(user_id)

    if session["state"] != "WAITING_VOICE":
        return

    status_msg = await update.message.reply_text("👂 Listening...")

    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tf:
            temp_path = tf.name
            await file.download_to_drive(temp_path)

        with open(temp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        
        voice_guess = transcript.text.lower().strip()
        correct_name = session["current_player"]["name"].lower()
        os.remove(temp_path)

        if any(word in voice_guess for word in correct_name.split()):
            await status_msg.edit_text(f"✅ *FANTASTIC!* You got {session['current_player']['name']}! 🎉\n/play again?")
            session["state"] = "IDLE"
        else:
            session["attempts"] += 1
            if session["attempts"] < 2:
                await status_msg.edit_text("❌ *I couldn't hear that correctly.* One more chance! 🎙️")
            else:
                session["battery_end"] = time.time() + 7200
                session["state"] = "IDLE"
                await status_msg.edit_text(f"❌ *Voice failed!* Battery exhausted. Wait 2 hours.")

    except Exception as e:
        logger.error(f"Voice Error: {e}")
        await status_msg.edit_text("⚠️ Error. Try again!")

# --- RENDER HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Football Legend Bot Active")
    def log_message(self, format, *args): return

def run_health_check():
    httpd = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    httpd.serve_forever()

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    async with app:
        await app.initialize()
        await app.start()
        await app.bot.delete_webhook(drop_pending_updates=True)
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
