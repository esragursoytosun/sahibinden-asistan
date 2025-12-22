// content.js - EKSİKSİZ FİNAL SÜRÜM (KAYDIRMA + HATA GÖSTERİMİ) 🚀

const API_URL = "https://sahiden.onrender.com"; 

console.log("SAHIBINDEN ASISTAN: Başlatılıyor..."); 

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

        // Fiyat yoksa ilan sayfası değildir
        if (price === 0) {
            console.log("SAHIBINDEN ASISTAN: Fiyat bulunamadı, bu bir ilan sayfası olmayabilir.");
            return null;
        }

        return { id: listingId, price: price, title: title, description: description, km: km, year: year, url: window.location.href };
    } catch (e) { 
        console.error("Veri okuma hatası:", e);
        return null; 
    }
}

// --- GRAFİK ---
function createPriceChart(history) {
    if (!history || history.length < 2) return ''; 
    const width = 240; const height = 60; const padding = 5;
    const prices = history.map(h => h.price);
    const minPrice = Math.min(...prices); const maxPrice = Math.max(...prices);
    if (minPrice === maxPrice) return `<div style="text-align:center; font-size:10px; color:#aaa; padding:10px;">Fiyat Stabil ⎯⎯⎯</div>`;
    
    const points = prices.map((p, i) => {
        const x = (i / (prices.length - 1)) * (width - 2 * padding) + padding;
        const y = height - ((p - minPrice) / (maxPrice - minPrice)) * (height - 2 * padding) - padding;
        return `${x},${y}`;
    }).join(' ');
    
    const strokeColor = prices[prices.length-1] < prices[0] ? '#2ecc71' : '#e74c3c';
    return `<svg width="100%" height="${height}"><polyline fill="none" stroke="${strokeColor}" stroke-width="2" points="${points}" /></svg>`;
}

// --- ANA EKRAN ---
function showOverlay(data, result) {
    console.log("SAHIBINDEN ASISTAN: Arayüz çiziliyor...");
    
    const oldOverlay = document.getElementById('sahibinden-asistan-box');
    if (oldOverlay) oldOverlay.remove();

    const overlay = document.createElement('div');
    overlay.id = 'sahibinden-asistan-box';
    
    const isError = !result || result.status === "error";
    let boxColor = isError ? "#e74c3c" : (result.is_price_drop ? "#27ae60" : "#2c3e50");
    let chartHtml = isError ? "" : createPriceChart(result.history);

    overlay.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:8px; margin-bottom: 10px;">
            <span style="font-weight: 800; font-size:14px;">🤖 AI ASİSTAN</span>
            <input type="text" id="usernameInput" value="${currentUser}" style="width:70px; background:rgba(0,0,0,0.3); border:none; color:white; padding:3px; border-radius:4px; font-size:10px; text-align:center;">
        </div>
        
        <div style="text-align:center; margin:10px 0;">
            <div style="font-size: 20px; font-weight: 800;">${data.price.toLocaleString('tr-TR')} ₺</div>
        </div>
        
        ${chartHtml}

        <button id="askAiBtn" style="width:100%; background:linear-gradient(90deg, #8e44ad, #9b59b6); color:white; border:none; padding:10px; border-radius:8px; cursor:pointer; font-size:12px; font-weight:bold; margin-top:10px; box-shadow:0 4px 10px rgba(142, 68, 173, 0.4);">
            ✨ YAPAY ZEKA EKSPERTİZİ
        </button>
        
        <div id="aiResult" style="display:none; font-size:11px; margin-top:10px; background:rgba(255,255,255,0.1); padding:10px; border-radius:8px; line-height:1.5; max-height: 250px; overflow-y: auto; border: 1px solid rgba(255,255,255,0.1);"></div>

        <button id="toggleCommentsBtn" style="width:100%; background:white; color:#333; border:none; padding:8px; border-radius:6px; margin-top:8px; font-size:11px; font-weight:bold;">💬 Yorumlar (${result.comments ? result.comments.length : 0})</button>

        <div id="commentSection" style="display:none; margin-top:10px; background:#f0f2f5; border-radius:8px; padding:8px; color:#333;">
            <div id="commentList" style="max-height:150px; overflow-y:auto; margin-bottom:8px;">${renderComments(result.comments || [])}</div>
            <div style="display:flex; gap:5px;">
                <input id="commentInput" placeholder="Yorum..." style="flex:1; border:1px solid #ddd; padding:5px; border-radius:4px; font-size:11px;">
                <button id="sendCommentBtn" style="background:#2c3e50; color:white; border:none; padding:0 8px; border-radius:4px;">➤</button>
            </div>
        </div>
    `;

    // Stil Ayarları (Scroll dahil)
    Object.assign(overlay.style, {
        position: 'fixed', 
        top: '120px', 
        right: '20px', 
        width: '280px',
        maxHeight: '85vh',       // Ekran taşmasını engeller
        overflowY: 'auto',       // Ana kutuda scroll çıkarır
        backgroundColor: boxColor, 
        color: 'white', 
        padding: '15px', 
        borderRadius: '16px',
        boxShadow: '0 10px 30px rgba(0,0,0,0.3)', 
        zIndex: '999999', 
        fontFamily: "'Segoe UI', sans-serif",
        backdropFilter: 'blur(10px)'
    });
    
    document.body.appendChild(overlay);

    // --- BUTON OLAYLARI ---

    // 1. AI Butonu
    document.getElementById('askAiBtn').onclick = async () => {
        const btn = document.getElementById('askAiBtn');
        const resultBox = document.getElementById('aiResult');
        
        btn.innerHTML = "⏳ Analiz Ediliyor...";
        btn.disabled = true;

        try {
            const response = await fetch(`${API_URL}/analyze-ai`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data) 
            });
            const json = await response.json();
            
            resultBox.style.display = "block";
            if(json.status === "success") {
                const modelInfo = json.used_model ? `<div style='font-size:9px; color:#aaa; margin-top:5px; text-align:right;'>Model: ${json.used_model}</div>` : "";
                resultBox.innerHTML = json.ai_response + modelInfo;
                btn.innerHTML = "✅ Analiz Tamamlandı";
            } else {
                resultBox.innerHTML = "Hata: " + (json.message || "Bilinmiyor");
                btn.innerHTML = "❌ Hata";
            }
        } catch (e) {
            btn.innerHTML = "❌ Bağlantı Hatası";
            resultBox.style.display = "block";
            resultBox.innerHTML = "Sunucuya bağlanılamadı. İnternetini kontrol et.";
        } finally {
            btn.disabled = false;
        }
    };

    // 2. Yorumları Göster/Gizle
    document.getElementById('toggleCommentsBtn').onclick = () => {
        const section = document.getElementById('commentSection');
        section.style.display = section.style.display === 'none' ? 'block' : 'none';
    };
    
    // 3. Yorum Gönder
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
        } catch (err) { console.error(err); } 
    };

    // 4. Yorum Beğen (Event Delegation)
    document.getElementById('commentList').addEventListener('click', async (e) => {
        const btn = e.target.closest('.like-btn');
        if (btn) {
            const commentId = btn.getAttribute('data-id');
            try {
                const response = await fetch(`${API_URL}/like_comment`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ listing_id: data.id, comment_id: commentId, user_id: userId })
                });
                const json = await response.json();
                if(json.status === "success") document.getElementById('commentList').innerHTML = renderComments(json.comments);
            } catch (err) { console.error(err); }
        }
    });
    
    // Kullanıcı Adı Değişimi
    document.getElementById('usernameInput').onchange = (e) => {
        currentUser = e.target.value;
        localStorage.setItem("sahibinden_user", currentUser);
    };
}

// Yardımcı Fonksiyon: Yorumları HTML'e dök
function renderComments(comments) {
    if (!comments || comments.length === 0) return '<div style="font-size:11px; text-align:center; padding:5px;">Henüz yorum yok.</div>';
    return comments.map(c => `
        <div style="background:white; padding:5px; margin-bottom:5px; border-radius:5px; font-size:11px;">
            <b>${c.user}</b>: ${c.text}
            <div style="text-align:right;"><button class="like-btn" data-id="${c.id}" style="border:none; background:none; cursor:pointer;">❤️ ${c.liked_by?.length||0}</button></div>
        </div>`).join('');
}

// Ana Başlatıcı
async function analyzeListing() {
    const data = getListingData();
    if (!data) return; // Veri yoksa çık
    
    try {
        console.log("Sunucuya istek atılıyor...");
        const response = await fetch(`${API_URL}/analyze`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        const result = await response.json();
        showOverlay(data, result);
    } catch (error) {
        console.error("Bağlantı hatası:", error);
        // Hata olsa bile kutuyu göster (Kırmızı modda)
        showOverlay(data, { status: "error" });
    }
}

// Sayfa yüklendikten 1 saniye sonra çalış
setTimeout(analyzeListing, 1000);
