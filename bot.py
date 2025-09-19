import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import sqlite3
import qrcode
from io import BytesIO
from PIL import Image
import uuid

BOT_TOKEN = os.environ['BOT_TOKEN']  # Uses environment variable

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    conn = sqlite3.connect('videos.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()
    
    # Generate QR for login (links to website with user_id)
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
    if not update.message.text.startswith('http'):
        await update.message.reply_text("Please send a direct video URL (e.g., .mp4 link). For YouTube, extract the direct URL first using yt-dlp.")
        return
    
    user_id = update.effective_user.id
    url = update.message.text
    title = url.split('/')[-1]  # Simple title from URL
    
    conn = sqlite3.connect('videos.db')
    c = conn.cursor()
    c.execute("INSERT INTO videos (user_id, url, title) VALUES (?, ?, ?)", (user_id, url, title))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"Added: {title}\nOpen your website in Tesla to play!")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_video))
    application.run_polling()

if __name__ == '__main__':
    main()