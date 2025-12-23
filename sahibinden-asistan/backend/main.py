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
from backend.database import listings_collection, users_collection

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

# --- AI AYARLARI ---
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# --- MODELLER ---
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
    try:
        keywords = set(title.lower().split()) if title else set()
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
        if not prices: return "Veritabanında benzer ilan yok."
        avg = sum(prices) / len(prices)
        return f"Benzer ilan ortalaması: {avg:,.0f} TL."
    except: return "Veri yok."

async def get_user_notes(listing_id):
    try:
        doc = await listings_collection.find_one({"_id": listing_id})
        if not doc or "comments" not in doc: return ""
        notes = [f"- {c.get('user')}: {c.get('text')}" for c in doc["comments"]]
        return "\n".join(notes) if notes else ""
    except: return ""

# --- ENDPOINTLER ---

@app.get("/")
async def root():
    return {"status": "active", "message": "Sunucu Aktif 🚀"}

# --- YENİ DEBUG ENDPOINT (Bunu tarayıcıda açıp bakacağız) ---
@app.get("/debug-ai")
async def check_models():
    """Hangi modellerin çalıştığını listeler"""
    if not GEMINI_KEY: return {"error": "API Key yok"}
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        return {"active_models": available_models}
    except Exception as e:
        return {"error": str(e)}

@app.post("/analyze-ai")
async def ask_ai(data: ListingData):
    """AI Analiz Endpointi - Gemini 2.0 Flash (Senin Listendeki Model)"""
    if not GEMINI_KEY: 
        return {"status": "error", "message": "API Key Eksik!"}

    db_context = await find_similars(data.title, data.id)
    user_notes = await get_user_notes(data.id)
    
    prompt = f"""
    Sen BAI Bilmiş adında bir asistanın.
    Şu ilanı kısaca analiz et (HTML liste formatında):
    Başlık: {data.title}, Fiyat: {data.price}, KM: {data.km}, Yıl: {data.year}
    Açıklama: {data.description}
    Piyasa verisi: {db_context}
    
    Format:
    <b>🧐 Analiz:</b> <ul><li>...</li></ul>
    <b>💰 Fiyat:</b> <ul><li>...</li></ul>
    <b>⚠️ Tavsiye:</b> <ul><li>...</li></ul>
    """

    try:
        # SENİN LİSTENDEN SEÇTİĞİMİZ MODEL:
        # "models/gemini-2.0-flash" -> Şu an senin hesabında aktif olan en iyi model.
        model_name = "gemini-2.0-flash" 
        
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        
        return {"status": "success", "ai_response": response.text, "used_model": model_name}
        
    except Exception as e:
        return {"status": "error", "message": f"AI Hatası ({model_name}): {str(e)}"}

@app.post("/auth/google")
async def google_login(data: GoogleLoginData):
    try:
        idinfo = None
        try:
            idinfo = id_token.verify_oauth2_token(data.token, google_requests.Request(), GOOGLE_CLIENT_ID)
        except: pass

        if not idinfo:
            res = requests.get(f"https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {data.token}"})
            if res.status_code == 200:
                idinfo = res.json()
                if 'sub' not in idinfo and 'id' in idinfo: idinfo['sub'] = idinfo['id']
            else: raise ValueError("Geçersiz Token")

        await users_collection.update_one(
            {"_id": idinfo['sub']}, 
            {"$set": {"email": idinfo.get('email'), "name": idinfo.get('name'), "picture": idinfo.get('picture'), "last_login": datetime.now()}}, 
            upsert=True
        )
        return {"status": "success", "user": {"id": idinfo['sub'], "name": idinfo.get('name'), "picture": idinfo.get('picture')}}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/analyze")
async def analyze_listing(data: ListingData):
    if not data.id or not data.price: return {"status": "error"}
    try:
        existing = await listings_collection.find_one({"_id": data.id})
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response = {"status": "success", "comments": [], "history": []}

        if existing:
            last_price = existing.get("current_price", data.price)
            if last_price != data.price:
                await listings_collection.update_one({"_id": data.id}, {"$set": {"current_price": data.price}, "$push": {"history": {"date": now, "price": last_price}}})
            full_history = existing.get("history", [])
            full_history.append({"date": "Şimdi", "price": data.price})
            response["history"] = full_history
            response["comments"] = existing.get("comments", [])
        else:
            new_record = {"_id": data.id, "title": data.title, "current_price": data.price, "history": [], "comments": []}
            await listings_collection.insert_one(new_record)
            response["history"] = [{"date": "Şimdi", "price": data.price}]
        return response
    except: return {"status": "error"}

@app.post("/add_comment")
async def add_comment(c: CommentData):
    u_name, u_pic = c.username or "Misafir", ""
    if c.user_id:
        user = await users_collection.find_one({"_id": c.user_id})
        if user: u_name, u_pic = user.get("name", u_name), user.get("picture", "")
    new_c = {"id": str(uuid.uuid4()), "user_id": c.user_id, "user": u_name, "user_pic": u_pic, "text": c.text, "date": datetime.now().strftime("%Y-%m-%d"), "liked_by": []}
    await listings_collection.update_one({"_id": c.listing_id}, {"$push": {"comments": new_c}})
    upd = await listings_collection.find_one({"_id": c.listing_id})
    return {"status": "success", "comments": upd.get("comments", [])}

@app.post("/like_comment")
async def like_comment(d: LikeData):
    doc = await listings_collection.find_one({"_id": d.listing_id})
    if not doc: return {"status": "error"}
    cmts = doc.get("comments", [])
    for c in cmts:
        if c.get("id") == d.comment_id:
            likes = c.get("liked_by", [])
            if d.user_id in likes: likes.remove(d.user_id)
            else: likes.append(d.user_id)
            c["liked_by"] = likes
    await listings_collection.update_one({"_id": d.listing_id}, {"$set": {"comments": cmts}})
    return {"status": "success", "comments": cmts}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

