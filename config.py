import re
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Regular pole types with special conditions (ordered, time-based)
POLE_TYPES = {
    "Pole": {
        "triggers": [r"^pole$", r"^oro$"],
        "points": 10,
        "order": 1,
        "emoji": "🏆",
        "time_condition": {
            "type": "daily_reset",
            "start_hour": 0  # 00:00 Madrid time
        }
    },
    "Subpole": {
        "triggers": [r"^subpole$", r"^plata$"],
        "points": 5,
        "order": 2,
        "emoji": "🥈",
        "time_condition": {
            "type": "daily_reset",
            "start_hour": 0  # 00:00 Madrid time
        }
    },
    "Subsubpole": {
        "triggers": [r"^subsubpole$", r"^bronce$"],
        "points": 2.5,
        "order": 3,
        "emoji": "🥉",
        "time_condition": {
            "type": "daily_reset",
            "start_hour": 0  # 00:00 Madrid time
        }
    },
    "Pole Canaria": {
        "triggers": [r"^pole canaria$", r"^oro canario$"],
        "points": 5,
        "order": 1,
        "emoji": "🏝️",
        "time_condition": {
            "type": "daily_reset",
            "start_hour": 1  # 01:00 Madrid time
        }
    },
    "Subpole Canaria": {
        "triggers": [r"^subpole canaria$", r"^plata canario$"],
        "points": 2.5,
        "order": 2,
        "emoji": "🌴",
        "time_condition": {
            "type": "daily_reset",
            "start_hour": 1  # 01:00 Madrid time
        }
    },
    "Subsubpole Canaria": {
        "triggers": [r"^subsubpole canaria$", r"^bronce canario$"],
        "points": 1.25,
        "order": 3,
        "emoji": "🌊",
        "time_condition": {
            "type": "daily_reset",
            "start_hour": 1  # 01:00 Madrid time
        }
    },
    "Pole Andaluza": {
        "triggers": [r"^pole andaluza$", r"^oro andaluz$"],
        "points": 0.5,
        "order": 1,
        "emoji": "🍊",
        "time_condition": {
            "type": "time_range",
            "start_hour": 12,  # 12:00
            "end_hour": 16     # 16:00
        }
    },
    "Subpole Andaluza": {
        "triggers": [r"^subpole andaluza$", r"^plata andaluza$"],
        "points": 0.25,
        "order": 2,
        "emoji": "🥘",
        "time_condition": {
            "type": "time_range",
            "start_hour": 12,  # 12:00
            "end_hour": 16     # 16:00
        }
    },
    "Subsubpole Andaluza": {
        "triggers": [r"^subsubpole andaluza$", r"^bronce andaluz$"],
        "points": 0.1,
        "order": 3,
        "emoji": "🍷",
        "time_condition": {
            "type": "time_range",
            "start_hour": 12,  # 12:00
            "end_hour": 16     # 16:00
        }
    },
}

# Special time-specific poles
TIME_SPECIFIC_POLES = {
    "Hora Porro": {
        "triggers": [r"^hora porro$"],
        "points": 4,
        "emoji": "🌿",
        "time_condition": {
            "type": "exact_time",
            "exact_times": [
                {"hour": 4, "minute": 20},  # 04:20
                {"hour": 16, "minute": 20}  # 16:20
            ]
        }
    },
    "Hora π": {
        "triggers": [r"^hora pi$", r"^hora π$"],
        "points": 3,
        "emoji": "🥧",
        "time_condition": {
            "type": "exact_time",
            "exact_times": [
                {"hour": 3, "minute": 14},  # 03:14
                {"hour": 15, "minute": 14}  # 15:14
            ]
        }
    },
    "Pole Mina": {
        "triggers": [r"^pole mina$"],
        "emoji": "💣",
        "time_condition": {
            "type": "counter_based",
            "counter": 20  # 20th message wins
        }
    },
}

# Additional standard poles without special conditions
ADDITIONAL_POLE_TYPES = {
    "Fracapole": {"points": 1, "triggers": [r"^fracapole$", r"^fail$"], "emoji": "😅"},
    "Poleet": {"points": 1, "triggers": [r"^poleet$"], "emoji": "📊"},
    "Poeet": {"points": 1, "triggers": [r"^poeet$"], "emoji": "📝"},
    "Polen": {"points": 0.1, "triggers": [r"^polen$"], "emoji": "🌼"},
    "Mastil": {"points": 0, "triggers": [r"^mastil$", r"^mástil$"], "emoji": "🏗️"},
    "Neopole": {"points": 0.05, "triggers": [r"^neopole$"], "emoji": "🆕"},
    "Pole Binaria": {"points": 0.05, "triggers": [r"^pole binaria$"], "emoji": "🔢"},
    "Pole Boix": {"points": 0.05, "triggers": [r"^pole boix$"], "emoji": "🌳"},
    "Pole Básica": {"points": 0.05, "triggers": [r"^pole básica$"], "emoji": "📌"},
    "Pole Cafelito": {"points": 0.5, "triggers": [r"^pole cafelito$"], "emoji": "☕"},
    "Pole Clásica": {"points": 0.05, "triggers": [r"^pole clásica$"], "emoji": "🏛️"},
    "Pole Contemporánea": {"points": 0.05, "triggers": [r"^pole contemporánea$"], "emoji": "🎨"},
    "Pole Cotizante": {"points": 1.5, "triggers": [r"^pole cotizante$"], "emoji": "📈"},
    "Pole CRX": {"points": 0.1, "triggers": [r"^pole crx$"], "emoji": "⚡"},
    "Pole Crítica": {"points": 0.05, "triggers": [r"^pole crítica$"], "emoji": "🔍"},
    "Pole Eterna": {"points": 0.05, "triggers": [r"^pole eterna$"], "emoji": "⏳"},
    "Pole Fran": {"points": 0.05, "triggers": [r"^pole fran$"], "emoji": "👨‍💻"},
    "Pole Germà": {"points": 0.05, "triggers": [r"^pole germà$", r"^pole germa$"], "emoji": "🌿"},
    "Pole Insomnio": {"points": 0.3, "triggers": [r"^pole insomnio$"], "emoji": "😴"},
    "Pole Letal": {"points": 0.05, "triggers": [r"^pole letal$"], "emoji": "💀"},
    "Pole Magnas": {"points": 0.05, "triggers": [r"^pole magnas$"], "emoji": "🎭"},
    "Alarma Magnas": {"points": 0.5, "triggers": [r"^alarma magnas$"], "emoji": "⏰"},
    "Pole Mistica": {"points": 0.05, "triggers": [r"^pole mística$"], "emoji": "✨"},
    "Pole Montero": {"points": 0.05, "triggers": [r"^pole montero$"], "emoji": "🏔️"},
    "Pole Máxima": {"points": 0.05, "triggers": [r"^pole máxima$"], "emoji": "📶"},
    "Pole Mínima": {"points": 0.05, "triggers": [r"^pole mínima$"], "emoji": "📉"},
    "Pole Presko": {"points": 0.05, "triggers": [r"^pole presko$"], "emoji": "❄️"},
    "Pole Toakiza": {"points": 1, "triggers": [r"^pole toakiza$"], "emoji": "🍻"},
    "Pole Ucraniana": {"points": 0.05, "triggers": [r"^pole ucraniana$"], "emoji": "🇺🇦"},
    "Polerdaka": {"points": 0.05, "triggers": [r"^polerdaka$"], "emoji": "🔄"},
    "Polerdakardamenaka": {"points": 0.05, "triggers": [r"^polerdakardamenaka$"], "emoji": "📚"},
    "Polerdamen": {"points": 0.05, "triggers": [r"^polerdamen$"], "emoji": "🔄"},
    "Postpole": {"points": 0.05, "triggers": [r"^postpole$"], "emoji": "📮"},
    "Prepole": {"points": 0.05, "triggers": [r"^prepole$"], "emoji": "⏱️"},
    "Pseudopole": {"points": 0.05, "triggers": [r"^pseudopole$"], "emoji": "🎭"},
    "Pole Cuck": {"points": 0.01, "triggers": [r"^pole cuck$"], "emoji": "🐐"},
}

# Merge all pole types into one dictionary
ALL_POLE_TYPES = {**POLE_TYPES, **TIME_SPECIFIC_POLES, **ADDITIONAL_POLE_TYPES}

# Compile all triggers into a list of tuples (regex_pattern, pole_type) for efficient checking
COMPILED_TRIGGERS = []
for pole_type, config in ALL_POLE_TYPES.items():
    for trigger in config["triggers"]:
        # Compile the regex and store with the pole type
        # Note: Using re.IGNORECASE to make the matching case-insensitive
        # Convert the pattern to a full match pattern if it's not already (e.g., "^pole$" stays as is, but "pole" becomes "^pole$")
        pattern = trigger
        if not pattern.startswith('^'):
            pattern = '^' + pattern
        if not pattern.endswith('$'):
            pattern = pattern + '$'
        
        try:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            COMPILED_TRIGGERS.append((compiled_pattern, pole_type))
            logger.debug(f"Compiled pattern '{pattern}' for pole type '{pole_type}'")
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}' for pole type '{pole_type}': {e}")

# Log the total number of triggers
logger.info(f"Loaded {len(COMPILED_TRIGGERS)} pole triggers for {len(ALL_POLE_TYPES)} pole types")

# Set debug mode to log all matching attempts
DEBUG_POLE_MATCHING = True