import os
import uuid
import requests
import re
from datetime import datetime, timedelta
from typing import List
import xml.etree.ElementTree as ET
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path

# --- AYARLAR ---
load_dotenv()
from backend.database import listings_collection, users_collection
from backend.scheduler import start_scheduler

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
FREE_DAILY_LIMIT = 5
ADMIN_EMAILS = ["cemerentosun@gmail.com", "esragursoytosun@gmail.com"]

# --- GOOGLE AI AYARLARI (YENİ SDK) ---
if GEMINI_KEY:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=GEMINI_KEY)

# --- VERİ MODELLERİ ---
class ListingData(BaseModel):
    id: str | None = None
    price: int | float | None = None
    title: str | None = None
    url: str | None = None
    description: str | None = None
    km: str | None = None
    year: str | None = None
    user_id: str | None = None
    category_path: str | None = None
    # --- YENİ ALANLAR ---
    transmission: str | None = None      # Manuel/Otomatik (Araçlar için)
    listing_type: str | None = None      # araba/konut_satilik/konut_kiralik
    location: str | None = None          # İl/İlçe/Mahalle
    room_count: str | None = None        # Oda sayısı (Konutlar için)
    area_m2: str | None = None           # Metrekare (Konutlar için)
    building_age: str | None = None      # Bina yaşı

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

def clean_number(value):
    """Metin içindeki sayıyı temizler (Örn: '120.000 KM' -> 120000)"""
    if not value: return 0
    if isinstance(value, (int, float)): return int(value)
    # Sadece rakamları al
    clean_val = re.sub(r'[^\d]', '', str(value))
    return int(clean_val) if clean_val else 0

async def calculate_valuation(title, current_price, current_id, current_year, category_path=None, listing_type=None, location=None, room_count=None, area_m2=None):
    """Araç ve emlak ilanları için piyasa değerlemesi yapar"""
    if not title or not current_price: return None
    try:
        # Daha geniş havuzdan (1500 ilan) tarama yap
        cursor = listings_collection.find().sort("first_seen_at", -1).limit(1500)
        all_listings = await cursor.to_list(length=1500)
        
        valid_prices = []
        similar_listings = []  # Benzer ilanları sakla
        cutoff_date = datetime.now() - timedelta(days=60)
        
        target_year = clean_number(current_year)
        target_area = clean_number(area_m2)
        
        # Kategori filtresi kullanılacak mı?
        use_category_filter = category_path and len(category_path) > 5
        
        # Emlak mı kontrol et
        is_real_estate = listing_type and ("konut" in listing_type or "isyeri" in listing_type or "arsa" in listing_type)
        
        # Lokasyon parçalama (İstanbul > Kadıköy > Fenerbahçe gibi)
        location_parts = []
        if location and is_real_estate:
            location_parts = [p.strip().lower() for p in location.replace(">", ",").split(",") if len(p.strip()) > 2]
        
        # Yedek plan için başlık kelimeleri
        keywords = [k.lower() for k in title.split() if len(k) > 2][:4]
        
        for item in all_listings:
            if str(item.get("_id")) == str(current_id): continue
            
            # Tarih kontrolü
            try:
                date_str = item.get("first_seen_at", "2000-01-01 00:00:00")
                if isinstance(date_str, str):
                    item_date = datetime.strptime(date_str.split(" ")[0], "%Y-%m-%d")
                    if item_date < cutoff_date: continue
            except: pass

            p = item.get("current_price", 0)
            t = item.get("title", "").lower()
            y = clean_number(item.get("year", 0))
            item_cat = item.get("category_path", "")
            item_location = (item.get("location", "") or "").lower()
            item_type = item.get("listing_type", "")
            item_room = item.get("room_count", "")
            item_area = clean_number(item.get("area_m2", 0))
            
            # 🏠 EMLAK İÇİN SIKI FİLTRELEME (MAHALLE + ODA + m²) 🏠
            if is_real_estate:
                # 1. TİP KONTROLÜ
                if listing_type and item_type and listing_type != item_type:
                    continue
                
                # 2. ODA SAYISI KONTROLÜ (TAM EŞLEŞME İSTENDİ)
                # İstisna: Eğer odasız (stüdyo) ise veya parse edilemiyorsa esnek davran
                room_match = False
                if room_count and item_room:
                    # Rakamları al (2+1 -> 2, 3+1 -> 3)
                    c_r = re.sub(r'[^\d]', '', room_count.split("+")[0])
                    i_r = re.sub(r'[^\d]', '', item_room.split("+")[0])
                    if c_r and i_r and c_r == i_r: # TAM EŞLEŞME
                        room_match = True
                else:
                    room_match = True # Veri yoksa eleme
                
                if not room_match: continue

                # 3. LOKASYON KONTROLÜ (MAHALLE SEVİYESİNDE)
                # location stringi genelde: İstanbul / Üsküdar / Küçüksu Mh.
                location_match = False
                
                if location_parts and item_location:
                    # En detaylı lokasyon (Mahalle) eşleşmeli
                    # location_parts[-1] genelde mahalleyi verir
                    target_spot = location_parts[-1] 
                    if len(target_spot) > 2 and target_spot in item_location:
                        location_match = True
                
                # KESİN LOKASYON ŞARTI (YANLIŞ EŞLEŞMEYİ ÖNLEMEK İÇİN)
                # Eğer aradığımız spesifik bir mahalle varsa, lokasyon bilgisi olmayan ilanları DAHİL ETME.
                if location_parts and not item_location:
                    location_match = False
                
                # Eğer hedef lokasyon yoksa (genel arama), o zaman mecburen kabul et
                elif not location_parts:
                    location_match = True
                    
                if not location_match: continue
                        
            # 🚗 ARAÇ İÇİN KATEGORİ/BAŞLIK FİLTRELEME 🚗
            else:
                if use_category_filter and item_cat:
                    if category_path not in item_cat and item_cat not in category_path:
                        continue
                else:
                    match_count = sum(1 for k in keywords if k in t)
                    if match_count < 2: continue

                # TAM YIL EŞLEŞMESİ (Araçlar için)
                if target_year > 1900 and y > 1900:
                    if y != target_year: 
                        continue 

            # Fiyat Mantık Kontrolü
            if p > 0:
                if p < (current_price * 0.3) or p > (current_price * 4):
                    continue
                valid_prices.append(p)
                
                # Benzer ilanları sakla (en fazla 5 tane)
                if len(similar_listings) < 5:
                    similar_listings.append({
                        "title": item.get("title", "")[:50],
                        "price": p,
                        "location": item.get("location", ""),
                        "url": item.get("url", "")
                    })
        
        if len(valid_prices) < 2: return None
        
        avg_price = sum(valid_prices) / len(valid_prices)
        min_price = min(valid_prices)
        max_price = max(valid_prices)
        ratio = current_price / avg_price
        
        status = "Piyasa Normali"
        color = "#f1c40f"
        if ratio <= 0.85: status = "🔥 Fırsat (Kelepir)"; color = "#2ecc71"
        elif ratio <= 0.95: status = "✅ Uygun Fiyat"; color = "#27ae60"
        elif ratio >= 1.15: status = "💸 Piyasa Üstü"; color = "#e74c3c"
        elif ratio >= 1.05: status = "⚠️ Biraz Yüksek"; color = "#e67e22"
        
        # Bilgi mesajı oluştur
        if is_real_estate:
            location_info = location_parts[0] if location_parts else "Bölge"
            info_msg = f"{len(valid_prices)} benzer ilan ({location_info.title()})"
            if room_count:
                info_msg += f" [{room_count}]"
        else:
            info_msg = f"{len(valid_prices)} benzer ilan ({target_year} Model)"
            if use_category_filter: info_msg += " [Kategori]"
        
        # m² fiyatı hesapla (emlak için)
        m2_price = None
        avg_m2_price = None
        if is_real_estate and target_area > 0:
            m2_price = int(current_price / target_area)
            # Ortalama m² fiyatı da hesapla
            if avg_price > 0:
                avg_m2_price = int(avg_price / target_area)
            
        return {
            "average_price": int(avg_price),
            "min_price": int(min_price),
            "max_price": int(max_price),
            "listing_count": len(valid_prices),
            "status": status,
            "color": color,
            "ratio": ratio,
            "info_msg": info_msg,
            "is_real_estate": is_real_estate,
            "m2_price": m2_price,
            "avg_m2_price": avg_m2_price,
            "similar_listings": similar_listings[:3]  # En fazla 3 benzer ilan
        }
    except Exception as e:
        print(f"Valuation Hatası: {e}")
        return None

async def get_user_notes(listing_id):
    try:
        doc = await listings_collection.find_one({"_id": listing_id})
        if not doc or "comments" not in doc: return ""
        return "\n".join([f"- {c.get('user')}: {c.get('text')}" for c in doc["comments"]])
    except: return ""

# 🟢 KATEGORİ ALGILAMA FONKSİYONU 🟢
def detect_listing_type(category_path: str, listing_type: str = None) -> str:
    """Kategori yolundan ilan tipini algılar"""
    if listing_type:
        return listing_type
    
    if not category_path:
        return "araba"  # Varsayılan
    
    path_lower = category_path.lower()
    
    # Emlak kategorileri
    if "konut" in path_lower or "daire" in path_lower or "ev" in path_lower:
        if "kiralık" in path_lower:
            return "konut_kiralik"
        elif "satılık" in path_lower:
            return "konut_satilik"
        return "konut_satilik"  # Varsayılan emlak
    
    # İşyeri kategorileri
    if "işyeri" in path_lower or "ofis" in path_lower:
        if "kiralık" in path_lower:
            return "isyeri_kiralik"
        return "isyeri_satilik"
    
    # Arsa
    if "arsa" in path_lower or "tarla" in path_lower:
        return "arsa"
    
    # Vasıta (varsayılan)
    return "araba"

# 🟢 BÖLGE ANALİZİ (HABER + GELİŞİM + ULAŞIM) 🟢
async def search_area_news(location: str) -> dict:
    """Belirtilen lokasyon hakkında kapsamlı bilgi toplar"""
    if not location or len(location) < 3:
        return {}
    
    result = {
        "safety": "",
        "development": "",
        "transport": "",
        "general": ""
    }
    
    # Lokasyonun ana kısmını al (İstanbul > Üsküdar > Küçüksu -> Üsküdar Küçüksu)
    loc_parts = [p.strip() for p in location.replace(">", ",").split(",") if len(p.strip()) > 2]
    search_loc = " ".join(loc_parts[-2:]) if len(loc_parts) >= 2 else location
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        # 1. GÜVENLİK ANALİZİ
        safety_query = f"{search_loc} asayiş olay suç haber"
        safety_url = f"https://www.google.com/search?q={requests.utils.quote(safety_query)}&tbm=nws"
        resp = requests.get(safety_url, headers=headers, timeout=5)
        if resp.status_code == 200:
            text = resp.text.lower()
            negative = ["cinayet", "hırsızlık", "gasp", "uyuşturucu", "kavga", "silahlı", "bıçaklı", "taciz"]
            found = [kw for kw in negative if kw in text]
            if len(found) >= 3:
                result["safety"] = f"⚠️ GÜVENLİK: Bu bölgede son dönemde güvenlik olayları haberlere yansımış. Dikkatli olun."
            elif len(found) >= 1:
                result["safety"] = f"ℹ️ GÜVENLİK: Nadiren güvenlik haberi var, genel olarak sakin bölge."
            else:
                result["safety"] = "✅ GÜVENLİK: Ciddi güvenlik sorunu tespit edilmedi."
        
        # 2. GELİŞİM / YATIRIM ANALİZİ
        dev_query = f"{search_loc} yeni proje inşaat metro kentsel dönüşüm"
        dev_url = f"https://www.google.com/search?q={requests.utils.quote(dev_query)}&tbm=nws"
        resp = requests.get(dev_url, headers=headers, timeout=5)
        if resp.status_code == 200:
            text = resp.text.lower()
            positive = ["metro", "tramvay", "hastane", "avm", "okul", "park", "dönüşüm", "yatırım", "proje"]
            found = [kw for kw in positive if kw in text]
            if len(found) >= 2:
                result["development"] = f"📈 GELİŞİM: Bölgede yeni projeler/yatırımlar planlanıyor ({', '.join(found[:3])}). Değer artışı bekleniyor."
            else:
                result["development"] = "📊 GELİŞİM: Bölgede büyük yatırım haberi bulunmadı."
        
        # 3. ULAŞIM ANALİZİ
        transport_query = f"{search_loc} ulaşım metro otobüs toplu taşıma"
        transport_url = f"https://www.google.com/search?q={requests.utils.quote(transport_query)}"
        resp = requests.get(transport_url, headers=headers, timeout=5)
        if resp.status_code == 200:
            text = resp.text.lower()
            transport_kw = ["metro", "metrobüs", "marmaray", "tramvay", "vapur", "minibüs"]
            found = [kw for kw in transport_kw if kw in text]
            if found:
                result["transport"] = f"🚇 ULAŞIM: Bölgede {', '.join(found[:3])} erişimi mevcut."
        
        # 4. GENEL BÖLGE BİLGİSİ
        result["general"] = f"📍 {search_loc} bölgesi analiz edildi."
        
    except Exception as e:
        print(f"Bölge analiz hatası: {e}")
    
    return result

# 🟢 ARAÇ PROMPT OLUŞTURUCU 🟢
def create_car_prompt(data, market_context: str, user_notes: str) -> str:
    """Araç ilanları için AI prompt oluşturur"""
    transmission_info = data.transmission or "Belirtilmemiş"
    desc = (data.description or "")[:500]
    
    return f"""Sen BAI Bilmiş - akıllı araç danışmanısın.

ARAÇ: {data.title}
FİYAT: {data.price:,} TL | YIL: {data.year} | KM: {data.km} | VİTES: {transmission_info}
AÇIKLAMA: {desc}

{market_context}

KULLANICI YORUMLARI: {user_notes or 'Yok'}

CEVABINI TAMAMEN AŞAĞIDAKİ HTML ŞABLONUNDA VER (sadece HTML, başka bir şey yazma):

<div style="font-family:sans-serif;font-size:13px;line-height:1.6;">
<h3 style="color:#2c3e50;margin:0 0 10px;font-size:15px;">🎯 GENEL DEĞERLENDİRME</h3>
<p style="background:#f8f9fa;padding:10px;border-radius:6px;margin:0 0 12px;">[2-3 cümle genel değerlendirme]</p>

<h3 style="color:#27ae60;margin:0 0 8px;font-size:14px;">✅ ARTILARI</h3>
<ul style="margin:0 0 12px;padding-left:20px;">
<li>[Artı 1]</li>
<li>[Artı 2]</li>
</ul>

<h3 style="color:#e74c3c;margin:0 0 8px;font-size:14px;">⚠️ EKSİLERİ</h3>
<ul style="margin:0 0 12px;padding-left:20px;">
<li>[Eksi 1]</li>
<li>[Eksi 2]</li>
</ul>

<h3 style="color:#3498db;margin:0 0 8px;font-size:14px;">💡 ÖNERİLER</h3>
<p style="background:#e8f4f8;padding:10px;border-radius:6px;border-left:3px solid #3498db;">[Alıcıya öneriler]</p>
</div>
"""

# 🟢 KİRALIK KONUT PROMPT OLUŞTURUCU 🟢
def create_rental_prompt(data, market_context: str, user_notes: str, area_info: dict = None) -> str:
    """Kiralık konut ilanları için AI prompt oluşturur"""
    desc = (data.description or "")[:400]
    location = data.location or "Belirtilmemiş"
    room_count = data.room_count or "?"
    area_m2 = data.area_m2 or "?"
    building_age = data.building_age or "?"
    
    # Bölge bilgilerini formatla
    area_news = ""
    if area_info:
        # Haber başlıklarını al
        news_headlines = ""
        if area_info.get("news_items"):
            news_headlines = "\nSON HABER BAŞLIKLARI:\n" + "\n".join([f"- {n['title']}" for n in area_info['news_items'][:5]])
            
        area_news = f"""
🔍 BÖLGE ANALİZİ:
{area_info.get('safety', '')}
{area_info.get('development', '')}
{area_info.get('transport', '')}

{news_headlines}
"""
    
    return f"""Sen BAI Bilmiş - akıllı emlak danışmanısın.

KİRALIK: {data.title}
KİRA: {data.price:,} TL/ay | LOKASYON: {location} | ODA: {room_count} | m²: {area_m2} | BİNA YAŞI: {building_age}
AÇIKLAMA: {desc}

{market_context}
{area_news}
KULLANICI YORUMLARI: {user_notes or 'Yok'}

CEVABINI TAMAMEN AŞAĞIDAKİ HTML ŞABLONUNDA VER (sadece HTML, başka bir şey yazma):

<div style="font-family:sans-serif;font-size:13px;line-height:1.6;">
<h3 style="color:#2c3e50;margin:0 0 10px;font-size:15px;">🏠 KİRA DEĞERLENDİRMESİ</h3>
<p style="background:#f8f9fa;padding:10px;border-radius:6px;margin:0 0 12px;">[Bu kira bölge ortalamasına göre nasıl? 2-3 cümle]</p>

<h3 style="color:#27ae60;margin:0 0 8px;font-size:14px;">✅ AVANTAJLARI</h3>
<ul style="margin:0 0 12px;padding-left:20px;">
<li>[Lokasyon avantajı]</li>
<li>[Ev özelliği avantajı]</li>
</ul>

<h3 style="color:#e74c3c;margin:0 0 8px;font-size:14px;">⚠️ DİKKAT EDİLECEKLER</h3>
<ul style="margin:0 0 12px;padding-left:20px;">
<li>[Dikkat 1]</li>
<li>[Dikkat 2]</li>
</ul>

<h3 style="color:#9b59b6;margin:0 0 8px;font-size:14px;">📍 BÖLGE BİLGİSİ</h3>
<p style="background:#f5f0ff;padding:10px;border-radius:6px;margin:0 0 12px;">[Güvenlik, ulaşım, gelişim bilgileri - yukarıdaki bölge analizini kullan]</p>

<h3 style="color:#3498db;margin:0 0 8px;font-size:14px;">💡 ÖNERİM</h3>
<p style="background:#e8f4f8;padding:10px;border-radius:6px;border-left:3px solid #3498db;">[Pazarlık ve karar önerisi]</p>
</div>
"""

# 🟢 SATILIK KONUT PROMPT OLUŞTURUCU 🟢
def create_home_sale_prompt(data, market_context: str, user_notes: str, area_info: dict = None) -> str:
    """Satılık konut ilanları için AI prompt oluşturur"""
    desc = (data.description or "")[:400]
    location = data.location or "Belirtilmemiş"
    room_count = data.room_count or "?"
    area_m2 = data.area_m2 or "?"
    building_age = data.building_age or "?"
    
    # m² fiyatı hesapla
    m2_price = ""
    try:
        if data.area_m2 and data.price:
            area_num = int(re.sub(r'[^\d]', '', str(data.area_m2)))
            if area_num > 0:
                m2_price = f"{int(data.price / area_num):,} TL/m²"
    except: pass
    
    # Bölge bilgilerini formatla
    area_news = ""
    if area_info:
        # Haber başlıklarını al
        news_headlines = ""
        if area_info.get("news_items"):
            news_headlines = "\nSON HABER BAŞLIKLARI:\n" + "\n".join([f"- {n['title']}" for n in area_info['news_items'][:5]])
            
        area_news = f"""
🔍 BÖLGE ANALİZİ:
{area_info.get('safety', '')}
{area_info.get('development', '')}
{area_info.get('transport', '')}

{news_headlines}
"""
    
    return f"""Sen BAI Bilmiş - akıllı emlak danışmanısın.

SATILIK: {data.title}
FİYAT: {data.price:,} TL | m² FİYATI: {m2_price or '?'} | LOKASYON: {location} | ODA: {room_count} | m²: {area_m2} | BİNA: {building_age}
AÇIKLAMA: {desc}

{market_context}
{area_news}
KULLANICI YORUMLARI: {user_notes or 'Yok'}

CEVABINI TAMAMEN AŞAĞIDAKİ HTML ŞABLONUNDA VER (sadece HTML, başka bir şey yazma):

<div style="font-family:sans-serif;font-size:13px;line-height:1.6;">
<h3 style="color:#2c3e50;margin:0 0 10px;font-size:15px;">🏡 FİYAT DEĞERLENDİRMESİ</h3>
<p style="background:#f8f9fa;padding:10px;border-radius:6px;margin:0 0 12px;">[Bu fiyat bölge ortalamasına göre nasıl? m² fiyatı değerlendirmesi. 2-3 cümle]</p>

<h3 style="color:#27ae60;margin:0 0 8px;font-size:14px;">✅ AVANTAJLARI</h3>
<ul style="margin:0 0 12px;padding-left:20px;">
<li>[Lokasyon avantajı]</li>
<li>[Ev özelliği avantajı]</li>
</ul>

<h3 style="color:#e74c3c;margin:0 0 8px;font-size:14px;">⚠️ RİSKLER</h3>
<ul style="margin:0 0 12px;padding-left:20px;">
<li>[Bina yaşı riski varsa]</li>
<li>[Diğer riskler]</li>
</ul>

<h3 style="color:#9b59b6;margin:0 0 8px;font-size:14px;">📍 BÖLGE BİLGİSİ</h3>
<p style="background:#f5f0ff;padding:10px;border-radius:6px;margin:0 0 12px;">[Güvenlik, ulaşım, gelişim - yukarıdaki bölge analizini kullan]</p>

<h3 style="color:#f39c12;margin:0 0 8px;font-size:14px;">📈 YATIRIM POTANSİYELİ</h3>
<p style="background:#fef9e7;padding:10px;border-radius:6px;margin:0 0 12px;">[Kira getirisi, değer artış potansiyeli]</p>

<h3 style="color:#3498db;margin:0 0 8px;font-size:14px;">💡 ÖNERİM</h3>
<p style="background:#e8f4f8;padding:10px;border-radius:6px;border-left:3px solid #3498db;">[Pazarlık ve karar önerisi, ekspertiz uyarısı]</p>
</div>
"""

# --- ENDPOINTLER ---

# 🟢 UptimeRobot Dostu
@app.get("/")
@app.head("/")
async def root():
    return {"status": "active", "message": "Sahiden Asistan Uyanık! ☕"}

# 🟢 ADMIN PANEL STATIC FILES
ADMIN_DIR = Path(__file__).parent.parent / "admin"

@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
async def admin_panel():
    """Admin panel ana sayfasını döndürür"""
    index_path = ADMIN_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Admin Panel Bulunamadı</h1>", status_code=404)

@app.get("/admin/{filename}")
async def admin_static(filename: str):
    """Admin panel static dosyalarını döndürür"""
    file_path = ADMIN_DIR / filename
    if file_path.exists() and file_path.is_file():
        content_types = {
            ".css": "text/css",
            ".js": "application/javascript",
            ".html": "text/html",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".ico": "image/x-icon"
        }
        suffix = file_path.suffix.lower()
        media_type = content_types.get(suffix, "application/octet-stream")
        return FileResponse(file_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="Dosya bulunamadı")

# 🟢 YENİ EKLENDİ: Arka Plan Görevleri (404 Hatasını Çözer) 🟢
@app.get("/get-update-task")
async def get_update_task():
    """Arka plan işçisi için güncellenmesi gereken eski bir ilanı döndürür."""
    try:
        # Son güncellemesi 24 saatten eski olan bir ilan bul
        cutoff_time = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Rastgele eski bir ilan seç (Sadece URL ve ID lazım)
        task = await listings_collection.find_one(
            {"last_update": {"$lt": cutoff_time}, "url": {"$exists": True, "$ne": ""}}
        )
        
        if task:
            return {"status": "task_found", "id": task["_id"], "url": task["url"]}
        
        return {"status": "no_task"}
    except: return {"status": "error"}

@app.post("/update-price-background")
async def update_price_background(data: ListingData):
    """Arka plan işçisinden gelen güncel fiyatı kaydeder."""
    if not data.id or not data.price: return {"status": "error"}
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    existing = await listings_collection.find_one({"_id": data.id})
    if existing:
        last_price = existing.get("current_price", 0)
        # Fiyat değişmişse geçmişe ekle
        if last_price != data.price:
            await listings_collection.update_one(
                {"_id": data.id}, 
                {
                    "$set": {"current_price": data.price, "last_update": now},
                    "$push": {"history": {"date": now, "price": last_price}}
                }
            )
        else:
            # Fiyat aynıysa sadece güncelleme tarihini yenile
            await listings_collection.update_one(
                {"_id": data.id}, 
                {"$set": {"last_update": now}}
            )
            
    return {"status": "success"}

@app.post("/analyze-ai")
async def ask_ai(data: ListingData):
    if not GEMINI_KEY: return {"status": "error", "message": "API Key Eksik!"}
    if not data.user_id: return {"status": "login_required", "message": "Giriş yapın."}

    user = await users_collection.find_one({"_id": data.user_id})
    if user:
        if user.get("plan") != "premium" and user.get("daily_usage", 0) >= FREE_DAILY_LIMIT:
            return {"status": "limit_reached", "message": "Günlük limit doldu."}
        await users_collection.update_one({"_id": data.user_id}, {"$inc": {"daily_usage": 1}})

    # 🟢 KATEGORİ ALGILAMA 🟢
    listing_type = detect_listing_type(data.category_path, data.listing_type)

    # Valuation'a tüm parametreleri gönder (emlak için lokasyon bazlı karşılaştırma)
    valuation = await calculate_valuation(
        title=data.title, 
        current_price=data.price, 
        current_id=data.id, 
        current_year=data.year, 
        category_path=data.category_path,
        listing_type=listing_type,
        location=data.location,
        room_count=data.room_count,
        area_m2=data.area_m2
    )
    user_notes = await get_user_notes(data.id)
    
    market_context = "Veri yok"
    if valuation:
        # Emlak için özel market context
        if valuation.get("is_real_estate"):
            m2_info = ""
            if valuation.get("m2_price"):
                m2_info = f"\n- Bu İlan m² Fiyatı: {valuation['m2_price']:,} TL/m²"
                if valuation.get("avg_m2_price"):
                    m2_info += f" | Bölge Ort: {valuation['avg_m2_price']:,} TL/m²"
            
            similar_info = ""
            if valuation.get("similar_listings"):
                similar_info = "\n- Benzer İlanlar: " + ", ".join([
                    f"{s['title'][:30]}... ({s['price']:,} TL)" 
                    for s in valuation['similar_listings'][:2]
                ])
            
            market_context = (
                f"VERİTABANI ANALİZİ (EMLAK):\n"
                f"- Lokasyon: {data.location or 'Belirtilmemiş'}\n"
                f"- Benzer İlan: {valuation['listing_count']} adet (aynı bölge, benzer m²)\n"
                f"- Ort: {valuation['average_price']:,} TL | Min: {valuation['min_price']:,} TL | Max: {valuation['max_price']:,} TL\n"
                f"- Durum: {valuation['status']}"
                f"{m2_info}{similar_info}"
            )
        else:
            # Araç için mevcut format
            market_context = (
                f"VERİTABANI ANALİZİ:\n"
                f"- Kategori: {data.category_path or 'Genel'}\n"
                f"- Benzer İlan: {valuation['listing_count']} adet\n"
                f"- Ort: {valuation['average_price']:,} TL | Min: {valuation['min_price']:,} TL | Max: {valuation['max_price']:,} TL\n"
                f"- Durum: {valuation['status']}"
            )

    # 🟢 BÖLGE HABERLERİNİ GETİR (Emlak için) 🟢
    area_info = {}
    if listing_type in ["konut_kiralik", "konut_satilik"]:
        area_info = await search_area_news_persistent(data.location)

    # 🟢 KATEGORİYE GÖRE PROMPT OLUŞTUR 🟢
    if listing_type == "konut_kiralik":
        prompt = create_rental_prompt(data, market_context, user_notes, area_info)
    elif listing_type == "konut_satilik":
        prompt = create_home_sale_prompt(data, market_context, user_notes, area_info)
    else:
        # Varsayılan: Araç
        prompt = create_car_prompt(data, market_context, user_notes)
    
    # 🟢 GOOGLE AI REST API (v1beta) 🟢
    import asyncio
    import requests
    import json
    
    if not GEMINI_KEY:
        return {"status": "error", "message": "API Key eksik!"}
    
    # Olası model isimleri (Geniş liste - Loglardan alındı)
    models_to_try = [
        "gemini-2.0-flash-lite",      # En hafif
        "gemini-2.0-flash",           # Standart
        "gemini-2.0-flash-lite-preview-02-05", # Alternatif preview
        "gemini-flash-latest",        # Backup
    ]
    
    last_error = ""
    
    # 1. GENERATE DENEMESİ
    for model_name in models_to_try:
        # Her model için 2 deneme hakkı (429 yersek bekleyip tekrar deneriz)
        for attempt in range(2): 
            try:
                print(f"🤖 Deneniyor ({model_name}) - Deneme {attempt+1}")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_KEY}"
                
                payload = { "contents": [{ "parts": [{"text": prompt}] }] }
                response = requests.post(url, json=payload, timeout=40)
                
                if response.status_code == 200:
                    result = response.json()
                    if "candidates" in result and len(result["candidates"]) > 0:
                        candidate = result["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            text = "".join([part.get("text", "") for part in candidate["content"]["parts"]])
                            if text:
                                print(f"✅ Başarılı: {model_name}")
                                
                                # 🟢 HABER FEED (Twitter Tarzı) EKLE 🟢
                                if area_info.get("news_items"):
                                    news_html = "<div style='margin-top:25px;padding-top:15px;border-top:2px solid #eee;'>"
                                    news_html += "<h3 style='font-size:14px;color:#293542;margin-bottom:12px;display:flex;align-items:center;'>🗞️ BÖLGE HABER AKIŞI <span style='font-size:10px;background:#eee;padding:2px 6px;border-radius:10px;margin-left:8px;color:#666;'>Canlı</span></h3>"
                                    for item in area_info['news_items'][:5]:
                                        source_name = item.get('source', 'Haber')
                                        date_str = item.get('date', '')[:16]
                                        news_html += f"""
                                        <div style="margin-bottom:10px;padding:10px;background:#fff;border:1px solid #e1e8ed;border-radius:8px;transition:all 0.2s;">
                                            <div style="display:flex;align-items:center;margin-bottom:5px;">
                                                <div style="width:20px;height:20px;background:#1da1f2;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:10px;font-weight:bold;margin-right:8px;">{source_name[0]}</div>
                                                <div style="font-size:11px;font-weight:bold;color:#14171a;">{source_name}</div>
                                                <div style="font-size:10px;color:#657786;margin-left:5px;">• {date_str}</div>
                                            </div>
                                            <a href="{item['link']}" target="_blank" style="text-decoration:none;color:#14171a;font-size:12px;line-height:1.4;display:block;">{item['title']}</a>
                                        </div>
                                        """
                                    news_html += "</div>"
                                    text += news_html
                                
                                return {"status": "success", "ai_response": text}
                
                # Hata yönetimi
                error_msg = response.text
                status_code = response.status_code
                
                print(f"⚠️ Yanıt: {status_code} - {error_msg[:200]}")
                
                # Eğer Rate Limit (429) ise bekle
                if status_code == 429:
                    if attempt == 0: # İlk denemeyse bekle
                        import time
                        wait_sec = 4
                        print(f"⏳ Kota doldu ({model_name}). {wait_sec} sn bekleniyor...")
                        time.sleep(wait_sec)
                        continue # Döngü başa döner, 2. denemeyi yapar
                    else:
                        last_error = "Rate Limit (Kota Doldu)"
                else:
                    # 429 değilse (örn 404, 500) direkt diğer modele geç
                    last_error = str(error_msg)
                    break 
                    
            except Exception as e:
                print(f"❌ Hata ({model_name}): {e}")
                last_error = str(e)
                break # Exception durumunda diğer modele geç

    return {"status": "error", "message": f"AI Şu an yoğun: {last_error[:100]}. Lütfen biraz bekleyip tekrar deneyin."}

@app.post("/analyze")
async def analyze_listing(data: ListingData):
    if not data.id or not data.price: return {"status": "error"}
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_doc = {
            "current_price": data.price,
            "last_update": now,
            "title": data.title,
            "url": data.url,
            "year": data.year,
            "km": data.km,
            "category_path": data.category_path,
            # Yeni alanlar
            "transmission": data.transmission,
            "listing_type": data.listing_type,
            "location": data.location,
            "room_count": data.room_count,
            "area_m2": data.area_m2,
            "building_age": data.building_age
        }
        
        existing = await listings_collection.find_one({"_id": data.id})
        
        if existing and existing.get("current_price") != data.price:
            await listings_collection.update_one({"_id": data.id}, {"$set": update_doc, "$push": {"history": {"date": now, "price": data.price}}})
        else:
            await listings_collection.update_one({"_id": data.id}, {"$set": update_doc}, upsert=True)
            
        doc = await listings_collection.find_one({"_id": data.id})
        
        # Kategori tipini algıla
        listing_type = detect_listing_type(data.category_path, data.listing_type)
        
        # Valuation hesapla (emlak için lokasyon bazlı karşılaştırma)
        valuation = await calculate_valuation(
            title=data.title, 
            current_price=data.price, 
            current_id=data.id, 
            current_year=data.year, 
            category_path=data.category_path,
            listing_type=listing_type,
            location=data.location,
            room_count=data.room_count,
            area_m2=data.area_m2
        )
        
        return {"status": "success", "valuation": valuation, "history": doc.get("history", []), "comments": doc.get("comments", [])}
    except Exception as e:
        print(f"Analyze Hatası: {e}")
        return {"status": "error"}

@app.post("/add_comment")
async def add_comment(comment: CommentData):
    if not comment.user_id: return {"status": "error", "message": "Giriş yapın."}
    user_name = comment.username or "Misafir"
    user = await users_collection.find_one({"_id": comment.user_id})
    if user: user_name = user.get("name", user_name)

    new_comment = {
        "id": str(uuid.uuid4()),
        "user_id": comment.user_id,
        "user": user_name,
        "text": comment.text,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "liked_by": []
    }
    await listings_collection.update_one({"_id": comment.listing_id}, {"$push": {"comments": new_comment}}, upsert=True)
    
    # Ödül / Limit Mantığı
    reward_msg = "Yorum eklendi!"
    if user and user.get("plan") != "premium":
        today_str = datetime.now().strftime("%Y-%m-%d")
        last_date = user.get("last_comment_date", "")
        earned_today = user.get("earned_credits_today", 0) if last_date == today_str else 0
        current_progress = user.get("comment_progress", 0) if last_date == today_str else 0

        if earned_today < 2: 
            current_progress += 1
            if current_progress >= 5:
                await users_collection.update_one(
                    {"_id": comment.user_id}, 
                    {"$set": {"comment_progress": 0, "last_comment_date": today_str, "earned_credits_today": earned_today + 1}, "$inc": {"daily_usage": -1}}
                )
                reward_msg = "🎉 5 Yorum yaptın, +1 Hak kazandın!"
            else:
                await users_collection.update_one(
                    {"_id": comment.user_id}, 
                    {"$set": {"comment_progress": current_progress, "last_comment_date": today_str}}
                )
                reward_msg = f"Yorum eklendi. ({current_progress}/5)"
    
    return {"status": "success", "message": reward_msg}

@app.post("/like_comment")
async def like_comment(data: LikeData):
    doc = await listings_collection.find_one({"_id": data.listing_id})
    if not doc: return {"status": "error"}
    comments = doc.get("comments", [])
    for c in comments:
        if c.get("id") == data.comment_id:
            likes = c.get("liked_by", [])
            if data.user_id in likes: likes.remove(data.user_id)
            else: likes.append(data.user_id)
            c["liked_by"] = likes
    await listings_collection.update_one({"_id": data.listing_id}, {"$set": {"comments": comments}})
    return {"status": "success", "comments": comments}

@app.post("/auth/google")
async def google_login(data: GoogleLoginData):
    try:
        res = requests.get(f"https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {data.token}"})
        if res.status_code == 200:
            idinfo = res.json()
            if 'sub' not in idinfo and 'id' in idinfo: idinfo['sub'] = idinfo['id']
        else: raise ValueError("Token reddedildi.")
        
        google_id = idinfo['sub']
        email = idinfo.get('email')
        
        # Mevcut kullanıcıyı kontrol et
        existing_user = await users_collection.find_one({"_id": google_id})
        
        update_data = {
            "$set": {"email": email, "name": idinfo.get('name'), "picture": idinfo.get('picture'), "last_login": datetime.now()},
            "$setOnInsert": {"daily_usage": 0, "comment_progress": 0, "earned_credits_today": 0, "telegram_chat_id": None}
        }
        if email in ADMIN_EMAILS: update_data["$set"]["plan"] = "premium"
        else: update_data["$setOnInsert"]["plan"] = "free"
        
        await users_collection.update_one({"_id": google_id}, update_data, upsert=True)
        
        # Güncel kullanıcı bilgilerini al
        updated_user = await users_collection.find_one({"_id": google_id})
        
        return {
            "status": "success", 
            "user": {
                "id": google_id, 
                "name": idinfo.get('name'), 
                "picture": idinfo.get('picture'),
                "email": email,
                "plan": updated_user.get("plan", "free"),
                "daily_usage": updated_user.get("daily_usage", 0)
            }
        }
    except Exception as e: raise HTTPException(status_code=401, detail=str(e))

# 🟢 KULLANICI PROFİL BİLGİLERİ (Güncel usage ve plan)
@app.get("/user/profile/{user_id}")
async def get_user_profile(user_id: str):
    """Kullanıcının güncel profil bilgilerini döndürür"""
    try:
        user = await users_collection.find_one({"_id": user_id})
        if not user:
            return {"status": "error", "message": "Kullanıcı bulunamadı"}
        
        is_premium = user.get("plan") == "premium"
        daily_limit = 999 if is_premium else FREE_DAILY_LIMIT
        daily_usage = user.get("daily_usage", 0)
        
        return {
            "status": "success",
            "profile": {
                "id": user_id,
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "picture": user.get("picture", ""),
                "plan": user.get("plan", "free"),
                "daily_usage": daily_usage,
                "daily_limit": daily_limit,
                "remaining": max(0, daily_limit - daily_usage) if not is_premium else 999,
                "comment_progress": user.get("comment_progress", 0)
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/admin/upgrade")
async def upgrade_user(email: str, key: str):
    if key != "cem_baba": return {"status": "error", "message": "Hatalı Şifre!"}
    user = await users_collection.find_one({"email": email})
    if not user: return {"status": "error", "message": "Kullanıcı bulunamadı."}
    await users_collection.update_one({"email": email},{"$set": {"plan": "premium", "daily_usage": 0}})
    return {"status": "success", "message": f"{email} artık PREMIUM!"}

# --- ADMIN PANEL API'LERİ ---

ADMIN_KEY = "UmutDeniz*21092025"  # Admin şifresi

class AdminAction(BaseModel):
    admin_email: str
    user_id: str = None
    plan: str = None
    search_query: str = None

async def verify_admin(email: str) -> bool:
    """Admin yetkisini kontrol eder"""
    return email in ADMIN_EMAILS

@app.post("/admin/login")
async def admin_login(data: dict):
    """Admin girişi - email ve şifre ile"""
    email = data.get("email", "").strip().lower()
    key = data.get("key", "")
    
    if not email or not key:
        return {"status": "error", "is_admin": False, "message": "Email ve şifre gerekli!"}
    
    if key != ADMIN_KEY:
        return {"status": "error", "is_admin": False, "message": "Şifre hatalı!"}
    
    if email not in [e.lower() for e in ADMIN_EMAILS]:
        return {"status": "error", "is_admin": False, "message": "Bu email admin değil!"}
    
    return {"status": "success", "is_admin": True, "email": email}

@app.post("/admin/verify")
async def admin_verify(data: dict):
    """Admin girişini doğrular"""
    email = data.get("email", "")
    if await verify_admin(email):
        return {"status": "success", "is_admin": True}
    return {"status": "error", "is_admin": False, "message": "Yetkiniz yok!"}

@app.post("/admin/users")
async def admin_get_users(data: dict):
    """Tüm kullanıcıları listeler (Admin only)"""
    admin_email = data.get("admin_email", "")
    if not await verify_admin(admin_email):
        return {"status": "error", "message": "Yetkiniz yok!"}
    
    try:
        limit = data.get("limit", 50)
        skip = data.get("skip", 0)
        
        cursor = users_collection.find().sort("last_login", -1).skip(skip).limit(limit)
        users = await cursor.to_list(length=limit)
        total = await users_collection.count_documents({})
        
        user_list = []
        for u in users:
            user_list.append({
                "id": u.get("_id"),
                "name": u.get("name", "İsimsiz"),
                "email": u.get("email", ""),
                "picture": u.get("picture", ""),
                "plan": u.get("plan", "free"),
                "daily_usage": u.get("daily_usage", 0),
                "last_login": str(u.get("last_login", "")) if u.get("last_login") else None,
                "is_admin": u.get("email") in ADMIN_EMAILS
            })
        
        return {"status": "success", "users": user_list, "total": total}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/admin/set-plan")
async def admin_set_plan(data: dict):
    """Kullanıcı planını değiştirir (Admin only)"""
    admin_email = data.get("admin_email", "")
    if not await verify_admin(admin_email):
        return {"status": "error", "message": "Yetkiniz yok!"}
    
    user_id = data.get("user_id")
    new_plan = data.get("plan", "free")
    
    if new_plan not in ["free", "premium"]:
        return {"status": "error", "message": "Geçersiz plan!"}
    
    try:
        result = await users_collection.update_one(
            {"_id": user_id},
            {"$set": {"plan": new_plan, "daily_usage": 0}}
        )
        
        if result.modified_count > 0:
            return {"status": "success", "message": f"Kullanıcı '{new_plan}' planına alındı!"}
        else:
            return {"status": "error", "message": "Kullanıcı bulunamadı veya zaten bu plandaydı."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/admin/search")
async def admin_search_users(data: dict):
    """Kullanıcı arar (Admin only)"""
    admin_email = data.get("admin_email", "")
    if not await verify_admin(admin_email):
        return {"status": "error", "message": "Yetkiniz yok!"}
    
    query = data.get("query", "").strip()
    if not query or len(query) < 2:
        return {"status": "error", "message": "En az 2 karakter girin."}
    
    try:
        # Email veya isimde arama yap
        cursor = users_collection.find({
            "$or": [
                {"email": {"$regex": query, "$options": "i"}},
                {"name": {"$regex": query, "$options": "i"}}
            ]
        }).limit(20)
        
        users = await cursor.to_list(length=20)
        
        user_list = []
        for u in users:
            user_list.append({
                "id": u.get("_id"),
                "name": u.get("name", "İsimsiz"),
                "email": u.get("email", ""),
                "picture": u.get("picture", ""),
                "plan": u.get("plan", "free"),
                "daily_usage": u.get("daily_usage", 0),
                "is_admin": u.get("email") in ADMIN_EMAILS
            })
        
        return {"status": "success", "users": user_list, "count": len(user_list)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/admin/stats")
async def admin_get_stats(admin_email: str):
    """Genel istatistikleri döndürür (Admin only)"""
    if not await verify_admin(admin_email):
        return {"status": "error", "message": "Yetkiniz yok!"}
    
    try:
        total_users = await users_collection.count_documents({})
        premium_users = await users_collection.count_documents({"plan": "premium"})
        free_users = total_users - premium_users
        total_listings = await listings_collection.count_documents({})
        
        # Bugün giriş yapanlar
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        active_today = await users_collection.count_documents({
            "last_login": {"$gte": today_start}
        })
        
        return {
            "status": "success",
            "stats": {
                "total_users": total_users,
                "premium_users": premium_users,
                "free_users": free_users,
                "total_listings": total_listings,
                "active_today": active_today
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- BULK UPLOAD (Kategori Destekli & Tüm Alanlar) ---
@app.post("/bulk-upload")
async def bulk_upload(listings: List[ListingData]):
    if not listings: return {"status": "empty"}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in listings:
        if not item.id or not item.price: continue
        
        # $min OPERATÖRÜ İLE ZEKİ TARİH GÜNCELLEMESİ
        await listings_collection.update_one(
            {"_id": item.id}, 
            {
                "$set": {
                    "current_price": item.price, 
                    "last_update": now, 
                    "url": item.url, 
                    "title": item.title, 
                    "year": item.year, 
                    "km": item.km,
                    "category_path": item.category_path,
                    # Yeni alanlar
                    "transmission": item.transmission,
                    "listing_type": item.listing_type,
                    "location": item.location,
                    "room_count": item.room_count,
                    "area_m2": item.area_m2,
                    "building_age": item.building_age
                },
                "$min": { "first_seen_at": now },
                "$setOnInsert": { "history": [], "comments": [] }
            },
            upsert=True
        )
    return {"status": "success"}

@app.on_event("startup")
async def startup_event():
    start_scheduler()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)

# 🟢 BÖLGE ANALİZİ (PERSISTENT - RSS) 🟢
async def search_area_news_persistent(location: str) -> dict:
    """Belirtilen lokasyon hakkında kapsamlı bilgi toplar (RSS) ve veritabanına kaydeder"""
    if not location or len(location) < 3: return {}
    
    # Lokasyon temizleme
    loc_parts = [p.strip() for p in location.replace(">", ",").split(",") if len(p.strip()) > 2]
    # En detaylı kısmı al (Örn: Üsküdar Küçüksu)
    if len(loc_parts) >= 2:
        search_loc_full = " ".join(loc_parts[-2:])
    elif len(loc_parts) == 1:
        search_loc_full = loc_parts[0]
    else:
        search_loc_full = location
        
    search_loc_slug = search_loc_full.lower().replace(" ", "-").replace("ı", "i").replace("ü", "u").replace("ö", "o").replace("ş", "s").replace("ç", "c").replace("ğ", "g")
    
    # 1. ÖNCE DB KONTROL ET (Son 24 saat - Haberler güncel olmalı)
    try:
        from backend.database import area_insights_collection
        existing_data = await area_insights_collection.find_one({"_id": search_loc_slug})
        
        if existing_data:
            last_date = existing_data.get("updated_at")
            if last_date:
                # 24 saat geçti mi? (Haber akışı için kısa tut)
                last_dt = datetime.strptime(last_date, "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - last_dt).days < 1:
                    return existing_data.get("data", {})
    except Exception as e:
        print(f"DB Read Error: {e}")
    
    # 2. RSS ARAMA (Google News)
    rss_url = f"https://news.google.com/rss/search?q={search_loc_full}+haber&hl=tr-TR&gl=TR&ceid=TR:tr"
    
    result = {
        "safety": "",
        "development": "",
        "transport": "",
        "general": f"📍 {search_loc_full} Bölgesi Haber Özeti",
        "news_items": []
    }
    
    try:
        resp = requests.get(rss_url, timeout=5)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            
            # Anahtar Kelimeler
            neg_kw = ["cinayet", "silahlı", "kavga", "hırsızlık", "uyuşturucu", "gasp", "ölü", "yaralı", "yangın", "kaza", "operasyon", "çete"]
            pos_kw = ["yatırım", "proje", "metro", "tören", "hizmet", "park", "okul", "hastane", "açılış", "değer", "konut"]
            trans_kw = ["metro", "otobüs", "sefer", "durak", "marmaray", "ulaşım", "yol", "köprü", "tünel"]
            
            safety_hits = []
            dev_hits = []
            trans_hits = []
            
            for item in items[:15]: # Son 15 haber
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                pubDate = item.find("pubDate").text if item.find("pubDate") is not None else ""
                source = item.find("source").text if item.find("source") is not None else "Google Haberler"
                
                # Listeye ekle
                result["news_items"].append({
                    "title": title,
                    "link": link,
                    "date": pubDate,
                    "source": source
                })
                
                t_low = title.lower()
                if any(k in t_low for k in neg_kw): safety_hits.append(title)
                if any(k in t_low for k in pos_kw): dev_hits.append(title)
                if any(k in t_low for k in trans_kw): trans_hits.append(title)
            
            # Analiz Metinlerini Oluştur
            if safety_hits:
                result["safety"] = f"⚠️ GÜVENLİK: Güncel haberlerde bazı asayiş olayları ({len(safety_hits)} adet) göze çarpıyor. Örn: {safety_hits[0]}"
            else:
                result["safety"] = "✅ GÜVENLİK: Güncel haber akışında bölgeyle ilgili olumsuz bir asayiş olayı öne çıkmıyor."
                
            if dev_hits:
                result["development"] = f"📈 GELİŞİM: Bölge hareketli, yeni projeler ve yatırımlar gündemde: {dev_hits[0]}"
            else:
                result["development"] = "📊 GELİŞİM: Son dönemde bölgeyle ilgili büyük bir yatırım haberi akışa düşmedi."

            if trans_hits:
                result["transport"] = f"🚇 ULAŞIM: Ulaşım ve altyapı ile ilgili haberler mevcut: {trans_hits[0]}"
        
        # DB'ye KAYDET
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await area_insights_collection.update_one(
            {"_id": search_loc_slug},
            {"$set": {
                "updated_at": now_str,
                "location_name": search_loc_full,
                "data": result
            }},
            upsert=True
        )

    except Exception as e:
        print(f"RSS Analiz Hatası: {e}")
    
    return result
