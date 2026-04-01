import os
import logging
import asyncio
import threading
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

if not TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN is not set!")
    sys.exit(1)

# Initialize OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- BOT LOGIC ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎙️ *Welcome to AudioGen AI* 🎙️\n\n"
        "I can turn your text into professional audio/music narration.\n\n"
        "✨ *How to use:*\n"
        "Just send me any text, and I will generate a high-quality audio file for you using AI."
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def handle_text_to_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if len(user_text) > 500:
        return await update.message.reply_text("⚠️ Text is too long! Please keep it under 500 characters.")

    status_msg = await update.message.reply_text("🔊 *Generating your audio...* Please wait.", parse_mode='Markdown')

    try:
        # Use OpenAI TTS-1 model for high-quality audio generation
        # You can change voice to 'alloy', 'echo', 'fable', 'onyx', 'nova', or 'shimmer'
        response = client.audio.speech.create(
            model="tts-1",
            voice="onyx", 
            input=user_text
        )

        # Save to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tf:
            temp_path = tf.name
            response.stream_to_file(temp_path)

        # Send the audio file to the user
        await update.message.reply_audio(
            audio=open(temp_path, 'rb'),
            title="Generated Audio",
            caption="Here is your AI-generated audio! 🎧"
        )

        # Cleanup
        os.remove(temp_path)
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Audio Generation Error: {e}")
        await status_msg.edit_text("❌ Sorry, I failed to generate audio. Make sure your OpenAI API Key is valid and has credits.")

# --- RENDER HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Audio Bot is running")
    def log_message(self, format, *args): return

def run_health_check():
    httpd = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    httpd.serve_forever()

# --- MAIN ---
async def main():
    # Start health check thread
    threading.Thread(target=run_health_check, daemon=True).start()
    
    application = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_to_audio))
    
    async with application:
        await application.initialize()
        await application.start()
        
        # Clear conflicts
        await application.bot.delete_webhook(drop_pending_updates=True)
        
        logger.info("AudioGen Bot Started!")
        await application.updater.start_polling(drop_pending_updates=True)
        
        while True:
            await asyncio.sleep(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
