import os
import uuid
import requests
import json
from datetime import datetime, timedelta
from typing import List
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
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
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# --- SABİTLER ---
FREE_DAILY_LIMIT = 5
ADMIN_EMAILS = ["cemerentosun@gmail.com", "esragursoytosun@gmail.com"]

# --- MODEL LİSTESİ (Sırayla denenecek) ---
# "v1beta" yerine "v1" endpointi kullanılacak.
GEMINI_MODELS = [
    "gemini-1.5-flash",
    "gemini-pro",
    "gemini-1.5-pro",
    "gemini-1.0-pro"
]

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
async def calculate_valuation(title, current_price, current_id):
    if not title or not current_price: return None
    try:
        keywords = [k.lower() for k in title.split() if len(k) > 2][:3]
        cursor = listings_collection.find().sort("first_seen_at", -1).limit(150)
        all_listings = await cursor.to_list(length=150)
        valid_prices = []
        cutoff_date = datetime.now() - timedelta(days=30)
        
        for item in all_listings:
            if str(item.get("_id")) == str(current_id): continue
            date_str = item.get("first_seen_at", "2000-01-01 00:00:00")
            try:
                item_date = datetime.strptime(date_str.split(" ")[0], "%Y-%m-%d")
                if item_date < cutoff_date: continue
            except: continue
            item_title = item.get("title", "").lower()
            item_price = item.get("current_price", 0)
            match_count = sum(1 for k in keywords if k in item_title)
            if match_count >= 2 and item_price > 0:
                valid_prices.append(item_price)
        
        if len(valid_prices) < 3: return None
        valid_prices.sort()
        trim_amount = int(len(valid_prices) * 0.1)
        if trim_amount > 0: filtered_prices = valid_prices[trim_amount:-trim_amount]
        else: filtered_prices = valid_prices
        if not filtered_prices: filtered_prices = valid_prices

        avg_price = sum(filtered_prices) / len(filtered_prices)
        ratio = current_price / avg_price
        status = "Piyasa Normali"
        color = "#f1c40f"
        if ratio <= 0.92: status = "🔥 Fırsat (Kelepir)"; color = "#2ecc71"
        elif ratio >= 1.08: status = "💸 Piyasa Üstü"; color = "#e74c3c"
            
        return {
            "average_price": int(avg_price),
            "listing_count": len(filtered_prices),
            "status": status,
            "color": color,
            "ratio": ratio,
            "difference_tl": int(avg_price - current_price),
            "info_msg": f"Son 30 gündeki {len(filtered_prices)} benzer ilan baz alındı."
        }
    except Exception as e: return None

async def get_user_notes(listing_id):
    try:
        doc = await listings_collection.find_one({"_id": listing_id})
        if not doc or "comments" not in doc: return ""
        notes = [f"- {c.get('user')}: {c.get('text')}" for c in doc["comments"]]
        return "\n".join(notes) if notes else ""
    except: return ""

# --- ENDPOINTLER ---
@app.get("/")
async def root(): return {"status": "active", "message": "Sahibinden Asistan Sunucusu Calisiyor! 🚀"}

@app.get("/version")
async def check_version():
    return {"latest_version": "2.8", "message": "Güncel (v1 API)", "force_update": False}

@app.post("/bulk-upload")
async def bulk_upload(listings: List[ListingData]):
    if not listings: return {"status": "empty"}
    count = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in listings:
        if not item.id or not item.price: continue
        existing = await listings_collection.find_one({"_id": item.id})
        if existing:
            last_price = existing.get("current_price", item.price)
            if last_price != item.price:
                await listings_collection.update_one({"_id": item.id}, {"$push": {"history": {"date": now, "price": last_price}}})
            await listings_collection.update_one({"_id": item.id}, {"$set": {"current_price": item.price, "last_update": now, "url": item.url}})
        else:
            new_record = {"_id": item.id, "title": item.title, "url": item.url, "first_seen_at": now, "last_update": now, "current_price": item.price, "year": item.year, "km": item.km, "history": [], "comments": []}
            await listings_collection.insert_one(new_record)
        count += 1
    return {"status": "success", "processed_count": count}

@app.get("/get-update-task")
async def get_update_task():
    try:
        yesterday = datetime.now() - timedelta(hours=24)
        yesterday_str = yesterday.strftime("%Y-%m-%d %H:%M:%S")
        pipeline = [{"$match": {"$or": [{"last_update": {"$lt": yesterday_str}}, {"last_update": {"$exists": False}}]}}, {"$sample": {"size": 1}}]
        cursor = listings_collection.aggregate(pipeline)
        tasks = await cursor.to_list(length=1)
        if tasks:
            task = tasks[0]
            return {"status": "task_found", "url": task.get("url"), "id": task.get("_id")}
        return {"status": "no_task", "message": "Her şey güncel!"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/update-price-background")
async def update_price_background(data: ListingData):
    if not data.id or not data.price: return {"status": "error"}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = await listings_collection.find_one({"_id": data.id})
    if existing:
        last_price = existing.get("current_price", 0)
        if last_price != data.price:
            await listings_collection.update_one({"_id": data.id}, {"$push": {"history": {"date": now, "price": last_price}}})
        await listings_collection.update_one({"_id": data.id}, {"$set": {"current_price": data.price, "last_update": now}})
        return {"status": "success", "message": "Fiyat güncellendi"}
    return {"status": "error"}

@app.post("/auth/google")
async def google_login(data: GoogleLoginData):
    try:
        idinfo = None
        try: idinfo = id_token.verify_oauth2_token(data.token, google_requests.Request(), GOOGLE_CLIENT_ID)
        except Exception: pass
        if not idinfo:
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

# --- AI ANALİZ (MULTI-MODEL REST API - v1) ---
@app.post("/analyze-ai")
async def ask_ai(data: ListingData):
    if not GEMINI_KEY: return {"status": "error", "message": "API Key Eksik!"}
    if not data.user_id: return {"status": "login_required", "message": "Giriş yapın."}

    user = await users_collection.find_one({"_id": data.user_id})
    if user:
        plan = user.get("plan", "free")
        usage = user.get("daily_usage", 0)
        if plan != "premium" and usage >= FREE_DAILY_LIMIT:
            return {"status": "limit_reached", "message": f"🔒 Günlük limit doldu. 5 yorum yaparak ek hak kazanabilirsin."}
        await users_collection.update_one({"_id": data.user_id}, {"$inc": {"daily_usage": 1}})

    valuation = await calculate_valuation(data.title, data.price, data.id)
    user_notes = await get_user_notes(data.id)
    market_context = "Yeterli piyasa verisi yok."
    if valuation: market_context = (f"Piyasa Ortalaması: {valuation['average_price']} TL. Durum: {valuation['status']}.")
    
    prompt = f"""
    KİMLİK: "BAI Bilmiş", uzman galericisin.
    İLAN: Başlık: {data.title}, Fiyat: {data.price} TL, KM/Yıl: {data.km}, {data.year}
    Açıklama: "{data.description[:500]}..."
    VERİ ANALİZİ: {market_context}, Yorumlar: {user_notes}
    GÖREV: Bu aracı almalı mıyım? Fiyat/Performans analizi yap. HTML formatında cevap ver.
    """
    
    # --- MODEL DENEME DÖNGÜSÜ ---
    last_error = ""
    for model_name in GEMINI_MODELS:
        try:
            # v1beta yerine v1 kullanıyoruz (ÇOK ÖNEMLİ)
            url = f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent?key={GEMINI_KEY}"
            headers = {"Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            
            response = requests.post(url, headers=headers, json=payload, timeout=25)
            
            if response.status_code == 200:
                result = response.json()
                try:
                    ai_text = result['candidates'][0]['content']['parts'][0]['text']
                    return {"status": "success", "ai_response": ai_text} # BAŞARILI!
                except:
                    continue # Cevap bozuksa sonrakini dene
            
            last_error = f"Model {model_name} Hatası: {response.status_code} - {response.text}"
            print(last_error) # Loglara yaz
            
        except Exception as e:
            last_error = f"Bağlantı hatası ({model_name}): {str(e)}"
            continue

    if "429" in last_error: return {"status": "error", "message": "⚠️ Kota doldu (429)."}
    return {"status": "error", "message": f"Tüm modeller denendi. Son hata: {last_error}"}

@app.post("/analyze")
async def analyze_listing(data: ListingData):
    if not data.id or not data.price: return {"status": "error"}
    try:
        existing = await listings_collection.find_one({"_id": data.id})
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response = {"status": "success", "comments": [], "history": []}
        update_doc = {"current_price": data.price, "last_update": now, "title": data.title, "url": data.url, "year": data.year, "km": data.km}

        if existing:
            last_price = existing.get("current_price", data.price)
            if last_price != data.price:
                await listings_collection.update_one({"_id": data.id}, {"$set": update_doc, "$push": {"history": {"date": now, "price": last_price}}})
            else:
                await listings_collection.update_one({"_id": data.id}, {"$set": update_doc})
            full_history = existing.get("history", [])
            full_history.append({"date": "Şimdi", "price": data.price})
            response["history"] = full_history
            response["comments"] = existing.get("comments", [])
        else:
            new_record = {"_id": data.id, "first_seen_at": now, "history": [], "comments": [], **update_doc}
            await listings_collection.insert_one(new_record)
            response["history"] = [{"date": "Şimdi", "price": data.price}]
        valuation = await calculate_valuation(data.title, data.price, data.id)
        response["valuation"] = valuation
        return response
    except: return {"status": "error"}

@app.post("/add_comment")
async def add_comment(comment: CommentData):
    if not comment.user_id: return {"status": "error", "message": "Giriş yapın."}
    
    user_name = comment.username or "Misafir"
    user = await users_collection.find_one({"_id": comment.user_id})
    if user: user_name = user.get("name", user_name)

    new_comment = {"id": str(uuid.uuid4()), "user_id": comment.user_id, "user": user_name, "text": comment.text, "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "liked_by": []}
    
    await listings_collection.update_one({"_id": comment.listing_id}, {"$push": {"comments": new_comment}}, upsert=True)

    reward_msg = "Yorum eklendi!"
    if user and user.get("plan") != "premium":
        today_str = datetime.now().strftime("%Y-%m-%d")
        last_date = user.get("last_comment_date", "")
        if last_date != today_str: earned_today, current_progress = 0, 0
        else: earned_today, current_progress = user.get("earned_credits_today", 0), user.get("comment_progress", 0)

        if earned_today < 2:
            current_progress += 1
            if current_progress >= 5:
                await users_collection.update_one({"_id": comment.user_id}, {"$set": {"comment_progress": 0, "last_comment_date": today_str, "earned_credits_today": earned_today + 1}, "$inc": {"daily_usage": -1}})
                reward_msg = "🎉 5 Yorum yaptın, +1 Hak kazandın!"
            else:
                await users_collection.update_one({"_id": comment.user_id}, {"$set": {"comment_progress": current_progress, "last_comment_date": today_str}})
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

@app.on_event("startup")
async def startup_event():
    start_scheduler()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)
