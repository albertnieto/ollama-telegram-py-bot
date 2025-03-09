from pymongo import MongoClient
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(mongo_uri)
db = client[os.getenv("DB_NAME", "telegram_bot")]

# Collections
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
            "updated_at": datetime.utcnow()
        }
        
        users_collection.update_one(
            {"telegram_id": telegram_id},
            {"$set": user_data, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True
        )
        
        return user_data
    
    @staticmethod
    def get_user(telegram_id):
        """Get user by Telegram ID."""
        return users_collection.find_one({"telegram_id": telegram_id})
    
    @staticmethod
    def get_user_points(telegram_id, group_id=None):
        """Get total points for a user, optionally filtered by group."""
        match = {"user_id": telegram_id}
        if group_id:
            match["group_id"] = group_id
            
        pipeline = [
            {"$match": match},
            {"$group": {"_id": "$user_id", "total_points": {"$sum": "$points"}}}
        ]
        
        result = list(poles_collection.aggregate(pipeline))
        if result:
            return result[0]["total_points"]
        return 0

class Group:
    """Group model for storing Telegram group data."""
    
    @staticmethod
    def create_or_update(chat_id, title, chat_type):
        """Create a new group or update an existing one."""
        group_data = {
            "chat_id": chat_id,
            "title": title,
            "type": chat_type,
            "updated_at": datetime.utcnow()
        }
        
        groups_collection.update_one(
            {"chat_id": chat_id},
            {"$set": group_data, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True
        )
        
        return group_data
    
    @staticmethod
    def get_group(chat_id):
        """Get group by chat ID."""
        return groups_collection.find_one({"chat_id": chat_id})

class Pole:
    """Pole model for storing pole data."""
    
    @staticmethod
    def create(user_id, group_id, pole_type, points, message_date):
        """Create a new pole record."""
        pole_date = message_date.strftime("%Y-%m-%d")
        
        pole_data = {
            "user_id": user_id,
            "group_id": group_id,
            "type": pole_type,
            "points": points,
            "date": pole_date,
            "created_at": message_date
        }
        
        result = poles_collection.insert_one(pole_data)
        pole_data["_id"] = result.inserted_id
        
        return pole_data
        
    @staticmethod
    def track_attempt(group_id, pole_type, user_id, message_date):
        """Track an attempt at a counter-based pole."""
        date_str = message_date.strftime("%Y-%m-%d")
        
        # Get or create the counter document
        counter_doc = db.pole_counters.find_one({
            "group_id": group_id,
            "type": pole_type,
            "date": date_str
        })
        
        if not counter_doc:
            # Create a new counter document
            counter_doc = {
                "group_id": group_id,
                "type": pole_type,
                "date": date_str,
                "count": 0,
                "user_attempts": [],
                "completed": False,
                "created_at": message_date
            }
        
        # Update the counter if not already completed
        if not counter_doc.get("completed", False):
            # Add this attempt
            counter_doc["count"] = counter_doc.get("count", 0) + 1
            
            # Track this user's attempt
            user_attempts = counter_doc.get("user_attempts", [])
            user_attempts.append({
                "user_id": user_id,
                "timestamp": message_date
            })
            counter_doc["user_attempts"] = user_attempts
            
            # Update the document
            db.pole_counters.update_one(
                {
                    "group_id": group_id,
                    "type": pole_type,
                    "date": date_str
                },
                {"$set": counter_doc},
                upsert=True
            )
        
        return counter_doc
    
    @staticmethod
    def pole_exists(group_id, pole_type, date):
        """Check if a pole already exists for the given group, type, and date."""
        date_str = date.strftime("%Y-%m-%d")
        return poles_collection.find_one({
            "group_id": group_id,
            "type": pole_type,
            "date": date_str
        }) is not None
    
    @staticmethod
    def get_daily_poles(group_id, date):
        """Get all poles for a group on a specific date."""
        date_str = date.strftime("%Y-%m-%d")
        return list(poles_collection.find({
            "group_id": group_id,
            "date": date_str
        }).sort("created_at", 1))
    
    @staticmethod
    def get_ranking(group_id=None, limit=10):
        """Get user ranking by points, optionally filtered by group."""
        match = {}
        if group_id:
            match["group_id"] = group_id
            
        pipeline = [
            {"$match": match},
            {"$group": {"_id": "$user_id", "total_points": {"$sum": "$points"}}},
            {"$sort": {"total_points": -1}},
            {"$limit": limit}
        ]
        
        return list(poles_collection.aggregate(pipeline))
        
    @staticmethod
    def get_counter_for_pole(group_id, pole_type, date):
        """Get the counter document for a counter-based pole."""
        date_str = date.strftime("%Y-%m-%d")
        return db.pole_counters.find_one({
            "group_id": group_id,
            "type": pole_type,
            "date": date_str
        })