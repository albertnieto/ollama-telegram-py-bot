import os
from dotenv import load_dotenv
from loguru import logger
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Load environment variables from .env
load_dotenv()

# Import our handler functions.
from handlers import start_command, ask_command, message_handler

# Read the bot token from the environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found. Please set it in your .env file.")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ask", ask_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Starting Telegram bot...")
    application.run_polling()

if __name__ == "__main__":
    main()
