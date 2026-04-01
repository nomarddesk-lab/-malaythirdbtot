import os
import logging
import asyncio
import threading
import sys
import yt_dlp
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --- CONFIGURATION ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
PORT = int(os.environ.get("PORT", 8080))

if not TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN is not set!")
    sys.exit(1)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- MUSIC SEARCH LOGIC ---
def search_and_download(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'music_download.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'default_search': 'ytsearch1',
        'quiet': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        # Handle search results
        if 'entries' in info:
            video = info['entries'][0]
        else:
            video = info
            
        return f"music_download.mp3", video.get('title', 'Unknown Title')

# --- BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I am your AI Music Assistant.\n\n"
        "Just send me the name of a song or a mood (e.g., 'chill jazz'), "
        "and I will find and play it for you!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    status_msg = await update.message.reply_text(f"🔍 Searching for '{user_query}'...")

    try:
        # Run the search in a separate thread to keep the bot responsive
        loop = asyncio.get_event_loop()
        file_path, title = await loop.run_in_executor(None, search_and_download, user_query)
        
        await status_msg.edit_text(f"🎵 Found: *{title}*\n📤 Uploading...")
        
        with open(file_path, 'rb') as audio:
            await update.message.reply_audio(
                audio=audio, 
                title=title,
                caption=f"Here is your music: {title} 🎧"
            )
            
        # Clean up file
        os.remove(file_path)
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Music Error: {e}")
        await status_msg.edit_text("❌ Sorry, I couldn't find or process that music.")

# --- RENDER HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Music Bot is running")
    def log_message(self, format, *args): return

def run_health_check():
    httpd = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    httpd.serve_forever()

# --- MAIN ---
async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    async with application:
        await application.initialize()
        await application.start()
        logger.info("Music Assistant is live!")
        await application.updater.start_polling()
        while True: await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
