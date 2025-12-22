// content.js - KESİN ÇÖZÜM (Event Delegation) 🛠️

// 1. KİMLİK AYARLARI
// Gizli ID (Beğeni takibi için)
let userId = localStorage.getItem("sahibinden_userid");
if (!userId) {
    userId = "uid_" + Math.random().toString(36).substr(2, 9);
    localStorage.setItem("sahibinden_userid", userId);
}
// Görünen İsim
let currentUser = localStorage.getItem("sahibinden_user") || "Misafir";

// 2. VERİ ÇEKME
function getListingData() {
    try {
        let priceText = document.querySelector('.classifiedInfo h3')?.innerText || 
                        document.querySelector('div.price-info')?.innerText;
        let price = priceText ? parseInt(priceText.replace(/\D/g, '')) : 0;
        const idElement = document.getElementById('classifiedId');
        const listingId = idElement ? idElement.innerText.trim() : "Bilinmiyor";
        const titleElement = document.querySelector('.classifiedDetailTitle h1');
        const title = titleElement ? titleElement.innerText.trim() : document.title;
        return { id: listingId, price: price, title: title, url: window.location.href };
    } catch (e) { return null; }
}

// 3. HTML OLUŞTURMA
function renderComments(comments) {
    if (!comments || comments.length === 0) {
        return '<div style="color:#999; font-size:12px; text-align:center; padding:15px;">Henüz ses yok. İlk yorumu sen yaz! 🎤</div>';
    }
    
    return comments.map(c => {
        // Beğeni Sayısı
        let likeCount = Array.isArray(c.liked_by) ? c.liked_by.length : (c.likes || 0);
        // Ben beğendim mi?
        let isLikedByMe = Array.isArray(c.liked_by) && c.liked_by.includes(userId);
        
        // Kalp Rengi: Beğendiysem Kırmızı, Yoksa Gri/Boş
        let heartIcon = isLikedByMe ? "❤️" : "🤍";
        let btnStyle = isLikedByMe ? "color:#e74c3c; font-weight:bold;" : "color:#555;";

        return `
        <div style="background:white; padding:10px; margin-bottom:8px; border-radius:8px; border:1px solid #eee;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:bold; color:#333; font-size:13px;">👤 ${c.user}</span>
                <span style="color:#aaa; font-size:10px;">${c.date}</span>
            </div>
            <div style="color:#555; font-size:13px; margin-top:4px;">${c.text}</div>
            
            <div style="margin-top:8px; display:flex; justify-content:flex-end;">
                <button class="like-btn" data-id="${c.id}" style="background:none; border:none; cursor:pointer; font-size:14px; display:flex; align-items:center; transition: transform 0.2s; ${btnStyle}">
                    ${heartIcon} <span style="margin-left:4px;">${likeCount}</span>
                </button>
            </div>
        </div>
    `}).join('');
}

// 4. ARAYÜZ VE OLAYLAR
function showOverlay(data, result) {
    const oldOverlay = document.getElementById('sahibinden-asistan-box');
    if (oldOverlay) oldOverlay.remove();

    const overlay = document.createElement('div');
    overlay.id = 'sahibinden-asistan-box';
    
    let boxColor = result.is_price_drop ? "#27ae60" : "#2c3e50"; 
    let statusText = result.is_price_drop ? `🔥 %${result.change_percentage} İndirim!` : "Fiyat Takipte";
    let commentCount = result.comments ? result.comments.length : 0;

    overlay.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; border-bottom:1px solid rgba(255,255,255,0.2); padding-bottom:8px; margin-bottom:8px;">
            <span style="font-weight: bold; font-size:14px;">🕵️‍♂️ Asistan</span>
            <input type="text" id="usernameInput" value="${currentUser}" 
                style="width:80px; background:rgba(255,255,255,0.2); border:none; color:white; padding:2px 5px; border-radius:4px; font-size:11px; text-align:center;">
        </div>

        <div style="text-align:center; margin-bottom:10px;">
            <div style="font-size: 18px; font-weight: bold;">${data.price.toLocaleString('tr-TR')} TL</div>
            <div style="font-size: 11px; opacity: 0.8; background:rgba(0,0,0,0.2); display:inline-block; padding:2px 6px; border-radius:4px; margin-top:2px;">${statusText}</div>
        </div>

        <button id="toggleCommentsBtn" style="width:100%; background:white; color:#333; border:none; padding:8px; border-radius:6px; cursor:pointer; font-size:12px; font-weight:bold;">
            💬 Yorumlar (${commentCount})
        </button>

        <div id="commentSection" style="display:none; margin-top:10px; background:#f8f9fa; border-radius:8px; padding:10px; color:#333;">
            <div id="commentList" style="max-height:200px; overflow-y:auto; margin-bottom:10px;">
                ${renderComments(result.comments)}
            </div>
            <div style="display:flex; gap:5px;">
                <input id="commentInput" placeholder="Yorum yaz..." style="flex:1; border:1px solid #ddd; padding:8px; border-radius:4px; font-size:12px;">
                <button id="sendCommentBtn" style="background:#3498db; color:white; border:none; padding:0 10px; border-radius:4px; cursor:pointer;">➤</button>
            </div>
        </div>
    `;

    Object.assign(overlay.style, {
        position: 'fixed', top: '150px', right: '20px', width: '260px',
        backgroundColor: boxColor, color: 'white', padding: '15px',
        borderRadius: '12px', boxShadow: '0 10px 30px rgba(0,0,0,0.4)',
        zIndex: '999999', fontFamily: "'Segoe UI', sans-serif"
    });

    document.body.appendChild(overlay);

    // --- OLAY YAKALAMA (DELEGATION) ---
    // En önemli kısım burası: Tıklamaları "Listeden" dinliyoruz
    const commentList = document.getElementById('commentList');
    
    commentList.addEventListener('click', async (e) => {
        // Tıklanan şey bir "like-btn" veya onun içindeki kalp/sayı mı?
        const btn = e.target.closest('.like-btn');
        
        if (btn) {
            // Evet, bir beğeni butonuna tıklandı!
            const commentId = btn.getAttribute('data-id');
            
            // Görsel geri bildirim (Anında tepki)
            btn.style.transform = "scale(1.2)";
            setTimeout(() => btn.style.transform = "scale(1)", 200);

            try {
                const response = await fetch('http://localhost:8000/like_comment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        listing_id: data.id, 
                        comment_id: commentId,
                        user_id: userId 
                    })
                });
                const json = await response.json();
                if(json.status === "success") {
                    // Listeyi güncelle (Renk ve sayı değişsin)
                    commentList.innerHTML = renderComments(json.comments);
                }
            } catch (err) { console.error(err); }
        }
    });

    // Diğer Butonlar
    document.getElementById('usernameInput').onchange = (e) => {
        currentUser = e.target.value;
        localStorage.setItem("sahibinden_user", currentUser);
    };

    document.getElementById('toggleCommentsBtn').onclick = () => {
        const section = document.getElementById('commentSection');
        section.style.display = section.style.display === 'none' ? 'block' : 'none';
    };

    document.getElementById('sendCommentBtn').onclick = async () => {
        const text = document.getElementById('commentInput').value;
        if (!text) return;
        
        try {
            const response = await fetch('http://localhost:8000/add_comment', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
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
    if (!data || data.price === 0) return;
    try {
        const response = await fetch('http://localhost:8000/analyze', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        const result = await response.json();
        showOverlay(data, result);
    } catch (error) {}
}

setTimeout(analyzeListing, 1000);