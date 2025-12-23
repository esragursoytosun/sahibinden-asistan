import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Localde çalışırken .env dosyasındaki şifreleri yükler
load_dotenv()

# MongoDB Bağlantı Ayarları
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "smart_buyer"  # Veritabanı adın bu, gayet güzel.

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# İlanların kaydedileceği yer
listings_collection = db["listings"]

# --- YENİ EKLENEN KISIM ---
# Google ile giriş yapan üyelerin kaydedileceği yer
users_collection = db["users"] 

async def get_db():
    return db
