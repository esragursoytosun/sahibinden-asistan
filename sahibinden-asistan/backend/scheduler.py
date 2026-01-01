import os
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.database import listings_collection, users_collection
import requests

# Render'a kaydettiğimiz şifreyi (Token) alıyoruz
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Zamanlayıcıyı başlatıyoruz
scheduler = AsyncIOScheduler()

def send_alert(chat_id, message):
    """
    Kullanıcıya Telegram üzerinden mesaj gönderir.
    """
    if not TELEGRAM_TOKEN or not chat_id:
        print("⚠️ Telegram Token veya Chat ID eksik, mesaj atılamadı.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML" # Mesajda kalın/italik yazı kullanabilmek için
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"✅ Mesaj gönderildi: {chat_id}")
        else:
            print(f"❌ Mesaj hatası: {response.text}")
    except Exception as e:
        print(f"❌ Bağlantı hatası: {e}")

async def check_price_drops():
    """
    Veritabanındaki ilanları gezer ve fiyat kontrolü yapar.
    """
    print("🕵️ BAI Bilmiş İş Başında: Fiyatlar kontrol ediliyor...")
    
    # 1. Takip edilen tüm ilanları getir
    cursor = listings_collection.find({})
    listings = await cursor.to_list(length=1000)
    
    for item in listings:
        try:
            old_price = item.get("current_price", 0)
            url = item.get("url")
            title = item.get("title", "İsimsiz İlan")
            listing_id = item.get("_id")
            
            if old_price == 0: continue

            # --- SİMÜLASYON BÖLÜMÜ (ÖNEMLİ) ---
            # Şu an Sahibinden.com'a istek atarsak banlanabiliriz.
            # Bu yüzden şimdilik "gerçek fiyatı çekmişiz de fiyat aynıymış" gibi davranıyoruz.
            # İleride buraya Proxy servisi eklenecek.
            current_price = old_price 
            
            # TEST İÇİN: Eğer gerçekten sistemin mesaj attığını görmek istersen
            # aşağıdaki satırın başındaki # işaretini kaldırabilirsin:
            # current_price = old_price - 100 # (Test: Fiyatı yapay olarak 100 TL düşürür)

            # EĞER FİYAT DÜŞTÜYSE
            if current_price < old_price:
                drop_amount = old_price - current_price
                print(f"🚨 FİYAT DÜŞTÜ! {title} (İndirim: {drop_amount} TL)")
                
                # Bu ilanı favorileyen kullanıcıyı bulmamız lazım.
                # Şimdilik sistemin çalışıp çalışmadığını anlamak için
                # Veritabanında 'telegram_chat_id'si olan İLK kullanıcıya mesaj atalım.
                # (Gerçek senaryoda ilanı kim takip ediyorsa ona atacağız)
                
                user = await users_collection.find_one({"telegram_chat_id": {"$exists": True}})
                
                if user:
                    msg = (
                        f"🚨 <b>FİYAT ALARMI!</b>\n\n"
                        f"🚗 <b>{title}</b>\n"
                        f"📉 <s>{old_price:,.0f} TL</s> -> <b>{current_price:,.0f} TL</b>\n"
                        f"🔥 <b>İndirim: {drop_amount:,.0f} TL</b>\n\n"
                        f"👉 <a href='{url}'>İlana Git</a>"
                    )
                    send_alert(user["telegram_chat_id"], msg)
                
                # Veritabanını güncelle ki tekrar tekrar mesaj atmasın
                await listings_collection.update_one(
                    {"_id": listing_id},
                    {"$set": {"current_price": current_price}}
                )
                
        except Exception as e:
            print(f"Hata (ID: {item.get('_id')}): {e}")

    print("✅ Fiyat kontrol turu tamamlandı.")

def start_scheduler():
    # Her 6 saatte bir çalıştır (Test ederken bunu 'minutes=1' yapabilirsin)
    scheduler.add_job(check_price_drops, 'interval', hours=6)
    scheduler.start()
