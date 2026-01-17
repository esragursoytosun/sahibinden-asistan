// content.js - BAI BİLMİŞ v2.5: AKILLI HATA YÖNETİMİ & HIZLI YORUM 🛡️⚡

const API_URL = "https://sahiden.onrender.com"; 

// --- VERSİYON ---
const CURRENT_VERSION = "2.5"; 
// ----------------

console.log(`BAI BILMIS: v${CURRENT_VERSION} Başlatıldı`); 

// --- KULLANICI YÖNETİMİ ---
// Profili her ihtiyaç duyulduğunda taze çeker, hata payını sıfırlar.
function getUser() {
    try {
        const stored = localStorage.getItem("sahibinden_user_profile");
        if (stored && stored !== "undefined" && stored !== "null") {
            return JSON.parse(stored);
        }
    } catch (e) {
        localStorage.removeItem("sahibinden_user_profile");
    }
    return null;
}

// Cihaz ID (Misafirler için)
let deviceId = localStorage.getItem("sahibinden_userid");
if (!deviceId) { 
    deviceId = "uid_" + Math.random().toString(36).substr(2, 9); 
    localStorage.setItem("sahibinden_userid", deviceId); 
}

// --- SÜPÜRGE MODU ---
async function runSweepMode() {
    if (document.querySelector('table#searchResultsTable')) {
        let rows = document.querySelectorAll('tr.searchResultsItem');
        let batchData = [];
        
        rows.forEach(row => {
            try {
                let id = row.getAttribute('data-id');
                let priceText = row.querySelector('.searchResultsPriceValue span')?.innerText;
                let title = row.querySelector('.searchResultsTitleValue a')?.innerText;
                let url = row.querySelector('.searchResultsTitleValue a')?.href;
                let attributes = row.querySelectorAll('.searchResultsAttributeValue');
                let year = attributes.length > 0 ? attributes[0].innerText.trim() : null;
                let km = attributes.length > 1 ? attributes[1].innerText.trim() : null;

                if (id && priceText) {
                    let price = parseInt(priceText.replace(/\D/g, ''));
                    batchData.push({ id, price, title: title || "Liste İlanı", url: url || "", year, km });
                }
            } catch (e) {}
        });

        if (batchData.length > 0) {
            try {
                await fetch(`${API_URL}/bulk-upload`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(batchData)
                });
            } catch (e) {}
        }
    }
}

// --- LOGİN İŞLEMLERİ ---
function loginWithGoogle() {
    const btn = document.getElementById('googleLoginBtn'); 
    if(btn) btn.innerText="⌛";
    
    // Yorum kısmındaki buton için
    const commentBtn = document.getElementById('loginForCommentBtn');
    if(commentBtn) commentBtn.innerText = "Giriş Yapılıyor...";

    chrome.runtime.sendMessage({ action: "login" }, (res) => {
        if (res && res.status === "success") {
            localStorage.setItem("sahibinden_user_profile", JSON.stringify(res.user));
            location.reload(); // Sayfayı yenile ki her şey otursun
        } else { 
            alert("Giriş başarısız."); 
            if(btn) btn.innerText="Giriş";
            if(commentBtn) commentBtn.innerText = "🔒 Yorum Yapmak İçin Giriş Yap";
        }
    });
}

function logout() { 
    if(confirm("Çıkış yapmak istiyor musunuz?")) { 
        localStorage.removeItem("sahibinden_user_profile"); 
        location.reload(); 
    } 
}

function handleTelegramClick() {
    const user = getUser();
    if (!user) { if(confirm("Bildirim almak için giriş yapmalısınız. Yapılsın mı?")) loginWithGoogle(); return; }
    window.open(`https://t.me/BAIBilmisBot?start=${user.id}`, '_blank');
}

// --- VERİ ÇEKME ---
function getListingData() {
    try {
        let price = parseInt((document.querySelector('.classifiedInfo h3')?.innerText || document.querySelector('div.price-info')?.innerText || "0").replace(/\D/g, ''));
        const id = document.getElementById('classifiedId')?.innerText.trim() || "Bilinmiyor";
        const title = document.querySelector('.classifiedDetailTitle h1')?.innerText.trim() || document.title;
        const desc = document.querySelector('#classifiedDescription')?.innerText || "";
        let km="Bilinmiyor", year="Bilinmiyor";
        document.querySelectorAll('.classifiedInfoList li').forEach(li => {
            const lbl=li.querySelector('strong')?.innerText, val=li.querySelector('span')?.innerText;
            if(lbl?.includes("KM")) km=val; if(lbl?.includes("Yıl")) year=val;
        });
        if (!price) return null;
        return { id, price, title, description: desc, km, year, url: window.location.href };
    } catch (e) { return null; }
}

// --- GÖRSEL BİLEŞENLER ---
function createValuationBar(val) {
    if (!val) return `<div style="font-size:11px; color:#999; text-align:center; margin-top:10px; background:#fff; padding:10px; border-radius:8px;">📉 <b>Yetersiz Güncel Veri</b><br>Son 30 günde yeterli benzer araç ilanı bulunamadı.</div>`;
    let percent = ((val.ratio - 0.7) / (1.3 - 0.7)) * 100;
    if(percent < 0) percent = 5; if(percent > 100) percent = 95;
    return `
        <div style="margin-top:15px; padding:12px; background:white; border-radius:8px; border:1px solid #e0e0e0; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span style="font-size:13px; font-weight:800; color:${val.color};">${val.status}</span>
                <div style="text-align:right;">
                    <div style="font-size:10px; color:#999;">Piyasa Ortalaması</div>
                    <div style="font-size:12px; font-weight:bold; color:#333;">${val.average_price.toLocaleString('tr-TR')} TL</div>
                </div>
            </div>
            <div style="width:100%; height:8px; background:#e0e0e0; border-radius:4px; position:relative; overflow:hidden;">
                <div style="position:absolute; left:0; width:33%; height:100%; background:#d4edda;"></div>
                <div style="position:absolute; left:33%; width:34%; height:100%; background:#fff3cd;"></div>
                <div style="position:absolute; left:67%; width:33%; height:100%; background:#f8d7da;"></div>
                <div style="position:absolute; left:${percent}%; top:0; width:4px; height:100%; background:#333; transform:scale(1.5); border:1px solid white; box-shadow:0 0 2px rgba(0,0,0,0.5);"></div>
            </div>
            <div style="display:flex; align-items:center; gap:5px; margin-top:8px; font-size:9px; color:#777;">
                <span>📅</span><span>${val.info_msg || "Son 30 gün analizi"}</span>
            </div>
        </div>
    `;
}

function createPriceChart(history) {
    if (!history || history.length < 2) return ''; 
    const w=240, h=50, pad=5;
    const prices=history.map(h=>h.price), min=Math.min(...prices), max=Math.max(...prices);
    if(min===max) return `<div style="text-align:center;font-size:10px;color:#666;padding:10px;">Fiyat Stabil ⎯⎯⎯</div>`;
    const pts = prices.map((p,i)=>`${(i/(prices.length-1))*(w-2*pad)+pad},${h-((p-min)/(max-min))*(h-2*pad)-pad}`).join(' ');
    return `<svg width="100%" height="${h}"><polyline fill="none" stroke="#293542" stroke-width="2" points="${pts}"/></svg>`;
}

function makeDraggable(el) {
    const h = document.getElementById("sahibinden-asistan-header");
    let isD=false, startX, startY, iL, iT;
    if(!h)return;
    h.onmousedown = (e) => {
        if(["BUTTON","IMG","SPAN"].includes(e.target.tagName) || e.target.id.includes("Btn")) return;
        e.preventDefault(); isD=true; startX=e.clientX; startY=e.clientY; iL=el.offsetLeft; iT=el.offsetTop;
        el.style.right="auto"; h.style.cursor="grabbing";
        document.onmousemove=(e)=>{if(!isD)return; el.style.left=(iL+e.clientX-startX)+"px"; el.style.top=(iT+e.clientY-startY)+"px";};
        document.onmouseup=()=>{isD=false; h.style.cursor="grab"; document.onmouseup=null; document.onmousemove=null;};
    };
}

function showOverlay(data, result) {
    const old = document.getElementById('sahibinden-asistan-box'); if(old) old.remove();
    const overlay = document.createElement('div'); overlay.id = 'sahibinden-asistan-box';
    
    // KULLANICIYI BURADA TAZE ÇEKİYORUZ
    const currentUser = getUser();
    
    let chartHtml = result?.status==="success" ? createPriceChart(result.history) : "";
    let valuationHtml = result?.status==="success" ? createValuationBar(result.valuation) : ""; 
    
    // HEADER (Üst Kısım)
    let headerRight = currentUser ? 
        `<div style="display:flex;align-items:center;gap:6px;"><img src="${currentUser.picture}" style="width:22px;height:22px;border-radius:50%;"><span style="font-size:10px;font-weight:bold;">${currentUser.name.split(' ')[0]}</span><span id="logoutText" style="font-size:9px;text-decoration:underline;cursor:pointer;">Çıkış</span><span id="closeOverlayBtn" style="cursor:pointer;font-size:18px;margin-left:5px;">&times;</span></div>` : 
        `<button id="googleLoginBtn" style="background:white;border:none;padding:4px 8px;border-radius:4px;font-size:10px;font-weight:bold;">G Giriş</button><span id="closeOverlayBtn" style="cursor:pointer;font-size:18px;margin-left:5px;">&times;</span>`;

    // YORUM ALANI (Giriş yaptıysa kutu, yapmadıysa buton)
    let commentInputHtml = "";
    if (currentUser) {
        commentInputHtml = `<div style="display:flex;gap:5px;"><input id="commentInput" placeholder="Yorum..." style="flex:1;padding:8px;border:1px solid #ddd;border-radius:4px;"><button id="sendCommentBtn" style="background:#293542;color:white;border:none;padding:0 12px;border-radius:4px;cursor:pointer;">➤</button></div>`;
    } else {
        commentInputHtml = `<button id="loginForCommentBtn" style="width:100%;background:#e74c3c;color:white;border:none;padding:10px;border-radius:4px;font-weight:bold;cursor:pointer;margin-top:5px;">🔒 Yorum Yapmak İçin Giriş Yap</button>`;
    }

    overlay.innerHTML = `
        <div id="sahibinden-asistan-header" style="background:#FFD000;color:#222;padding:10px 15px;border-top-left-radius:8px;border-top-right-radius:8px;display:flex;justify-content:space-between;align-items:center;cursor:grab;box-shadow:0 2px 5px rgba(0,0,0,0.1);">
            <div style="font-weight:900;font-size:14px;">🤖 BAI BİLMİŞ <span style="font-size:9px;opacity:0.7;">v${CURRENT_VERSION}</span></div>${headerRight}
        </div>
        <div style="display:flex;background:#e9ecef;border-bottom:1px solid #ddd;">
            <button id="tabAnaliz" style="flex:1;padding:10px;border:none;background:#fff;font-weight:bold;color:#293542;border-bottom:2px solid #293542;">📊 Analiz</button>
            <button id="tabYorumlar" style="flex:1;padding:10px;border:none;background:#e9ecef;font-weight:bold;color:#666;">💬 Yorumlar (${result?.comments?.length||0})</button>
        </div>
        <div style="padding:15px;background:#F2F4F6;border-bottom-left-radius:8px;border-bottom-right-radius:8px;min-height:300px;">
            <div id="viewAnaliz">
                <div style="text-align:center;">
                    <div style="font-size:22px;font-weight:800;color:#293542;">${data.price.toLocaleString('tr-TR')} TL</div>
                    <button id="telegramBtn" style="width:100%;background:#0088cc;color:white;border:none;padding:8px;border-radius:6px;font-weight:bold;margin:10px 0;">🔔 Fiyat Alarmı (Telegram)</button>
                </div>
                ${valuationHtml} 
                ${chartHtml}
                <button id="askAiBtn" style="width:100%;background:#293542;color:#FFD000;border:none;padding:12px;border-radius:6px;font-weight:bold;margin-top:15px;">✨ DETAYLI AI ANALİZ</button>
                <div id="aiResult" style="display:none;font-size:12px;margin-top:15px;background:#fff;padding:12px;border:1px solid #ddd;border-radius:6px;max-height:250px;overflow-y:auto;"></div>
            </div>
            <div id="viewYorumlar" style="display:none;">
                <div id="commentList" style="height:220px;overflow-y:auto;margin-bottom:10px;background:#fff;padding:5px;">${renderComments(result?.comments)}</div>
                ${commentInputHtml}
            </div>
        </div>
    `;
    overlay.style.cssText = `position:fixed;top:130px;right:20px;width:320px;background:transparent;border-radius:8px;box-shadow:0 15px 50px rgba(0,0,0,0.3);z-index:2147483647;font-family:'Open Sans',sans-serif;border:1px solid #dcdcdc;`;
    document.body.appendChild(overlay); makeDraggable(overlay);

    // Event Listeners
    if(document.getElementById('googleLoginBtn')) document.getElementById('googleLoginBtn').onclick=loginWithGoogle;
    if(document.getElementById('logoutText')) document.getElementById('logoutText').onclick=logout;
    if(document.getElementById('telegramBtn')) document.getElementById('telegramBtn').onclick=handleTelegramClick;
    if(document.getElementById('loginForCommentBtn')) document.getElementById('loginForCommentBtn').onclick=loginWithGoogle;
    
    document.getElementById('closeOverlayBtn').onclick=()=>overlay.remove();
    const tA=document.getElementById('tabAnaliz'), tY=document.getElementById('tabYorumlar'), vA=document.getElementById('viewAnaliz'), vY=document.getElementById('viewYorumlar');
    tA.onclick=()=>{vA.style.display='block';vY.style.display='none';tA.style.background='#fff';tA.style.borderBottom='2px solid #293542';tY.style.background='#e9ecef';tY.style.borderBottom='none';};
    tY.onclick=()=>{vA.style.display='none';vY.style.display='block';tY.style.background='#fff';tY.style.borderBottom='2px solid #293542';tA.style.background='#e9ecef';tA.style.borderBottom='none';};

    // --- AI BUTONU (DÜZELTİLDİ: Sadece Login Gerekliyse Butonu Değiştirir) ---
    document.getElementById('askAiBtn').onclick = async () => {
        const btn=document.getElementById('askAiBtn'), resBox=document.getElementById('aiResult');
        const userNow = getUser(); // Güncel kullanıcıyı al
        btn.innerHTML="⏳..."; btn.disabled=true;
        
        try {
            const payload = { ...data, user_id: userNow ? userNow.id : null };
            const r=await fetch(`${API_URL}/analyze-ai`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
            const j=await r.json(); 
            
            resBox.style.display="block"; 
            if (j.status === "limit_reached") {
                btn.innerHTML = "🔒 Limit Doldu";
                resBox.innerHTML = `
                    <div style="text-align:center; padding:15px; background:#fff5f5; border:1px solid #ffcccc; border-radius:8px;">
                        <div style="font-size:32px; margin-bottom:10px;">🛑</div>
                        <div style="font-weight:bold; color:#c0392b; margin-bottom:5px;">Günlük Limit Doldu</div>
                        <p style="font-size:11px; color:#555; margin-bottom:10px;">${j.message}</p>
                        <a href="https://shopier.com/SENIN_LINKIN" target="_blank" style="display:block; background:#27ae60; color:white; padding:10px; border-radius:5px; text-decoration:none; font-weight:bold; font-size:12px;">👑 Premium'a Geç (Sınırsız)</a>
                    </div>`;
            } else if (j.status === "login_required") { // Sadece bu kod gelirse giriş iste
                 btn.innerHTML = "🔒 Giriş Yapın";
                 resBox.innerHTML = `<div style="text-align:center;padding:10px;">${j.message}<br><button onclick="loginWithGoogle()" style="margin-top:10px;background:#293542;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;">Giriş Yap</button></div>`;
            } else if (j.status === "success") {
                resBox.innerHTML=j.ai_response; 
                btn.innerHTML="✅ Bitti";
            } else {
                // Diğer tüm hatalarda (404, 500 vb.) hata mesajını göster ama butonu "Giriş Yap" yapma
                resBox.innerHTML = `<span style="color:red">⚠️ Sistem Hatası:</span> ${j.message}`;
                btn.innerHTML = "❌ Hata";
                btn.disabled = false;
            }
        } catch(e){
            resBox.innerHTML="Sunucu hatası veya internet yok."; 
            btn.innerHTML = "❌ Hata";
            btn.disabled=false;
        }
    };
    
    // --- YORUM GÖNDERME (ANLIK & SESSİZ) ---
    if(document.getElementById('sendCommentBtn')) {
        document.getElementById('sendCommentBtn').onclick=async()=>{
            const txt=document.getElementById('commentInput').value; if(!txt)return;
            const userNow = getUser();
            
            // 1. ANINDA LİSTEYE EKLE
            const list = document.getElementById('commentList');
            if (list.innerHTML.includes("Yorum yok")) list.innerHTML = "";
            const newCommentHtml = `<div style="border-bottom:1px solid #eee;padding:5px;font-size:11px;"><b>${userNow.name}</b>: ${txt}</div>`;
            list.insertAdjacentHTML('beforeend', newCommentHtml);
            list.scrollTop = list.scrollHeight; 
            
            // 2. SAYAÇ GÜNCELLE
            const tabBtn = document.getElementById('tabYorumlar');
            let currentCount = parseInt(tabBtn.innerText.match(/\d+/)[0] || 0);
            tabBtn.innerText = `💬 Yorumlar (${currentCount + 1})`;

            // 3. BUTON TEPKİSİ
            const btn = document.getElementById('sendCommentBtn');
            const originalText = btn.innerText;
            btn.innerText = "✓";
            document.getElementById('commentInput').value = ""; 

            // 4. SUNUCUYA GÖNDER
            try {
                await fetch(`${API_URL}/add_comment`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({listing_id:data.id,user_id:userNow.id,username:userNow.name,text:txt})});
                setTimeout(() => btn.innerText = originalText, 1000);
            } catch (e) {
                btn.innerText = "❌";
            }
        };
    }
}

function renderComments(c) {
    if(!c||!c.length) return '<div style="text-align:center;color:#999;padding:20px;">Yorum yok.</div>';
    return c.map(x=>`<div style="border-bottom:1px solid #eee;padding:5px;font-size:11px;"><b>${x.user}</b>: ${x.text}</div>`).join('');
}

// --- GİZLİ AJAN & BAŞLATICI ---
async function runBackgroundWorker() {
    try {
        const response = await fetch(`${API_URL}/get-update-task`);
        const task = await response.json();
        if (task.status === "task_found" && task.url) {
            const htmlResponse = await fetch(task.url);
            const htmlText = await htmlResponse.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(htmlText, "text/html");
            let priceText = doc.querySelector('.classifiedInfo h3')?.innerText || doc.querySelector('div.price-info')?.innerText;
            if (priceText) {
                let price = parseInt(priceText.replace(/\D/g, ''));
                await fetch(`${API_URL}/update-price-background`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: task.id, price: price }) });
            }
        }
    } catch (e) {}
}

async function init() {
    // await checkUpdate(); // Kapalı
    await runSweepMode(); 
    
    const data = getListingData();
    if(data) {
        try {
            const res = await fetch(`${API_URL}/analyze`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
            showOverlay(data, await res.json());
        } catch(e) { showOverlay(data, {status:"error"}); }
    }
}

setTimeout(init, 1000);
setTimeout(runBackgroundWorker, 5000);
