# backend/main.py - GOOGLE LOGIN & PROFILE 🔐
import os
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import motor.motor_asyncio
import google.generativeai as genai
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AYARLAR ---
MONGO_URL = os.environ.get("MONGO_URL")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
# Google Cloud'dan aldığın Client ID'yi buraya Environment Variable olarak eklesen iyi olur
# Render'da GOOGLE_CLIENT_ID adıyla ekleyebilirsin.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID") 

# DB BAĞLANTISI
collection = None
users_collection = None # Kullanıcıları tutacağımız yeni tablo
if MONGO_URL:
    try:
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
        db = client.sahibinden_db
        collection = db.listings
        users_collection = db.users
    except Exception as e:
        print(f"DB Bağlantı Hatası: {e}")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# --- MODELLER ---
class ListingData(BaseModel):
    id: str | None = None; price: int | float | None = None; title: str | None = None
    url: str | None = None; description: str | None = None; km: str | None = None; year: str | None = None

class CommentData(BaseModel):
    listing_id: str; user_id: str; text: str # user_id artık google ID olacak

class LikeData(BaseModel):
    listing_id: str; comment_id: str; user_id: str

class GoogleLoginData(BaseModel):
    token: str # Frontend'den gelen Google ID Token

# --- ENDPOINTLER ---

@app.post("/auth/google")
async def google_login(data: GoogleLoginData):
    """Google Token'ı doğrular ve kullanıcıyı kaydeder."""
    try:
        # 1. Google'a sor: Bu token gerçek mi?
        idinfo = id_token.verify_oauth2_token(data.token, google_requests.Request(), GOOGLE_CLIENT_ID)
        
        # 2. Bilgileri al
        google_id = idinfo['sub']
        email = idinfo.get('email')
        name = idinfo.get('name')
        picture = idinfo.get('picture')
        
        # 3. Veritabanına kaydet/güncelle (Upsert)
        if users_collection is not None:
            user_data = {
                "_id": google_id,
                "email": email,
                "name": name,
                "picture": picture,
                "last_login": datetime.now()
            }
            await users_collection.update_one({"_id": google_id}, {"$set": user_data}, upsert=True)
            
        return {"status": "success", "user": {"id": google_id, "name": name, "picture": picture}}
        
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Geçersiz Token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ... (ask_ai, analyze, find_similars fonksiyonları aynen kalacak, yer kaplamasın diye kısalttım) ...
# BAI BİLMİŞ'in diğer kodları burada devam ediyor (find_similars vs.)
# analyze-ai, analyze endpointleri önceki kodla aynı kalabilir.
# Sadece yorum eklerken artık "username" yerine veritabanından isim çekeceğiz.

@app.post("/add_comment")
async def add_comment(comment: CommentData):
    if collection is None: return {"status": "error"}
    
    # Kullanıcı adını veritabanından bul
    user_name = "Anonim"
    user_pic = ""
    if users_collection:
        user = await users_collection.find_one({"_id": comment.user_id})
        if user: 
            user_name = user.get("name", "Anonim")
            user_pic = user.get("picture", "")

    new_comment = {
        "id": str(uuid.uuid4()), 
        "user_id": comment.user_id,
        "user": user_name, # İsmi artık Google'dan alıyoruz
        "user_pic": user_pic,
        "text": comment.text, 
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"), 
        "liked_by": []
    }
    await collection.update_one({"_id": comment.listing_id}, {"$push": {"comments": new_comment}})
    updated = await collection.find_one({"_id": comment.listing_id})
    return {"status": "success", "comments": updated.get("comments", [])}

# Diğer endpointler (like_comment, analyze, analyze-ai) önceki kodun aynısı olarak kalmalı.
# Sadece main bloğunu eklemeyi unutma.

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)
