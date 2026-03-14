import os
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- Pelayan Web untuk Render.com (Health Check) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Cikgu Fesyen Cina Bot sedang aktif! Jom bergaya!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Kandungan Bot (Belajar Fesyen Cina dalam Bahasa Melayu) ---

LEARNING_CONTENT = [
    # Hari 1: Cheongsam & Qipao (Wanita)
    "👗 *Hari 1: Keanggunan Cheongsam & Qipao*\n\n"
    "Cheongsam (sebutan Kantonis) atau Qipao (sebutan Mandarin) adalah pakaian ikonik wanita Cina.\n\n"
    "*Ciri-ciri Utama:*\n"
    "- *Kolar Mandarin:* Kolar tinggi yang melambangkan kesopanan.\n"
    "- *Butang Pankou:* Butang simpulan tangan yang berseni.\n"
    "- *Belahan Tepi:* Memudahkan pergerakan dan memberi imej elegan.\n\n"
    "*Tips Gaya:* Untuk majlis formal di Malaysia, pilih fabrik sutera atau broked. Untuk gaya harian, pilih kapas dengan corak floral yang ringkas.",

    # Hari 2: Samfu & Tang Suit (Lelaki)
    "👔 *Hari 2: Samfu & Tang Suit untuk Lelaki*\n\n"
    "Lelaki juga mempunyai pakaian tradisi yang sangat segak!\n\n"
    "*Jenis Pakaian:*\n"
    "- *Samfu:* Terdiri daripada baju dan seluar (bermaksud 'baju seluar'). Sesuai untuk gaya santai atau kerja.\n"
    "- *Tang Suit:* Lebih formal, biasanya mempunyai lapis dalam dan sulaman naga atau awan yang rumit.\n\n"
    "*Tips Gaya:* Pastikan bahu baju terletak dengan betul. Tang Suit biasanya dipakai sedikit longgar untuk keselesaan dan nampak lebih berwibawa.",

    # Hari 3: Simbolisme Warna & Aksesori
    "🧧 *Hari 3: Makna Warna & Pemilihan Aksesori*\n\n"
    "Dalam budaya Cina, warna memainkan peranan penting dalam nasib dan gaya!\n\n"
    "*Makna Warna:*\n"
    "- *Merah:* Melambangkan tuah, kegembiraan, dan kemakmuran (Wajib untuk Tahun Baru Cina!).\n"
    "- *Emas:* Melambangkan kekayaan dan kemuliaan.\n\n"
    "*Aksesori:* Wanita boleh memadankan Cheongsam dengan cucuk sanggul atau kipas tangan. Elakkan memakai pakaian berwarna hitam atau putih sepenuhnya semasa perayaan kerana ia sering dikaitkan dengan kedukaan.",
]

QUIZ_DATA = [
    {
        "question": "Apakah nama butang simpulan tangan yang terdapat pada baju Cheongsam?",
        "options": ["Butang Pankou", "Butang Plastik", "Butang Zip"],
        "correct": 0
    },
    {
        "question": "Apakah maksud perkataan 'Samfu'?",
        "options": ["Baju Melayu", "Baju dan Seluar", "Kain Sarung"],
        "correct": 1
    },
    {
        "question": "Warna manakah yang melambangkan tuah dan kemakmuran dalam budaya Cina?",
        "options": ["Hitam", "Biru", "Merah"],
        "correct": 2
    }
]

# --- Logik Bot ---
user_progress = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_progress:
        user_progress[user_id] = {"day": 0, "quiz_day": 0, "last_learned_date": None}
    
    keyboard = [
        ["Belajar Gaya Cina 👘", "Kuiz Fesyen 🧠"],
        ["Rehat Dulu ☕"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = (
        f"Ni Hao! Selamat Datang ke *Cikgu Fesyen Cina Bot*! 👨‍🎨🧧\n\n"
        "Saya akan bantu anda memahami cara pemakaian tradisi Cina yang betul dan bergaya.\n"
        "Pilih menu di bawah untuk mula belajar."
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id not in user_progress:
        user_progress[user_id] = {"day": 0, "quiz_day": 0, "last_learned_date": None}

    if text == "Belajar Gaya Cina 👘":
        current_day = user_progress[user_id]["day"]
        today = str(datetime.now().date())
        
        if user_progress[user_id]["last_learned_date"] == today:
            await update.message.reply_text("Bagus! Anda dah belajar gaya hari ini. Esok kita belajar gaya lain pula ya! ✨")
            return

        if current_day < len(LEARNING_CONTENT):
            await update.message.reply_text(LEARNING_CONTENT[current_day], parse_mode='Markdown')
            user_progress[user_id]["day"] += 1
            user_progress[user_id]["last_learned_date"] = today
        else:
            await update.message.reply_text("Tahniah! Anda kini pakar gaya pemakaian Cina. Tunggu modul tambahan nanti!")

    elif text == "Kuiz Fesyen 🧠":
        current_quiz_idx = user_progress[user_id]["quiz_day"]
        
        if current_quiz_idx < len(QUIZ_DATA):
            q = QUIZ_DATA[current_quiz_idx]
            buttons = [[InlineKeyboardButton(opt, callback_data=f"quiz_{idx}")] for idx, opt in enumerate(q["options"])]
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(f"Soalan Kuiz Fesyen:\n\n{q['question']}", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Anda telah menjawab semua soalan kuiz dengan cemerlang! 🌟")

    elif text == "Rehat Dulu ☕":
        await update.message.reply_text("Baiklah, pergi minum teh dulu! Nanti kita sambung sesi bergaya. Zai jian! 👋")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    current_quiz_idx = user_progress[user_id]["quiz_day"]
    if current_quiz_idx >= len(QUIZ_DATA):
        return

    selected_option = int(query.data.split("_")[1])
    if selected_option == QUIZ_DATA[current_quiz_idx]["correct"]:
        feedback = "Hebat! Jawapan anda tepat. ✅\n\n"
    else:
        feedback = "Alahai, hampir tepat! Cuba lagi nanti.\n\n"
    
    feedback += "Pengetahuan tentang budaya menjadikan kita lebih menghormati satu sama lain! 🌟"
    user_progress[user_id]["quiz_day"] += 1
    await query.edit_message_text(text=feedback)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TOKEN:
        print("RALAT: TELEGRAM_TOKEN tidak dijumpai dalam persekitaran.")
        exit(1)
    
    print("Memulakan Cikgu Fesyen Cina Bot...")
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    application.run_polling()
