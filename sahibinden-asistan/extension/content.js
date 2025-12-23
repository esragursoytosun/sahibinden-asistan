// content.js - FINAL SÜRÜM (SÜRÜKLEME GARANTİLİ) 🚀

const API_URL = "https://sahiden.onrender.com"; 

console.log("BAI BILMIS: Yeni Sürüm Yüklendi! (V3)"); // Konsolda bunu görmelisin

// --- KİMLİK ---
let userId = localStorage.getItem("sahibinden_userid");
if (!userId) { userId = "uid_" + Math.random().toString(36).substr(2, 9); localStorage.setItem("sahibinden_userid", userId); }
let currentUser = localStorage.getItem("sahibinden_user") || "Misafir";

// --- VERİ OKUMA ---
function getListingData() {
    try {
        let priceText = document.querySelector('.classifiedInfo h3')?.innerText || document.querySelector('div.price-info')?.innerText;
        let price = priceText ? parseInt(priceText.replace(/\D/g, '')) : 0;
        const idElement = document.getElementById('classifiedId');
        const listingId = idElement ? idElement.innerText.trim() : "Bilinmiyor";
        const titleElement = document.querySelector('.classifiedDetailTitle h1');
        const title = titleElement ? titleElement.innerText.trim() : document.title;
        const description = document.querySelector('#classifiedDescription')?.innerText || "Açıklama yok";
        
        let km = "Bilinmiyor";
        let year = "Bilinmiyor";
        const details = document.querySelectorAll('.classifiedInfoList li');
        details.forEach(li => {
            const label = li.querySelector('strong')?.innerText;
            const value = li.querySelector('span')?.innerText;
            if(label?.includes("KM")) km = value;
            if(label?.includes("Yıl")) year = value;
        });

        if (price === 0) return null;
        return { id: listingId, price: price, title: title, description: description, km: km, year: year, url: window.location.href };
    } catch (e) { return null; }
}

// --- GRAFİK ---
function createPriceChart(history) {
    if (!history || history.length < 2) return ''; 
    const width = 240; const height = 60; const padding = 5;
    const prices = history.map(h => h.price);
    const minPrice = Math.min(...prices); const maxPrice = Math.max(...prices);
    if (minPrice === maxPrice) return `<div style="text-align:center; font-size:10px; color:#666; padding:10px;">Fiyat Stabil ⎯⎯⎯</div>`;
    
    const points = prices.map((p, i) => {
        const x = (i / (prices.length - 1)) * (width - 2 * padding) + padding;
        const y = height - ((p - minPrice) / (maxPrice - minPrice)) * (height - 2 * padding) - padding;
        return `${x},${y}`;
    }).join(' ');
    
    return `<svg width="100%" height="${height}"><polyline fill="none" stroke="#293542" stroke-width="2" points="${points}" /></svg>`;
}

// --- SÜRÜKLEME MANTIĞI (GÜÇLENDİRİLMİŞ) ---
function makeDraggable(el) {
    const header = document.getElementById("sahibinden-asistan-header");
    let isDragging = false;
    let startX, startY, initialLeft, initialTop;

    if (!header) return;

    header.onmousedown = function(e) {
        e.preventDefault(); // Metin seçimini engelle
        isDragging = true;
        
        // Mouse başlangıç pozisyonu
        startX = e.clientX;
        startY = e.clientY;
        
        // Elementin şu anki konumu
        initialLeft = el.offsetLeft;
        initialTop = el.offsetTop;

        // "right" özelliğini iptal et ki "left" çalışsın
        el.style.right = "auto";
        el.style.bottom = "auto";
        
        // Sürüklerken cursor değişsin
        header.style.cursor = "grabbing";

        document.onmousemove = elementDrag;
        document.onmouseup = closeDragElement;
    };

    function elementDrag(e) {
        if (!isDragging) return;
        e.preventDefault();

        // Ne kadar hareket ettik?
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;

        // Yeni konumu uygula
        el.style.left = (initialLeft + dx) + "px";
        el.style.top = (initialTop + dy) + "px";
    }

    function closeDragElement() {
        isDragging = false;
        header.style.cursor = "grab";
        document.onmouseup = null;
        document.onmousemove = null;
    }
}

// --- ANA EKRAN ---
function showOverlay(data, result) {
    // Eski paneli temizle
    const oldOverlay = document.getElementById('sahibinden-asistan-box');
    if (oldOverlay) oldOverlay.remove();

    const overlay = document.createElement('div');
    overlay.id = 'sahibinden-asistan-box';
    
    const isError = !result || result.status === "error";
    let chartHtml = isError ? "" : createPriceChart(result.history);

    overlay.innerHTML = `
        <div id="sahibinden-asistan-header" style="
            background: #FFD000; 
            color: #222; 
            padding: 12px; 
            border-top-left-radius: 8px; 
            border-top-right-radius: 8px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            cursor: grab; 
            user-select: none;
            border-bottom: 2px solid #e0b800;
        ">
            <div style="font-weight: 900; font-size:14px;">🧐 BAI BİLMİŞ</div>
            <div style="display:flex; align-items:center; gap:5px;">
                <span id="closeOverlayBtn" style="cursor:pointer; font-size:16px; font-weight:bold; color:#333; padding:0 5px;">✖</span>
            </div>
        </div>
        
        <div style="padding: 15px; background: #fff; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
            <div style="text-align:center; margin-bottom:15px;">
                <div style="font-size: 22px; font-weight: 800; color:#293542;">${data.price.toLocaleString('tr-TR')} TL</div>
                <div style="font-size:10px; color:#888;">İlan Fiyatı</div>
            </div>
            ${chartHtml}
            
            <button id="askAiBtn" style="width:100%; background: #293542; color: #FFD000; border: none; padding: 12px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: bold; margin-top: 15px;">
                ✨ ANALİZ ET
            </button>
            
            <div id="aiResult" style="display:none; font-size:12px; margin-top:15px; background: #f9f9f9; padding: 10px; border: 1px solid #eee; border-radius: 4px; max-height: 300px; overflow-y: auto;"></div>

            <button id="toggleCommentsBtn" style="width:100%; background: #f1f1f1; color: #555; border: 1px solid #ddd; padding: 8px; border-radius: 4px; margin-top: 10px; font-size: 11px; font-weight: bold; cursor: pointer;">
                💬 Yorumlar (${result.comments ? result.comments.length : 0})
            </button>

            <div id="commentSection" style="display:none; margin-top:10px;">
                <div id="commentList" style="max-height:150px; overflow-y:auto; margin-bottom:8px; word-break: break-word;">${renderComments(result.comments || [])}</div>
                <div style="display:flex; gap:5px;">
                    <input id="commentInput" placeholder="Yorum..." style="flex:1; border:1px solid #ccc; padding:5px; font-size:11px;">
                    <button id="sendCommentBtn" style="background:#293542; color:white; border:none; padding:0 10px;">➤</button>
                </div>
            </div>
        </div>
    `;

    // CSS STİLLERİ (Important ile zorla)
    overlay.style.cssText = `
        position: fixed !important;
        top: 150px !important;
        right: 20px !important;
        left: auto;
        width: 300px !important;
        background-color: transparent !important;
        border-radius: 8px !important;
        box-shadow: 0 10px 40px rgba(0,0,0,0.4) !important;
        z-index: 2147483647 !important; /* En üst katman */
        font-family: sans-serif !important;
    `;
    
    document.body.appendChild(overlay);

    // SÜRÜKLEMEYİ BAŞLAT
    makeDraggable(overlay);

    // EVENTS
    document.getElementById('closeOverlayBtn').onclick = () => overlay.remove();

    document.getElementById('askAiBtn').onclick = async () => {
        const btn = document.getElementById('askAiBtn');
        const resultBox = document.getElementById('aiResult');
        btn.innerHTML = "⏳ Düşünüyor...";
        btn.disabled = true;

        try {
            const response = await fetch(`${API_URL}/analyze-ai`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) 
            });
            const json = await response.json();
            resultBox.style.display = "block";
            
            if(json.status === "success") {
                const modelInfo = json.used_model ? `<div style='font-size:9px; color:#aaa; margin-top:5px; text-align:right;'>🤖 ${json.used_model}</div>` : "";
                resultBox.innerHTML = json.ai_response + modelInfo;
                btn.innerHTML = "✅ Tamamlandı";
            } else {
                resultBox.innerHTML = "Hata: " + json.message;
                btn.innerHTML = "❌ Hata";
            }
        } catch (e) {
            btn.innerHTML = "❌ Bağlantı Yok";
            resultBox.style.display = "block";
            resultBox.innerHTML = "Sunucuya bağlanılamadı.";
        } finally { btn.disabled = false; }
    };

    document.getElementById('toggleCommentsBtn').onclick = () => {
        const section = document.getElementById('commentSection');
        section.style.display = section.style.display === 'none' ? 'block' : 'none';
    };
    
    // Yorum Gönderme ve Beğenme kodları (Öncekilerle aynı mantık)
    setupCommentEvents(data, result.comments);
}

function renderComments(comments) {
    if (!comments || comments.length === 0) return '<div style="font-size:11px; text-align:center; padding:5px; color:#999;">Henüz yorum yok.</div>';
    return comments.map(c => `
        <div style="background:#fff; padding:6px; margin-bottom:6px; border:1px solid #eee; font-size:11px; word-break: break-word;">
            <b>${c.user}</b>: ${c.text}
            <div style="text-align:right; font-size:10px;">❤️ ${c.liked_by?.length||0}</div>
        </div>`).join('');
}

function setupCommentEvents(data, comments) {
    document.getElementById('sendCommentBtn').onclick = async () => {
        const text = document.getElementById('commentInput').value;
        if (!text) return;
        try {
            const response = await fetch(`${API_URL}/add_comment`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ listing_id: data.id, username: currentUser, text: text })
            });
            const json = await response.json();
            if (json.status === "success") {
                document.getElementById('commentList').innerHTML = renderComments(json.comments);
                document.getElementById('commentInput').value = "";
                document.getElementById('toggleCommentsBtn').innerText = `💬 Yorumlar (${json.comments.length})`;
            }
        } catch (err) {} 
    };
}

async function analyzeListing() {
    const data = getListingData();
    if (!data) return;
    try {
        const response = await fetch(`${API_URL}/analyze`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        const result = await response.json();
        showOverlay(data, result);
    } catch (error) { showOverlay(data, { status: "error" }); }
}

setTimeout(analyzeListing, 1000);
