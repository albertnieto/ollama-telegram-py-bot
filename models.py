from pymongo import MongoClient
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from loguru import logger
import string
import random

# Load environment variables
load_dotenv()

# MongoDB connection
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
logger.info(f"Connecting to MongoDB at: {mongo_uri}")

try:
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    # Test connection
    client.server_info()
    db = client[os.getenv("DB_NAME", "telegram_bot")]

    # Collections
    users_collection = db.users
    groups_collection = db.groups
    poles_collection = db.poles

    logger.info("Successfully connected to MongoDB")
except Exception as e:
    logger.error(f"MongoDB connection error: {e}")
    # Create a fallback to allow the bot to start even without MongoDB
    logger.warning("Using memory-based fallbacks for database. Data will not persist!")

    class DummyCollection:
        def __init__(self, name):
            self.name = name
            self.data = []
            self._id_counter = 1

        def insert_one(self, document):
            document["_id"] = self._id_counter
            self._id_counter += 1
            self.data.append(document)
            return type("obj", (object,), {"inserted_id": document["_id"]})

        def update_one(self, filter, update, upsert=False):
            for i, doc in enumerate(self.data):
                match = True
                for k, v in filter.items():
                    if k not in doc or doc[k] != v:
                        match = False
                        break

                if match:
                    for op, fields in update.items():
                        if op == "$set":
                            for k, v in fields.items():
                                doc[k] = v
                        elif op == "$inc":
                            for k, v in fields.items():
                                if k in doc:
                                    doc[k] += v
                                else:
                                    doc[k] = v
                        elif op == "$setOnInsert" and i == len(self.data) - 1:
                            for k, v in fields.items():
                                if k not in doc:
                                    doc[k] = v
                    return type("obj", (object,), {"modified_count": 1})

            if upsert:
                new_doc = {}
                for k, v in filter.items():
                    new_doc[k] = v

                for op, fields in update.items():
                    if op in ["$set", "$setOnInsert"]:
                        for k, v in fields.items():
                            new_doc[k] = v
                    elif op == "$inc":
                        for k, v in fields.items():
                            new_doc[k] = v

                self.insert_one(new_doc)
                return type("obj", (object,), {"upserted_id": new_doc["_id"]})

            return type("obj", (object,), {"modified_count": 0})

        def find_one(self, filter):
            for doc in self.data:
                match = True
                for k, v in filter.items():
                    if k not in doc or doc[k] != v:
                        match = False
                        break

                if match:
                    return doc
            return None

        def find(self, filter=None):
            if filter is None:
                return self.data.copy()

            results = []
            for doc in self.data:
                match = True
                for k, v in filter.items():
                    if k not in doc or doc[k] != v:
                        match = False
                        break

                if match:
                    results.append(doc)

            return type(
                "obj",
                (object,),
                {
                    "sort": lambda field, direction: sorted(
                        results, key=lambda x: x.get(field[0], 0), reverse=direction < 0
                    )
                },
            )

        def aggregate(self, pipeline):
            # Very simple aggregation implementation
            # Only supports basic $match and $group operations
            data = self.data.copy()

            for stage in pipeline:
                if "$match" in stage:
                    new_data = []
                    for doc in data:
                        match = True
                        for k, v in stage["$match"].items():
                            if k not in doc or doc[k] != v:
                                match = False
                                break

                        if match:
                            new_data.append(doc)
                    data = new_data

                elif "$group" in stage:
                    groups = {}
                    id_field = stage["$group"]["_id"]

                    for doc in data:
                        key = doc.get(id_field, None)
                        if key not in groups:
                            groups[key] = {"_id": key}

                            for output_field, operation in stage["$group"].items():
                                if output_field != "_id":
                                    if "$sum" in operation:
                                        field = operation["$sum"]
                                        if field == 1:
                                            groups[key][output_field] = 1
                                        else:
                                            groups[key][output_field] = doc.get(
                                                field, 0
                                            )
                        else:
                            for output_field, operation in stage["$group"].items():
                                if output_field != "_id":
                                    if "$sum" in operation:
                                        field = operation["$sum"]
                                        if field == 1:
                                            groups[key][output_field] += 1
                                        else:
                                            groups[key][output_field] += doc.get(
                                                field, 0
                                            )

                    data = list(groups.values())

                elif "$sort" in stage:
                    for field, direction in stage["$sort"].items():
                        data.sort(key=lambda x: x.get(field, 0), reverse=direction < 0)

                elif "$limit" in stage:
                    data = data[: stage["$limit"]]

            return data

    class DummyDb:
        def __init__(self):
            self.users = DummyCollection("users")
            self.groups = DummyCollection("groups")
            self.poles = DummyCollection("poles")
            self.user_poles = DummyCollection("user_poles")
            self.pole_counters = DummyCollection("pole_counters")
            self.pole_mina = DummyCollection("pole_mina")

    db = DummyDb()
    users_collection = db.users
    groups_collection = db.groups
    poles_collection = db.poles


class User:
    """User model for storing Telegram user data and pole statistics."""

    @staticmethod
    def create_or_update(telegram_id, first_name, username=None, is_bot=False):
        """Create a new user or update an existing one."""
        user_data = {
            "telegram_id": telegram_id,
            "first_name": first_name,
            "username": username,
            "is_bot": is_bot,
            "updated_at": datetime.utcnow(),
        }

        try:
            users_collection.update_one(
                {"telegram_id": telegram_id},
                {
                    "$set": user_data,
                    "$setOnInsert": {
                        "created_at": datetime.utcnow(),
                        "total_points": 0,
                        "poles_claimed": 0,
                    },
                },
                upsert=True,
            )

            return user_data
        except Exception as e:
            logger.error(f"Error creating/updating user: {e}")
            return None

    @staticmethod
    def get_user(telegram_id):
        """Get user by Telegram ID."""
        try:
            return users_collection.find_one({"telegram_id": telegram_id})
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None

    @staticmethod
    def get_user_points(telegram_id, group_id=None):
        """Get total points for a user, optionally filtered by group."""
        try:
            if group_id:
                # Get points for specific group
                user_group_stats = db.user_poles.find_one(
                    {"user_id": telegram_id, "group_id": group_id}
                )
                return (
                    user_group_stats.get("total_points", 0) if user_group_stats else 0
                )
            else:
                # Get global points
                user = User.get_user(telegram_id)
                return user.get("total_points", 0) if user else 0
        except Exception as e:
            logger.error(f"Error getting user points: {e}")
            return 0

    @staticmethod
    def update_points(telegram_id, group_id, points, pole_type):
        """
        Update user points for a specific pole.
        This efficiently increments points without storing each pole record.
        """
        current_time = datetime.utcnow()

        try:
            # Update global user stats
            users_collection.update_one(
                {"telegram_id": telegram_id},
                {
                    "$inc": {"total_points": points, "poles_claimed": 1},
                    "$set": {"last_pole_at": current_time},
                },
            )

            # Update group-specific stats
            db.user_poles.update_one(
                {"user_id": telegram_id, "group_id": group_id},
                {
                    "$inc": {
                        "total_points": points,
                        "poles_claimed": 1,
                        f"pole_types.{pole_type}": 1,  # Count by pole type
                    },
                    "$set": {
                        "updated_at": current_time,
                        "last_pole_at": current_time,
                        "last_pole_type": pole_type,
                    },
                },
                upsert=True,
            )

            return True
        except Exception as e:
            logger.error(f"Error updating user points: {e}")
            return False


class Group:
    """Group model for storing Telegram group data."""

    @staticmethod
    def create_or_update(chat_id, title, chat_type):
        """Create a new group or update an existing one."""
        group_data = {
            "chat_id": chat_id,
            "title": title,
            "type": chat_type,
            "updated_at": datetime.utcnow(),
        }

        try:
            groups_collection.update_one(
                {"chat_id": chat_id},
                {
                    "$set": group_data,
                    "$setOnInsert": {"created_at": datetime.utcnow(), "total_poles": 0},
                },
                upsert=True,
            )

            return group_data
        except Exception as e:
            logger.error(f"Error creating/updating group: {e}")
            return None

    @staticmethod
    def get_group(chat_id):
        """Get group by chat ID."""
        try:
            return groups_collection.find_one({"chat_id": chat_id})
        except Exception as e:
            logger.error(f"Error getting group: {e}")
            return None

    @staticmethod
    def increment_pole_count(chat_id):
        """Increment the total poles counter for a group."""
        try:
            groups_collection.update_one(
                {"chat_id": chat_id}, {"$inc": {"total_poles": 1}}
            )
            return True
        except Exception as e:
            logger.error(f"Error incrementing group pole count: {e}")
            return False


class Pole:
    """Pole model for storing pole data."""

    @staticmethod
    def create(user_id, group_id, pole_type, points, message_date):
        """
        Create a new pole record and update user stats.

        This method is more efficient because it:
        1. Updates user stats directly
        2. Only stores minimal pole info for analytics
        3. Uses a TTL index to automatically delete old pole records
        """
        pole_date = message_date.strftime("%Y-%m-%d")

        # Create minimal pole record for historical tracking
        pole_data = {
            "user_id": user_id,
            "group_id": group_id,
            "type": pole_type,
            "points": points,
            "date": pole_date,
            "created_at": message_date,
            "expiry_date": message_date + timedelta(days=30),  # For TTL index
        }

        try:
            # Store the pole record (will be auto-deleted after 30 days)
            result = poles_collection.insert_one(pole_data)
            pole_data["_id"] = result.inserted_id

            # Update user points
            User.update_points(user_id, group_id, points, pole_type)

            # Increment group pole count
            Group.increment_pole_count(group_id)

            return pole_data
        except Exception as e:
            logger.error(f"Error creating pole: {e}")
            return None

    @staticmethod
    def track_attempt(group_id, pole_type, user_id, message_date):
        """Track an attempt at a counter-based pole."""
        date_str = message_date.strftime("%Y-%m-%d")

        try:
            # Get or create the counter document
            counter_doc = db.pole_counters.find_one(
                {"group_id": group_id, "type": pole_type, "date": date_str}
            )

            if not counter_doc:
                # Create a new counter document
                counter_doc = {
                    "group_id": group_id,
                    "type": pole_type,
                    "date": date_str,
                    "count": 0,
                    "user_attempts": [],
                    "completed": False,
                    "created_at": message_date,
                    "expiry_date": message_date + timedelta(days=7),  # For TTL index
                }

            # Update the counter if not already completed
            if not counter_doc.get("completed", False):
                # Add this attempt
                counter_doc["count"] = counter_doc.get("count", 0) + 1

                # Track this user's attempt
                user_attempts = counter_doc.get("user_attempts", [])
                user_attempts.append({"user_id": user_id, "timestamp": message_date})
                counter_doc["user_attempts"] = user_attempts

                # Update the document
                db.pole_counters.update_one(
                    {"group_id": group_id, "type": pole_type, "date": date_str},
                    {"$set": counter_doc},
                    upsert=True,
                )

            return counter_doc
        except Exception as e:
            logger.error(f"Error tracking pole attempt: {e}")
            # Create a minimal counter doc for offline mode
            return {
                "group_id": group_id,
                "type": pole_type,
                "date": date_str,
                "count": 1,
                "user_attempts": [{"user_id": user_id, "timestamp": message_date}],
                "completed": False,
            }

    @staticmethod
    def pole_exists(group_id, pole_type, date):
        """Check if a pole already exists for the given group, type, and date."""
        date_str = date.strftime("%Y-%m-%d")
        try:
            # First, check the poles_cache collection which is faster
            pole_cache = db.poles_cache.find_one(
                {
                    "group_id": group_id,
                    "date": date_str,
                    f"claimed.{pole_type}": {"$exists": True},
                }
            )

            if pole_cache:
                return True

            # Fallback to checking the poles collection
            return (
                poles_collection.find_one(
                    {"group_id": group_id, "type": pole_type, "date": date_str}
                )
                is not None
            )
        except Exception as e:
            logger.error(f"Error checking if pole exists: {e}")
            return False

    @staticmethod
    def get_daily_poles(group_id, date):
        """Get all poles for a group on a specific date."""
        date_str = date.strftime("%Y-%m-%d")
        try:
            return list(
                poles_collection.find({"group_id": group_id, "date": date_str}).sort(
                    "created_at", 1
                )
            )
        except Exception as e:
            logger.error(f"Error getting daily poles: {e}")
            return []

    @staticmethod
    def get_ranking(group_id=None, limit=10):
        """Get user ranking by points, optionally filtered by group."""
        try:
            if group_id:
                # Use the user_poles collection which has pre-aggregated data
                users = list(
                    db.user_poles.find({"group_id": group_id})
                    .sort([("total_points", -1)])
                    .limit(limit)
                )

                # Convert to the expected format
                result = []
                for user in users:
                    result.append(
                        {"_id": user["user_id"], "total_points": user["total_points"]}
                    )

                return result
            else:
                # Get global rankings from users collection
                return list(
                    users_collection.find({"is_bot": False})
                    .sort([("total_points", -1)])
                    .limit(limit)
                )
        except Exception as e:
            logger.error(f"Error getting ranking: {e}")
            return []

    @staticmethod
    def get_counter_for_pole(group_id, pole_type, date):
        """Get the counter document for a counter-based pole."""
        date_str = date.strftime("%Y-%m-%d")
        try:
            return db.pole_counters.find_one(
                {"group_id": group_id, "type": pole_type, "date": date_str}
            )
        except Exception as e:
            logger.error(f"Error getting pole counter: {e}")
            return None

    @staticmethod
    def mark_pole_claimed(group_id, pole_type, date, user_id):
        """
        Mark a pole as claimed in the cache for faster lookups.
        This is a performance optimization.
        """
        date_str = date.strftime("%Y-%m-%d")
        try:
            db.poles_cache.update_one(
                {"group_id": group_id, "date": date_str},
                {
                    "$set": {
                        f"claimed.{pole_type}": {
                            "user_id": user_id,
                            "claimed_at": datetime.utcnow(),
                        }
                    }
                },
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"Error marking pole as claimed: {e}")
            return False


class PoleMina:
    """Class for pole mina-related functionality."""

    @staticmethod
    def generate_random_string(length=20):
        """Generate a random string of specified length."""
        characters = string.ascii_uppercase + string.digits
        return "".join(random.choice(characters) for _ in range(length))

    @staticmethod
    def get_or_create_daily_info(group_id, date):
        """Get or create daily random string and required count for a group."""
        date_str = date.strftime("%Y-%m-%d")

        try:
            # Check if we already have a string for today
            pole_mina_doc = db.pole_mina.find_one(
                {"group_id": group_id, "date": date_str}
            )

            if not pole_mina_doc:
                # Create a new random string and random required count (1-10)
                random_string = PoleMina.generate_random_string(20)
                required_count = random.randint(1, 10)

                pole_mina_doc = {
                    "group_id": group_id,
                    "date": date_str,
                    "random_string": random_string,
                    "required_count": required_count,
                    "revealed_positions": [],
                    "created_at": datetime.utcnow(),
                    "expiry_date": datetime.utcnow()
                    + timedelta(days=7),  # For TTL index
                }

                db.pole_mina.insert_one(pole_mina_doc)
                logger.info(
                    f"Created new pole mina for group {group_id}: string={random_string}, required_count={required_count}"
                )

            return pole_mina_doc
        except Exception as e:
            logger.error(f"Error getting/creating pole mina info: {e}")
            # Return a fallback document
            return {
                "group_id": group_id,
                "date": date_str,
                "random_string": PoleMina.generate_random_string(20),
                "required_count": 5,  # Default fallback
                "revealed_positions": [],
            }

    @staticmethod
    def get_or_create_daily_string(group_id, date):
        """Get or create daily random string for a group."""
        # Alias for backward compatibility
        return PoleMina.get_or_create_daily_info(group_id, date)

    @staticmethod
    def reveal_character(group_id, date):
        """Reveal the next character in the random string."""
        date_str = date.strftime("%Y-%m-%d")

        try:
            # Get the pole mina document
            pole_mina_doc = PoleMina.get_or_create_daily_info(group_id, date)

            # Calculate which position to reveal next
            random_string = pole_mina_doc["random_string"]
            revealed_positions = pole_mina_doc.get("revealed_positions", [])

            if len(revealed_positions) >= len(random_string):
                # All characters are already revealed
                return pole_mina_doc

            # Find a position that hasn't been revealed yet
            unrevealed_positions = [
                i for i in range(len(random_string)) if i not in revealed_positions
            ]
            if unrevealed_positions:
                # Reveal the next character (in sequence from left to right)
                next_position = min(unrevealed_positions)
                revealed_positions.append(next_position)

                # Update the document
                db.pole_mina.update_one(
                    {"group_id": group_id, "date": date_str},
                    {"$set": {"revealed_positions": revealed_positions}},
                )

                # Update the local document
                pole_mina_doc["revealed_positions"] = revealed_positions

            return pole_mina_doc
        except Exception as e:
            logger.error(f"Error revealing character: {e}")
            return None

    @staticmethod
    def get_masked_string(pole_mina_doc):
        """Get the partially revealed string."""
        if not pole_mina_doc:
            return "????????????????????????"

        random_string = pole_mina_doc["random_string"]
        revealed_positions = pole_mina_doc.get("revealed_positions", [])

        # Create masked string
        masked = []
        for i in range(len(random_string)):
            if i in revealed_positions:
                masked.append(random_string[i])
            else:
                masked.append("?")

        return "".join(masked)
