# backend/main.py - HATASIZ FİNAL SÜRÜM (PYMONGO FIX) 🛠️
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
        collection = None
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

# --- YARDIMCI FONKSİYON: EMSAL BULUCU ---
async def find_similars(title, current_id):
    """Veritabanındaki benzer araçların ortalama fiyatını bulur."""
    # DÜZELTME 1: collection is None kontrolü
    if not title or collection is None: return None
    
    try:
        # Başlıktaki kelimeleri ayır
        keywords = set(title.lower().split())
        keywords = {k for k in keywords if len(k) > 2} # Kısa kelimeleri at
        
        # Son 100 ilanı çek
        cursor = collection.find().sort("first_seen_at", -1).limit(100)
        all_listings = await cursor.to_list(length=100)
        
        similar_prices = []
        
        for item in all_listings:
            if str(item.get("_id")) == str(current_id): continue
            
            item_title = item.get("title", "").lower()
            item_price = item.get("current_price", 0)
            
            # Benzerlik kontrolü: En az 2 kelime tutuyor mu?
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
        Daha önce kaydettiğin {len(similar_prices)} benzer araç var.
        - Ortalama Piyasa: {avg_price:,.0f} TL
        - En Ucuzu: {min_price:,.0f} TL
        - En Pahalı: {max_price:,.0f} TL
        (Bu veriyi kullanarak şu anki ilanın fiyatını eleştir.)
        """
    except Exception as e:
        return f"Veritabanı hatası: {str(e)}"

# --- ENDPOINTLER ---

@app.post("/analyze-ai")
async def ask_ai(data: ListingData):
    if not GEMINI_KEY: return {"status": "error", "message": "API Key Eksik"}

    # 1. Emsal Kontrolü
    db_context = await find_similars(data.title, data.id)
    
    # 2. Yedekli Model Listesi (Sırayla dener)
    models_to_try = [
        "gemini-flash-latest", 
        "gemini-2.0-flash", 
        "gemini-2.0-flash-lite-preview-02-05",
        "gemini-pro"
    ]
    
    # 3. Sanayi Ustası Prompt'u
    prompt = f"""
    ROLÜN:
    Sen "Sanayi Ustası Cemil Abi"sin. 30 yıldır araba tamir ediyorsun. 
    Kibar konuşmayı sevmezsin, "dobra" ve teknik konuşursun. 
    Bana "Kardeşim", "Hocam" diye hitap et.
    Kısa, net, vurucu ve hafif iğneleyici analizler yap.

    ARAÇ BİLGİLERİ:
    - Başlık: {data.title}
    - Fiyat: {data.price} TL
    - Yıl: {data.year}
    - KM: {data.km}
    - Satıcı Açıklaması: "{data.description}"
    
    VERİTABANI BİLGİSİ (EMSALLER):
    {db_context if db_context else "Veritabanında kayıtlı emsal yok."}

    GÖREVLERİN:
    1. ARABANIN CİĞERİ: Açıklamayı oku. "Keyfe keder boyalı", "Çıtır hasarlı" gibi galerici yalanlarını yakala. Motor/Mekanik ne durumdadır tahmin et.
    2. FİYAT ANALİZİ: Yıl, KM ve Hasar durumuna göre bu para eder mi? Veritabanındaki emsallere bak, pahalıysa "Kazık", ucuzsa "Kupon" de.
    3. SANAYİDEN TAVSİYE: Bu modelin kronik sorunu (DSG, Enjektör, Zincir vb.) var mı? Alırsam sanayiden çıkamaz mıyım?

    Yanıtı HTML formatında (<b>, <br>) ver. Destan yazma, sadede gel.
    """

    last_error = ""
    
    # Modelleri sırayla dene
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return {"status": "success", "ai_response": response.text, "used_model": model_name}
        except Exception as e:
            last_error = str(e)
            print(f"Model Hatası ({model_name}): {e}")
            continue
            
    return {"status": "error", "message": f"Usta şu an çok yoğun, sunucu cevap veremiyor. (Hata: {last_error})"}

@app.post("/analyze")
async def analyze_listing(data: ListingData):
    # DÜZELTME 2: collection is None kontrolü
    if collection is None: return {"status": "error", "message": "Veritabanı bağlantısı yok"}
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
    except Exception as e:
        print(f"Analyze Hatası: {e}")
        return {"status": "error"}

@app.post("/add_comment")
async def add_comment(comment: CommentData):
    # DÜZELTME 3: collection is None kontrolü
    if collection is None: return {"status": "error"}
    new_comment = {"id": str(uuid.uuid4()), "user": comment.username, "text": comment.text, "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "liked_by": []}
    await collection.update_one({"_id": comment.listing_id}, {"$push": {"comments": new_comment}})
    updated = await collection.find_one({"_id": comment.listing_id})
    return {"status": "success", "comments": updated.get("comments", [])}

@app.post("/like_comment")
async def like_comment(data: LikeData):
    # DÜZELTME 4: collection is None kontrolü
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
