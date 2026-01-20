import os
import requests
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.database import listings_collection, users_collection
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
# Kendi adresini buraya yazıyoruz ki kendine istek atıp uyanık kalsın
SELF_URL = "https://sahiden.onrender.com" 

scheduler = AsyncIOScheduler()

def send_alert(chat_id, message):
    if not TELEGRAM_TOKEN or not chat_id: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})

async def check_price_drops():
    """Fiyatları kontrol eder ve Telegram'a bildirir."""
    print("🕵️ Fiyat Kontrolü Başladı...")
    cursor = listings_collection.find({})
    listings = await cursor.to_list(length=1000)
    
    for item in listings:
        try:
            old_price = item.get("current_price", 0)
            if old_price == 0: continue
            
            # --- TEST İÇİN SİMÜLASYON ---
            # Gerçek hayatta burası 'yeni çekilen fiyat' olmalı.
            # Şimdilik veritabanındaki fiyatı baz alıyoruz.
            current_price = old_price 

            if current_price < old_price:
                drop = old_price - current_price
                user = await users_collection.find_one({"telegram_chat_id": {"$exists": True}})
                if user:
                    msg = f"🚨 <b>İNDİRİM!</b>\n{item.get('title')}\n<s>{old_price}</s> -> <b>{current_price}</b> TL"
                    send_alert(user["telegram_chat_id"], msg)
                await listings_collection.update_one({"_id": item.get("_id")}, {"$set": {"current_price": current_price}})
        except: pass

async def keep_alive():
    """Sunucuyu uyku modundan korur (Self-Ping)"""
    try:
        print("☕ Sunucuya kahve ısmarlanıyor (Keep-Alive)...")
        response = requests.get(f"{SELF_URL}/", timeout=10)
        print(f"✅ Sunucu Ayakta: {response.status_code}")
    except Exception as e:
        print(f"❌ Keep-Alive Hatası: {e}")

async def reset_daily_limits():
    """Gece 00:00'da limitleri sıfırlar"""
    await users_collection.update_many({}, {"$set": {"daily_usage": 0}})
    print("✅ Günlük limitler sıfırlandı.")

def start_scheduler():
    # 1. Fiyat Kontrolü (6 Saatte bir)
    scheduler.add_job(check_price_drops, 'interval', hours=6)
    
    # 2. Limit Sıfırlama (Her gece 00:00)
    scheduler.add_job(reset_daily_limits, 'cron', hour=0, minute=0)
    
    # 3. CRITICAL: Sunucuyu Uyanık Tut (Her 5 dakikada bir)
    # Bu sayede Render sunucuyu kapatmaz.
    scheduler.add_job(keep_alive, 'interval', minutes=5)
    
    scheduler.start()
    print("🚀 Zamanlayıcı ve Keep-Alive Başlatıldı!")
