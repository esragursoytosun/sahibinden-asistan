from fastapi import Request
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

# --- AYARLAR ---
load_dotenv()
# Database.py'den tabloları çekiyoruz
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
                
        if not prices: return "Henüz yeterli kıyaslama verisi birikmedi."
        
        avg = sum(prices) / len(prices)
        return f"Veritabanımdaki {len(prices)} benzer ilanın ortalaması: {avg:,.0f} TL."
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

@app.get("/")
async def root():
    return {"status": "active", "message": "Sahibinden Asistan Sunucusu Calisiyor! 🚀"}

@app.get("/debug-ai")
async def check_models():
    """Hangi modellerin çalıştığını listeler (Debug için)"""
    if not GEMINI_KEY: return {"error": "API Key yok"}
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        return {"active_models": available_models}
    except Exception as e:
        return {"error": str(e)}

# --- VERSİYON KONTROLÜ ---
@app.get("/version")
async def check_version():
    """Eklentinin güncel olup olmadığını kontrol eder."""
    return {
        "latest_version": "1.1",  # BURAYI HER GÜNCELLEMEDE DEĞİŞTİRECEĞİZ
        "message": "🚨 Yeni Özellik: Telegram Fiyat Alarmı Eklendi! Lütfen eklentiyi yenileyin.",
        "force_update": True # Zorunlu güncelleme mi?
    }
    
@app.post("/auth/google")
async def google_login(data: GoogleLoginData):
    """Google Giriş İşlemi"""
    try:
        idinfo = None
        try:
            idinfo = id_token.verify_oauth2_token(data.token, google_requests.Request(), GOOGLE_CLIENT_ID)
        except Exception:
            pass

        if not idinfo:
            res = requests.get(f"https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {data.token}"})
            if res.status_code == 200:
                idinfo = res.json()
                if 'sub' not in idinfo and 'id' in idinfo:
                    idinfo['sub'] = idinfo['id']
            else:
                raise ValueError("Token Google tarafından reddedildi.")

        google_id = idinfo['sub']
        email = idinfo.get('email')
        name = idinfo.get('name')
        picture = idinfo.get('picture')
        
        await users_collection.update_one(
            {"_id": google_id}, 
            {"$set": {
                "email": email, 
                "name": name, 
                "picture": picture, 
                "last_login": datetime.now()
            }}, 
            upsert=True
        )
            
        return {"status": "success", "user": {"id": google_id, "name": name, "picture": picture}}
        
    except Exception as e:
        print(f"Login Hatası: {e}")
        raise HTTPException(status_code=401, detail=f"Giriş Başarısız: {str(e)}")

@app.post("/analyze-ai")
async def ask_ai(data: ListingData):
    """BAI Bilmiş - AKILLI Analiz Modu"""
    if not GEMINI_KEY: 
        return {"status": "error", "message": "API Key Eksik!"}

    # 1. Veri Toplama
    db_context = await find_similars(data.title, data.id)
    user_notes = await get_user_notes(data.id)
    
    # 2. AKILLI PROMPT (Zeka Burada!)
    prompt = f"""
    KİMLİK:
    Senin adın "BAI Bilmiş". Sen Türkiye'nin en tecrübeli galericisi, emlak uzmanı ve veri analistisin. 
    Lafı dolandırmayı sevmezsin. Net, çarpıcı, esprili ve nokta atışı tespitler yaparsın.
    
    GÖREV:
    Aşağıdaki ilanı benim için detaylıca analiz et.
    
    İLAN VERİLERİ:
    - Başlık: {data.title}
    - Fiyat: {data.price} TL
    - Yıl: {data.year}
    - KM/Özellik: {data.km}
    - Satıcı Açıklaması: "{data.description}"
    
    EKSTRA BİLGİLER (Bunları mutlaka kullan):
    - Veritabanı Ortalaması: {db_context}
    - Kullanıcı Yorumları: {user_notes}

    ANALİZ KURALLARI:
    1. KM ve Yıl analizi yap. (Örn: "Bu yaşta bu KM çok temiz" veya "Bu KM'de taksi çıkması riski var" gibi.)
    2. Fiyatı veritabanı ortalamasıyla kıyasla. Pahalı mı, kelepir mi?
    3. Satıcı açıklamasındaki gizli anlamları çöz. ("Keyfe keder boyalı", "Çıtır hasarlı", "Gırtlak dolu" gibi tabirleri yorumla.)
    4. HTML formatında (<ul>, <li>, <b>) çıktı ver.

    ÇIKTI FORMATI:
    <b>🏎️ Genel Durum ve Yorumum:</b>
    <ul>
       <li>(KM, Yıl ve Araç Yorgunluğu hakkında yorumun)</li>
       <li>(Açıklamadan yakaladığın detaylar veya riskler)</li>
    </ul>

    <b>💰 Fiyat ve Piyasa Raporu:</b>
    <ul>
       <li>(Piyasa ortalamasına göre durumu. Yatırımlık mı? Biniciye mi?)</li>
    </ul>

    <b>🕵️ BAI Bilmiş'in Son Kararı:</b>
    <ul>
       <li>(Kısa ve net tavsiyen: "Kaçırma", "Uzak dur", "Ekspertizsiz alma" vb.)</li>
    </ul>
    """

    try:
        # Senin hesabında çalışan model ismi:
        model_name = "gemini-flash-latest"
        
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        
        return {"status": "success", "ai_response": response.text, "used_model": model_name}
        
    except Exception as e:
        # Yedek plan (Pro Latest)
        try:
            print(f"Flash hatası: {e}, Pro deneniyor...")
            model = genai.GenerativeModel("gemini-pro-latest")
            response = model.generate_content(prompt)
            return {"status": "success", "ai_response": response.text, "used_model": "gemini-pro-latest (Yedek)"}
        except Exception as e2:
            return {"status": "error", "message": f"AI Hatası: {str(e)}"}

@app.post("/analyze")
async def analyze_listing(data: ListingData):
    """İlanı kaydeder ve geçmişi tutar"""
    if not data.id or not data.price: return {"status": "error"}
    
    try:
        existing = await listings_collection.find_one({"_id": data.id})
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response = {"status": "success", "comments": [], "is_price_drop": False, "history": []}

        if existing:
            last_price = existing.get("current_price", data.price)
            if last_price != data.price:
                await listings_collection.update_one({"_id": data.id}, {"$set": {"current_price": data.price}, "$push": {"history": {"date": now, "price": last_price}}})
                if data.price < last_price: response["is_price_drop"] = True 
            full_history = existing.get("history", [])
            full_history.append({"date": "Şimdi", "price": data.price})
            response["history"] = full_history
            response["comments"] = existing.get("comments", [])
        else:
            new_record = {"_id": data.id, "title": data.title, "url": data.url, "first_seen_at": now, "current_price": data.price, "history": [], "comments": []}
            await listings_collection.insert_one(new_record)
            response["history"] = [{"date": "Şimdi", "price": data.price}]
        return response
    except: return {"status": "error"}

@app.post("/add_comment")
async def add_comment(comment: CommentData):
    """Yorum ekler"""
    user_name = comment.username or "Misafir"
    user_pic = ""
    
    if comment.user_id:
        user = await users_collection.find_one({"_id": comment.user_id})
        if user:
            user_name = user.get("name", user_name)
            user_pic = user.get("picture", "")

    new_comment = {
        "id": str(uuid.uuid4()), 
        "user_id": comment.user_id,
        "user": user_name,
        "user_pic": user_pic,
        "text": comment.text, 
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"), 
        "liked_by": []
    }
    
    await listings_collection.update_one({"_id": comment.listing_id}, {"$push": {"comments": new_comment}})
    updated = await listings_collection.find_one({"_id": comment.listing_id})
    return {"status": "success", "comments": updated.get("comments", [])}

@app.post("/like_comment")
async def like_comment(data: LikeData):
    """Yorumu beğenir"""
    doc = await listings_collection.find_one({"_id": data.listing_id})
    if not doc: return {"status": "error"}
    
    comments = doc.get("comments", [])
    updated_comments = []
    
    for c in comments:
        if c.get("id") == data.comment_id:
            likes = c.get("liked_by", [])
            if not isinstance(likes, list): likes = []
            
            if data.user_id in likes:
                likes.remove(data.user_id)
            else:
                likes.append(data.user_id)
            c["liked_by"] = likes
        updated_comments.append(c)
    
    await listings_collection.update_one({"_id": data.listing_id}, {"$set": {"comments": updated_comments}})
    return {"status": "success", "comments": updated_comments}

# --- TELEGRAM ENTGRASYONU ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Telegram'dan gelen mesajları dinler ve kullanıcıyı eşleştirir."""
    try:
        data = await request.json()
        
        # Mesaj var mı kontrol et
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "")
            
            # Kullanıcı '/start GOOGLE_ID' formatında linke tıkladıysa:
            if text.startswith("/start") and len(text.split()) > 1:
                google_user_id = text.split()[1]
                
                # Veritabanında bu kullanıcıyı bul ve Telegram ID'sini kaydet
                await users_collection.update_one(
                    {"_id": google_user_id},
                    {"$set": {"telegram_chat_id": chat_id}}
                )
                
                # Kullanıcıya "Hoşgeldin" mesajı at
                send_telegram_message(chat_id, "🎉 Harika! Fiyat alarmları aktif edildi. Favori ilanlarında indirim olunca sana haber vereceğim.")
                
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook Hatası: {e}")
        return {"status": "error"}

def send_telegram_message(chat_id, text):
    """Telegram mesajı gönderen yardımcı fonksiyon"""
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)




