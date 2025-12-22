# backend/main.py - SANAYİ USTASI SÜRÜMÜ (HAFIZALI & ACIMASIZ) 🛠️
import os
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
if MONGO_URL:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
    db = client.sahibinden_db
    collection = db.listings
else:
    print("UYARI: Database bagli degil!")

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
    listing_id: str; username: str; text: str

class LikeData(BaseModel):
    listing_id: str; comment_id: str; user_id: str

# --- YARDIMCI FONKSİYON: EMSAL BULUCU ---
async def find_similars(title, current_id):
    """Veritabanındaki benzer araçların ortalama fiyatını bulur."""
    if not title or not collection: return None
    
    # Başlıktaki kelimeleri ayır (Örn: "Volkswagen Passat 2015" -> {"volkswagen", "passat", "2015"})
    keywords = set(title.lower().split())
    # Gereksiz kısa kelimeleri at
    keywords = {k for k in keywords if len(k) > 2}
    
    # Veritabanından son 100 ilanı çek (Performans için limitli)
    cursor = collection.find().sort("first_seen_at", -1).limit(100)
    all_listings = await cursor.to_list(length=100)
    
    similar_prices = []
    
    for item in all_listings:
        # Kendisiyle kıyaslama
        if str(item.get("_id")) == str(current_id): continue
        
        item_title = item.get("title", "").lower()
        item_price = item.get("current_price", 0)
        
        # Basit Benzerlik: En az 2 anahtar kelime tutuyorsa emsal say
        item_keywords = set(item_title.split())
        common = keywords.intersection(item_keywords)
        
        if len(common) >= 2 and item_price > 0:
            similar_prices.append(item_price)
            
    if not similar_prices:
        return "Veritabanında henüz yeterli emsal yok."
    
    avg_price = sum(similar_prices) / len(similar_prices)
    min_price = min(similar_prices)
    max_price = max(similar_prices)
    
    return f"""
    BİZİM VERİTABANI RAPORU:
    Senin daha önce kaydettiğin {len(similar_prices)} benzer araç var.
    Bu araçların Ortalaması: {avg_price:,.0f} TL
    En Ucuzu: {min_price:,.0f} TL
    En Pahalı: {max_price:,.0f} TL
    (Bu veriyi kullanarak şu anki ilanın fiyatını eleştir.)
    """

# --- ENDPOINTLER ---

@app.post("/analyze-ai")
async def ask_ai(data: ListingData):
    if not GEMINI_KEY: return {"status": "error", "message": "API Key Eksik"}

    # 1. Adım: Veritabanından Emsal Ara
    db_context = await find_similars(data.title, data.id)
    
    # 2. Adım: Modelleri Hazırla
    models_to_try = ["gemini-flash-latest", "gemini-2.0-flash", "gemini-pro"]
    
    # 3. Adım: Sanayi Ustası Prompt'u
    prompt = f"""
    ROLÜN:
    Sen "Sanayi Ustası Cemil Abi"sin. 30 yıldır araba tamir ediyorsun. 
    Kibar konuşmayı sevmezsin, "dobra" konuşursun. 
    Müşteriye (bana) "Kardeşim", "Hocam", "Bak şimdi" gibi hitap et.
    Kısa, net, vurucu ve hafif iğneleyici analizler yap.

    ANALİZ EDİLECEK ARAÇ:
    - Başlık: {data.title}
    - Fiyat: {data.price} TL
    - Yıl: {data.year} (Buna çok dikkat et!)
    - KM: {data.km} (Yıla göre KM çok mu az mı? Oynanmış olabilir mi?)
    - Satıcı Açıklaması: "{data.description}"
    
    EKSTRA BİLGİ (SENİN DEFTERİNDEN):
    {db_context if db_context else "Daha önce bu modelden pek dükkana gelmedi (Veritabanı boş)."}

    GÖREVLERİN:
    1. ARABANIN CİĞERİ (Durum Analizi): Açıklamayı oku. "Keyfe keder boyalı", "Çıtır hasarlı" gibi galerici yalanlarını yakala. Samimi mi söylüyor yoksa bizi mi yiyor?
    2. PARA EDER Mİ? (Fiyat Analizi): Yıl, KM ve Hasar durumuna göre bu para verilir mi? Veritabanındaki emsallere bak, ona göre pahalıysa "Kazık", ucuzsa "Kupon" de.
    3. SANAYİDEN TAVSİYE: Bu modelin kronik sorunu var mı? (DSG şanzıman, Enjektör vb.) Alırsam sanayiden çıkamaz mıyım?

    Yanıtı HTML (<b>, <br>) formatında ver. Listeleme yap. Uzun uzun destan yazma, sadede gel.
    """

    last_error = ""
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return {"status": "success", "ai_response": response.text, "used_model": model_name}
        except Exception as e:
            last_error = str(e)
            continue
            
    return {"status": "error", "message": f"Usta şu an meşgul (Hata: {last_error})"}

@app.post("/analyze")
async def analyze_listing(data: ListingData):
    if not data.id or not data.price: return {"status": "error"}  
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

@app.post("/add_comment")
async def add_comment(comment: CommentData):
    import uuid
    new_comment = {"id": str(uuid.uuid4()), "
