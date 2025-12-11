import os
import sys
import asyncio
import threading
import tempfile
import requests
import logging
from flask import Flask
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# ==========================================
# 🚑 ផ្នែកពិសេស៖ FIX PYTHON 3.13 & TIMEZONE
# ==========================================
try:
    import pytz
    import apscheduler.util
    def force_utc_timezone(timezone): return pytz.UTC
    apscheduler.util.astimezone = force_utc_timezone
except Exception: pass
# ==========================================

import google.generativeai as genai
from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ==========================================
# 🌐 WEBSERVER
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot is Alive and Running Securely!"

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 🔐 CONFIGURATION
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not TELEGRAM_TOKEN or not GOOGLE_API_KEY:
    print("❌ Error: រកមិនឃើញ TELEGRAM_TOKEN ឬ GOOGLE_API_KEY ទេ។")
    sys.exit(1)

genai.configure(api_key=GOOGLE_API_KEY)

# 🔍 Auto-Detect Model
def get_best_model():
    try:
        all_models = list(genai.list_models())
        available = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods]
        priority = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
        for p in priority:
            for name in available:
                if p in name: return name
        return available[0] if available else 'gemini-1.5-flash'
    except: return 'gemini-1.5-flash'

REAL_MODEL_NAME = get_best_model()
DISPLAY_NAME = "✨ AI Vision Pro (v2.5)" 

# 📝 PROMPT
FORENSIC_PROMPT = """
You are an AI Forensic Expert. Analyze the provided image/video to determine if it is AI-generated.

IMPORTANT: Response in KHMER LANGUAGE (ភាសាខ្មែរ) ONLY.
Structure:
1. **កម្រិតនៃការសង្ស័យ (Likelihood)**: 0-100%.
2. **ភស្តុតាងដែលរកឃើញ (Visual Evidence)**: Describe artifacts (hands, eyes, lighting, text) in Khmer.
3. **សន្និដ្ឋាន (Conclusion)**: Real or Fake summary in Khmer.
"""

# ==========================================
# 📱 MENU & LOGIC (កែសម្រួលថ្មី)
# ==========================================

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "🏠 ម៉ឺនុយដើម / Main Menu"),
        BotCommand("help", "📖 របៀបប្រើ / How to use"),
        BotCommand("about", "ℹ️ អំពី Bot / About"),
    ])

# 1. Function សម្រាប់ Help (ប្រើបានទាំង Command និង Button)
async def send_help_message(update: Update, is_callback=False):
    text = (
        "📚 **របៀបប្រើប្រាស់៖**\n\n"
        "1. ផ្ញើ **រូបភាព** (Photo) មកផ្ទាល់\n"
        "2. ផ្ញើ **វីដេអូ** (Video) មកផ្ទាល់\n"
        "3. ផ្ញើ **Link** (URL) ពីវេបសាយនានា\n\n"
        "🔍 Bot នឹងវិភាគរកស្នាម AI ដោយស្វ័យប្រវត្តិជាភាសាខ្មែរ! 🚀"
    )
    if is_callback:
        await update.callback_query.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

# 2. Function សម្រាប់ About (ប្រើបានទាំង Command និង Button)
async def send_about_message(update: Update, is_callback=False):
    text = (
        "ℹ️ **អំពី Bot នេះ៖**\n\n"
        "Bot នេះប្រើប្រាស់ **បច្ចេកវិទ្យាឆ្លាតវ៉ៃ**។\n"
        "👨‍💻 បង្កើតដោយ៖ **លោក ស្រ៊ាង ស៊ីណាន**\n"
        "គោលបំណង៖ ជួយសម្គាល់ខ្លឹមសារ Deepfake/AI Generated។"
    )
    if is_callback:
        await update.callback_query.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📸 របៀបប្រើប្រាស់", callback_data='help'),
            InlineKeyboardButton("ℹ️ អំពី Bot", callback_data='about')
        ],
        [InlineKeyboardButton("👨‍💻 អ្នកបង្កើត (Developer)", url="https://t.me/Sinan_Sreang")] 
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"👋 **សួស្តីបង! នេះគឺ Bot សម្រាប់ធ្វើការវិភាគរូបភាព ឫ វីឌីអូ AI** 🤖\n"
        f"⚙️ Model: `{DISPLAY_NAME}`\n\n"
        "សូមផ្ញើ **រូបភាព**, **Video**, ឬ **Link** មកខ្ញុំដើម្បីវិភាគ។\n\n"
        "👇 *លោកអ្នកអាចចុច Menu ខាងក្រោម ឬប៊ូតុងនេះ៖*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Handler សម្រាប់ប៊ូតុងចុច (Inline Buttons)
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # បំបាត់សញ្ញា Loading
    
    if query.data == 'help':
        await send_help_message(update, is_callback=True)
    elif query.data == 'about':
        await send_about_message(update, is_callback=True)

# Handler សម្រាប់ Command (/help, /about)
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_help_message(update, is_callback=False)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_about_message(update, is_callback=False)

async def process_media(temp_path, mime, status_msg):
    try:
        uploaded = genai.upload_file(temp_path, mime_type=mime)
        while uploaded.state.name == "PROCESSING":
            await asyncio.sleep(2)
            uploaded = genai.get_file(uploaded.name)
        
        if uploaded.state.name == "FAILED": raise Exception("Google AI Read Failed")

        model = genai.GenerativeModel(REAL_MODEL_NAME, system_instruction=FORENSIC_PROMPT)
        res = model.generate_content([uploaded, "Analyze this media in Khmer."])
        
        await status_msg.edit_text(f"🤖 **លទ្ធផលវិភាគ៖**\n\n{res.text}")
    except Exception as e:
        await status_msg.edit_text(f"⚠️ Error: {str(e)[:200]}")
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = update.effective_chat.id
    
    # Handle Link
    if msg.text and msg.text.startswith(("http", "www")):
        status = await context.bot.send_message(chat_id, "🔗 កំពុងបើក Link... ⏳", reply_to_message_id=msg.id)
        try:
            r = requests.get(msg.text, stream=True, timeout=10)
            ct = r.headers.get('Content-Type', '')
            ext, mime = (".mp4", "video/mp4") if 'video' in ct else (".jpg", "image/jpeg")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in r.iter_content(8192): tmp.write(chunk)
                path = tmp.name
            
            await status.edit_text("🔍 កំពុងវិភាគ... ⏳")
            await process_media(path, mime, status)
        except Exception as e:
            await status.edit_text(f"❌ បើក Link មិនកើតទេ: {e}")
        return

    # Handle Photo/Video
    if not (msg.photo or msg.video):
        await msg.reply_text("❌ សូមផ្ញើរូបភាព, វីដេអូ ឬ Link ប៉ុណ្ណោះ។")
        return

    status = await context.bot.send_message(chat_id, "📥 កំពុងទទួលឯកសារ... ⏳", reply_to_message_id=msg.id)
    try:
        f_obj = await (msg.photo[-1].get_file() if msg.photo else msg.video.get_file())
        ext, mime = (".jpg", "image/jpeg") if msg.photo else (".mp4", "video/mp4")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            await f_obj.download_to_drive(tmp.name)
            path = tmp.name
            
        await status.edit_text("🔍 កំពុងវិភាគ... ⏳")
        await process_media(path, mime, status)
    except Exception as e:
        await status.edit_text(f"❌ Error: {e}")

def main():
    print("🚀 Starting Web Server & Bot...")
    threading.Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
    # ✅ កែសម្រួលចំណុចសំខាន់ (ហៅ Function ត្រឹមត្រូវ)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))   # កែពី lambda មកជា function
    app.add_handler(CommandHandler("about", about_command)) # កែពី lambda មកជា function

    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | (filters.TEXT & filters.Entity("url")), handle_message))
    
    app.run_polling()

if __name__ == "__main__":
    main()
