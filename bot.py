import os
import logging
import asyncio
import threading
import sys
import yt_dlp
import tempfile
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
    print("ERROR: TELEGRAM_BOT_TOKEN is not set in Environment Variables!")
    sys.exit(1)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- MUSIC SEARCH LOGIC ---
def search_and_download(query):
    # Use a unique temporary filename to avoid conflicts
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, "song.mp3")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(temp_dir, 'song.%(ext)s'),
        'noplaylist': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'default_search': 'ytsearch1',
        'quiet': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        video_title = info['entries'][0]['title'] if 'entries' in info else info.get('title', 'Music')
        # yt-dlp might change extension to .mp3 after post-processing
        actual_file = os.path.join(temp_dir, "song.mp3")
        return actual_file, video_title

# --- BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 *AI Music Assistant* 🎵\n\n"
        "Send me a song name or artist, and I'll find it for you!\n"
        "Example: `Blinding Lights Weeknd`",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    status_msg = await update.message.reply_text(f"🔍 Searching for: {user_query}...")

    try:
        loop = asyncio.get_event_loop()
        file_path, title = await loop.run_in_executor(None, search_and_download, user_query)
        
        await status_msg.edit_text(f"📥 Found: {title}\nUploading to Telegram...")
        
        with open(file_path, 'rb') as audio:
            await update.message.reply_audio(
                audio=audio, 
                title=title,
                caption=f"Enjoy! 🎧"
            )
            
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Bot Error: {e}")
        await status_msg.edit_text("❌ Sorry, I couldn't process that music. Check Render logs for details.")

# --- RENDER HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")
    def log_message(self, format, *args): return

def run_health_check():
    httpd = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    httpd.serve_forever()

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    async with application:
        await application.initialize()
        await application.start()
        logger.info("Music Bot Started!")
        await application.updater.start_polling()
        while True: await asyncio.sleep(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
