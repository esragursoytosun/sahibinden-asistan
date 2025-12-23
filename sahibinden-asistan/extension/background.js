// background.js - Auth ve API İşlemleri

// Backend Adresi (Canlı sunucu veya Localhost)
// Test ederken: "http://localhost:8000" yapabilirsin.
// Canlıda: "https://sahiden.onrender.com"
const API_URL = "https://sahiden.onrender.com"; 

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    
    // --- LOGIN İŞLEMİ ---
    if (request.action === "login") {
        console.log("BAI BILMIS: Google Login başlatılıyor...");

        // 1. Chrome'dan Token İste (Access Token döner)
        chrome.identity.getAuthToken({ interactive: true }, function(token) {
            
            if (chrome.runtime.lastError || !token) {
                console.error("Token Hatası:", chrome.runtime.lastError);
                sendResponse({ status: "error", message: "Google hesabına erişilemedi. Lütfen tarayıcıda oturum açın." });
                return;
            }

            console.log("BAI BILMIS: Token alındı, Backend'e gönderiliyor...");

            // 2. Token'ı Python Backend'e Gönder
            fetch(`${API_URL}/auth/google`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: token })
            })
            .then(res => res.json())
            .then(data => {
                if(data.status === "success") {
                    console.log("BAI BILMIS: Giriş Başarılı!", data.user);
                    sendResponse({ status: "success", user: data.user });
                } else {
                    console.error("BAI BILMIS: Backend Reddedildi", data);
                    sendResponse({ status: "error", message: data.detail || "Sunucu girişi reddetti." });
                }
            })
            .catch(err => {
                console.error("BAI BILMIS: Sunucu Hatası", err);
                sendResponse({ status: "error", message: "Sunucuya bağlanılamadı." });
            });
        });

        return true; // Asenkron cevap vereceğimizi Chrome'a bildiriyoruz
    }
});
