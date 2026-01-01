// content.js - BAI BİLMİŞ: AKILLI ARAYÜZ (Giriş Zorunlu Modu) 🚀

const API_URL = "https://sahiden.onrender.com"; 

console.log("BAI BILMIS: Sistem Başlatıldı"); 

// --- KİMLİK & LOGİN KONTROLÜ ---
let userId = localStorage.getItem("sahibinden_userid");
let userProfile = null;

// Sayfa açılışında profili kontrol et
try {
    const storedProfile = localStorage.getItem("sahibinden_user_profile");
    if (storedProfile && storedProfile !== "undefined") {
        userProfile = JSON.parse(storedProfile);
    }
} catch (e) {
    localStorage.removeItem("sahibinden_user_profile");
}

// Profil yoksa geçici ID oluştur
if (!userId) { 
    userId = "uid_" + Math.random().toString(36).substr(2, 9); 
    localStorage.setItem("sahibinden_userid", userId); 
}

// --- LOGİN FONKSİYONU ---
function loginWithGoogle() {
    const btn = document.getElementById('googleLoginBtn');
    if(btn) btn.innerHTML = "⌛ Bekleyin...";
    
    chrome.runtime.sendMessage({ action: "login" }, (response) => {
        if (response && response.status === "success") {
            userProfile = response.user;
            localStorage.setItem("sahibinden_user_profile", JSON.stringify(userProfile));
            localStorage.setItem("sahibinden_userid", userProfile.id);
            alert(`✅ Giriş Başarılı! Hoş geldin, ${userProfile.name}`);
            location.reload(); // Paneli güncellemek için yenile
        } else {
            console.error("Login Hatası:", response);
            alert("❌ Giriş yapılamadı. Lütfen tekrar deneyin.");
            if(btn) btn.innerHTML = '<span style="color:#4285F4; font-weight:900;">G</span> Giriş Yap';
        }
    });
}

function logout() {
    if(confirm("Çıkış yapmak istiyor musun?")) {
        localStorage.removeItem("sahibinden_user_profile");
        userId = "uid_" + Math.random().toString(36).substr(2, 9);
        localStorage.setItem("sahibinden_userid", userId);
        location.reload();
    }
}

// --- TELEGRAM / FAVORİ İŞLEMİ (AKILLI KONTROL) ---
function handleTelegramClick() {
    // KONTROL: Kullanıcı giriş yapmış mı?
    if (!userProfile) {
        // SENARYO 1: Giriş Yapmamış
        let onay = confirm("⚠️ Bu özellik için Google ile giriş yapmalısınız.\n\nŞimdi giriş yapmak ister misiniz?");
        if (onay) {
            loginWithGoogle(); // Otomatik giriş fonksiyonunu çağır
        }
        return; // İşlemi durdur
    }

    // SENARYO 2: Giriş Yapmış -> Telegram'ı Aç
    let botName = "BAIBilmisBot"; 
    // Kullanıcının Google ID'sini gönderiyoruz ki eşleşsin
    let url = `https://t.me/${botName}?start=${userProfile.id}`;
    
    window.open(url, '_blank');
}

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
        
        // Araç/Emlak detaylarını çek
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
        
        return { 
            id: listingId, 
            price: price, 
            title: title, 
            description: description, 
            km: km, 
            year: year, 
            url: window.location.href 
        };
    } catch (e) { 
        return null; 
    }
}

// --- GRAFİK ---
function createPriceChart(history) {
    if (!history || history.length < 2) return ''; 
    const width = 240; const height = 50; const padding = 5;
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

// --- SÜRÜKLEME ÖZELLİĞİ ---
function makeDraggable(el) {
    const header = document.getElementById("sahibinden-asistan-header");
    let isDragging = false;
    let startX, startY, initialLeft, initialTop;
    if (!header) return;
    
    header.onmousedown = function(e) {
        if(e.target.id === "closeOverlayBtn" || e.target.id === "googleLoginBtn" || e.target.id === "logoutText" || e.target.tagName === "BUTTON") return; 
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

// --- ARAYÜZ OLUŞTURMA ---
function showOverlay(data, result) {
    const oldOverlay = document.getElementById('sahibinden-asistan-box');
    if (oldOverlay) oldOverlay.remove();

    const overlay = document.createElement('div');
    overlay.id = 'sahibinden-asistan-box';
    
    const isError = !result || result.status === "error";
    let chartHtml = isError ? "" : createPriceChart(result.history);
    const commentCount = result.comments ? result.comments.length : 0;

    // Header Sağ Kısım (Login Durumu)
    let headerRightHtml = "";
    if (userProfile) {
        headerRightHtml = `
            <div style="display:flex; align-items:center; gap:6px;">
                <img src="${userProfile.picture}" style="width:22px; height:22px; border-radius:50%; border:1px solid #fff;">
                <div style="display:flex; flex-direction:column; line-height:1;">
                    <span style="font-size:10px; font-weight:bold;">${userProfile.name.split(' ')[0]}</span>
                    <span id="logoutText" style="font-size:9px; text-decoration:underline; cursor:pointer; color:#444;">Çıkış</span>
                </div>
                <span id="closeOverlayBtn" style="cursor:pointer; font-size:18px; font-weight:bold; color:#333; margin-left:5px;">&times;</span>
            </div>
        `;
    } else {
        headerRightHtml = `
            <div style="display:flex; align-items:center; gap:5px;">
                <button id="googleLoginBtn" style="background:white; color:#333; border:none; padding:4px 8px; border-radius:4px; font-size:10px; cursor:pointer; font-weight:bold; display:flex; align-items:center; gap:3px;">
                    <span style="color:#4285F4; font-weight:900;">G</span> Giriş Yap
                </button>
                <span id="closeOverlayBtn" style="cursor:pointer; font-size:18px; font-weight:bold; color:#333; padding:0 4px;">&times;</span>
            </div>
        `;
    }

    // HTML İÇERİĞİ
    overlay.innerHTML = `
        <div id="sahibinden-asistan-header" style="background: #FFD000; color: #222; padding: 10px 15px; border-top-left-radius: 8px; border-top-right-radius: 8px; display: flex; justify-content: space-between; align-items: center; cursor: grab; user-select: none; box-shadow: 0 2px 5px rgba(0,0,0,0.1); z-index: 10;">
            <div style="font-weight: 900; font-size:14px; display:flex; align-items:center; gap:5px;">
                <span>🤖</span> BAI BİLMİŞ
            </div>
            ${headerRightHtml}
        </div>

        <div style="display:flex; background:#e9ecef; border-bottom:1px solid #ddd;">
            <button id="tabAnaliz" style="flex:1; padding:10px; border:none; background:#fff; font-weight:bold; color:#293542; cursor:pointer; font-size:12px; border-bottom: 2px solid #293542;">📊 Analiz</button>
            <button id="tabYorumlar" style="flex:1; padding:10px; border:none; background:#e9ecef; font-weight:bold; color:#666; cursor:pointer; font-size:12px; border-bottom: 2px solid transparent;">💬 Yorumlar (<span id="commentCountBadge">${commentCount}</span>)</button>
        </div>
        
        <div style="padding: 15px; background: #F2F4F6; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; color: #333; min-height: 300px;">
            <div id="viewAnaliz">
                <div style="text-align:center; margin-bottom:10px;">
                    <div style="font-size: 22px; font-weight: 800; color:#293542; letter-spacing:-0.5px;">${data.price.toLocaleString('tr-TR')} TL</div>
                    <div style="font-size:10px; color:#777;">Güncel İlan Fiyatı</div>
                </div>
                ${chartHtml}
                
                <button id="askAiBtn" style="width:100%; background: #293542; color: #FFD000; border: none; padding: 12px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: bold; margin-top: 15px; box-shadow: 0 3px 6px rgba(0,0,0,0.15);">
                    ✨ DETAYLI ANALİZ ET
                </button>
                
                <button id="telegramBtn" style="display:block; width:100%; background: #0088cc; color: white; border: none; padding: 10px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: bold; margin-top: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                    🔔 Fiyat Alarmını Aç (Telegram)
                </button>
                
                <div id="aiResult" style="display:none; font-size:12px; margin-top:15px; background: #fff; padding: 12px; border: 1px solid #ddd; border-radius: 6px; max-height: 250px; overflow-y: auto; line-height: 1.5;"></div>
            </div>

            <div id="viewYorumlar" style="display:none; height:100%;">
                <div id="commentList" style="height: 220px; overflow-y: auto; margin-bottom: 10px; word-break: break-word; background: #fff; border: 1px solid #e1e1e1; border-radius: 4px; padding: 5px; overscroll-behavior: contain;">
                    ${renderComments(result.comments || [])}
                </div>
                <div style="display:flex; gap:5px;">
                    <input id="commentInput" placeholder="Yorum ekle..." style="flex:1; border:1px solid #ccc; padding:8px; font-size:12px; border-radius:4px; outline:none;">
                    <button id="sendCommentBtn" style="background:#293542; color:white; border:none; padding:0 12px; border-radius:4px; cursor:pointer;">➤</button>
                </div>
            </div>
        </div>
    `;

    overlay.style.cssText = `position: fixed !important; top: 130px !important; right: 20px !important; width: 320px !important; background-color: transparent !important; border-radius: 8px !important; box-shadow: 0 15px 50px rgba(0,0,0,0.3) !important; z-index: 2147483647 !important; font-family: 'Open Sans', Helvetica, Arial, sans-serif !important; border: 1px solid #dcdcdc !important;`;
    
    document.body.appendChild(overlay);
    makeDraggable(overlay);

    // --- EVENT LISTENERLAR ---
    if(document.getElementById('googleLoginBtn')) document.getElementById('googleLoginBtn').onclick = loginWithGoogle;
    if(document.getElementById('logoutText')) document.getElementById('logoutText').onclick = logout;
    
    // BURASI ÖNEMLİ: Telegram butonuna tıklayınca akıllı fonksiyon çalışsın
    if(document.getElementById('telegramBtn')) document.getElementById('telegramBtn').onclick = handleTelegramClick;

    const tabAnaliz = document.getElementById('tabAnaliz');
    const tabYorumlar = document.getElementById('tabYorumlar');
    const viewAnaliz = document.getElementById('viewAnaliz');
    const viewYorumlar = document.getElementById('viewYorumlar');

    function switchTab(tabName) {
        if (tabName === 'analiz') {
            viewAnaliz.style.display = 'block'; viewYorumlar.style.display = 'none';
            tabAnaliz.style.background = '#fff'; tabAnaliz.style.color = '#293542'; tabAnaliz.style.borderBottom = '2px solid #293542';
            tabYorumlar.style.background = '#e9ecef'; tabYorumlar.style.color = '#666'; tabYorumlar.style.borderBottom = '2px solid transparent';
        } else {
            viewAnaliz.style.display = 'none'; viewYorumlar.style.display = 'block';
            tabYorumlar.style.background = '#fff'; tabYorumlar.style.color = '#293542'; tabYorumlar.style.borderBottom = '2px solid #293542';
            tabAnaliz.style.background = '#e9ecef'; tabAnaliz.style.color = '#666'; tabAnaliz.style.borderBottom = '2px solid transparent';
        }
    }
    tabAnaliz.onclick = () => switchTab('analiz');
    tabYorumlar.onclick = () => switchTab('yorumlar');
    document.getElementById('closeOverlayBtn').onclick = () => overlay.remove();

    document.getElementById('askAiBtn').onclick = async () => {
        const btn = document.getElementById('askAiBtn');
        const resultBox = document.getElementById('aiResult');
        btn.innerHTML = "⏳ Piyasa Araştırılıyor...";
        btn.disabled = true;
        btn.style.opacity = "0.7";
        try {
            const response = await fetch(`${API_URL}/analyze-ai`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
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
        } finally { btn.disabled = false; btn.style.opacity = "1"; }
    };

    setupCommentEvents(data);
}

function renderComments(comments) {
    if (!comments || comments.length === 0) return '<div style="font-size:11px; text-align:center; padding:20px; color:#999;">Henüz yorum yok.<br>İlk yorumu sen yaz!</div>';
    return comments.map(c => `
        <div style="border-bottom: 1px solid #eee; padding: 8px; margin-bottom: 4px; font-size: 11px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:3px; align-items:center;">
                <div style="display:flex; align-items:center; gap:4px;">
                    ${c.user_pic ? `<img src="${c.user_pic}" style="width:16px; height:16px; border-radius:50%;">` : ''}
                    <b style="color:#293542;">${c.user}</b>
                </div>
                <span style="color:#999; font-size:9px;">${c.date ? c.date.split(' ')[0] : ''}</span>
            </div>
            <span style="color:#555;">${c.text}</span>
            <div style="text-align:right; margin-top:2px;">
                <button class="like-btn" data-id="${c.id}" style="border:none; background:none; cursor:pointer; color:#e74c3c; font-size:10px;">❤️ ${c.liked_by?.length||0}</button>
            </div>
        </div>`).join('');
}

function setupCommentEvents(data) {
    document.getElementById('sendCommentBtn').onclick = async () => {
        const text = document.getElementById('commentInput').value;
        if (!text) return;
        // Kullanıcı kontrolü: Eğer giriş yapmamışsa yorum atamaz, uyarı ver
        if (!userProfile) {
            if(confirm("Yorum yapmak için giriş yapmalısınız. Giriş yapmak ister misiniz?")) {
                loginWithGoogle();
            }
            return;
        }

        const currentUserId = userProfile.id;
        const currentUserName = userProfile.name;
        try {
            const response = await fetch(`${API_URL}/add_comment`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ listing_id: data.id, user_id: currentUserId, username: currentUserName, text: text })
            });
            const json = await response.json();
            if (json.status === "success") {
                document.getElementById('commentList').innerHTML = renderComments(json.comments);
                document.getElementById('commentInput').value = "";
                document.getElementById('commentCountBadge').innerText = json.comments.length; 
            }
        } catch (err) {} 
    };

    document.getElementById('commentList').addEventListener('click', async (e) => {
        const btn = e.target.closest('.like-btn');
        if (btn) {
            if (!userProfile) { alert("Beğenmek için giriş yapmalısınız."); return; }
            const commentId = btn.getAttribute('data-id');
            const currentUserId = userProfile.id;
            try {
                const response = await fetch(`${API_URL}/like_comment`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ listing_id: data.id, comment_id: commentId, user_id: currentUserId })
                });
                const json = await response.json();
                if(json.status === "success") document.getElementById('commentList').innerHTML = renderComments(json.comments);
            } catch (err) {}
        }
    });
}

async function analyzeListing() {
    const data = getListingData();
    if (!data) return; 
    try {
        const response = await fetch(`${API_URL}/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        const result = await response.json();
        showOverlay(data, result);
    } catch (error) { 
        showOverlay(data, { status: "error" }); 
    }
}

setTimeout(analyzeListing, 1000);
