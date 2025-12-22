# backend/main.py - TANI VE ÇÖZ SÜRÜMÜ (DIAGNOSTIC MODE)
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

# 2. AI BAĞLANTISI
model = None
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        # Öncelikli olarak en hızlı modeli deniyoruz
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"AI Model Yukleme Hatasi: {e}")
else:
    print("UYARI: API Key yok!")

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

# --- ENDPOINTLER ---

# YENİ: Hangi modellerin açık olduğunu gösteren dedektif endpoint
@app.get("/models")
def list_available_models():
    if not GEMINI_KEY: 
        return {"status": "error", "message": "API Key Yok"}
    try:
        genai.configure(api_key=GEMINI_KEY)
        # API Key'in görebildiği tüm modelleri listele
        all_models = list(genai.list_models())
        # Sadece metin üretebilenleri filtrele
        supported = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods]
        return {
            "status": "success", 
            "message": "API Anahtarınız bu modelleri görebiliyor:",
            "available_models": supported
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/analyze-ai")
async def ask_ai(data: ListingData):
    # Model yüklenmemişse tekrar denemeyi veya varsayılanı zorlayalım
    local_model = model
    if not local_model and GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            # Eğer yukarıdaki flash çalışmazsa burada pro'yu deneyebilir
            local_model = genai.GenerativeModel('gemini-pro') 
        except: pass
    
    if not local_model:
        return {
            "status": "error", 
            "message": "AI Modeline Erişilemedi. Lütfen tarayıcıdan /models adresine gidip yetkili modelleri kontrol edin."
        }
    
    prompt = f"""
    Sen uzman bir oto ekspertizisin. Bu aracı analiz et:
    Başlık: {data.title}
    Fiyat: {data.price} TL
    KM: {data.km}
    Yıl: {data.year}
    Açıklama: {data.description}
    
    Lütfen HTML formatında (<b>, <br>) şu 3 maddeyi yaz:
    1. ARACIN DURUMU (Boya, değişen var mı?)
    2. FİYAT YORUMU (Pahalı mı?)
    3. RİSK ANALİZİ
    """
    
    try:
        response = local_model.generate_content(prompt)
        return {"status": "success", "ai_response": response.text}
    except Exception as e:
        return {"status": "error", "message": f"AI Hatasi: {str(e)}. (Model ismini /models sayfasindan kontrol edin)"}

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
    new_comment = {"id": str(uuid.uuid4()), "user": comment.username, "text": comment.text, "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "liked_by": []}
    await collection.update_one({"_id": comment.listing_id}, {"$push": {"comments": new_comment}})
    updated = await collection.find_one({"_id": comment.listing_id})
    return {"status": "success", "comments": updated.get("comments", [])}

@app.post("/like_comment")
async def like_comment(data: LikeData):
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
