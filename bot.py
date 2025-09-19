import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import sqlite3
import qrcode
from io import BytesIO
from PIL import Image
import uuid
from database import init_db  # Import database initialization

# Enable logging for debugging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ['BOT_TOKEN']

# Initialize database on bot startup
init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start from user {update.effective_user.id}")
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    conn = sqlite3.connect('videos.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()
    
    qr_data = f"https://tesla-video-streamer.onrender.com/login?user_id={user_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    
    await update.message.reply_photo(photo=bio, caption="Scan this QR in your Tesla browser to log in and see your videos!")

async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received video URL from user {update.effective_user.id}: {update.message.text}")
    if not update.message.text.startswith('http'):
        await update.message.reply_text("Please send a direct video URL (e.g., .mp4 link). For YouTube, extract the direct URL first using yt-dlp.")
        return
    
    user_id = update.effective_user.id
    url = update.message.text
    title = url.split('/')[-1]
    
    conn = sqlite3.connect('videos.db')
    c = conn.cursor()
    c.execute("INSERT INTO videos (user_id, url, title) VALUES (?, ?, ?)", (user_id, url, title))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"Added: {title}\nOpen your website in Tesla to play!")

def main():
    try:
        logger.info("Starting bot...")
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_video))
        application.run_polling()
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
        raise

if __name__ == '__main__':
    main()