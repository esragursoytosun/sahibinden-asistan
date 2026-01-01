import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.database import listings_collection, users_collection
import requests
from bs4 import BeautifulSoup

# Zamanlayıcıyı başlatıyoruz
scheduler = AsyncIOScheduler()

async def check_price_drops():
    """
    Bu fonksiyon belirli aralıklarla çalışır.
    Veritabanındaki ilanları gezer, güncel fiyatı kontrol eder.
    """
    print("🕵️ BAI Bilmiş İş Başında: Fiyatlar kontrol ediliyor...")
    
    # 1. Takip edilen tüm ilanları getir
    cursor = listings_collection.find({})
    listings = await cursor.to_list(length=1000)
    
    for item in listings:
        try:
            old_price = item.get("current_price")
            url = item.get("url")
            title = item.get("title")
            
            # --- BURASI KRİTİK ---
            # Normalde sunucudan Sahibinden'e istek atmak zordur (Bot koruması vardır).
            # Şimdilik "Simülasyon" yapıyoruz. 
            # İleride buraya Proxy veya Scraper servisi entegre edeceğiz.
            # ---------------------
            
            # TEST İÇİN: Rastgele bir senaryo uyduralım
            # Gerçek hayatta burada requests.get(url) çalışacak.
            # Şimdilik veritabanındaki fiyatı 1 TL düşmüş gibi hayal edelim.
            current_price = old_price  # Burası normalde siteden çekilen yeni fiyat olacak
            
            # EĞER FİYAT DÜŞTÜYSE
            if current_price < old_price:
                drop_amount = old_price - current_price
                print(f"🚨 FİYAT DÜŞTÜ! İlan: {title}")
                print(f"Eski: {old_price} -> Yeni: {current_price} (İndirim: {drop_amount} TL)")
                
                # TODO: Telegram Token alınca burayı açacağız
                # await send_telegram_alert(title, old_price, current_price, url)
                
                # Veritabanını güncelle
                await listings_collection.update_one(
                    {"_id": item["_id"]},
                    {"$set": {"current_price": current_price}}
                )
                
        except Exception as e:
            print(f"Hata (ID: {item.get('_id')}): {e}")

    print("✅ Kontrol tamamlandı.")

def start_scheduler():
    # Her 6 saatte bir çalışacak şekilde ayarla (Test için 'seconds=30' yapabilirsin)
    scheduler.add_job(check_price_drops, 'interval', hours=6)
    scheduler.start()
