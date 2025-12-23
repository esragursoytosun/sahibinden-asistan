import os
import uuid
import requests 
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from dotenv import load_dotenv

# --- AYARLAR VE VERİTABANI ---
load_dotenv() # .env dosyasını yükle

# Database.py'den tabloları çekiyoruz (Modüler Yapı)
# Not: Aynı klasörde oldukları için ".database" veya "backend.database" kullanılır.
from backend.database import listings_collection, users_collection

app = FastAPI()

# --- CORS AYARLARI ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API ANAHTARLARI ---
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")

# --- AI AYARLARI ---
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# --- VERİ MODELLERİ ---
class ListingData(BaseModel):
    id: str | None = None
    price: int | float | None = None
    title: str | None = None
    url: str | None = None
    description: str | None = None
    km: str | None = None
    year: str | None = None

class CommentData(BaseModel):
    listing_id: str
    user_id: str
    text: str
    username: str | None = None

class LikeData(BaseModel):
    listing_id: str
    comment_id: str
    user_id: str

class GoogleLoginData(BaseModel):
    token: str

# --- YARDIMCI FONKSİYONLAR ---

async def find_similars(title, current_id):
    """Veritabanındaki benzer ilanların fiyatlarını getirir."""
    if not title: return "Veritabanı bağlantısı yok."
    try:
        keywords = set(title.lower().split())
        keywords = {k for k in keywords if len(k) > 2}
        
        cursor = listings_collection.find().sort("first_seen_at", -1).limit(50)
        all_listings = await cursor.to_list(length=50)
        
        prices = []
        for item in all_listings:
            if str(item.get("_id")) == str(current_id): continue
            item_title = item.get("title", "").lower()
            item_price = item.get("current_price", 0)
            
            common = keywords.intersection(set(item_title.split()))
            if len(common) >= 2 and item_price > 0:
                prices.append(item_price)
                
        if not prices: return "Veritabanımızda henüz yeterli kıyaslama verisi yok."
        
        avg = sum(prices) / len(prices)
        return f"Daha önce kaydettiğin {len(prices)} benzer ilanın ortalaması: {avg:,.0f} TL."
    except: return "Veritabanı analizi yapılamadı."

async def get_user_notes(listing_id):
    """Bu ilana yapılan yorumları getirir."""
    try:
        doc = await listings_collection.find_one({"_id": listing_id})
        if not doc or "comments" not in doc: return ""
        notes = [f"- {c.get('user')}: {c.get('text')}" for c in doc["comments"]]
        return "\n".join(notes) if notes else ""
    except: return ""

# --- ENDPOINTLER ---

@app.post("/auth/google")
async def google_login(data: GoogleLoginData):
    """Gelişmiş Google Giriş İşlemi (Hem ID Token Hem Access Token Destekler)"""
    try:
        idinfo = None
        # 1. Yöntem: ID Token doğrulamayı dene
        try:
            idinfo = id_token.verify_oauth2_token(data.token, google_requests.Request(), GOOGLE_CLIENT_ID)
        except Exception:
            pass

        # 2. Yöntem: Eğer ID Token çalışmadıysa, Access Token (Chrome Extension) olarak dene
        if not idinfo:
            res = requests.get(f"https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {data.token}"})
            if res.status_code == 200:
                idinfo = res.json()
                # Google bazen 'sub' bazen 'id' döndürür, standartlaştıralım:
                if 'sub' not in idinfo and 'id' in idinfo:
                    idinfo['sub'] = idinfo['id']
            else:
                raise ValueError("Token Google tarafından reddedildi.")

        # Kullanıcı bilgilerini al
        google_id = idinfo['sub']
        email = idinfo.get('email')
        name = idinfo.get('name')
