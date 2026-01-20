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
const loginBtn = document.getElementById('loginBtn');
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
    loginBtn.addEventListener('click', login);
    logoutBtn.addEventListener('click', logout);
    searchBtn.addEventListener('click', searchUsers);
    refreshBtn.addEventListener('click', () => loadUsers(currentPage));
    prevPageBtn.addEventListener('click', () => changePage(-1));
    nextPageBtn.addEventListener('click', () => changePage(1));

    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchUsers();
    });

    // Enter tuşu ile giriş
    document.getElementById('adminKey').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') login();
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

// Email + Key Login
async function login() {
    const email = document.getElementById('adminEmail').value.trim();
    const key = document.getElementById('adminKey').value.trim();

    if (!email) {
        showToast('Email girin', 'error');
        return;
    }
    if (!key) {
        showToast('Şifre girin', 'error');
        return;
    }

    loginBtn.innerHTML = '⏳ Kontrol ediliyor...';
    loginBtn.disabled = true;

    try {
        // Backend'e admin doğrulaması yap
        const res = await fetch(`${API_URL}/admin/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, key: key })
        });

        const data = await res.json();

        if (data.status === 'success' && data.is_admin) {
            currentAdmin = {
                email: email,
                name: email.split('@')[0]
            };
            localStorage.setItem('bai_admin', JSON.stringify(currentAdmin));
            showAdminPanel();
            showToast('Hoş geldin! 👋', 'success');
        } else {
            showToast('❌ ' + (data.message || 'Giriş başarısız!'), 'error');
            resetLoginButton();
        }
    } catch (e) {
        showToast('Sunucu hatası: ' + e.message, 'error');
        resetLoginButton();
    }
}

function resetLoginButton() {
    loginBtn.innerHTML = '🔐 Giriş Yap';
    loginBtn.disabled = false;
}

function logout() {
    if (confirm('Çıkış yapmak istediğinize emin misiniz?')) {
        localStorage.removeItem('bai_admin');
        currentAdmin = null;
        adminPanel.style.display = 'none';
        loginScreen.style.display = 'flex';
        document.getElementById('adminEmail').value = '';
        document.getElementById('adminKey').value = '';
    }
}

function showAdminPanel() {
    loginScreen.style.display = 'none';
    adminPanel.style.display = 'block';

    document.getElementById('adminName').textContent = currentAdmin.email;

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
