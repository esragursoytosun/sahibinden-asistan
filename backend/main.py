import os
import uuid
import requests
import re
from datetime import datetime, timedelta
from typing import List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path

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

# --- GOOGLE AI AYARLARI (YENİ SDK) ---
if GEMINI_KEY:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=GEMINI_KEY)

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

# 🟢 ADMIN PANEL STATIC FILES
ADMIN_DIR = Path(__file__).parent.parent / "admin"

@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
async def admin_panel():
    """Admin panel ana sayfasını döndürür"""
    index_path = ADMIN_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Admin Panel Bulunamadı</h1>", status_code=404)

@app.get("/admin/{filename}")
async def admin_static(filename: str):
    """Admin panel static dosyalarını döndürür"""
    file_path = ADMIN_DIR / filename
    if file_path.exists() and file_path.is_file():
        content_types = {
            ".css": "text/css",
            ".js": "application/javascript",
            ".html": "text/html",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".ico": "image/x-icon"
        }
        suffix = file_path.suffix.lower()
        media_type = content_types.get(suffix, "application/octet-stream")
        return FileResponse(file_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="Dosya bulunamadı")

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
    
    # 🟢 YENİ GOOGLE AI SDK 🟢
    import asyncio
    
    if not GEMINI_KEY:
        return {"status": "error", "message": "API Key eksik!"}
    
    print(f"🔑 API Key durumu: VAR")
    
    # Yeni SDK ile model isimleri
    models_to_try = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-pro",
    ]
    
    last_error = ""
    
    for model_name in models_to_try:
        try:
            print(f"🤖 Deneniyor: {model_name}")
            
            # Yeni SDK formatı
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            
            if response and response.text:
                print(f"✅ Başarılı: {model_name}")
                return {"status": "success", "ai_response": response.text}
            
            print(f"⚠️ Boş yanıt: {model_name}")
            continue
                
        except Exception as e:
            error_str = str(e)
            print(f"❌ Hata ({model_name}): {error_str}")
            last_error = error_str
            continue
    
    # Hiçbir model çalışmadı
    print(f"❌ Tüm modeller başarısız. Son hata: {last_error}")
    return {"status": "error", "message": f"AI Hatası: {last_error[:150]}"}

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

# --- ADMIN PANEL API'LERİ ---

ADMIN_KEY = "UmutDeniz*21092025"  # Admin şifresi

class AdminAction(BaseModel):
    admin_email: str
    user_id: str = None
    plan: str = None
    search_query: str = None

async def verify_admin(email: str) -> bool:
    """Admin yetkisini kontrol eder"""
    return email in ADMIN_EMAILS

@app.post("/admin/login")
async def admin_login(data: dict):
    """Admin girişi - email ve şifre ile"""
    email = data.get("email", "").strip().lower()
    key = data.get("key", "")
    
    if not email or not key:
        return {"status": "error", "is_admin": False, "message": "Email ve şifre gerekli!"}
    
    if key != ADMIN_KEY:
        return {"status": "error", "is_admin": False, "message": "Şifre hatalı!"}
    
    if email not in [e.lower() for e in ADMIN_EMAILS]:
        return {"status": "error", "is_admin": False, "message": "Bu email admin değil!"}
    
    return {"status": "success", "is_admin": True, "email": email}

@app.post("/admin/verify")
async def admin_verify(data: dict):
    """Admin girişini doğrular"""
    email = data.get("email", "")
    if await verify_admin(email):
        return {"status": "success", "is_admin": True}
    return {"status": "error", "is_admin": False, "message": "Yetkiniz yok!"}

@app.post("/admin/users")
async def admin_get_users(data: dict):
    """Tüm kullanıcıları listeler (Admin only)"""
    admin_email = data.get("admin_email", "")
    if not await verify_admin(admin_email):
        return {"status": "error", "message": "Yetkiniz yok!"}
    
    try:
        limit = data.get("limit", 50)
        skip = data.get("skip", 0)
        
        cursor = users_collection.find().sort("last_login", -1).skip(skip).limit(limit)
        users = await cursor.to_list(length=limit)
        total = await users_collection.count_documents({})
        
        user_list = []
        for u in users:
            user_list.append({
                "id": u.get("_id"),
                "name": u.get("name", "İsimsiz"),
                "email": u.get("email", ""),
                "picture": u.get("picture", ""),
                "plan": u.get("plan", "free"),
                "daily_usage": u.get("daily_usage", 0),
                "last_login": str(u.get("last_login", "")) if u.get("last_login") else None,
                "is_admin": u.get("email") in ADMIN_EMAILS
            })
        
        return {"status": "success", "users": user_list, "total": total}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/admin/set-plan")
async def admin_set_plan(data: dict):
    """Kullanıcı planını değiştirir (Admin only)"""
    admin_email = data.get("admin_email", "")
    if not await verify_admin(admin_email):
        return {"status": "error", "message": "Yetkiniz yok!"}
    
    user_id = data.get("user_id")
    new_plan = data.get("plan", "free")
    
    if new_plan not in ["free", "premium"]:
        return {"status": "error", "message": "Geçersiz plan!"}
    
    try:
        result = await users_collection.update_one(
            {"_id": user_id},
            {"$set": {"plan": new_plan, "daily_usage": 0}}
        )
        
        if result.modified_count > 0:
            return {"status": "success", "message": f"Kullanıcı '{new_plan}' planına alındı!"}
        else:
            return {"status": "error", "message": "Kullanıcı bulunamadı veya zaten bu plandaydı."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/admin/search")
async def admin_search_users(data: dict):
    """Kullanıcı arar (Admin only)"""
    admin_email = data.get("admin_email", "")
    if not await verify_admin(admin_email):
        return {"status": "error", "message": "Yetkiniz yok!"}
    
    query = data.get("query", "").strip()
    if not query or len(query) < 2:
        return {"status": "error", "message": "En az 2 karakter girin."}
    
    try:
        # Email veya isimde arama yap
        cursor = users_collection.find({
            "$or": [
                {"email": {"$regex": query, "$options": "i"}},
                {"name": {"$regex": query, "$options": "i"}}
            ]
        }).limit(20)
        
        users = await cursor.to_list(length=20)
        
        user_list = []
        for u in users:
            user_list.append({
                "id": u.get("_id"),
                "name": u.get("name", "İsimsiz"),
                "email": u.get("email", ""),
                "picture": u.get("picture", ""),
                "plan": u.get("plan", "free"),
                "daily_usage": u.get("daily_usage", 0),
                "is_admin": u.get("email") in ADMIN_EMAILS
            })
        
        return {"status": "success", "users": user_list, "count": len(user_list)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/admin/stats")
async def admin_get_stats(admin_email: str):
    """Genel istatistikleri döndürür (Admin only)"""
    if not await verify_admin(admin_email):
        return {"status": "error", "message": "Yetkiniz yok!"}
    
    try:
        total_users = await users_collection.count_documents({})
        premium_users = await users_collection.count_documents({"plan": "premium"})
        free_users = total_users - premium_users
        total_listings = await listings_collection.count_documents({})
        
        # Bugün giriş yapanlar
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        active_today = await users_collection.count_documents({
            "last_login": {"$gte": today_start}
        })
        
        return {
            "status": "success",
            "stats": {
                "total_users": total_users,
                "premium_users": premium_users,
                "free_users": free_users,
                "total_listings": total_listings,
                "active_today": active_today
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
