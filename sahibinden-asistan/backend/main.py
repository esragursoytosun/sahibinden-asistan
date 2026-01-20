import os
import uuid
import requests
import re
from datetime import datetime, timedelta
from typing import List
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from dotenv import load_dotenv

# --- AYARLAR ---
load_dotenv()
from backend.database import listings_collection, users_collection
from backend.scheduler import start_scheduler

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
FREE_DAILY_LIMIT = 5
ADMIN_EMAILS = ["cemerentosun@gmail.com", "esragursoytosun@gmail.com"]

# --- GOOGLE AI AYARLARI ---
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
    user_id: str | None = None

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

def clean_number(value):
    """Metin içindeki sayıyı temizler (Örn: '120.000 KM' -> 120000)"""
    if not value: return 0
    if isinstance(value, (int, float)): return int(value)
    # Sadece rakamları al
    clean_val = re.sub(r'[^\d]', '', str(value))
    return int(clean_val) if clean_val else 0

async def calculate_valuation(title, current_price, current_id, current_year):
    if not title or not current_price: return None
    try:
        # Veritabanındaki son 500 ilanı çek (Daha geniş havuz)
        cursor = listings_collection.find().sort("first_seen_at", -1).limit(500)
        all_listings = await cursor.to_list(length=500)
        
        valid_prices = []
        # Son 60 günün ilanlarına bakalım (Daha güncel piyasa)
        cutoff_date = datetime.now() - timedelta(days=60)
        
        # Hedef aracın yılı (Sayısal temizleme)
        target_year = clean_number(current_year)
        
        # Başlık analizi için anahtar kelimeler
        keywords = [k.lower() for k in title.split() if len(k) > 2][:4]
        
        for item in all_listings:
            # Kendisiyle kıyaslama
            if str(item.get("_id")) == str(current_id): continue
            
            # Tarih kontrolü
            try:
                date_str = item.get("first_seen_at", "2000-01-01 00:00:00")
                if isinstance(date_str, str):
                    item_date = datetime.strptime(date_str.split(" ")[0], "%Y-%m-%d")
                    if item_date < cutoff_date: continue
            except: pass

            p = item.get("current_price", 0)
            t = item.get("title", "").lower()
            y = clean_number(item.get("year", 0))
            
            # --- GELİŞMİŞ FİLTRELEME ---
            
            # 1. Başlık Benzerliği (En az 2 anahtar kelime tutmalı)
            match_count = sum(1 for k in keywords if k in t)
            if match_count < 2: continue

            # 2. Yıl Kontrolü (Varsa, +/- 2 yıl aralığına bak)
            # Eğer ilanın yılı yoksa, sadece başlığa göre kıyasla (mecburen)
            if target_year > 1900 and y > 1900:
                if not (target_year - 2 <= y <= target_year + 2):
                    continue 

            # 3. Fiyat Mantık Kontrolü (Çok uçuk fiyatları ele)
            # Örn: Aranan araç 1 Milyon ise, 500k altı veya 3 Milyon üstü ilanları yoksay.
            if p > 0:
                if p < (current_price * 0.5) or p > (current_price * 3):
                    continue
                valid_prices.append(p)
        
        if len(valid_prices) < 2: return None
        
        # İstatistikler
        avg_price = sum(valid_prices) / len(valid_prices)
        min_price = min(valid_prices)
        max_price = max(valid_prices)
        ratio = current_price / avg_price
        
        # Durum Analizi
        status = "Piyasa Normali"
        color = "#f1c40f" # Sarı
        if ratio <= 0.90: 
            status = "🔥 Fırsat (Kelepir)"
            color = "#2ecc71" # Yeşil
        elif ratio >= 1.10: 
            status = "💸 Piyasa Üstü"
            color = "#e74c3c" # Kırmızı
            
        return {
            "average_price": int(avg_price),
            "min_price": int(min_price),
            "max_price": int(max_price),
            "listing_count": len(valid_prices),
            "status": status,
            "color": color,
            "ratio": ratio,
            "info_msg": f"Veritabanındaki {len(valid_prices)} benzer ilan ({target_year-2}-{target_year+2} model) baz alındı."
        }
    except Exception as e:
        print(f"Valuation Hatası: {e}")
        return None

async def get_user_notes(listing_id):
    try:
        doc = await listings_collection.find_one({"_id": listing_id})
        if not doc or "comments" not in doc: return ""
        return "\n".join([f"- {c.get('user')}: {c.get('text')}" for c in doc["comments"]])
    except: return ""

# --- ENDPOINTLER ---

# 🟢 UptimeRobot Dostu Root Endpoint
@app.get("/")
@app.head("/")
async def root():
    return {"status": "active", "message": "Sahiden Asistan Uyanık! ☕"}

@app.post("/analyze-ai")
async def ask_ai(data: ListingData):
    if not GEMINI_KEY: return {"status": "error", "message": "API Key Eksik!"}
    if not data.user_id: return {"status": "login_required", "message": "Giriş yapın."}

    user = await users_collection.find_one({"_id": data.user_id})
    if user:
        if user.get("plan") != "premium" and user.get("daily_usage", 0) >= FREE_DAILY_LIMIT:
            return {"status": "limit_reached", "message": "Günlük limit doldu."}
        await users_collection.update_one({"_id": data.user_id}, {"$inc": {"daily_usage": 1}})

    # Detaylı Analiz Fonksiyonunu Çağır (Yıl bilgisini de gönderiyoruz)
    valuation = await calculate_valuation(data.title, data.price, data.id, data.year)
    user_notes = await get_user_notes(data.id)
    
    # AI'ya Gidecek Piyasa Bilgisi (Artık daha detaylı)
    if valuation:
        market_context = (
            f"VERİTABANI ANALİZİ:\n"
            f"- Benzer İlan Sayısı: {valuation['listing_count']}\n"
            f"- Piyasa Ortalaması: {valuation['average_price']} TL\n"
            f"- En Düşük Fiyat: {valuation['min_price']} TL\n"
            f"- En Yüksek Fiyat: {valuation['max_price']} TL\n"
            f"- Durum: {valuation['status']}"
        )
    else:
        market_context = "Veritabanında henüz yeterli kıyaslanabilir veri yok."

    prompt = f"""
    Sen uzman bir araç alım-satım danışmanısın (BAI Bilmiş).
    
    GÖREVİN: Aşağıdaki aracı piyasa verilerine ve kullanıcı yorumlarına göre analiz etmek.
    
    ARAÇ BİLGİLERİ:
    - Başlık: {data.title}
    - Fiyat: {data.price} TL
    - Yıl: {data.year}
    - KM: {data.km}
    - Açıklama: {data.description[:600]}...
    
    {market_context}
    
    KULLANICI YORUMLARI:
    {user_notes}
    
    İSTENEN CEVAP FORMATI:
    HTML formatında (<b>, <br> kullanarak), samimi ve net bir Türkçe ile:
    1. Fiyat Analizi (Piyasaya göre nasıl?)
    2. Araç Hakkında (KM, Yıl ve Açıklamaya göre yorumun)
    3. Sonuç (Alınır mı, pazarlık mı edilmeli?)
    """
    
    # --- MODEL DENEME ZİNCİRİ ---
    models_to_try = [
        "gemini-2.0-flash", 
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-pro"
    ]
    
    last_error = ""
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return {"status": "success", "ai_response": response.text}
        except Exception as e:
            last_error = str(e)
            print(f"Model {model_name} başarısız: {last_error}")
            continue

    if "429" in last_error: return {"status": "error", "message": "⚠️ Kota doldu (429)."}
    return {"status": "error", "message": f"AI Hatası: {last_error}"}

@app.post("/analyze")
async def analyze_listing(data: ListingData):
    if not data.id or not data.price: return {"status": "error"}
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_doc = {
            "current_price": data.price,
            "last_update": now,
            "title": data.title,
            "url": data.url,
            "year": data.year, # Yıl verisini kaydetmek önemli
            "km": data.km
        }
        
        existing = await listings_collection.find_one({"_id": data.id})
        
        # Fiyat geçmişi güncelleme
        if existing and existing.get("current_price") != data.price:
            await listings_collection.update_one({"_id": data.id}, {"$set": update_doc, "$push": {"history": {"date": now, "price": data.price}}})
        else:
            await listings_collection.update_one({"_id": data.id}, {"$set": update_doc}, upsert=True)
            
        doc = await listings_collection.find_one({"_id": data.id})
        
        # Hesaplama fonksiyonuna Yıl bilgisini de gönderiyoruz
        valuation = await calculate_valuation(data.title, data.price, data.id, data.year)
        
        return {"status": "success", "valuation": valuation, "history": doc.get("history", []), "comments": doc.get("comments", [])}
    except Exception as e:
        print(f"Analyze Hatası: {e}")
        return {"status": "error"}

@app.post("/add_comment")
async def add_comment(comment: CommentData):
    if not comment.user_id: return {"status": "error", "message": "Giriş yapın."}
    user_name = comment.username or "Misafir"
    user = await users_collection.find_one({"_id": comment.user_id})
    if user: user_name = user.get("name", user_name)

    new_comment = {
        "id": str(uuid.uuid4()),
        "user_id": comment.user_id,
        "user": user_name,
        "text": comment.text,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "liked_by": []
    }
    await listings_collection.update_one({"_id": comment.listing_id}, {"$push": {"comments": new_comment}}, upsert=True)
    
    # Ödül / Limit Mantığı
    reward_msg = "Yorum eklendi!"
    if user and user.get("plan") != "premium":
        today_str = datetime.now().strftime("%Y-%m-%d")
        last_date = user.get("last_comment_date", "")
        
        earned_today = user.get("earned_credits_today", 0) if last_date == today_str else 0
        current_progress = user.get("comment_progress", 0) if last_date == today_str else 0

        if earned_today < 2: 
            current_progress += 1
            if current_progress >= 5:
                await users_collection.update_one(
                    {"_id": comment.user_id}, 
                    {"$set": {"comment_progress": 0, "last_comment_date": today_str, "earned_credits_today": earned_today + 1}, "$inc": {"daily_usage": -1}}
                )
                reward_msg = "🎉 5 Yorum yaptın, +1 Hak kazandın!"
            else:
                await users_collection.update_one(
                    {"_id": comment.user_id}, 
                    {"$set": {"comment_progress": current_progress, "last_comment_date": today_str}}
                )
                reward_msg = f"Yorum eklendi. ({current_progress}/5)"
    
    return {"status": "success", "message": reward_msg}

@app.post("/like_comment")
async def like_comment(data: LikeData):
    doc = await listings_collection.find_one({"_id": data.listing_id})
    if not doc: return {"status": "error"}
    comments = doc.get("comments", [])
    for c in comments:
        if c.get("id") == data.comment_id:
            likes = c.get("liked_by", [])
            if data.user_id in likes: likes.remove(data.user_id)
            else: likes.append(data.user_id)
            c["liked_by"] = likes
    await listings_collection.update_one({"_id": data.listing_id}, {"$set": {"comments": comments}})
    return {"status": "success", "comments": comments}

@app.post("/auth/google")
async def google_login(data: GoogleLoginData):
    try:
        res = requests.get(f"https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {data.token}"})
        if res.status_code == 200:
            idinfo = res.json()
            if 'sub' not in idinfo and 'id' in idinfo: idinfo['sub'] = idinfo['id']
        else: raise ValueError("Token reddedildi.")
        
        google_id = idinfo['sub']
        email = idinfo.get('email')
        update_data = {
            "$set": {"email": email, "name": idinfo.get('name'), "picture": idinfo.get('picture'), "last_login": datetime.now()},
            "$setOnInsert": {"daily_usage": 0, "comment_progress": 0, "earned_credits_today": 0, "telegram_chat_id": None}
        }
        if email in ADMIN_EMAILS: update_data["$set"]["plan"] = "premium"
        else: update_data["$setOnInsert"]["plan"] = "free"
        
        await users_collection.update_one({"_id": google_id}, update_data, upsert=True)
        return {"status": "success", "user": {"id": google_id, "name": idinfo.get('name'), "picture": idinfo.get('picture')}}
    except Exception as e: raise HTTPException(status_code=401, detail=str(e))

@app.get("/admin/upgrade")
async def upgrade_user(email: str, key: str):
    if key != "cem_baba": return {"status": "error", "message": "Hatalı Şifre!"}
    user = await users_collection.find_one({"email": email})
    if not user: return {"status": "error", "message": "Kullanıcı bulunamadı."}
    await users_collection.update_one({"email": email},{"$set": {"plan": "premium", "daily_usage": 0}})
    return {"status": "success", "message": f"{email} artık PREMIUM!"}

# --- BULK UPLOAD ---
@app.post("/bulk-upload")
async def bulk_upload(listings: List[ListingData]):
    if not listings: return {"status": "empty"}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in listings:
        if not item.id or not item.price: continue
        # Basit update, geçmiş kaydı tutmaz (hız için)
        await listings_collection.update_one(
            {"_id": item.id}, 
            {"$set": {"current_price": item.price, "last_update": now, "url": item.url, "title": item.title, "year": item.year, "km": item.km}},
            upsert=True
        )
    return {"status": "success"}

@app.on_event("startup")
async def startup_event():
    start_scheduler()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)
