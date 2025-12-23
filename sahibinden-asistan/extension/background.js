// background.js - Auth İşlemleri
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "login") {
        // Chrome'un kendi Login penceresini aç
        chrome.identity.getAuthToken({ interactive: true }, function(token) {
            if (chrome.runtime.lastError) {
                sendResponse({ status: "error", message: chrome.runtime.lastError.message });
                return;
            }
            // Token alındı, şimdi Backend'e gönderip kullanıcı bilgilerini alalım
            fetch("https://sahiden.onrender.com/auth/google", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: token })
            })
            .then(res => res.json())
            .then(data => {
                sendResponse({ status: "success", user: data.user, token: token });
            })
            .catch(err => {
                sendResponse({ status: "error", message: err.toString() });
            });
        });
        return true; // Asenkron cevap vereceğimizi belirtiyoruz
    }
});
