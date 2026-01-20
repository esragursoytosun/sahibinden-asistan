// background.js - Auth ve API İşlemleri

// Backend Adresi
const API_URL = "https://sahiden.onrender.com";

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

    // --- LOGIN İŞLEMİ ---
    if (request.action === "login") {
        console.log("BAI BILMIS: Google Login başlatılıyor...");

        // Chrome'dan Token İste
        chrome.identity.getAuthToken({ interactive: true }, function (token) {

            if (chrome.runtime.lastError) {
                const errorMsg = chrome.runtime.lastError.message || "Bilinmeyen hata";
                console.error("BAI BILMIS Token Hatası:", errorMsg);

                // Daha açıklayıcı hata mesajları
                let userMessage = "Google girişi başarısız.";

                if (errorMsg.includes("not signed in") || errorMsg.includes("No account")) {
                    userMessage = "Chrome'da Google hesabınızla giriş yapın (sağ üst köşe).";
                } else if (errorMsg.includes("OAuth2") || errorMsg.includes("invalid_client")) {
                    userMessage = "Eklenti ayarı hatası. Geliştiriciyle iletişime geçin.";
                } else if (errorMsg.includes("user gesture") || errorMsg.includes("popup")) {
                    userMessage = "Lütfen tekrar deneyin (popup engellendi).";
                } else if (errorMsg.includes("canceled") || errorMsg.includes("denied")) {
                    userMessage = "Giriş iptal edildi.";
                }

                sendResponse({ status: "error", message: userMessage, detail: errorMsg });
                return;
            }

            if (!token) {
                console.error("BAI BILMIS: Token alınamadı (boş)");
                sendResponse({ status: "error", message: "Token alınamadı. Chrome'da Google hesabınızla giriş yapın." });
                return;
            }

            console.log("BAI BILMIS: Token alındı, Backend'e gönderiliyor...");

            // Token'ı Python Backend'e Gönder
            fetch(`${API_URL}/auth/google`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: token })
            })
                .then(res => {
                    if (!res.ok) {
                        throw new Error(`HTTP ${res.status}`);
                    }
                    return res.json();
                })
                .then(data => {
                    if (data.status === "success") {
                        console.log("BAI BILMIS: Giriş Başarılı!", data.user);
                        sendResponse({ status: "success", user: data.user });
                    } else {
                        console.error("BAI BILMIS: Backend Reddetti", data);
                        sendResponse({ status: "error", message: data.detail || data.message || "Sunucu girişi reddetti." });
                    }
                })
                .catch(err => {
                    console.error("BAI BILMIS: Sunucu Hatası", err);
                    sendResponse({ status: "error", message: "Sunucuya bağlanılamadı: " + err.message });
                });
        });

        return true; // Asenkron cevap
    }

    // --- LOGOUT İŞLEMİ ---
    if (request.action === "logout") {
        chrome.identity.clearAllCachedAuthTokens(() => {
            console.log("BAI BILMIS: Token cache temizlendi");
            sendResponse({ status: "success" });
        });
        return true;
    }
});
