import random
import pytz
from loguru import logger
from models import User, Pole, PoleMina
from config import ALL_POLE_TYPES, COMPILED_TRIGGERS, DEBUG_POLE_MATCHING
# Get db reference for updates
from models import db

# Madrid timezone
MADRID_TZ = pytz.timezone('Europe/Madrid')

def check_pole_message(message_text, message_date, user_id, group_id):
    """
    Check if a message is a valid pole attempt and process it if so.
    
    Args:
        message_text (str): The message text to check
        message_date (datetime): The date and time of the message
        user_id (int): The Telegram user ID
        group_id (int): The Telegram group ID
        
    Returns:
        dict or None: Pole data if successful, None otherwise
        str or None: Special message for counter-based poles that aren't yet completed
    """
    # Convert message date to Madrid time
    madrid_time = message_date.astimezone(MADRID_TZ)
    
    # Log the message for debugging
    logger.debug(f"Checking message: '{message_text}' from user {user_id} in group {group_id}")
    
    # Normalize message text: strip whitespace and convert to lowercase
    normalized_text = message_text.strip().lower()
    
    # Check all triggers
    for pattern, pole_type in COMPILED_TRIGGERS:        
        # Use fullmatch to ensure entire string matches
        match = pattern.fullmatch(normalized_text)
        
        if match:
            logger.info(f"Matched pole type: {pole_type} for message: '{message_text}'")
            
            # Check if this is a counter-based pole
            pole_config = ALL_POLE_TYPES[pole_type]
            if "time_condition" in pole_config and pole_config["time_condition"].get("type") == "counter_based":
                # Process counter-based pole attempts differently
                return process_counter_based_pole(pole_type, madrid_time, user_id, group_id)
            else:
                # Process regular pole attempt
                return process_pole_attempt(pole_type, madrid_time, user_id, group_id), None
    
    # Try again with a more lenient match (contains instead of fullmatch)
    # This is helpful for debugging but could cause false positives in production
    if DEBUG_POLE_MATCHING:
        for pattern, pole_type in COMPILED_TRIGGERS:
            if pattern.search(normalized_text):
                logger.debug(f"Partial match found for pole type: {pole_type}, but fullmatch required")
    
    logger.debug(f"No pole pattern matched for message: '{message_text}'")
    return None, None

def process_pole_attempt(pole_type, madrid_time, user_id, group_id):
    """
    Process a pole attempt and create a new pole record if valid.
    
    Args:
        pole_type (str): The type of pole
        madrid_time (datetime): The date and time in Madrid timezone
        user_id (int): The Telegram user ID
        group_id (int): The Telegram group ID
        
    Returns:
        dict or None: Pole data if successful, None otherwise
    """
    pole_config = ALL_POLE_TYPES[pole_type]
    
    # Check if this pole type has already been claimed today
    if Pole.pole_exists(group_id, pole_type, madrid_time.date()):
        logger.info(f"Pole {pole_type} already exists for today in group {group_id}")
        return None
    
    # Check time conditions if they exist
    if "time_condition" in pole_config and pole_config["time_condition"]:
        if not check_time_condition(pole_config["time_condition"], madrid_time):
            logger.info(f"Time condition not met for pole {pole_type}")
            return None
    
    # Check order conditions for ordered poles (like pole, subpole, subsubpole)
    if "order" in pole_config:
        if not check_order_condition(pole_config, group_id, madrid_time, user_id):
            logger.info(f"Order condition not met for pole {pole_type}")
            return None
    
    # Create the pole record
    points = pole_config["points"]
    pole_data = Pole.create(user_id, group_id, pole_type, points, madrid_time)
    logger.info(f"Created pole {pole_type} for user {user_id} in group {group_id} with {points} points")
    
    return pole_data
    
def process_counter_based_pole(pole_type, madrid_time, user_id, group_id):
    """
    Process a counter-based pole attempt.
    
    Args:
        pole_type (str): The type of pole
        madrid_time (datetime): The date and time in Madrid timezone
        user_id (int): The Telegram user ID
        group_id (int): The Telegram group ID
        
    Returns:
        tuple: (pole_data, message) where:
            pole_data: dict or None - Pole data if successful, None otherwise
            message: str or None - Progress message if not completed yet
    """
    pole_config = ALL_POLE_TYPES[pole_type]
    required_count = pole_config["time_condition"]["counter"]
    
    # Track this attempt
    counter = Pole.track_attempt(group_id, pole_type, user_id, madrid_time)
    
    # Check if we've reached the required count
    if counter["count"] == required_count and not counter.get("completed", False):
        # Pole completed! Generate random points for Pole Mina
        if pole_type == "Pole Mina":
            points = random.randint(1, 10)
            pole_data = Pole.create(user_id, group_id, pole_type, points, madrid_time)
            
            # Mark as completed
            db.pole_counters.update_one(
                {"_id": counter.get("_id")},
                {"$set": {"completed": True}}
            )
            
            logger.info(f"Created {pole_type} for user {user_id} with {points} points (attempt #{required_count})")
            return pole_data, None
        else:
            # For other counter-based poles if added in the future
            return None, None
    else:
        # Not completed yet, return a progress message
        remaining = required_count - counter["count"]
        emoji = pole_config.get("emoji", "🎯")
        
        # For Pole Mina, show the masked string
        if pole_type == "Pole Mina":
            # Reveal one more character
            pole_mina_doc = PoleMina.reveal_character(group_id, madrid_time.date())
            masked_string = PoleMina.get_masked_string(pole_mina_doc)
            
            message = (
                f"{emoji} ¡Intento #{counter['count']} de {pole_type}!\n"
                f"Código secreto: `{masked_string}`\n"
                f"Faltan {remaining} intentos más para detonar."
            )
        else:
            message = f"{emoji} ¡Intento #{counter['count']} de {pole_type}! Faltan {remaining} intentos más hoy."
        
        return None, message


def check_time_condition(time_condition, current_time):
    """
    Check if the current time meets the time condition.
    
    Args:
        time_condition (dict): The time condition to check
        current_time (datetime): The current time
        
    Returns:
        bool: True if the condition is met, False otherwise
    """
    condition_type = time_condition["type"]
    
    if condition_type == "exact_time":
        # Check if current time matches any of the exact times
        for exact_time in time_condition["exact_times"]:
            if (current_time.hour == exact_time["hour"] and 
                current_time.minute == exact_time["minute"]):
                return True
        return False
    
    elif condition_type == "time_range":
        # Check if current time is within the range
        start_hour = time_condition["start_hour"]
        end_hour = time_condition["end_hour"]
        
        current_hour = current_time.hour
        return start_hour <= current_hour < end_hour
    
    elif condition_type == "daily_reset":
        # No specific check needed for daily reset, just used for grouping related poles
        return True
    
    elif condition_type == "counter_based":
        # No specific time check for counter-based poles
        return True
    
    return False

def check_order_condition(pole_config, group_id, current_time, user_id):
    """
    Check if the pole order condition is met.
    
    Args:
        pole_config (dict): The pole configuration
        group_id (int): The Telegram group ID
        current_time (datetime): The current time
        user_id (int): The user ID
        
    Returns:
        bool: True if the condition is met, False otherwise
    """
    order = pole_config["order"]
    
    # Get the start hour for the day's reset (default to 0 for regular poles)
    start_hour = 0
    if "time_condition" in pole_config and pole_config["time_condition"]:
        if pole_config["time_condition"]["type"] == "daily_reset":
            start_hour = pole_config["time_condition"]["start_hour"]
    
    # Get all poles for today in this group
    daily_poles = Pole.get_daily_poles(group_id, current_time.date())
    
    # Filter poles by the same "family" (determined by start hour)
    family_poles = []
    for pole in daily_poles:
        pole_type_config = ALL_POLE_TYPES.get(pole["type"])
        if pole_type_config and "order" in pole_type_config:
            # Check if this pole belongs to the same family
            pole_start_hour = 0
            if "time_condition" in pole_type_config and pole_type_config["time_condition"]:
                if pole_type_config["time_condition"]["type"] == "daily_reset":
                    pole_start_hour = pole_type_config["time_condition"]["start_hour"]
            
            if pole_start_hour == start_hour:
                family_poles.append(pole)
    
    # If we already have enough poles of this family, check fails
    if len(family_poles) >= order:
        return False
    
    # Check that this user hasn't already claimed a pole in this family today
    for pole in family_poles:
        if pole["user_id"] == user_id:
            return False
    
    # Check that the current order matches what we expect
    return len(family_poles) + 1 == order

def get_user_ranking(group_id=None, limit=10):
    """
    Get user ranking by points.
    
    Args:
        group_id (int, optional): The group ID to filter by. Defaults to None.
        limit (int, optional): The maximum number of users to return. Defaults to 10.
        
    Returns:
        list: A list of user rankings
    """
    rankings = Pole.get_ranking(group_id, limit)
    
    # Add user information to the rankings
    for rank in rankings:
        user = User.get_user(rank["_id"])
        if user:
            rank["user"] = {
                "telegram_id": user["telegram_id"],
                "first_name": user["first_name"],
                "username": user.get("username")
            }
    
    return rankings

def format_ranking_message(rankings, group_title=None):
    """
    Format the ranking data into a user-friendly message.
    
    Args:
        rankings (list): The ranking data
        group_title (str, optional): The group title. Defaults to None.
        
    Returns:
        str: A formatted message with the rankings
    """
    if not rankings:
        return "No hay puntuaciones disponibles aún."
    
    header = "🏆 Ranking de puntos"
    if group_title:
        header += f" en {group_title}"
    
    message = f"{header}:\n\n"
    
    for i, rank in enumerate(rankings):
        user_name = rank.get("user", {}).get("first_name", "Usuario Desconocido")
        points = rank["total_points"]
        
        # Add medal emoji for top 3
        if i == 0:
            medal = "🥇"
        elif i == 1:
            medal = "🥈"
        elif i == 2:
            medal = "🥉"
        else:
            medal = f"{i+1}."
        
        message += f"{medal} {user_name}: {points} puntos\n"
    
    return message

def format_pole_message(pole_data, user_name):
    """
    Format a pole success message with some variety and flair.
    
    Args:
        pole_data (dict): The pole data
        user_name (str): The user's name
        
    Returns:
        str: A formatted message
    """
    pole_type = pole_data["type"]
    points = pole_data["points"]
    
    # Get the emoji for this pole type
    pole_config = ALL_POLE_TYPES.get(pole_type, {})
    emoji = pole_config.get("emoji", "🎯")
    
    # Congratulation intros - pick one randomly
    intros = [
        f"🎉 ¡{user_name} ha conseguido la *{pole_type}*!",
        f"{emoji} ¡Increíble! {user_name} acaba de lograr la *{pole_type}*",
        f"⚡ ¡BOOM! {user_name} se lleva la *{pole_type}*",
        f"🔥 ¡{user_name} lo ha hecho! La *{pole_type}* es suya",
        f"🏆 ¡Victoria para {user_name}! Ha conseguido la *{pole_type}*",
        f"💪 ¡Impresionante, {user_name}! La *{pole_type}* es tuya",
        f"✨ ¡Un aplauso para {user_name}! Ha logrado la *{pole_type}*"
    ]
    
    # Points messages - pick one randomly
    points_msgs = [
        f"✨ Has ganado *{points} puntos* ✨",
        f"💰 *{points} puntos* para tu colección",
        f"📊 Tu saldo aumenta en *{points} puntos*",
        f"⭐ Te llevas *{points} puntos* de premio",
        f"🎁 Recompensa: *{points} puntos*"
    ]
    
    # Special messages for specific pole types
    special_msgs = []
    
    # Regular pole/subpole/subsubpole
    if pole_type in ["Pole", "Subpole", "Subsubpole"]:
        special_msgs = [
            f"¡Eres {['el primero', 'el segundo', 'el tercero'][['Pole', 'Subpole', 'Subsubpole'].index(pole_type)]} del día!",
            f"¡Te has levantado con energía hoy!",
            f"La velocidad es tu fuerte"
        ]
    
    # Pole Mina (completed)
    elif pole_type == "Pole Mina":
        # Get the fully revealed string
        try:
            pole_mina_doc = PoleMina.get_or_create_daily_string(pole_data['group_id'], 
                                                              pole_data['created_at'].date())
            revealed_string = pole_mina_doc["random_string"]
        except:
            # Fallback if we can't get the string
            revealed_string = "???????????"
        
        special_msgs = [
            f"¡BOOM! La mina ha explotado en tus manos 💣 Código completo: `{revealed_string}`",
            f"¡Has desactivado la mina con precisión! Código: `{revealed_string}`",
            f"Tu perseverancia ha dado frutos, ¡20 intentos y lo conseguiste! Código: `{revealed_string}`",
            f"La suerte del minero está contigo hoy. Código secreto: `{revealed_string}`"
        ]
    
    # Time-specific poles
    elif pole_type in ["Hora Porro", "Hora π"]:
        special_msgs = [
            f"¡Qué puntualidad!",
            f"Tu reloj está perfectamente sincronizado",
            f"¡La precisión es la clave del éxito!"
        ]
    
    # Build the complete message
    message = f"{random.choice(intros)}\n"
    message += f"{random.choice(points_msgs)}"
    
    # Add special message if available
    if special_msgs:
        message += f"\n{random.choice(special_msgs)}"
    
    # Occasional random extra flair (20% chance)
    if random.random() < 0.2:
        flairs = [
            "¡Sigue así! 🚀",
            "¿Alguien puede detener a este campeón? 🤔",
            "La competencia tiembla ante ti 😎",
            "¡Recuerda usar tus poderes para el bien! 🦸",
            "¡A este ritmo serás leyenda! 📚"
        ]
        message += f"\n\n{random.choice(flairs)}"
    
    return message

