// BAI Bilmiş Admin Panel - JavaScript

const API_URL = "https://sahiden.onrender.com";

// State
let currentAdmin = null;
let currentPage = 1;
let totalUsers = 0;
const USERS_PER_PAGE = 20;

// DOM Elements
const loginScreen = document.getElementById('loginScreen');
const adminPanel = document.getElementById('adminPanel');
const googleLoginBtn = document.getElementById('googleLoginBtn');
const logoutBtn = document.getElementById('logoutBtn');
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const refreshBtn = document.getElementById('refreshBtn');
const usersTableBody = document.getElementById('usersTableBody');
const prevPageBtn = document.getElementById('prevPage');
const nextPageBtn = document.getElementById('nextPage');
const pageInfo = document.getElementById('pageInfo');
const toast = document.getElementById('toast');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkExistingLogin();
    setupEventListeners();
});

function setupEventListeners() {
    googleLoginBtn.addEventListener('click', loginWithGoogle);
    logoutBtn.addEventListener('click', logout);
    searchBtn.addEventListener('click', searchUsers);
    refreshBtn.addEventListener('click', () => loadUsers(currentPage));
    prevPageBtn.addEventListener('click', () => changePage(-1));
    nextPageBtn.addEventListener('click', () => changePage(1));
    
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchUsers();
    });
}

function checkExistingLogin() {
    const stored = localStorage.getItem('bai_admin');
    if (stored) {
        try {
            currentAdmin = JSON.parse(stored);
            showAdminPanel();
        } catch (e) {
            localStorage.removeItem('bai_admin');
        }
    }
}

// Google Login
async function loginWithGoogle() {
    googleLoginBtn.innerHTML = '⏳ Giriş yapılıyor...';
    googleLoginBtn.disabled = true;
    
    try {
        // Google OAuth popup
        const clientId = '755978aborov.apps.googleusercontent.com'; // Eklentideki client ID
        const redirectUri = encodeURIComponent(window.location.origin + '/admin/');
        const scope = encodeURIComponent('email profile');
        
        const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=token&scope=${scope}`;
        
        // Check if we have a token in URL (redirect callback)
        const hash = window.location.hash;
        if (hash && hash.includes('access_token')) {
            const params = new URLSearchParams(hash.substring(1));
            const accessToken = params.get('access_token');
            if (accessToken) {
                await handleGoogleToken(accessToken);
                return;
            }
        }
        
        // Redirect to Google OAuth
        window.location.href = authUrl;
    } catch (e) {
        showToast('Giriş hatası: ' + e.message, 'error');
        resetLoginButton();
    }
}

async function handleGoogleToken(token) {
    try {
        // Get user info from Google
        const res = await fetch('https://www.googleapis.com/oauth2/v2/userinfo', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!res.ok) throw new Error('Token geçersiz');
        
        const userInfo = await res.json();
        
        // Verify admin status
        const verifyRes = await fetch(`${API_URL}/admin/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: userInfo.email })
        });
        
        const verifyData = await verifyRes.json();
        
        if (verifyData.is_admin) {
            currentAdmin = {
                email: userInfo.email,
                name: userInfo.name,
                picture: userInfo.picture
            };
            localStorage.setItem('bai_admin', JSON.stringify(currentAdmin));
            
            // Clear URL hash
            history.replaceState(null, '', window.location.pathname);
            
            showAdminPanel();
            showToast('Hoş geldin, ' + currentAdmin.name + '! 👋', 'success');
        } else {
            showToast('❌ Admin yetkiniz yok!', 'error');
            resetLoginButton();
        }
    } catch (e) {
        showToast('Giriş hatası: ' + e.message, 'error');
        resetLoginButton();
    }
}

function resetLoginButton() {
    googleLoginBtn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 48 48">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
        </svg>
        Google ile Giriş Yap
    `;
    googleLoginBtn.disabled = false;
}

function logout() {
    if (confirm('Çıkış yapmak istediğinize emin misiniz?')) {
        localStorage.removeItem('bai_admin');
        currentAdmin = null;
        adminPanel.style.display = 'none';
        loginScreen.style.display = 'flex';
    }
}

function showAdminPanel() {
    loginScreen.style.display = 'none';
    adminPanel.style.display = 'block';
    
    document.getElementById('adminName').textContent = currentAdmin.name;
    document.getElementById('adminPicture').src = currentAdmin.picture;
    
    loadStats();
    loadUsers(1);
}

// Load Stats
async function loadStats() {
    try {
        const res = await fetch(`${API_URL}/admin/stats?admin_email=${encodeURIComponent(currentAdmin.email)}`);
        const data = await res.json();
        
        if (data.status === 'success') {
            document.getElementById('totalUsers').textContent = data.stats.total_users;
            document.getElementById('premiumUsers').textContent = data.stats.premium_users;
            document.getElementById('totalListings').textContent = data.stats.total_listings.toLocaleString('tr-TR');
            document.getElementById('activeToday').textContent = data.stats.active_today;
        }
    } catch (e) {
        console.error('Stats yüklenemedi:', e);
    }
}

// Load Users
async function loadUsers(page) {
    usersTableBody.innerHTML = '<tr><td colspan="6" class="loading-row">⏳ Yükleniyor...</td></tr>';
    currentPage = page;
    
    try {
        const res = await fetch(`${API_URL}/admin/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                limit: USERS_PER_PAGE,
                skip: (page - 1) * USERS_PER_PAGE
            })
        });
        
        const data = await res.json();
        
        if (data.status === 'success') {
            totalUsers = data.total;
            renderUsers(data.users);
            updatePagination();
        } else {
            throw new Error(data.message);
        }
    } catch (e) {
        usersTableBody.innerHTML = `<tr><td colspan="6" class="loading-row">❌ Hata: ${e.message}</td></tr>`;
    }
}

// Search Users
async function searchUsers() {
    const query = searchInput.value.trim();
    if (!query) {
        loadUsers(1);
        return;
    }
    
    if (query.length < 2) {
        showToast('En az 2 karakter girin', 'error');
        return;
    }
    
    usersTableBody.innerHTML = '<tr><td colspan="6" class="loading-row">🔍 Aranıyor...</td></tr>';
    
    try {
        const res = await fetch(`${API_URL}/admin/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                query: query
            })
        });
        
        const data = await res.json();
        
        if (data.status === 'success') {
            renderUsers(data.users);
            pageInfo.textContent = `${data.count} sonuç`;
            prevPageBtn.disabled = true;
            nextPageBtn.disabled = true;
        } else {
            throw new Error(data.message);
        }
    } catch (e) {
        usersTableBody.innerHTML = `<tr><td colspan="6" class="loading-row">❌ Arama hatası: ${e.message}</td></tr>`;
    }
}

// Render Users Table
function renderUsers(users) {
    if (!users || users.length === 0) {
        usersTableBody.innerHTML = '<tr><td colspan="6" class="loading-row">Kullanıcı bulunamadı</td></tr>';
        return;
    }
    
    usersTableBody.innerHTML = users.map(user => `
        <tr>
            <td>
                <div class="user-cell">
                    <img src="${user.picture || 'https://via.placeholder.com/40'}" alt="" class="user-avatar">
                    <span class="user-name">
                        ${escapeHtml(user.name)}
                        ${user.is_admin ? '<span class="admin-tag">ADMIN</span>' : ''}
                    </span>
                </div>
            </td>
            <td>${escapeHtml(user.email)}</td>
            <td>
                <span class="plan-badge ${user.plan}">${user.plan === 'premium' ? '⭐ Premium' : 'Ücretsiz'}</span>
            </td>
            <td>${user.daily_usage}/5</td>
            <td>${formatDate(user.last_login)}</td>
            <td>
                ${user.plan === 'premium' 
                    ? `<button class="action-btn free-btn" onclick="changePlan('${user.id}', 'free')">Ücretsiz Yap</button>`
                    : `<button class="action-btn premium-btn" onclick="changePlan('${user.id}', 'premium')">⭐ Premium Yap</button>`
                }
            </td>
        </tr>
    `).join('');
}

// Change User Plan
async function changePlan(userId, newPlan) {
    const actionText = newPlan === 'premium' ? 'Premium yapmak' : 'Ücretsiz yapmak';
    
    if (!confirm(`Bu kullanıcıyı ${actionText} istediğinize emin misiniz?`)) {
        return;
    }
    
    try {
        const res = await fetch(`${API_URL}/admin/set-plan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                user_id: userId,
                plan: newPlan
            })
        });
        
        const data = await res.json();
        
        if (data.status === 'success') {
            showToast('✅ ' + data.message, 'success');
            loadUsers(currentPage);
            loadStats();
        } else {
            throw new Error(data.message);
        }
    } catch (e) {
        showToast('❌ Hata: ' + e.message, 'error');
    }
}

// Pagination
function changePage(delta) {
    const newPage = currentPage + delta;
    const maxPage = Math.ceil(totalUsers / USERS_PER_PAGE);
    
    if (newPage >= 1 && newPage <= maxPage) {
        loadUsers(newPage);
    }
}

function updatePagination() {
    const maxPage = Math.ceil(totalUsers / USERS_PER_PAGE);
    
    prevPageBtn.disabled = currentPage <= 1;
    nextPageBtn.disabled = currentPage >= maxPage;
    pageInfo.textContent = `Sayfa ${currentPage} / ${maxPage} (${totalUsers} kullanıcı)`;
}

// Helpers
function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;');
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('tr-TR', { 
            day: '2-digit', 
            month: '2-digit', 
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        return dateStr;
    }
}

function showToast(message, type = 'success') {
    toast.textContent = message;
    toast.className = 'toast show ' + type;
    
    setTimeout(() => {
        toast.className = 'toast';
    }, 3000);
}

// Check for OAuth callback on page load
window.addEventListener('load', () => {
    const hash = window.location.hash;
    if (hash && hash.includes('access_token')) {
        const params = new URLSearchParams(hash.substring(1));
        const accessToken = params.get('access_token');
        if (accessToken) {
            handleGoogleToken(accessToken);
        }
    }
});
