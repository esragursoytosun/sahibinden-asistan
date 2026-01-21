// content.js - BAI BİLMİŞ v4.0: ZORUNLU GİRİŞ & PREMİUM ÖZELLİKLER 🚀⭐

const API_URL = "https://sahiden.onrender.com";

const CURRENT_VERSION = "4.0";
console.log(`BAI BILMIS: v${CURRENT_VERSION} Başlatıldı`);

function getUser() {
    try {
        const stored = localStorage.getItem("sahibinden_user_profile");
        if (stored && stored !== "undefined" && stored !== "null") return JSON.parse(stored);
    } catch (e) { localStorage.removeItem("sahibinden_user_profile"); }
    return null;
}

let userId = localStorage.getItem("sahibinden_userid");
if (!userId) { userId = "uid_" + Math.random().toString(36).substr(2, 9); localStorage.setItem("sahibinden_userid", userId); }

// 🟢 1. KATEGORİ YOLUNU OKUMA (Breadcrumb)
// HTML yapısı: <ul> <li class="bc-item"> <a ...> <span>Renault</span> </a> </li> ... </ul>
function getCategoryPath() {
    try {
        // Senin gönderdiğin HTML'deki yapıya birebir uygun seçici:
        const items = document.querySelectorAll('li.bc-item > a > span');

        if (items.length > 0) {
            // Span içindeki metinleri alıp ">" ile birleştiriyoruz
            const path = Array.from(items)
                .map(item => item.innerText.trim())
                .filter(text => text.length > 0) // Boşlukları temizle
                .join(' > ');

            console.log("BAI BILMIS: Algılanan Kategori ->", path);
            return path;
        }
    } catch (e) { console.error("Kategori okuma hatası:", e); }
    return null;
}

// 🟢 2. HIZLI TARAMA MODU (Liste Sayfası - Genişletilmiş)
async function runSweepMode() {
    const searchTable = document.querySelector('table#searchResultsTable');

    if (searchTable) {
        // 1. Sayfanın genel kategorisini TEPEDEN al
        const pageCategory = getCategoryPath();
        const listingType = detectListingType(pageCategory);

        let rows = document.querySelectorAll('tr.searchResultsItem');
        let batchData = [];

        rows.forEach(row => {
            try {
                let id = row.getAttribute('data-id');
                let priceText = row.querySelector('.searchResultsPriceValue span')?.innerText;

                let titleElement = row.querySelector('.searchResultsTitleValue a');
                let title = titleElement?.innerText || "Liste İlanı";
                let url = titleElement?.href || "";

                // --- SÜTUN AYRIŞTIRMA ---
                let attributes = row.querySelectorAll('.searchResultsAttributeValue');
                let year = null, km = null, roomCount = null, areaM2 = null;

                // Araç kategorisi için
                if (listingType === "araba" && attributes.length >= 2) {
                    year = attributes[0].innerText.trim();
                    km = attributes[1].innerText.trim();
                }

                // Emlak kategorisi için
                if (listingType.includes("konut") && attributes.length >= 2) {
                    roomCount = attributes[0].innerText.trim();  // Oda sayısı
                    areaM2 = attributes[1].innerText.trim();     // m²
                }

                if (id && priceText) {
                    let price = parseInt(priceText.replace(/\D/g, ''));
                    if (price > 0) {
                        batchData.push({
                            id,
                            price,
                            title,
                            url,
                            year,
                            km,
                            category_path: pageCategory,
                            listing_type: listingType,
                            room_count: roomCount,
                            area_m2: areaM2
                        });
                    }
                }
            } catch (e) { }
        });

        // Toplanan verileri backend'e gönder
        if (batchData.length > 0) {
            try {
                await fetch(`${API_URL}/bulk-upload`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(batchData)
                });
                console.log(`BAI BILMIS: ${batchData.length} ilan (${listingType}) başarıyla işlendi.`);
            } catch (e) { }
        }
    }
}

// 🟢 3. TEKİL İLAN VERİSİ (GENİŞLETİLMİŞ)
function getListingData() {
    try {
        let priceElem = document.querySelector('.classifiedInfo h3') || document.querySelector('div.price-info');
        if (!priceElem) return null;
        let price = parseInt(priceElem.innerText.replace(/\D/g, ''));

        const id = document.getElementById('classifiedId')?.innerText.trim() || "Bilinmiyor";
        const title = document.querySelector('.classifiedDetailTitle h1')?.innerText.trim() || document.title;
        const desc = document.querySelector('#classifiedDescription')?.innerText || "";

        // Detay sayfasında da aynı kategori yolunu alıyoruz
        const categoryPath = getCategoryPath();

        // 🟢 KATEGORİ TİPİNİ ALGILAMA 🟢
        const listingType = detectListingType(categoryPath);

        // 🟢 ORTAK BİLGİLER 🟢
        let km = "Bilinmiyor", year = "Bilinmiyor", transmission = "Bilinmiyor";
        let roomCount = "Bilinmiyor", areaM2 = "Bilinmiyor", buildingAge = "Bilinmiyor";
        let location = "";

        // Tüm bilgi listelerini tara
        document.querySelectorAll('.classifiedInfoList li').forEach(li => {
            const lbl = li.querySelector('strong')?.innerText?.toLowerCase() || "";
            const val = li.querySelector('span')?.innerText?.trim() || "";

            // Araç bilgileri
            if (lbl.includes("km")) km = val;
            if (lbl.includes("yıl") || lbl.includes("model yılı")) year = val;
            if (lbl.includes("vites")) transmission = val;

            // Emlak bilgileri
            if (lbl.includes("oda sayısı") || lbl.includes("oda")) roomCount = val;
            if (lbl.includes("m²") || lbl.includes("brüt") || lbl.includes("net m")) areaM2 = val;
            if (lbl.includes("bina yaşı") || lbl.includes("yaş")) buildingAge = val;
        });

        // 🟢 LOKASYON BİLGİSİ 🟢
        // Sahibinden'de lokasyon genelde breadcrumb veya info bölümünde
        try {
            // Lokasyon bilgisini al (İl > İlçe > Mahalle formatında)
            const locationEl = document.querySelector('.classifiedInfo h2') ||
                document.querySelector('[class*="location"]') ||
                document.querySelector('.classifiedInfoList li:last-child span');
            if (locationEl) {
                location = locationEl.innerText.trim();
            }

            // Alternatif: Breadcrumb'dan lokasyon
            if (!location || location.length < 3) {
                const bcItems = document.querySelectorAll('li.bc-item > a > span');
                const allItems = Array.from(bcItems).map(s => s.innerText.trim());
                // Son 2-3 eleman genelde lokasyon (İstanbul > Kadıköy gibi)
                const locationParts = allItems.slice(-3).filter(t =>
                    !t.includes("Satılık") && !t.includes("Kiralık") &&
                    !t.includes("Konut") && !t.includes("Vasıta") && t.length > 2
                );
                if (locationParts.length > 0) {
                    location = locationParts.join(" > ");
                }
            }
        } catch (e) { console.log("Lokasyon okuma hatası:", e); }

        return {
            id,
            price,
            title,
            description: desc,
            km,
            year,
            url: window.location.href,
            category_path: categoryPath,
            // Yeni alanlar
            transmission,
            listing_type: listingType,
            location,
            room_count: roomCount,
            area_m2: areaM2,
            building_age: buildingAge
        };
    } catch (e) { return null; }
}

// 🟢 4. KATEGORİ TİPİ ALGILAMA 🟢
function detectListingType(categoryPath) {
    if (!categoryPath) return "araba";

    const path = categoryPath.toLowerCase();

    if (path.includes("konut") || path.includes("daire") || path.includes("ev") || path.includes("residence")) {
        if (path.includes("kiralık")) return "konut_kiralik";
        if (path.includes("satılık")) return "konut_satilik";
        return "konut_satilik";
    }

    if (path.includes("işyeri") || path.includes("ofis") || path.includes("dükkan")) {
        if (path.includes("kiralık")) return "isyeri_kiralik";
        return "isyeri_satilik";
    }

    if (path.includes("arsa") || path.includes("tarla") || path.includes("arazi")) {
        return "arsa";
    }

    return "araba";
}

// --- STANDART FONKSİYONLAR (Arayüz vb.) ---

function loginWithGoogle() {
    const btn = document.getElementById('googleLoginBtn'); if (btn) btn.innerText = "⌛";
    chrome.runtime.sendMessage({ action: "login" }, (res) => {
        if (res && res.status === "success") {
            localStorage.setItem("sahibinden_user_profile", JSON.stringify(res.user));
            location.reload();
        } else { alert("Giriş başarısız."); if (btn) btn.innerText = "Giriş"; }
    });
}
function logout() { if (confirm("Çıkış?")) { localStorage.removeItem("sahibinden_user_profile"); location.reload(); } }

function handleTelegramClick() {
    const user = getUser();
    if (!user) { if (confirm("Giriş yapmalısın. Yapılsın mı?")) loginWithGoogle(); return; }
    window.open(`https://t.me/BAIBilmisBot?start=${user.id}`, '_blank');
}

function createValuationBar(val) {
    if (!val) return `<div style="font-size:11px; color:#999; text-align:center; margin-top:10px; background:#fff; padding:10px; border-radius:8px;">📉 <b>Yetersiz Veri</b><br>Bu kategoride yeterli veri yok. Listelerde gezerek sistemi eğitebilirsin.</div>`;
    let percent = ((val.ratio - 0.7) / (1.3 - 0.7)) * 100;
    if (percent < 0) percent = 5; if (percent > 100) percent = 95;
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
                <span>📊</span><span>${val.info_msg}</span>
            </div>
        </div>
    `;
}

function createPriceChart(history) {
    if (!history || history.length < 2) return '';
    const w = 240, h = 50, pad = 5;
    const prices = history.map(h => h.price), min = Math.min(...prices), max = Math.max(...prices);
    if (min === max) return `<div style="text-align:center;font-size:10px;color:#666;padding:10px;">Fiyat Stabil ⎯⎯⎯</div>`;
    const pts = prices.map((p, i) => `${(i / (prices.length - 1)) * (w - 2 * pad) + pad},${h - ((p - min) / (max - min)) * (h - 2 * pad) - pad}`).join(' ');
    return `<svg width="100%" height="${h}"><polyline fill="none" stroke="#293542" stroke-width="2" points="${pts}"/></svg>`;
}

function makeDraggable(el) {
    const h = document.getElementById("sahibinden-asistan-header");
    let isD = false, startX, startY, iL, iT;
    if (!h) return;
    h.onmousedown = (e) => {
        if (["BUTTON", "IMG", "SPAN"].includes(e.target.tagName) || e.target.id.includes("Btn")) return;
        e.preventDefault(); isD = true; startX = e.clientX; startY = e.clientY; iL = el.offsetLeft; iT = el.offsetTop;
        el.style.right = "auto"; h.style.cursor = "grabbing";
        document.onmousemove = (e) => { if (!isD) return; el.style.left = (iL + e.clientX - startX) + "px"; el.style.top = (iT + e.clientY - startY) + "px"; };
        document.onmouseup = () => { isD = false; h.style.cursor = "grab"; document.onmouseup = null; document.onmousemove = null; };
    };
}

function showOverlay(data, result) {
    const old = document.getElementById('sahibinden-asistan-box'); if (old) old.remove();
    const overlay = document.createElement('div'); overlay.id = 'sahibinden-asistan-box';
    const currentUser = getUser();

    // 🔐 GİRİŞ YAPILMAMIŞSA - HOŞGELDİN EKRANI
    if (!currentUser) {
        overlay.innerHTML = `
            <div style="background:linear-gradient(135deg, #293542 0%, #1a2530 100%);border-radius:12px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.4);">
                <div style="padding:25px;text-align:center;">
                    <div style="font-size:48px;margin-bottom:15px;">🤖</div>
                    <div style="font-size:20px;font-weight:900;color:#FFD000;margin-bottom:5px;">BAI BİLMİŞ</div>
                    <div style="font-size:11px;color:#aaa;margin-bottom:20px;">Akıllı İlan Asistanı v${CURRENT_VERSION}</div>
                    
                    <div style="background:rgba(255,255,255,0.1);border-radius:8px;padding:15px;margin-bottom:20px;">
                        <div style="font-size:24px;font-weight:800;color:#fff;">${data.price.toLocaleString('tr-TR')} TL</div>
                        <div style="font-size:11px;color:#ccc;margin-top:5px;">${data.title?.substring(0, 40) || 'İlan'}...</div>
                    </div>
                    
                    <div style="color:#FFD000;font-size:13px;margin-bottom:20px;">
                        ✨ AI Analiz &nbsp;•&nbsp; 📊 Fiyat Karşılaştırma &nbsp;•&nbsp; 🔔 Alarm
                    </div>
                    
                    <button id="googleLoginBtn" style="width:100%;background:#fff;color:#333;border:none;padding:14px 20px;border-radius:8px;font-size:14px;font-weight:bold;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:10px;transition:all 0.2s;">
                        <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
                        Google ile Giriş Yap
                    </button>
                    
                    <div style="font-size:10px;color:#666;margin-top:15px;">
                        🔒 Tek tıkla güvenli giriş • Ücretsiz üyelik
                    </div>
                </div>
                <div style="background:#FFD000;padding:10px;text-align:center;">
                    <span style="font-size:11px;color:#293542;font-weight:bold;">🎁 Günlük 5 Ücretsiz AI Analiz!</span>
                </div>
            </div>
        `;
        overlay.style.cssText = `position:fixed;top:130px;right:20px;width:340px;z-index:2147483647;font-family:'Open Sans',sans-serif;`;
        document.body.appendChild(overlay);
        document.getElementById('googleLoginBtn').onclick = loginWithGoogle;
        makeDraggable(overlay);
        return;
    }

    // 🎯 GİRİŞ YAPILMIŞSA - TAM PANEL
    let chartHtml = result?.status === "success" ? createPriceChart(result.history) : "";
    let valuationHtml = result?.status === "success" ? createValuationBar(result.valuation) : "";

    // Premium rozet kontrolü
    const isPremium = currentUser.plan === "premium";
    const premiumBadge = isPremium ? `<span style="background:linear-gradient(135deg,#FFD700,#FFA500);color:#000;font-size:8px;padding:2px 6px;border-radius:10px;margin-left:5px;font-weight:bold;">⭐ PRO</span>` : '';

    let headerRight = `
        <div style="display:flex;align-items:center;gap:6px;">
            <img src="${currentUser.picture}" style="width:24px;height:24px;border-radius:50%;border:2px solid ${isPremium ? '#FFD700' : '#fff'};">
            <span style="font-size:10px;font-weight:bold;">${currentUser.name.split(' ')[0]}</span>${premiumBadge}
            <span id="logoutText" style="font-size:9px;text-decoration:underline;cursor:pointer;opacity:0.7;">Çıkış</span>
            <span id="closeOverlayBtn" style="cursor:pointer;font-size:18px;margin-left:5px;">&times;</span>
        </div>`;

    // Yorum input (artık hep göster, kullanıcı giriş yapmış)
    let commentInputHtml = `<div style="display:flex;gap:5px;"><input id="commentInput" placeholder="Yorum yaz..." style="flex:1;padding:8px;border:1px solid #ddd;border-radius:4px;"><button id="sendCommentBtn" style="background:#293542;color:white;border:none;padding:0 12px;border-radius:4px;cursor:pointer;">➤</button></div>`;

    overlay.innerHTML = `
        <div id="sahibinden-asistan-header" style="background:${isPremium ? 'linear-gradient(135deg,#FFD700 0%,#FFA500 100%)' : '#FFD000'};color:#222;padding:10px 15px;border-top-left-radius:10px;border-top-right-radius:10px;display:flex;justify-content:space-between;align-items:center;cursor:grab;box-shadow:0 2px 5px rgba(0,0,0,0.1);">
            <div style="font-weight:900;font-size:14px;">🤖 BAI BİLMİŞ <span style="font-size:9px;opacity:0.7;">v${CURRENT_VERSION}</span></div>${headerRight}
        </div>
        <div style="display:flex;background:#e9ecef;border-bottom:1px solid #ddd;">
            <button id="tabAnaliz" class="bai-tab active" style="flex:1;padding:10px;border:none;background:#fff;font-weight:bold;color:#293542;border-bottom:2px solid #293542;font-size:12px;">📊 Analiz</button>
            <button id="tabYorumlar" class="bai-tab" style="flex:1;padding:10px;border:none;background:#e9ecef;font-weight:bold;color:#666;font-size:12px;">💬 Yorumlar (${result?.comments?.length || 0})</button>
            <button id="tabProfil" class="bai-tab" style="flex:1;padding:10px;border:none;background:#e9ecef;font-weight:bold;color:#666;font-size:12px;">👤 Profil</button>
        </div>
        <div style="padding:15px;background:#F2F4F6;border-bottom-left-radius:10px;border-bottom-right-radius:10px;min-height:320px;">
            <div id="viewAnaliz">
                <div style="text-align:center;">
                    <div style="font-size:24px;font-weight:800;color:#293542;">${data.price.toLocaleString('tr-TR')} TL</div>
                    <button id="telegramBtn" style="width:100%;background:#0088cc;color:white;border:none;padding:10px;border-radius:6px;font-weight:bold;margin:12px 0;font-size:12px;">🔔 Fiyat Alarmı Kur (Telegram)</button>
                </div>
                ${valuationHtml} 
                ${chartHtml}
                <button id="askAiBtn" style="width:100%;background:linear-gradient(135deg,#293542,#1a2530);color:#FFD000;border:none;padding:14px;border-radius:8px;font-weight:bold;margin-top:15px;font-size:13px;cursor:pointer;">✨ DETAYLI AI ANALİZ</button>
                <div id="aiResult" style="display:none;font-size:13px;margin-top:15px;background:#fff;padding:15px;border:1px solid #ddd;border-radius:8px;max-height:400px;overflow-y:auto;line-height:1.6;color:#333;box-shadow:inset 0 2px 4px rgba(0,0,0,0.05);"></div>
            </div>
            <div id="viewYorumlar" style="display:none;">
                <div id="commentList" style="height:220px;overflow-y:auto;margin-bottom:10px;background:#fff;padding:8px;border-radius:6px;">${renderComments(result?.comments)}</div>
                ${commentInputHtml}
            </div>
            <div id="viewProfil" style="display:none;">
                <div style="text-align:center;padding:10px;">
                    <img src="${currentUser.picture}" style="width:60px;height:60px;border-radius:50%;border:3px solid ${isPremium ? '#FFD700' : '#293542'};">
                    <div style="font-size:16px;font-weight:bold;margin-top:10px;">${currentUser.name}</div>
                    <div style="font-size:11px;color:#666;">${currentUser.email || ''}</div>
                    ${isPremium ?
            `<div style="background:linear-gradient(135deg,#FFD700,#FFA500);color:#000;padding:8px 15px;border-radius:20px;display:inline-block;margin-top:10px;font-weight:bold;font-size:12px;">⭐ PREMIUM ÜYE</div>` :
            `<div style="background:#e9ecef;color:#666;padding:8px 15px;border-radius:20px;display:inline-block;margin-top:10px;font-size:12px;">Ücretsiz Plan</div>`
        }
                </div>
                <div style="background:#fff;border-radius:8px;padding:12px;margin-top:15px;">
                    <div style="font-size:12px;font-weight:bold;margin-bottom:10px;">📊 Günlük Kullanım</div>
                    <div style="background:#e9ecef;height:8px;border-radius:4px;overflow:hidden;">
                        <div id="usageBar" style="background:linear-gradient(90deg,#2ecc71,#27ae60);height:100%;width:${isPremium ? '100' : Math.min((currentUser.daily_usage || 0) / 5 * 100, 100)}%;transition:width 0.3s;"></div>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:10px;color:#666;margin-top:5px;">
                        <span>${isPremium ? '∞ Sınırsız' : `${currentUser.daily_usage || 0}/5 AI Analiz`}</span>
                        <span>${isPremium ? 'Premium Aktif' : 'Ücretsiz Plan'}</span>
                    </div>
                </div>
                ${!isPremium ? `
                    <button id="upgradePremiumBtn" style="width:100%;background:linear-gradient(135deg,#FFD700,#FFA500);color:#000;border:none;padding:12px;border-radius:8px;font-weight:bold;margin-top:15px;cursor:pointer;font-size:13px;">
                        ⭐ PREMIUM'A YÜKSELT
                    </button>
                    <div style="font-size:10px;color:#666;text-align:center;margin-top:8px;">
                        Sınırsız AI Analiz • Öncelikli Destek • Reklamsız
                    </div>
                ` : ''}
                <button id="logoutBtn" style="width:100%;background:#e74c3c;color:white;border:none;padding:10px;border-radius:6px;font-weight:bold;margin-top:15px;cursor:pointer;font-size:12px;">🚪 Çıkış Yap</button>
            </div>
        </div>
    `;
    overlay.style.cssText = `position:fixed;top:130px;right:20px;width:340px;background:transparent;border-radius:10px;box-shadow:0 15px 50px rgba(0,0,0,0.3);z-index:2147483647;font-family:'Open Sans',sans-serif;border:1px solid #dcdcdc;`;
    document.body.appendChild(overlay); makeDraggable(overlay);

    if (document.getElementById('googleLoginBtn')) document.getElementById('googleLoginBtn').onclick = loginWithGoogle;
    if (document.getElementById('logoutText')) document.getElementById('logoutText').onclick = logout;
    if (document.getElementById('telegramBtn')) document.getElementById('telegramBtn').onclick = handleTelegramClick;
    if (document.getElementById('logoutBtn')) document.getElementById('logoutBtn').onclick = logout;
    if (document.getElementById('upgradePremiumBtn')) {
        document.getElementById('upgradePremiumBtn').onclick = () => {
            alert('Premium üyelik için: cemerentosun@gmail.com adresine mail atın veya Telegram üzerinden iletişime geçin!');
        };
    }
    document.getElementById('closeOverlayBtn').onclick = () => overlay.remove();

    // Tab navigation (3 sekme)
    const tA = document.getElementById('tabAnaliz'), tY = document.getElementById('tabYorumlar'), tP = document.getElementById('tabProfil');
    const vA = document.getElementById('viewAnaliz'), vY = document.getElementById('viewYorumlar'), vP = document.getElementById('viewProfil');

    function switchTab(activeTab, activeView) {
        [tA, tY, tP].forEach(t => { t.style.background = '#e9ecef'; t.style.borderBottom = 'none'; t.style.color = '#666'; });
        [vA, vY, vP].forEach(v => { v.style.display = 'none'; });
        activeTab.style.background = '#fff';
        activeTab.style.borderBottom = '2px solid #293542';
        activeTab.style.color = '#293542';
        activeView.style.display = 'block';
    }

    tA.onclick = () => switchTab(tA, vA);
    tY.onclick = () => switchTab(tY, vY);
    tP.onclick = () => switchTab(tP, vP);

    // --- AI BUTONU ---
    document.getElementById('askAiBtn').onclick = async () => {
        const btn = document.getElementById('askAiBtn'), resBox = document.getElementById('aiResult');
        const userNow = getUser();
        btn.innerHTML = "⏳ Analiz Yapılıyor..."; btn.disabled = true;
        try {
            const payload = { ...data, user_id: userNow ? userNow.id : null };
            const r = await fetch(`${API_URL}/analyze-ai`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            const j = await r.json();
            resBox.style.display = "block";

            if (j.status === "limit_reached") {
                btn.innerHTML = "🔒 Limit Doldu";
                resBox.innerHTML = `<div style="text-align:center;padding:10px;background:#fff5f5;">🛑 ${j.message}</div>`;
            }
            else if (j.status === "login_required") {
                btn.innerHTML = "🔒 Giriş Yapın";
                resBox.innerHTML = `<div style="text-align:center;">Analiz için giriş yapmalısınız.</div>`;
            }
            else if (j.status === "success") {
                resBox.innerHTML = j.ai_response;
                btn.innerHTML = "✅ Analiz Tamamlandı";
            }
            else {
                // Hata durumu - meşgul uyarısı veya diğer hatalar
                if (j.message && j.message.includes("yoğun")) {
                    resBox.innerHTML = `<div style="text-align:center;padding:15px;background:#fff3cd;border-radius:8px;">
                        <div style="font-size:24px;margin-bottom:10px;">⏳</div>
                        <div style="font-weight:bold;color:#856404;">${j.message}</div>
                        <div style="font-size:11px;color:#666;margin-top:8px;">Butona tekrar tıklayarak deneyebilirsiniz.</div>
                    </div>`;
                    btn.innerHTML = "🔄 Tekrar Dene";
                } else {
                    resBox.innerHTML = `<span style="color:red">⚠️ Sistem Hatası:</span> ${j.message}`;
                    btn.innerHTML = "❌ Hata - Tekrar Dene";
                }
                btn.disabled = false;
            }
        } catch (e) {
            resBox.style.display = "block";
            resBox.innerHTML = `<div style="text-align:center;padding:10px;">⚠️ Sunucuya erişilemiyor. İnternet bağlantınızı kontrol edin.</div>`;
            btn.innerHTML = "🔄 Tekrar Dene";
            btn.disabled = false;
        }
    };

    if (document.getElementById('sendCommentBtn')) {
        document.getElementById('sendCommentBtn').onclick = async () => {
            const txt = document.getElementById('commentInput').value; if (!txt) return;
            const userNow = getUser();

            const list = document.getElementById('commentList');
            if (list.innerHTML.includes("Yorum yok")) list.innerHTML = "";
            list.insertAdjacentHTML('beforeend', `<div style="border-bottom:1px solid #eee;padding:5px;font-size:11px;"><b>${userNow.name}</b>: ${txt}</div>`);
            list.scrollTop = list.scrollHeight;

            const tabBtn = document.getElementById('tabYorumlar');
            let currentCount = parseInt(tabBtn.innerText.match(/\d+/)[0] || 0);
            tabBtn.innerText = `💬 Yorumlar (${currentCount + 1})`;

            const btn = document.getElementById('sendCommentBtn');
            const originalText = btn.innerText;
            btn.innerText = "✓";
            document.getElementById('commentInput').value = "";

            try {
                await fetch(`${API_URL}/add_comment`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ listing_id: data.id, user_id: userNow.id, username: userNow.name, text: txt }) });
                setTimeout(() => btn.innerText = originalText, 1000);
            } catch (e) { btn.innerText = "❌"; }
        };
    }
}

function renderComments(c) {
    if (!c || !c.length) return '<div style="text-align:center;color:#999;padding:20px;">Yorum yok.</div>';
    return c.map(x => `<div style="border-bottom:1px solid #eee;padding:5px;font-size:11px;"><b>${x.user}</b>: ${x.text}</div>`).join('');
}

async function runBackgroundWorker() {
    try {
        const response = await fetch(`${API_URL}/get-update-task`);
        const task = await response.json();
        if (task.status === "task_found" && task.url) {
            const htmlResponse = await fetch(task.url);
            const doc = new DOMParser().parseFromString(await htmlResponse.text(), "text/html");
            let priceText = doc.querySelector('.classifiedInfo h3')?.innerText || doc.querySelector('div.price-info')?.innerText;
            if (priceText) {
                await fetch(`${API_URL}/update-price-background`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: task.id, price: parseInt(priceText.replace(/\D/g, '')) }) });
            }
        }
    } catch (e) { }
}

async function init() {
    await runSweepMode();
    const data = getListingData();
    if (data) {
        try {
            const res = await fetch(`${API_URL}/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
            showOverlay(data, await res.json());
        } catch (e) { showOverlay(data, { status: "error" }); }
    }
}

setTimeout(init, 1000);
setTimeout(runBackgroundWorker, 5000);
