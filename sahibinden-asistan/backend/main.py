# backend/main.py - MONGODB PRO VERSION 🚀
import os
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import motor.motor_asyncio # MongoDB motoru

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- VERİTABANI BAĞLANTISI ---
# Render'daki gizli anahtarı alıyoruz
MONGO_URL = os.environ.get("MONGO_URL")

# Eğer anahtar yoksa (Localde çalışıyorsan) hata vermesin diye boş kontrolü
if not MONGO_URL:
    print("UYARI: MONGO_URL bulunamadı! Veritabanı çalışmayabilir.")
    client = None
    db = None
else:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
    db = client.sahibinden_db # Veritabanı adı
    collection = db.listings  # Tablo adı

# --- MODELLER ---
class ListingData(BaseModel):
    id: str | None = None
    price: int | float | None = None
    title: str | None = None
    url: str | None = None

class CommentData(BaseModel):
    listing_id: str
    username: str
    text: str

class LikeData(BaseModel):
    listing_id: str
    comment_id: str
    user_id: str

# --- ENDPOINTLER ---

@app.post("/analyze")
async def analyze_listing(data: ListingData):
    if not data.id or not data.price: return {"status": "error"}
    
    # MongoDB'den veriyi çek
    existing = await collection.find_one({"_id": data.id})
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    response = {"status": "success", "comments": [], "is_price_drop": False}

    if existing:
        last_price = existing["current_price"]
        if last_price != data.price:
            # Fiyat değişmiş, geçmişe ekle ve güncelle
            await collection.update_one(
                {"_id": data.id},
                {
                    "$set": {"current_price": data.price},
                    "$push": {"history": {"date": now, "price": last_price}}
                }
            )
            if data.price < last_price:
                response["is_price_drop"] = True
                response["change_percentage"] = int(((last_price - data.price)/last_price)*100)
        
        response["comments"] = existing.get("comments", [])
    else:
        # Yeni kayıt oluştur
        new_record = {
            "_id": data.id, # MongoDB'de ID "_id" olarak tutulur
            "title": data.title, 
            "url": data.url, 
            "first_seen_at": now, 
            "current_price": data.price,
            "history": [],
            "comments": []
        }
        await collection.insert_one(new_record)

    return response

@app.post("/add_comment")
async def add_comment(comment: CommentData):
    import uuid
    new_comment = {
        "id": str(uuid.uuid4()),
        "user": comment.username,
        "text": comment.text,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "liked_by": []
    }
    
    # MongoDB'de listeye eleman eklemek için $push kullanılır (Çok hızlıdır)
    await collection.update_one(
        {"_id": comment.listing_id},
        {"$push": {"comments": new_comment}}
    )
    
    # Güncel veriyi çekip geri dön
    updated_doc = await collection.find_one({"_id": comment.listing_id})
    return {"status": "success", "comments": updated_doc.get("comments", [])}

@app.post("/like_comment")
async def like_comment(data: LikeData):
    # MongoDB'de iç içe veriyi güncellemek biraz karışıktır,
    # Bu yüzden en güvenli yol: Veriyi çek -> Python'da düzelt -> Kaydet
    
    doc = await collection.find_one({"_id": data.listing_id})
    if not doc: return {"status": "error"}

    comments = doc.get("comments", [])
    updated_comments = []
    
    for c in comments:
        if c.get("id") == data.comment_id:
            # Garanti altına al
            if "liked_by" not in c or not isinstance(c["liked_by"], list):
                c["liked_by"] = []
            
            # Toggle (Ekle/Çıkar)
            if data.user_id in c["liked_by"]:
                c["liked_by"].remove(data.user_id)
            else:
                c["liked_by"].append(data.user_id)
        updated_comments.append(c)
    
    # Tüm yorum listesini güncelle
    await collection.update_one(
        {"_id": data.listing_id},
        {"$set": {"comments": updated_comments}}
    )
    
    return {"status": "success", "comments": updated_comments}

# --- SERVER BAŞLATMA ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)
