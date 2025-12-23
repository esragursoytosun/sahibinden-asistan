// content.js - SAHİBİNDEN TEMALI, SÜRÜKLENEBİLİR & KAPATILABİLİR 🟡⚫

const API_URL = "https://sahiden.onrender.com"; 

console.log("BAI BILMIS: Başlatılıyor..."); 

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

// --- GRAFİK (Renkler güncellendi) ---
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
    
    // Grafik rengi: Sahibinden mavisi
    return `<svg width="100%" height="${height}"><polyline fill="none" stroke="#293542" stroke-width="2" points="${points}" /></svg>`;
}

// --- SÜRÜKLEME FONKSİYONU (Düzeltildi) ---
function makeDraggable(el) {
    const header = document.getElementById("sahibinden-asistan-header");
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

    if (header) {
        header.onmousedown = dragMouseDown;
    }

    function dragMouseDown(e) {
        e = e || window.event;
        e.preventDefault();
        // Mouse başlangıç pozisyonu
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        document.onmousemove = elementDrag;
    }

    function elementDrag(e) {
        e = e || window.event;
        e.preventDefault();
        
        // Yeni pozisyon hesapla
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        
        // Elementi kaydır
        el.style.top = (el.offsetTop - pos2) + "px";
        el.style.left = (el.offsetLeft - pos1) + "px";
        
        // ÖNEMLİ: Sağa yaslamayı iptal et ki left çalışsın
        el.style.right = "auto"; 
    }

    function closeDragElement() {
        document.onmouseup = null;
        document.onmousemove = null;
    }
}

// --- ANA EKRAN ---
function showOverlay(data, result) {
    // Varsa eskiyi sil
    const oldOverlay = document.getElementById('sahibinden-asistan-box');
    if (oldOverlay) oldOverlay.remove();

    const overlay = document.createElement('div');
    overlay.id = 'sahibinden-asistan-box';
    
    const isError = !result || result.status === "error";
    let chartHtml = isError ? "" : createPriceChart(result.history);

    // HTML İÇERİĞİ
    overlay.innerHTML = `
        <div id="sahibinden-asistan-header" style="
            background: #FFD000; 
            color: #222; 
            padding: 10px 15px; 
            border-top-left-radius: 8px; 
            border-top-right-radius: 8px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            cursor: move; 
            font-family: 'Roboto', sans-serif;
            border-bottom: 2px solid #e0b800;
        ">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:18px;">🧐</span>
                <span style="font-weight: 900; font-size:14px; letter-spacing:0.5px;">BAI BİLMİŞ</span>
            </div>
            <div style="display:flex; gap:8px; align-items:center;">
                <input type="text" id="usernameInput" value="${currentUser}" 
                    style="width:70px; background:rgba(255,255,255,0.8); border:1px solid #ccc; color:#333; padding:2px 5px; border-radius:4px; font-size:11px; text-align:center;">
                <span id="closeOverlayBtn" style="cursor:pointer; font-size:18px; font-weight:bold; color:#333; padding:0 5px;">✖</span>
            </div>
        </div>
        
        <div style="padding: 15px; background: #fff; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
            
            <div style="text-align:center; margin-bottom:15px;">
                <div style="font-size: 22px; font-weight: 800; color:#293542;">${data.price.toLocaleString('tr-TR')} TL</div>
                <div style="font-size:10px; color:#888;">Güncel İlan Fiyatı</div>
            </div>
            
            ${chartHtml}

            <button id="askAiBtn" style="
                width:100%; 
                background: #293542; 
                color: #FFD000; 
                border: none; 
                padding: 12px; 
                border-radius: 4px; 
                cursor: pointer; 
                font-size: 13px; 
                font-weight: bold; 
                margin-top: 15px; 
                transition: background 0.2s;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            ">
                ✨ ANALİZ ET
            </button>
            
            <div id="aiResult" style="
                display:none; 
                font-size:12px; 
                margin-top:15px; 
                background: #f4f6f9; 
                color: #333;
                padding: 12px; 
                border-radius: 4px; 
                line-height: 1.5; 
                max-height: 250px; 
                overflow-y: auto; 
                border: 1px solid #ddd;
                box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);
            "></div>

            <button id="toggleCommentsBtn" style="
                width:100%; 
                background: #f1f1f1; 
                color: #555; 
                border: 1px solid #ddd; 
                padding: 8px; 
                border-radius: 4px; 
                margin-top: 10px; 
                font-size: 11px; 
                font-weight: bold;
                cursor: pointer;
            ">💬 Yorumlar (${result.comments ? result.comments.length : 0})</button>

            <div id="commentSection" style="display:none; margin-top:10px; border-top:1px solid #eee; padding-top:10px;">
                <div id="commentList" style="max-height:150px; overflow-y:auto; margin-bottom:8px; word-break: break-word;">${renderComments(result.comments || [])}</div>
                <div style="display:flex; gap:5px;">
                    <input id="commentInput" placeholder="Bir not bırak..." style="flex:1; border:1px solid #ccc; padding:6px; border-radius:4px; font-size:11px;">
                    <button id="sendCommentBtn" style="background:#293542; color:white; border:none; padding:0 10px; border-radius:4px; cursor:pointer;">➤</button>
                </div>
            </div>
        </div>
    `;

    // ANA KUTU STİLİ
    Object.assign(overlay.style, {
        position: 'fixed', 
        top: '130px', 
        right: '20px', 
        width: '300px',
        maxHeight: '90vh', 
        backgroundColor: 'transparent', // Arkaplanı iç divlere bıraktık
        borderRadius: '8px',
        boxShadow: '0 8px 25px rgba(0,0,0,0.25)', 
        zIndex: '9999999', 
        fontFamily: "'Roboto', sans-serif",
        border: '1px solid #ccc'
    });
    
    document.body.appendChild(overlay);

    // SÜRÜKLEME AKTİF
    makeDraggable(overlay);

    // --- BUTON OLAYLARI ---

    // 1. KAPATMA
    document.getElementById('closeOverlayBtn').onclick = () => {
        overlay.style.display = 'none';
    };

    // 2. AI BUTONU
    document.getElementById('askAiBtn').onmouseover = function() { this.style.backgroundColor = '#1a222c'; }
    document.getElementById('askAiBtn').onmouseout = function() { this.style.backgroundColor = '#293542'; }

    document.getElementById('askAiBtn').onclick = async () => {
        const btn = document.getElementById('askAiBtn');
        const resultBox = document.getElementById('aiResult');
        
        btn.innerHTML = "⏳ Piyasa Araştırılıyor...";
        btn.disabled = true;
        btn.style.opacity = "0.7";

        try {
            const response = await fetch(`${API_URL}/analyze-ai`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) 
            });
            const json = await response.json();
            
            resultBox.style.display = "block";
            if(json.status === "success") {
                const modelInfo = json.used_model ? `<div style='font-size:9px; color:#999; margin-top:8px; text-align:right; border-top:1px solid #eee; padding-top:4px;'>🤖 ${json.used_model}</div>` : "";
                resultBox.innerHTML = json.ai_response + modelInfo;
                btn.innerHTML = "✅ Analiz Tamamlandı";
            } else {
                resultBox.innerHTML = `<span style="color:red;">Hata: ${json.message || "Bilinmiyor"}</span>`;
                btn.innerHTML = "❌ Tekrar Dene";
            }
        } catch (e) {
            btn.innerHTML = "❌ Bağlantı Yok";
            resultBox.style.display = "block";
            resultBox.innerHTML = "Sunucuya ulaşılamadı. İnternetini kontrol et.";
        } finally { 
            btn.disabled = false;
            btn.style.opacity = "1";
        }
    };

    // 3. DİĞER BUTONLAR
    document.getElementById('toggleCommentsBtn').onclick = () => {
        const section = document.getElementById('commentSection');
        section.style.display = section.style.display === 'none' ? 'block' : 'none';
    };
    
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
    
    document.getElementById('usernameInput').onchange = (e) => {
        currentUser = e.target.value;
        localStorage.setItem("sahibinden_user", currentUser);
    };
}

// YORUM RENDER
function renderComments(comments) {
    if (!comments || comments.length === 0) return '<div style="font-size:11px; text-align:center; padding:5px; color:#999;">Henüz yorum yok.</div>';
    return comments.map(c => `
        <div style="background:#fff; padding:6px; margin-bottom:6px; border:1px solid #eee; border-radius:4px; font-size:11px; word-break: break-word;">
            <b style="color:#293542;">${c.user}</b>: <span style="color:#555;">${c.text}</span>
            <div style="text-align:right;"><button class="like-btn" data-id="${c.id}" style="border:none; background:none; cursor:pointer; color:#e74c3c; font-size:10px;">❤️ ${c.liked_by?.length||0}</button></div>
        </div>`).join('');
}

// BAŞLAT
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
