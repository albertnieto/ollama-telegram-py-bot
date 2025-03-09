from dotenv import load_dotenv
import os
from pymongo import MongoClient

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
    
    # Create collections if they don't exist
    if 'users' not in collection_names:
        db.create_collection('users')
        db.users.create_index({"telegram_id": 1}, unique=True)
        print("Created users collection")
    
    if 'groups' not in collection_names:
        db.create_collection('groups')
        db.groups.create_index({"chat_id": 1}, unique=True)
        print("Created groups collection")
    
    if 'poles' not in collection_names:
        db.create_collection('poles')
        db.poles.create_index({"group_id": 1, "type": 1, "date": 1})
        print("Created poles collection")
    
    if 'pole_counters' not in collection_names:
        db.create_collection('pole_counters')
        db.pole_counters.create_index({"group_id": 1, "type": 1, "date": 1}, unique=True)
        print("Created pole_counters collection")
        
    if 'pole_mina' not in collection_names:
        db.create_collection('pole_mina')
        db.pole_mina.create_index({"group_id": 1, "date": 1}, unique=True)
        print("Created pole_mina collection")
    
    print("Database setup complete!")
    
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")