from dotenv import load_dotenv
import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# MongoDB connection
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db_name = os.getenv("DB_NAME", "telegram_bot")

print(f"Attempting to connect to: {mongo_uri}")
print(f"Database name: {db_name}")

try:
    # Try to connect
    client = MongoClient(mongo_uri)

    # Verify connection
    server_info = client.server_info()
    print(f"Successfully connected to MongoDB (version {server_info['version']})")

    # List databases
    database_names = client.list_database_names()
    print(f"Available databases: {database_names}")

    # Use the telegram_bot database
    db = client[db_name]

    # Check collections
    collection_names = db.list_collection_names()
    print(f"Collections in {db_name}: {collection_names}")

    # Create collections and indexes if they don't exist
    if "users" not in collection_names:
        db.create_collection("users")
        db.users.create_index([("telegram_id", ASCENDING)], unique=True)
        db.users.create_index([("total_points", DESCENDING)])
        print("Created users collection with indexes")

    if "groups" not in collection_names:
        db.create_collection("groups")
        db.groups.create_index([("chat_id", ASCENDING)], unique=True)
        print("Created groups collection with indexes")

    if "poles" not in collection_names:
        db.create_collection("poles")
        db.poles.create_index(
            [("group_id", ASCENDING), ("type", ASCENDING), ("date", ASCENDING)]
        )
        db.poles.create_index([("user_id", ASCENDING)])
        db.poles.create_index([("created_at", ASCENDING)])
        # TTL index to auto-delete old pole records after 30 days
        db.poles.create_index([("expiry_date", ASCENDING)], expireAfterSeconds=0)
        print("Created poles collection with indexes")

    if "user_poles" not in collection_names:
        db.create_collection("user_poles")
        db.user_poles.create_index(
            [("user_id", ASCENDING), ("group_id", ASCENDING)], unique=True
        )
        db.user_poles.create_index(
            [("group_id", ASCENDING), ("total_points", DESCENDING)]
        )
        print("Created user_poles collection with indexes")

    if "poles_cache" not in collection_names:
        db.create_collection("poles_cache")
        db.poles_cache.create_index(
            [("group_id", ASCENDING), ("date", ASCENDING)], unique=True
        )
        # TTL index to auto-delete old cache entries after 30 days
        db.poles_cache.create_index(
            [("date", ASCENDING)], expireAfterSeconds=2592000
        )  # 30 days in seconds
        print("Created poles_cache collection with indexes")

    if "pole_counters" not in collection_names:
        db.create_collection("pole_counters")
        db.pole_counters.create_index(
            [("group_id", ASCENDING), ("type", ASCENDING), ("date", ASCENDING)],
            unique=True,
        )
        # TTL index to auto-delete old counter entries after 7 days
        db.pole_counters.create_index(
            [("expiry_date", ASCENDING)], expireAfterSeconds=0
        )
        print("Created pole_counters collection with indexes")

    if "pole_mina" not in collection_names:
        db.create_collection("pole_mina")
        db.pole_mina.create_index(
            [("group_id", ASCENDING), ("date", ASCENDING)], unique=True
        )
        # TTL index to auto-delete old pole mina entries after 7 days
        db.pole_mina.create_index([("expiry_date", ASCENDING)], expireAfterSeconds=0)
        print("Created pole_mina collection with indexes")

    # Insert some test data if collections are empty (optional)
    if db.users.count_documents({}) == 0:
        test_user = {
            "telegram_id": 12345,
            "first_name": "Test User",
            "username": "testuser",
            "is_bot": False,
            "total_points": 0,
            "poles_claimed": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        db.users.insert_one(test_user)
        print("Added test user")

    if db.groups.count_documents({}) == 0:
        test_group = {
            "chat_id": -12345,
            "title": "Test Group",
            "type": "supergroup",
            "total_poles": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        db.groups.insert_one(test_group)
        print("Added test group")

    print("Database setup complete!")

except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
