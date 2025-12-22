# backend/main.py - DEBUG MODU (HATAYI GÖSTEREN SÜRÜM) 🐞
import json
import os
import uuid
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel
import os
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "database.json"

def read_db():
    if not os.path.exists(DB_FILE): return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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

@app.post("/analyze")
def analyze_listing(data: ListingData):
    if not data.id or not data.price: return {"status": "error"}
    db_data = read_db()
    existing = db_data.get(data.id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    response = {"status": "success", "comments": [], "is_price_drop": False}

    if existing:
        last_price = existing["current_price"]
        if last_price != data.price:
            existing["history"].append({"date": now, "price": last_price})
            existing["current_price"] = data.price
            if data.price < last_price:
                response["is_price_drop"] = True
                response["change_percentage"] = int(((last_price - data.price)/last_price)*100)
        
        if "comments" not in existing: existing["comments"] = []
        response["comments"] = existing["comments"]
        db_data[data.id] = existing
    else:
        new_record = {
            "title": data.title, "url": data.url, 
            "first_seen_at": now, "current_price": data.price,
            "history": [], "comments": []
        }
        db_data[data.id] = new_record

    save_db(db_data)
    return response

@app.post("/add_comment")
def add_comment(comment: CommentData):
    db_data = read_db()
    listing = db_data.get(comment.listing_id)
    if not listing: return {"status": "error"}

    new_comment = {
        "id": str(uuid.uuid4()),
        "user": comment.username,
        "text": comment.text,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "liked_by": [] # Yeni yorumlar boş listeyle başlar
    }
    
    if "comments" not in listing: listing["comments"] = []
    listing["comments"].append(new_comment)
    db_data[comment.listing_id] = listing
    save_db(db_data)
    print(f"💬 YORUM EKLENDİ: {comment.text}")
    return {"status": "success", "comments": listing["comments"]}

@app.post("/like_comment")
def like_comment(data: LikeData):
    print(f"❤️ BEĞENİ İSTEĞİ GELDİ! Kullanıcı: {data.user_id}") # LOG
    
    db_data = read_db()
    listing = db_data.get(data.listing_id)
    
    if not listing: 
        print("❌ HATA: İlan bulunamadı.")
        return {"status": "error"}

    updated_comments = []
    for c in listing.get("comments", []):
        if c.get("id") == data.comment_id:
            # Garanti Altına Alma: Eğer eski veri varsa listeye çevir
            if "liked_by" not in c or not isinstance(c["liked_by"], list):
                c["liked_by"] = []

            # İŞLEM
            if data.user_id in c["liked_by"]:
                c["liked_by"].remove(data.user_id) # Geri al
                print("   -> Beğeni Geri Alındı 💔")
            else:
                c["liked_by"].append(data.user_id) # Ekle
                print("   -> Beğenildi ❤️")
        
        updated_comments.append(c)
    
    listing["comments"] = updated_comments
    db_data[data.listing_id] = listing
    save_db(db_data)
    return {"status": "success", "comments": listing["comments"]}

# Dosyanın en altı:
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)