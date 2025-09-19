import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import psycopg
import qrcode
from io import BytesIO
from PIL import Image

# NOTE: We are removing 'from database import init_db' and the init_db() call
# because the web process already handles database initialization.

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ['BOT_TOKEN']

# The database is initialized by the 'web' process, so we remove init_db() here.

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start from user {update.effective_user.id}")
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    try:
        conn_str = os.environ['DATABASE_URL']
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as c:
                c.execute("INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (user_id, username))
        
        # Ensure your web URL is correct here
        qr_data = f"https://tesla-video-streamer.onrender.com/login?user_id={user_id}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        
        await update.message.reply_photo(photo=bio, caption="Scan this QR in your Tesla browser to log in and see your videos!")
    except Exception as e:
        logger.error(f"Error in /start: {e}")
        await update.message.reply_text("Error generating QR code. Please try again.")

async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received message from user {update.effective_user.id}: {update.message.text}")
    url = update.message.text.strip()
    if not url.startswith('http'):
        await update.message.reply_text("Please send a direct video URL (e.g., .mp4 or .mkv).")
        return
    
    user_id = update.effective_user.id
    title = url.split('/')[-1]
    
    try:
        conn_str = os.environ['DATABASE_URL']
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM videos WHERE user_id = %s", (user_id,))
                c.execute("INSERT INTO videos (user_id, url, title) VALUES (%s, %s, %s)", (user_id, url, title))
        logger.info(f"Added video for user {user_id}: {title}")
        await update.message.reply_text(f"Added: {title}\nOpen your website in Tesla to play!")
    except Exception as e:
        logger.error(f"Error adding video: {e}")
        await update.message.reply_text("Error adding video. Please try again.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}")
    if update and update.message:
        await update.message.reply_text("An error occurred. Please try again or contact support.")

# *** CHANGE IS HERE: Reverted main() to a standard synchronous function ***
def main():
    try:
        logger.info("Starting bot...")
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_video))
        application.add_error_handler(error_handler)
        
        # This function is blocking and handles the async loop internally.
        # The drop_pending_updates=True argument helps prevent conflicts after a restart.
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
        raise

if __name__ == '__main__':
    main()