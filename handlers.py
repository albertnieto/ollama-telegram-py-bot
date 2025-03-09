from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes
from api_helpers import query_llm, check_llm_availability
from models import User, Group
from pole import (
    check_pole_message,
    get_user_ranking,
    format_ranking_message,
    format_pole_message,
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /start command.
    """
    # Check LLM availability
    llm_available = check_llm_availability()

    welcome_text = (
        "¡Hola! Soy un bot de Telegram con múltiples funciones.\n\n"
        "• Gestiono el juego de los poles en grupos: 'pole', 'subpole', 'bronce', etc.\n"
    )

    if llm_available:
        welcome_text += "• Puedo responder preguntas usando un LLM local (Ollama)\n\n"
    else:
        welcome_text += "• (El asistente LLM no está disponible actualmente)\n\n"

    welcome_text += (
        "Comandos disponibles:\n"
        "/ranking - Ver el ranking de puntos en este grupo\n"
        "/mypoints - Ver tus puntos acumulados\n"
    )

    if llm_available:
        welcome_text += "/ask <pregunta> - Hacer una pregunta al LLM\n"

    welcome_text += "/help - Ver esta ayuda"

    await update.message.reply_text(welcome_text)
    logger.info(f"Sent welcome message to user: {update.effective_user.id}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /help command.
    """
    # Check LLM availability
    llm_available = check_llm_availability()

    help_text = "🤖 *Comandos del Bot*\n\n"

    if llm_available:
        help_text += "/ask <pregunta> - Hacer una pregunta al LLM\n"

    help_text += (
        "/ranking - Ver el ranking de puntos en este grupo\n"
        "/mypoints - Ver tus puntos acumulados\n"
        "/help - Ver esta ayuda\n\n"
        "*Sobre los Poles*\n"
        "• Pole/oro - Ser el primero del día (10 pts)\n"
        "• Subpole/plata - Ser el segundo del día (5 pts)\n"
        "• Bronce - Ser el tercero del día (2.5 pts)\n"
        "• Pole Canaria - Igual pero a partir de la 1:00 (5 pts)\n"
        "• Hora Porro - A las 4:20 o 16:20 (4 pts)\n"
        "• Hora π - A las 3:14 o 15:14 (3 pts)\n"
        "• Pole Andaluza - Entre las 12:00 y 16:00 (0.5 pts)\n"
        "• Pole Mina - Después de 20 intentos ganas puntos aleatorios (1-10 pts)\n"
        "Y muchos más tipos de poles..."
    )

    await update.message.reply_text(help_text, parse_mode="Markdown")
    logger.info(f"Sent help message to user: {update.effective_user.id}")


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /ask command.
    """
    # First check if LLM is available
    if not check_llm_availability():
        await update.message.reply_text(
            "Lo siento, el asistente LLM no está disponible en este momento."
        )
        return

    user_input = " ".join(context.args)
    if not user_input:
        await update.message.reply_text(
            "Por favor, proporciona una pregunta, ej: /ask ¿De qué está hecha el agua?"
        )
        return

    logger.info(f"User {update.effective_user.id} asked: {user_input}")

    # Send a typing indicator while processing
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    answer = query_llm(user_input)
    await update.message.reply_text(answer)


async def ranking_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /ranking command to show pole points ranking.
    """
    chat = update.effective_chat

    try:
        # Global ranking if in private chat, group ranking if in a group
        if chat.type == "private":
            rankings = get_user_ranking(None, 10)
            message = format_ranking_message(rankings)
        else:
            Group.create_or_update(chat.id, chat.title, chat.type)
            rankings = get_user_ranking(chat.id, 10)
            message = format_ranking_message(rankings, chat.title)

        await update.message.reply_text(message, parse_mode="Markdown")
        logger.info(f"Sent ranking to chat: {chat.id}")
    except Exception as e:
        logger.error(f"Error getting ranking: {e}")
        logger.exception("Stack trace:")
        await update.message.reply_text(
            "Ocurrió un error al obtener el ranking. Por favor, inténtalo de nuevo."
        )


async def my_points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /mypoints command to show user's own points.
    """
    try:
        user = update.effective_user
        User.create_or_update(user.id, user.first_name, user.username, user.is_bot)

        chat = update.effective_chat
        if chat.type != "private":
            Group.create_or_update(chat.id, chat.title, chat.type)
            group_points = User.get_user_points(user.id, chat.id)
            # Round points to 3 decimal places
            group_points = round(group_points, 3)
            message = (
                f"🏆 {user.first_name}, tienes {group_points} puntos en este grupo."
            )
        else:
            total_points = User.get_user_points(user.id)
            # Round points to 3 decimal places
            total_points = round(total_points, 3)
            message = f"🏆 {user.first_name}, tienes un total de {total_points} puntos."

        await update.message.reply_text(message)
        logger.info(f"Sent points info to user: {user.id}")
    except Exception as e:
        logger.error(f"Error getting user points: {e}")
        logger.exception("Stack trace:")
        await update.message.reply_text(
            "Ocurrió un error al obtener tus puntos. Por favor, inténtalo de nuevo."
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles plain text messages. Checks for pole attempts and message reactions.
    
    Behavior:
    - POLE_TYPES and TIME_SPECIFIC_POLES: Send text message, no reaction
    - ADDITIONAL_POLE_TYPES: React with 👍, no text message
    - Clown pole (invalid pole attempt): React with 🤡, no text message
    - Other message reactions: React with 👍, send text response if configured
    """
    # Skip if this is not a text message
    if not update.message or not update.message.text:
        return
    
    # Process in different ways depending on chat type
    chat = update.effective_chat
    user = update.effective_user
    message_text = update.message.text
    
    # Debug log all messages that come through
    logger.debug(f"Received message in {chat.type} chat: '{message_text}' from user {user.id}")
    
    try:
        # Create or update user record
        User.create_or_update(user.id, user.first_name, user.username, user.is_bot)
        
        # If in a group, check for pole attempts and message reactions
        if chat.type in ["group", "supergroup"]:
            Group.create_or_update(chat.id, chat.title, chat.type)
            
            message_date = update.message.date
            
            logger.debug(f"Processing message in group {chat.id}: '{message_text}'")
            
            # Check if this is a pole attempt or reaction trigger
            pole_data, counter_message, reaction_data = check_pole_message(message_text, message_date, user.id, chat.id)
            
            # Main pole types: Send text message, no reaction
            if pole_data:
                # Successfully claimed a main pole (POLE_TYPES or TIME_SPECIFIC_POLES)
                response_message = format_pole_message(pole_data, user.first_name)
                await update.message.reply_text(response_message, parse_mode="Markdown")
                logger.info(f"User {user.id} claimed pole {pole_data['type']} in group {chat.id}")
                return
                
            # Counter-based poles still in progress: Send text message, no reaction
            elif counter_message:
                # Counter-based pole attempt (not yet completed)
                await update.message.reply_text(counter_message, parse_mode="Markdown")
                logger.info(f"User {user.id} made counter-based pole attempt in group {chat.id}")
                return
                
            # All other cases that trigger a reaction
            elif reaction_data:
                reaction_type = reaction_data.get("type")
                response = reaction_data.get("response")
                
                try:
                    # Simple logic: if it's a clown pole, use clown emoji, otherwise use thumbs up
                    if reaction_type == "clown_pole":
                        await update.message.set_reaction("🤡")
                        logger.info(f"Added 🤡 reaction for clown pole to message from user {user.id}")
                    else:
                        # All other reaction types (including ADDITIONAL_POLE_TYPES)
                        await update.message.set_reaction("👍")
                        logger.info(f"Added 👍 reaction to message from user {user.id}")
                except Exception as e:
                    logger.warning(f"Unable to add emoji reaction: {e}")
                
                # Send text response if available (mostly for message reactions, not poles)
                if response:
                    await update.message.reply_text(response)
                    logger.info(f"Sent reaction response to user {user.id} in group {chat.id}")
                
                return
        
        # In private chat, inform user to use the /ask command
        elif chat.type == "private":
            if check_llm_availability():
                await update.message.reply_text(
                    "Para hacer preguntas al asistente, por favor usa el comando /ask seguido de tu pregunta. "
                    "Por ejemplo: /ask ¿Cuál es la capital de Francia?"
                )
            else:
                await update.message.reply_text(
                    "Lo siento, el asistente LLM no está disponible en este momento. "
                    "Puedes usar los comandos /help, /ranking o /mypoints."
                )
    except Exception as e:
        logger.error(f"Error in message handler: {e}")
        logger.exception("Stack trace:")
        await update.message.reply_text("Ocurrió un error procesando tu mensaje. Por favor, inténtalo de nuevo.")




