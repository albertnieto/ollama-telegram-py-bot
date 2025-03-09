import os
from dotenv import load_dotenv
from loguru import logger
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Load environment variables from .env
load_dotenv()

# Import our handler functions
from handlers import (
    start_command, 
    help_command,
    ask_command, 
    message_handler, 
    ranking_command,
    my_points_command
)

# Read the bot token from the environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def main(lambda_mode=False):
    """
    Main function to start the bot.
    
    Args:
        lambda_mode (bool, optional): Whether to run in AWS Lambda mode. Defaults to False.
    
    Returns:
        Application: The Telegram bot application (in Lambda mode) or None (in polling mode)
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found. Please set it in your .env file.")
        return None

    # Configure logging
    logger.remove()  # Remove default handlers
    logger.add("bot.log", rotation="500 MB", level="DEBUG")  # Set level to DEBUG
    logger.add(lambda msg: print(msg), level="DEBUG")  # Also print to console
    
    # Log the startup
    logger.info("Starting Telegram bot...")
    logger.info("Logging configured at DEBUG level for more verbose output")
    
    # Build the application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ask", ask_command))
    application.add_handler(CommandHandler("ranking", ranking_command))
    application.add_handler(CommandHandler("mypoints", my_points_command))
    
    # Make sure the message handler is added and properly filters for text messages
    # This handler should catch any text message that is not a command
    logger.info("Registering message handler for text messages")
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    if lambda_mode:
        # In Lambda mode, return the application for webhook handling
        return application
    else:
        # In polling mode, start the bot
        logger.info("Starting Telegram bot in polling mode...")
        application.run_polling()
        return None

if __name__ == "__main__":
    main()