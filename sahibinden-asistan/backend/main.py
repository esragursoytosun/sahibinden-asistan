# backend/main.py - BAI BİLMİŞ: AZ LAF ÇOK İŞ & OKUNAKLI FORMAT 🧠
import os
import uuid
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import motor.motor_asyncio
import google.generativeai as genai

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

# 1. DB BAĞLANTISI
collection = None
if MONGO_URL:
    try:
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
        db = client.sahibinden_db
        collection = db.listings
    except Exception as e:
        print(f"DB Bağlantı Hatası: {e}")
else:
    print("UYARI: Database URL yok!")

# 2. AI AYARLARI
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# --- VERİ TİPLERİ ---
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
    username: str
    text: str

class LikeData(BaseModel):
    listing_id: str
    comment_id: str
    user_id: str

# --- YARDIMCI FONKSİYONLAR ---

async def find_similars(title, current_id):
    """Veritabanındaki benzer ilanların fiyatlarını getirir."""
    if not title or collection is None: return "Veritabanı bağlantısı yok."
    try:
        keywords = set(title.lower().split())
        keywords = {k for k in keywords if len(k) > 2}
        cursor = collection.find().sort("first_seen_at", -1).limit(50)
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
    """Kullanıcı yorumlarını getirir."""
    if collection is None: return ""
    try:
        doc = await collection.find_one({"_id": listing_id})
        if not doc or "comments" not in doc: return ""
        notes = [f"- {c.get('user')}: {c.get('text')}" for c in doc["comments"]]
        return "\n".join(notes) if notes else ""
    except: return ""

# --- ENDPOINTLER ---

@app.post("/analyze-ai")
async def ask_ai(data: ListingData):
    if not GEMINI_KEY: return {"status": "error", "message": "API Key Eksik"}

    # 1. Bağlam Toplama
    db_context = await find_similars(data.title, data.id)
    user_notes = await get_user_notes(data.id)
    
    # 2. Modeller
    models_to_try = ["gemini-2.0-flash", "gemini-flash-latest", "gemini-pro"]
    
    # 3. BAI BİLMİŞ PROMPT'U (Direkt Analiz + HTML Liste)
    prompt = f"""
    ROLÜN: Adın "BAI Bilmiş". Otomotiv ve emlak piyasası uzmanısın.
    ÜSLUBUN: "Cemil Usta" tecrübesinde ama nazik, yapıcı ve çözüm odaklısın.
    KURAL: Kendini uzun uzun tanıtma ("Ben BAI Bilmiş..." deme). Direkt analize gir.
    
    GÖREVİN:
    Aşağıdaki ilanı; bizim veritabanımız, kullanıcı notları ve genel piyasa bilginle analiz et.
    Çıktıyı kesinlikle HTML listeleri (<ul>, <li>) kullanarak madde madde ver. Okuması kolay olsun.

    İLAN DETAYLARI:
    - Başlık: {data.title}
    - Fiyat: {data.price} TL
    - Yıl: {data.year}
    - KM/Özellik: {data.km}
    - Satıcı Notu: "{data.description}"
    
    ÖZEL BAĞLAM (BUNLARI KULLAN):
    - Bizim Veritabanı Durumu: {db_context}
    - Kullanıcı Notları (Varsa dikkate al): {user_notes}

    ANALİZ FORMATI (HTML KULLAN):
    
    <b>🧐 BAI Bilmiş Analizi:</b>
    <ul>
        <li>(İlanın teknik durumu, gizli kusur ihtimali veya avantajları hakkında 2-3 kısa madde.)</li>
    </ul>

    <b>💰 Fiyat ve Piyasa Raporu:</b>
    <ul>
        <li>(Fiyatı veritabanımızla ve piyasayla kıyasla. Pahalı mı, fırsat mı?)</li>
        <li>(Satılabilirlik hızı ve yatırım değeri.)</li>
    </ul>

    <b>⚠️ Riskler ve Tavsiyeler:</b>
    <ul>
        <li>(Alırken nelere dikkat edilmeli? Kronik sorun riski var mı?)</li>
        <li>(Yapıcı tavsiyen: "Şu fiyata düşerse kaçırma" veya "Ekspertiz şart" gibi.)</li>
    </ul>
    """

    last_error = ""
    for model_name in models_to_try:
        try:
            # Google Search Tool (Varsa kullanır)
            tools = 'google_search_retrieval' if '2.0' in model_name else None
            
            if tools:
                model = genai.GenerativeModel(model_name, tools=tools)
            else:
                model = genai.GenerativeModel(model_name)

            response = model.generate_content(prompt)
            if not response.text: raise Exception("Boş cevap")
            
            return {"status": "success", "ai_response": response.text, "used_model": model_name}
        except Exception as e:
            last_error = str(e)
            print(f"Hata ({model_name}): {e}")
            continue
            
    return {"status": "error", "message": f"BAI Bilmiş şu an yoğun. ({last_error})"}

@app.post("/analyze")
async def analyze_listing(data: ListingData):
    if collection is None: return {"status": "error", "message": "DB Yok"}
    if not data.id or not data.price: return {"status": "error"}
    
    try:
        existing = await collection.find_one({"_id": data.id})
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response = {"status": "success", "comments": [], "is_price_drop": False, "history": []}

        if existing:
            last_price = existing.get("current_price", data.price)
            if last_price != data.price:
                await collection.update_one({"_id": data.id}, {"$set": {"current_price": data.price}, "$push": {"history": {"date": now, "price": last_price}}})
                if data.price < last_price: response["is_price_drop"] = True 
            full_history = existing.get("history", [])
            full_history.append({"date": "Şimdi", "price": data.price})
            response["history"] = full_history
            response["comments"] = existing.get("comments", [])
        else:
            new_record = {"_id": data.id, "title": data.title, "url": data.url, "first_seen_at": now, "current_price": data.price, "history": [], "comments": []}
            await collection.insert_one(new_record)
            response["history"] = [{"date": "Şimdi", "price": data.price}]
        return response
    except: return {"status": "error"}

@app.post("/add_comment")
async def add_comment(comment: CommentData):
    if collection is None: return {"status": "error"}
    new_comment = {"id": str(uuid.uuid4()), "user": comment.username, "text": comment.text, "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "liked_by": []}
    await collection.update_one({"_id": comment.listing_id}, {"$push": {"comments": new_comment}})
    updated = await collection.find_one({"_id": comment.listing_id})
    return {"status": "success", "comments": updated.get("comments", [])}

@app.post("/like_comment")
async def like_comment(data: LikeData):
    if collection is None: return {"status": "error"}
    doc = await collection.find_one({"_id": data.listing_id})
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
    
    await collection.update_one({"_id": data.listing_id}, {"$set": {"comments": updated_comments}})
    return {"status": "success", "comments": updated_comments}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)
