from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes
from api_helpers import query_llm

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /start command.
    """
    welcome_text = (
        "Hello! I’m a Python Telegram bot connected to a local LLM.\n"
        "Use /ask <question>, or just send a message."
    )
    await update.message.reply_text(welcome_text)
    logger.info("Sent welcome message to user: {}", update.effective_user.id)

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /ask command.
    """
    user_input = " ".join(context.args)
    if not user_input:
        await update.message.reply_text("Please provide a question, e.g., /ask What is water made of?")
        return

    logger.info("User {} asked: {}", update.effective_user.id, user_input)
    answer = query_llm(user_input)
    await update.message.reply_text(answer)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles plain text messages.
    """
    user_input = update.message.text
    logger.info("Received message from user {}: {}", update.effective_user.id, user_input)
    answer = query_llm(user_input)
    await update.message.reply_text(answer)
