import os
import uuid
import requests
from datetime import datetime, timedelta
from typing import List
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
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
FREE_DAILY_LIMIT = 5  # Standart Günlük Hak
ADMIN_EMAILS = ["cemerentosun@gmail.com", "esragursoytosun@gmail.com"]

if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
    except: pass

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
    return {
        "latest_version": "1.4",
        "message": "🧹 SÜPÜRGE MODU AKTİF! Liste sayfalarındaki ilanlar artık otomatik kaydediliyor.",
        "force_update": False
    }

@app.get("/debug-models")
async def debug_models():
    if not GEMINI_KEY: return {"error": "API Key eksik"}
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        return {"available_models": models}
    except Exception as e: return {"error": str(e)}

# --- SÜPÜRGE MODU ---
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

# --- ZOMBI AJAN ---
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

# --- AUTH & USER MANAGEMENT ---
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
            "$set": {
                "email": email, 
                "name": idinfo.get('name'), 
                "picture": idinfo.get('picture'), 
                "last_login": datetime.now()
            },
            "$setOnInsert": {
                "daily_usage": 0,
                "comment_progress": 0,
                "earned_credits_today": 0,
                "telegram_chat_id": None
            }
        }

        # PATRON MODU
        if email in ADMIN_EMAILS:
            update_data["$set"]["plan"] = "premium"
        else:
            update_data["$setOnInsert"]["plan"] = "free"

        await users_collection.update_one({"_id": google_id}, update_data, upsert=True)
        return {"status": "success", "user": {"id": google_id, "name": idinfo.get('name'), "picture": idinfo.get('picture')}}
    except Exception as e: raise HTTPException(status_code=401, detail=str(e))

# --- GİZLİ ADMIN PANELİ ---
@app.get("/admin/upgrade")
async def upgrade_user(email: str, key: str):
    if key != "cem_baba": return {"status": "error", "message": "Hatalı Şifre!"}
    user = await users_collection.find_one({"email": email})
    if not user: return {"status": "error", "message": "Kullanıcı bulunamadı."}
    await users_collection.update_one({"email": email},{"$set": {"plan": "premium", "daily_usage": 0}})
    return {"status": "success", "message": f"{email} artık PREMIUM!"}

# --- AI ANALİZ ---
@app.post("/analyze-ai")
async def ask_ai(data: ListingData):
    if not GEMINI_KEY: return {"status": "error", "message": "API Key Eksik!"}
    
    # 1. MİSAFİR KONTROLÜ
    if not data.user_id:
        return {
            "status": "error",
            "message": "🔒 Analiz yapmak için **Giriş Yapmalısınız!**"
        }

    # 2. LİMİT KONTROLÜ
    user = await users_collection.find_one({"_id": data.user_id})
    if user:
        plan = user.get("plan", "free")
        usage = user.get("daily_usage", 0)
        
        # Premium değilse ve limit dolduysa
        if plan != "premium" and usage >= FREE_DAILY_LIMIT:
            return {
                "status": "limit_reached",
                "message": f"🔒 Günlük {FREE_DAILY_LIMIT} adet ücretsiz analiz hakkınız doldu.\n\n💬 **İPUCU:** 5 farklı ilana yorum yaparsan **+1 Analiz Hakkı** kazanırsın!\n(Günde en fazla 2 ek hak kazanılabilir)\n\n👑 Sınırsız analiz için Premium'a geç."
            }
        
        await users_collection.update_one({"_id": data.user_id}, {"$inc": {"daily_usage": 1}})

    # 3. ANALİZ İŞLEMİ
    valuation = await calculate_valuation(data.title, data.price, data.id)
    user_notes = await get_user_notes(data.id)
    market_context = "Yeterli piyasa verisi yok."
    if valuation: market_context = (f"Piyasa Ortalaması: {valuation['average_price']} TL. Durum: {valuation['status']}. {valuation['info_msg']}")
    
    prompt = f"""
    KİMLİK: "BAI Bilmiş", uzman galericisin.
    İLAN: Başlık: {data.title}, Fiyat: {data.price} TL, KM/Yıl: {data.km}, {data.year}
    Açıklama: "{data.description[:500]}..."
    VERİ ANALİZİ: {market_context}, Yorumlar: {user_notes}
    GÖREV: Bu aracı almalı mıyım? Fiyat/Performans analizi yap. HTML formatında (<b>, <ul>, <li>) cevap ver.
    """
    
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return {"status": "success", "ai_response": response.text}
    except Exception as e:
        if "429" in str(e): return {"status": "error", "message": "⚠️ Sunucu çok yoğun, lütfen bekleyin."}
        return {"status": "error", "message": str(e)}

# --- YORUM VE ÖDÜL SİSTEMİ (YENİ KURGU: 5 Yorum = 1 Hak / Max 2 Kez) ---
@app.post("/add_comment")
async def add_comment(comment: CommentData):
    # 1. MİSAFİR KONTROLÜ
    if not comment.user_id:
        return {"status": "error", "message": "❌ Yorum yapmak için giriş yapmalısınız!"}

    user_name = comment.username or "Misafir"
    user = await users_collection.find_one({"_id": comment.user_id})
    if user: user_name = user.get("name", user_name)

    # Yorumu Ekle
    new_comment = {"id": str(uuid.uuid4()), "user_id": comment.user_id, "user": user_name, "text": comment.text, "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "liked_by": []}
    await listings_collection.update_one({"_id": comment.listing_id}, {"$push": {"comments": new_comment}})

    # 2. ÖDÜL SİSTEMİ
    reward_msg = "Yorum eklendi! ✅"
    
    if user and user.get("plan") != "premium": # Premium değilse
        today_str = datetime.now().strftime("%Y-%m-%d")
        last_date = user.get("last_comment_date", "")
        
        # Eğer gün değiştiyse sayaçları sıfırla
        if last_date != today_str:
            earned_today = 0
            current_progress = 0
        else:
            earned_today = user.get("earned_credits_today", 0)
            current_progress = user.get("comment_progress", 0)

        # Eğer günlük max ödül (2 tane) alınmadıysa devam et
        if earned_today < 2:
            current_progress += 1
            
            # 5 Yorum hedefine ulaşıldı mı?
            if current_progress >= 5:
                # Ödülü ver, sayacı sıfırla
                await users_collection.update_one(
                    {"_id": comment.user_id}, 
                    {
                        "$set": {
                            "comment_progress": 0, 
                            "last_comment_date": today_str,
                            "earned_credits_today": earned_today + 1
                        },
                        "$inc": {"daily_usage": -1} # Limiti 1 geri çek (hak ver)
                    }
                )
                reward_msg = f"🎉 TEBRİKLER! 5 yorum yaptın ve +1 Analiz Hakkı kazandın! (Bugün: {earned_today + 1}/2 Ödül) 🎁"
            else:
                # İlerlemeyi kaydet
                await users_collection.update_one(
                    {"_id": comment.user_id}, 
                    {
                        "$set": {
                            "comment_progress": current_progress,
                            "last_comment_date": today_str
                        }
                    }
                )
                reward_msg = f"Yorum eklendi. ({current_progress}/5 yorum sonra +1 Hak! 🎁)"
        else:
            # Günlük ödül limiti doldu
             await users_collection.update_one(
                    {"_id": comment.user_id}, 
                    {"$set": {"last_comment_date": today_str}}
            )
             reward_msg = "Yorum eklendi. (Bugünlük kazanabileceğiniz maksimum ek hakka ulaştınız) ✅"

    return {"status": "success", "message": reward_msg}

@app.post("/like_comment")
async def like_comment(data: LikeData):
    doc = await listings_collection.find_one({"_id": data.listing_id})
    if not doc: return {"status": "error"}
    comments = doc.get("comments", [])
    updated_comments = []
    for c in comments:
        if c.get("id") == data.comment_id:
            likes = c.get("liked_by", [])
            if not isinstance(likes, list): likes = []
            if data.user_id in likes: likes.remove(data.user_id)
            else: likes.append(data.user_id)
            c["liked_by"] = likes
        updated_comments.append(c)
    await listings_collection.update_one({"_id": data.listing_id}, {"$set": {"comments": updated_comments}})
    return {"status": "success", "comments": updated_comments}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "")
            if text.startswith("/start") and len(text.split()) > 1:
                google_user_id = text.split()[1]
                await users_collection.update_one({"_id": google_user_id}, {"$set": {"telegram_chat_id": chat_id}})
    except: pass
    return {"status": "ok"}

@app.on_event("startup")
async def startup_event():
    start_scheduler()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)
