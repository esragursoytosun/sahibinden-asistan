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
    category_path: str | None = None # <-- YENİ: Kategori Yolu

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

async def calculate_valuation(title, current_price, current_id, current_year, category_path=None):
    if not title or not current_price: return None
    try:
        # Daha geniş havuzdan (1000 ilan) tarama yap
        cursor = listings_collection.find().sort("first_seen_at", -1).limit(1000)
        all_listings = await cursor.to_list(length=1000)
        
        valid_prices = []
        cutoff_date = datetime.now() - timedelta(days=60)
        
        target_year = clean_number(current_year)
        
        # Kategori filtresi kullanılacak mı? (En az 5 karakterse geçerli say)
        use_category_filter = category_path and len(category_path) > 5
        
        # Yedek plan için başlık kelimeleri
        keywords = [k.lower() for k in title.split() if len(k) > 2][:4]
        
        for item in all_listings:
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
            item_cat = item.get("category_path", "")
            
            # --- GELİŞMİŞ FİLTRELEME ---
            
            if use_category_filter and item_cat:
                # KATEGORİ MODU: Kategori yolları eşleşiyor mu?
                if category_path not in item_cat and item_cat not in category_path:
                    continue # Eşleşmezse bu ilanı geç
            else:
                # BAŞLIK MODU (Eski Sistem): Başlık Benzerliği
                match_count = sum(1 for k in keywords if k in t)
                if match_count < 2: continue

            # 🟢 TAM YIL EŞLEŞMESİ (Strict Year Match) 🟢
            # Hedef yıl varsa, SADECE o yılın araçlarını al. (±0 Yıl)
            if target_year > 1900 and y > 1900:
                if y != target_year: 
                    continue 

            # Fiyat Mantık Kontrolü
            if p > 0:
                if p < (current_price * 0.5) or p > (current_price * 3):
                    continue
                valid_prices.append(p)
        
        if len(valid_prices) < 2: return None
        
        avg_price = sum(valid_prices) / len(valid_prices)
        min_price = min(valid_prices)
        max_price = max(valid_prices)
        ratio = current_price / avg_price
        
        status = "Piyasa Normali"
        color = "#f1c40f"
        if ratio <= 0.90: status = "🔥 Fırsat (Kelepir)"; color = "#2ecc71"
        elif ratio >= 1.10: status = "💸 Piyasa Üstü"; color = "#e74c3c"
        
        # Bilgi mesajı: Tam Yıl olduğunu belirtiyoruz
        info_msg = f"{len(valid_prices)} benzer ilan ({target_year} Model)"
        if use_category_filter: info_msg += " [Kategori]"
            
        return {
            "average_price": int(avg_price),
            "min_price": int(min_price),
            "max_price": int(max_price),
            "listing_count": len(valid_prices),
            "status": status,
            "color": color,
            "ratio": ratio,
            "info_msg": info_msg
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

# 🟢 UptimeRobot Dostu
@app.get("/")
@app.head("/")
async def root():
    return {"status": "active", "message": "Sahiden Asistan Uyanık! ☕"}

# 🟢 YENİ EKLENDİ: Arka Plan Görevleri (404 Hatasını Çözer) 🟢
@app.get("/get-update-task")
async def get_update_task():
    """Arka plan işçisi için güncellenmesi gereken eski bir ilanı döndürür."""
    try:
        # Son güncellemesi 24 saatten eski olan bir ilan bul
        cutoff_time = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Rastgele eski bir ilan seç (Sadece URL ve ID lazım)
        task = await listings_collection.find_one(
            {"last_update": {"$lt": cutoff_time}, "url": {"$exists": True, "$ne": ""}}
        )
        
        if task:
            return {"status": "task_found", "id": task["_id"], "url": task["url"]}
        
        return {"status": "no_task"}
    except: return {"status": "error"}

@app.post("/update-price-background")
async def update_price_background(data: ListingData):
    """Arka plan işçisinden gelen güncel fiyatı kaydeder."""
    if not data.id or not data.price: return {"status": "error"}
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    existing = await listings_collection.find_one({"_id": data.id})
    if existing:
        last_price = existing.get("current_price", 0)
        # Fiyat değişmişse geçmişe ekle
        if last_price != data.price:
            await listings_collection.update_one(
                {"_id": data.id}, 
                {
                    "$set": {"current_price": data.price, "last_update": now},
                    "$push": {"history": {"date": now, "price": last_price}}
                }
            )
        else:
            # Fiyat aynıysa sadece güncelleme tarihini yenile
            await listings_collection.update_one(
                {"_id": data.id}, 
                {"$set": {"last_update": now}}
            )
            
    return {"status": "success"}

@app.post("/analyze-ai")
async def ask_ai(data: ListingData):
    if not GEMINI_KEY: return {"status": "error", "message": "API Key Eksik!"}
    if not data.user_id: return {"status": "login_required", "message": "Giriş yapın."}

    user = await users_collection.find_one({"_id": data.user_id})
    if user:
        if user.get("plan") != "premium" and user.get("daily_usage", 0) >= FREE_DAILY_LIMIT:
            return {"status": "limit_reached", "message": "Günlük limit doldu."}
        await users_collection.update_one({"_id": data.user_id}, {"$inc": {"daily_usage": 1}})

    # Valuation'a kategori yolunu da gönder
    valuation = await calculate_valuation(data.title, data.price, data.id, data.year, data.category_path)
    user_notes = await get_user_notes(data.id)
    
    market_context = "Veri yok"
    if valuation:
        market_context = (
            f"VERİTABANI ANALİZİ:\n"
            f"- Kategori: {data.category_path or 'Genel'}\n"
            f"- Benzer İlan: {valuation['listing_count']} adet\n"
            f"- Ort: {valuation['average_price']} TL | Min: {valuation['min_price']} TL | Max: {valuation['max_price']} TL\n"
            f"- Durum: {valuation['status']}"
        )

    prompt = f"""
    Sen uzman bir araç alım-satım danışmanısın (BAI Bilmiş).
    ARAÇ: {data.title}, {data.price} TL, {data.year}, {data.km}
    KATEGORİ: {data.category_path}
    AÇIKLAMA: {data.description[:600]}...
    {market_context}
    NOTLAR: {user_notes}
    GÖREV: Fiyat/Performans analizi yap. HTML ile cevap ver.
    """
    
    # 🟢 MODEL LİSTESİ VE HATA YÖNETİMİ (RETRY MEKANİZMASI İLE) 🟢
    import time
    import asyncio
    
    models_to_try = [
        "gemini-2.0-flash",       # 2026'da standart
        "gemini-2.0-flash-lite",  # Hafif sürüm
        "gemini-1.5-flash",       # Yedek
        "gemini-pro"              # En eski yedek
    ]
    
    max_retries = 3
    last_error = ""
    
    for model_name in models_to_try:
        for retry in range(max_retries):
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                return {"status": "success", "ai_response": response.text}
            except Exception as e:
                error_str = str(e).lower()
                print(f"❌ Model {model_name} Hatası (Deneme {retry+1}/{max_retries}): {e}")
                last_error = str(e)
                
                # Rate limit veya resource exhausted hatası mı kontrol et
                if "resource" in error_str or "exhausted" in error_str or "429" in error_str or "quota" in error_str or "rate" in error_str:
                    # Bu model için bekle ve tekrar dene
                    if retry < max_retries - 1:
                        wait_time = (retry + 1) * 2  # 2, 4, 6 saniye bekle
                        print(f"⏳ AI meşgul, {wait_time} saniye bekleniyor...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # Bu model için tüm denemeler tükendi, sonraki modele geç
                        break
                else:
                    # Başka bir hata, sonraki modele geç
                    break

    # Tüm modeller başarısız olduysa
    error_lower = last_error.lower()
    if "resource" in error_lower or "exhausted" in error_lower or "429" in error_lower or "quota" in error_lower or "rate" in error_lower:
        return {"status": "error", "message": "🔄 AI şu an yoğun. Lütfen birkaç saniye sonra tekrar deneyin."}
    
    return {"status": "error", "message": f"AI Bağlantı Hatası: {last_error}"}

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
            "year": data.year,
            "km": data.km,
            "category_path": data.category_path # <-- Kategori Kaydı
        }
        
        existing = await listings_collection.find_one({"_id": data.id})
        
        if existing and existing.get("current_price") != data.price:
            await listings_collection.update_one({"_id": data.id}, {"$set": update_doc, "$push": {"history": {"date": now, "price": data.price}}})
        else:
            await listings_collection.update_one({"_id": data.id}, {"$set": update_doc}, upsert=True)
            
        doc = await listings_collection.find_one({"_id": data.id})
        valuation = await calculate_valuation(data.title, data.price, data.id, data.year, data.category_path)
        
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
        
        # Mevcut kullanıcıyı kontrol et
        existing_user = await users_collection.find_one({"_id": google_id})
        
        update_data = {
            "$set": {"email": email, "name": idinfo.get('name'), "picture": idinfo.get('picture'), "last_login": datetime.now()},
            "$setOnInsert": {"daily_usage": 0, "comment_progress": 0, "earned_credits_today": 0, "telegram_chat_id": None}
        }
        if email in ADMIN_EMAILS: update_data["$set"]["plan"] = "premium"
        else: update_data["$setOnInsert"]["plan"] = "free"
        
        await users_collection.update_one({"_id": google_id}, update_data, upsert=True)
        
        # Güncel kullanıcı bilgilerini al
        updated_user = await users_collection.find_one({"_id": google_id})
        
        return {
            "status": "success", 
            "user": {
                "id": google_id, 
                "name": idinfo.get('name'), 
                "picture": idinfo.get('picture'),
                "email": email,
                "plan": updated_user.get("plan", "free"),
                "daily_usage": updated_user.get("daily_usage", 0)
            }
        }
    except Exception as e: raise HTTPException(status_code=401, detail=str(e))

# 🟢 KULLANICI PROFİL BİLGİLERİ (Güncel usage ve plan)
@app.get("/user/profile/{user_id}")
async def get_user_profile(user_id: str):
    """Kullanıcının güncel profil bilgilerini döndürür"""
    try:
        user = await users_collection.find_one({"_id": user_id})
        if not user:
            return {"status": "error", "message": "Kullanıcı bulunamadı"}
        
        is_premium = user.get("plan") == "premium"
        daily_limit = 999 if is_premium else FREE_DAILY_LIMIT
        daily_usage = user.get("daily_usage", 0)
        
        return {
            "status": "success",
            "profile": {
                "id": user_id,
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "picture": user.get("picture", ""),
                "plan": user.get("plan", "free"),
                "daily_usage": daily_usage,
                "daily_limit": daily_limit,
                "remaining": max(0, daily_limit - daily_usage) if not is_premium else 999,
                "comment_progress": user.get("comment_progress", 0)
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/admin/upgrade")
async def upgrade_user(email: str, key: str):
    if key != "cem_baba": return {"status": "error", "message": "Hatalı Şifre!"}
    user = await users_collection.find_one({"email": email})
    if not user: return {"status": "error", "message": "Kullanıcı bulunamadı."}
    await users_collection.update_one({"email": email},{"$set": {"plan": "premium", "daily_usage": 0}})
    return {"status": "success", "message": f"{email} artık PREMIUM!"}

# --- BULK UPLOAD (Kategori Destekli & Tarih Düzeltmeli) ---
@app.post("/bulk-upload")
async def bulk_upload(listings: List[ListingData]):
    if not listings: return {"status": "empty"}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in listings:
        if not item.id or not item.price: continue
        
        # $min OPERATÖRÜ İLE ZEKİ TARİH GÜNCELLEMESİ
        await listings_collection.update_one(
            {"_id": item.id}, 
            {
                "$set": {
                    "current_price": item.price, 
                    "last_update": now, 
                    "url": item.url, 
                    "title": item.title, 
                    "year": item.year, 
                    "km": item.km,
                    "category_path": item.category_path # <-- Kategori Kaydı
                },
                "$min": { "first_seen_at": now }, # Eksik tarihleri düzeltir
                "$setOnInsert": { "history": [], "comments": [] }
            },
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
