import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import psycopg
# Note: qrcode, BytesIO, and Image imports have been removed as they are no longer needed.

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ['BOT_TOKEN']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start from user {update.effective_user.id}")
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    try:
        conn_str = os.environ['DATABASE_URL']
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as c:
                c.execute("INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (user_id, username))
        
        app_hostname = "https://teslastreamer.fly.dev" # <-- Make sure this is your correct URL
        login_url = f"{app_hostname}/login?user_id={user_id}"
        
        # *** CHANGE IS HERE: Replaced QR code generation with a simple text link ***
        message = (
            "Click this link in your Tesla browser to log in and see your videos.\n\n"
            f"➡️ [{login_url}]({login_url})"
        )
        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in /start: {e}")
        await update.message.reply_text("Error generating login link. Please try again.")

async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received message from user {update.effective_user.id}: {update.message.text}")
    url = update.message.text.strip()
    if not url.startswith('http'):
        await update.message.reply_text("Please send a direct video URL (e.g., .mp4 or .mkv).")
        return
    
    user_id = update.effective_user.id
    title = url.split('/')[-1]
    
    incompatible_keywords = ['hevc', 'h265', 'x265']
    warning_message = ""
    if any(keyword in url.lower() for keyword in incompatible_keywords):
        warning_message = "\n\n⚠️ **Warning:** This link appears to be an HEVC/x265 video, which may not play in the Tesla browser. If it doesn't work, please find an H.264/x264 source."

    try:
        conn_str = os.environ['DATABASE_URL']
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM videos WHERE user_id = %s", (user_id,))
                c.execute("INSERT INTO videos (user_id, url, title) VALUES (%s, %s, %s)", (user_id, url, title))
        logger.info(f"Added video for user {user_id}: {title}")
        await update.message.reply_text(f"Added: {title}\nOpen your website in Tesla to play!{warning_message}", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error adding video: {e}")
        await update.message.reply_text("Error adding video. Please try again.")

async def clear_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Received /clear command from user {user_id}")
    try:
        conn_str = os.environ['DATABASE_URL']
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM videos WHERE user_id = %s", (user_id,))
                deleted_count = c.rowcount
        
        logger.info(f"Cleared {deleted_count} videos for user {user_id}")
        await update.message.reply_text(f"✅ Successfully cleared {deleted_count} video(s).")
    except Exception as e:
        logger.error(f"Error clearing videos for user {user_id}: {e}")
        await update.message.reply_text("❌ Error clearing videos. Please try again.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}")
    if update and update.message:
        await update.message.reply_text("An error occurred. Please try again or contact support.")

def main():
    try:
        logger.info("Starting bot...")
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("clear", clear_videos))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_video))
        application.add_error_handler(error_handler)
        
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
        raise

if __name__ == '__main__':
    main()