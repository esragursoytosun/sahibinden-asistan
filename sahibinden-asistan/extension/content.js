// content.js - FINAL SÜRÜM: KONTRASTLI ARAYÜZ & GELİŞMİŞ SCROLL 🛠️

const API_URL = "https://sahiden.onrender.com"; 

console.log("BAI BILMIS: Arayüz Güncellendi (V4)"); 

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

// --- SÜRÜKLEME ---
function makeDraggable(el) {
    const header = document.getElementById("sahibinden-asistan-header");
    let isDragging = false;
    let startX, startY, initialLeft, initialTop;

    if (!header) return;

    header.onmousedown = function(e) {
        if(e.target.id === "closeOverlayBtn" || e.target.id === "usernameInput") return; // Butonlara basınca sürükleme
        e.preventDefault();
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        initialLeft = el.offsetLeft;
        initialTop = el.offsetTop;
        el.style.right = "auto";
        header.style.cursor = "grabbing";
        document.onmousemove = elementDrag;
        document.onmouseup = closeDragElement;
    };

    function elementDrag(e) {
        if (!isDragging) return;
        e.preventDefault();
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
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
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            z-index: 10;
        ">
            <div style="font-weight: 900; font-size:14px; display:flex; align-items:center; gap:5px;">
                <span>🤖</span> BAI BİLMİŞ
            </div>
            <div style="display:flex; align-items:center; gap:6px;">
                 <input type="text" id="usernameInput" value="${currentUser}" 
                    style="width:80px; background:rgba(255,255,255,0.9); border:none; padding:3px; border-radius:4px; font-size:11px; text-align:center; color:#333;">
                <span id="closeOverlayBtn" style="cursor:pointer; font-size:18px; font-weight:bold; color:#333; padding:0 4px;">&times;</span>
            </div>
        </div>
        
        <div style="
            padding: 15px; 
            background: #F2F4F6; /* Kontrast Rengi */
            border-bottom-left-radius: 8px; 
            border-bottom-right-radius: 8px;
            color: #333;
        ">
            <div style="text-align:center; margin-bottom:15px;">
                <div style="font-size: 24px; font-weight: 800; color:#293542; letter-spacing:-0.5px;">${data.price.toLocaleString('tr-TR')} TL</div>
                <div style="font-size:11px; color:#777; font-weight:500;">İlan Fiyatı</div>
            </div>
            
            ${chartHtml}
            
            <button id="askAiBtn" style="
                width:100%; 
                background: #293542; 
                color: #FFD000; 
                border: none; 
                padding: 12px; 
                border-radius: 6px; 
                cursor: pointer; 
                font-size: 13px; 
                font-weight: bold; 
                margin-top: 15px;
                box-shadow: 0 3px 6px rgba(0,0,0,0.15);
                transition: all 0.2s;
            ">
                ✨ ANALİZ ET
            </button>
            
            <div id="aiResult" style="
                display:none; 
                font-size:12px; 
                margin-top:15px; 
                background: #fff; /* İç kutu beyaz */
                padding: 12px; 
                border: 1px solid #ddd;
                border-radius: 6px; 
                max-height: 250px; 
                overflow-y: auto;
                line-height: 1.5;
                box-shadow: inset 0 2px 4px rgba(0,0,0,0.03);
            "></div>

            <button id="toggleCommentsBtn" style="
                width:100%; 
                background: #e0e4e8; 
                color: #444; 
                border: none; 
                padding: 8px; 
                border-radius: 6px; 
                margin-top: 12px; 
                font-size: 11px; 
                font-weight: bold; 
                cursor: pointer;
            ">
                💬 Yorumlar (${result.comments ? result.comments.length : 0})
            </button>

            <div id="commentSection" style="display:none; margin-top:10px;">
                <div id="commentList" style="
                    max-height: 180px; 
                    overflow-y: auto; 
                    margin-bottom: 8px; 
                    word-break: break-word;
                    background: #fff;
                    border: 1px solid #e1e1e1;
                    border-radius: 4px;
                    padding: 5px;
                    overscroll-behavior: contain; /* ÖNEMLİ: Fare tekerleği sadece burayı etkiler */
                ">
                    ${renderComments(result.comments || [])}
                </div>
                
                <div style="display:flex; gap:5px;">
                    <input id="commentInput" placeholder="Yorum ekle..." style="
                        flex:1; 
                        border:1px solid #ccc; 
                        padding:8px; 
                        font-size:12px; 
                        border-radius:4px;
                        outline:none;
                    ">
                    <button id="sendCommentBtn" style="background:#293542; color:white; border:none; padding:0 12px; border-radius:4px; cursor:pointer;">➤</button>
                </div>
            </div>
        </div>
    `;

    // CSS STİLLERİ
    overlay.style.cssText = `
        position: fixed !important;
        top: 150px !important;
        right: 20px !important;
        width: 310px !important;
        background-color: transparent !important;
        border-radius: 8px !important;
        box-shadow: 0 15px 50px rgba(0,0,0,0.3) !important;
        z-index: 2147483647 !important;
        font-family: 'Open Sans', Helvetica, Arial, sans-serif !important;
        border: 1px solid #dcdcdc !important;
    `;
    
    document.body.appendChild(overlay);

    makeDraggable(overlay);

    // EVENTS
    document.getElementById('closeOverlayBtn').onclick = () => overlay.remove();

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
                const modelInfo = json.used_model ? `<div style='font-size:10px; color:#aaa; margin-top:8px; border-top:1px solid #eee; padding-top:4px; text-align:right;'>🤖 ${json.used_model}</div>` : "";
                resultBox.innerHTML = json.ai_response + modelInfo;
                btn.innerHTML = "✅ Analiz Bitti";
            } else {
                resultBox.innerHTML = "Hata: " + json.message;
                btn.innerHTML = "❌ Hata";
            }
        } catch (e) {
            btn.innerHTML = "❌ Bağlantı Yok";
            resultBox.style.display = "block";
            resultBox.innerHTML = "Sunucuya bağlanılamadı.";
        } finally { 
            btn.disabled = false;
            btn.style.opacity = "1";
        }
    };

    document.getElementById('toggleCommentsBtn').onclick = () => {
        const section = document.getElementById('commentSection');
        section.style.display = section.style.display === 'none' ? 'block' : 'none';
    };
    
    setupCommentEvents(data);
}

function renderComments(comments) {
    if (!comments || comments.length === 0) return '<div style="font-size:11px; text-align:center; padding:10px; color:#999;">Henüz yorum yok.</div>';
    return comments.map(c => `
        <div style="
            border-bottom: 1px solid #eee; 
            padding: 6px; 
            margin-bottom: 4px;
            font-size: 11px;
        ">
            <b style="color:#293542;">${c.user}</b>: <span style="color:#555;">${c.text}</span>
            <div style="text-align:right; font-size:10px; margin-top:2px;">
                <button class="like-btn" data-id="${c.id}" style="border:none; background:none; cursor:pointer; color:#e74c3c;">❤️ ${c.liked_by?.length||0}</button>
            </div>
        </div>`).join('');
}

function setupCommentEvents(data) {
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
            } catch (err) {}
        }
    });

    document.getElementById('usernameInput').onchange = (e) => {
        currentUser = e.target.value;
        localStorage.setItem("sahibinden_user", currentUser);
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
