import os
from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB Connection Configuration
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "smart_buyer"

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
listings_collection = db["listings"]

async def get_db():
    return db
