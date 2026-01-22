const API_URL = "https://sahiden.onrender.com";

// State
let currentAdmin = null;
let charts = {};

// DOM Elements
const loginScreen = document.getElementById('loginScreen');
const adminPanel = document.getElementById('adminPanel');
const loginBtn = document.getElementById('loginBtn');
const logoutBtn = document.getElementById('logoutBtn');
const toast = document.getElementById('toast');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkExistingLogin();
    setupEventListeners();
});

function setupEventListeners() {
    loginBtn.addEventListener('click', login);
    logoutBtn.addEventListener('click', logout);

    // Tab Switching
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = item.dataset.tab;
            switchTab(tabId);
        });
    });

    document.getElementById('refreshStatsBtn').addEventListener('click', loadStats);

    document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);
    document.getElementById('refreshDbBtn').addEventListener('click', loadDbData);

    // Login on Enter
    document.getElementById('adminKey').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') login();
    });
}

function switchTab(tabId) {
    // Nav Active State
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    document.querySelector(`.nav-item[data-tab="${tabId}"]`).classList.add('active');

    // Content Show/Hide
    document.querySelectorAll('.content-tab').forEach(c => c.style.display = 'none');
    document.getElementById(`tab-${tabId}`).style.display = 'block';

    if (tabId === 'users') loadUsers(1);
    if (tabId === 'settings') loadSettings();
}

// AUTH FUNCTIONS
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

async function login() {
    const email = document.getElementById('adminEmail').value.trim();
    const key = document.getElementById('adminKey').value.trim();

    if (!email || !key) return showToast('Tüm alanları doldurun', 'error');

    loginBtn.innerHTML = '🔄 Kontrol ediliyor...';
    loginBtn.disabled = true;

    try {
        const res = await fetch(`${API_URL}/admin/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, key })
        });
        const data = await res.json();

        if (data.status === 'success' && data.is_admin) {
            currentAdmin = { email, name: email.split('@')[0] };
            localStorage.setItem('bai_admin', JSON.stringify(currentAdmin));
            showToast('Giriş başarılı!', 'success');
            showAdminPanel();
        } else {
            showToast(data.message || 'Giriş başarısız', 'error');
        }
    } catch (e) {
        showToast('Sunucu hatası', 'error');
    } finally {
        loginBtn.innerHTML = 'Giriş Yap';
        loginBtn.disabled = false;
    }
}

function logout() {
    localStorage.removeItem('bai_admin');
    location.reload();
}

function showAdminPanel() {
    loginScreen.style.display = 'none';
    adminPanel.style.display = 'flex';
    document.getElementById('adminNameDisplay').textContent = currentAdmin.name;
    loadStats();
}

// STATS & CHARTS
async function loadStats() {
    try {
        const res = await fetch(`${API_URL}/admin/stats?admin_email=${encodeURIComponent(currentAdmin.email)}`);
        const data = await res.json();

        if (data.status === 'success') {
            // Update KPIs
            animateValue('totalUsers', data.stats.total_users);
            animateValue('premiumUsers', data.stats.premium_users);
            animateValue('activeToday', data.stats.active_today);
            document.getElementById('totalListings').textContent = data.stats.total_listings.toLocaleString('tr-TR');

            // Check Last Updated
            const now = new Date();
            document.getElementById('lastUpdated').textContent = `Son güncelleme: ${now.toLocaleTimeString()}`;

            // Render Charts
            if (data.charts) {
                renderCharts(data.charts);
            }
        }
    } catch (e) {
        console.error(e);
        showToast('Veriler yüklenemedi', 'error');
    }
}

function renderCharts(chartData) {
    const ctx1 = document.getElementById('queriesChart').getContext('2d');
    const ctx2 = document.getElementById('usersChart').getContext('2d');

    // Destroy existing charts to update
    if (charts.queries) charts.queries.destroy();
    if (charts.users) charts.users.destroy();

    // Common Chart Options
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: { color: '#38444d' },
                ticks: { color: '#8899a6' }
            },
            x: {
                grid: { display: false },
                ticks: { color: '#8899a6' }
            }
        }
    };

    // 1. Queries Chart (Line)
    charts.queries = new Chart(ctx1, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: [{
                label: 'Günlük Sorgu',
                data: chartData.queries,
                borderColor: '#1da1f2',
                backgroundColor: 'rgba(29, 161, 242, 0.1)',
                borderWidth: 2,
                tension: 0.4,
                fill: true
            }]
        },
        options: commonOptions
    });

    // 2. Active Users Chart (Bar)
    charts.users = new Chart(ctx2, {
        type: 'bar',
        data: {
            labels: chartData.labels,
            datasets: [{
                label: 'Aktif Kullanıcı',
                data: chartData.active_users,
                backgroundColor: '#00ba7c',
                borderRadius: 4
            }]
        },
        options: commonOptions
    });
}

// USERS TABLE (Simplified implementation)
async function loadUsers(page) {
    const tbody = document.getElementById('usersTableBody');
    tbody.innerHTML = '<tr><td colspan="5" class="text-center">Yükleniyor...</td></tr>';

    try {
        const res = await fetch(`${API_URL}/admin/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                limit: 20,
                skip: (page - 1) * 20
            })
        });
        const data = await res.json();

        if (data.status === 'success') {
            if (data.users.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center">Kullanıcı bulunamadı.</td></tr>';
                return;
            }

            tbody.innerHTML = data.users.map(u => `
                <tr>
                    <td>
                        <div style="display:flex;align-items:center;gap:10px;">
                            <img src="${u.picture || ''}" style="width:30px;height:30px;border-radius:50%;background:#333;">
                            <div>
                                <div>${u.name}</div>
                                <div style="font-size:11px;color:#888;">${u.email}</div>
                            </div>
                        </div>
                    </td>
                    <td><span class="badge ${u.plan}">${u.plan}</span></td>
                    <td>${u.daily_usage}</td>
                    <td>${u.last_login ? new Date(u.last_login).toLocaleDateString() : '-'}</td>
                    <td>
                        <button class="btn-sm ${u.plan === 'premium' ? 'btn-downgrade' : 'btn-upgrade'}" onclick="togglePlan('${u.id}', '${u.plan}')">
                            ${u.plan === 'premium' ? 'Free Yap' : 'Premium Yap'}
                        </button>
                    </td>
                </tr>
            `).join('');

            document.getElementById('pageIndicator').textContent = `Sayfa ${page}`;
        }
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Hata oluştu.</td></tr>';
    }
}

// ACTIONS
async function togglePlan(userId, currentPlan) {
    const newPlan = currentPlan === 'premium' ? 'free' : 'premium';
    if (!confirm(`Kullanıcıyı ${newPlan} paketine geçirmek istiyor musunuz?`)) return;

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
            showToast('Paket güncellendi', 'success');
            loadUsers(1); // Reload table
            loadStats();  // Reload KPIs
        }
    } catch (e) {
        showToast('İşlem başarısız', 'error');
    }
}

/* SYSTEM SETTINGS */
async function loadSettings() {
    try {
        const res = await fetch(`${API_URL}/admin/settings?admin_email=${encodeURIComponent(currentAdmin.email)}`);
        const data = await res.json();

        if (data.status === 'success') {
            document.getElementById('settingFreeLimit').value = data.settings.free_daily_limit;
            document.getElementById('settingMaintenance').checked = data.settings.maintenance_mode;
        }
    } catch (e) {
        showToast('Ayarlar yüklenemedi', 'error');
    }
}

async function saveSettings() {
    const freeLimit = parseInt(document.getElementById('settingFreeLimit').value);
    const maintenance = document.getElementById('settingMaintenance').checked;

    try {
        const res = await fetch(`${API_URL}/admin/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                settings: {
                    free_daily_limit: freeLimit,
                    maintenance_mode: maintenance
                }
            })
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('Ayarlar kaydedildi', 'success');
        } else {
            showToast(data.message || 'Hata', 'error');
        }
    } catch (e) {
        showToast('Kaydedilemedi', 'error');
    }
}

async function triggerJob(jobType) {
    if (!confirm('Bu işlemi manuel başlatmak istediğinize emin misiniz?')) return;

    try {
        const res = await fetch(`${API_URL}/admin/trigger-job`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                job_type: jobType
            })
        });
        const data = await res.json();
        showToast(data.message, data.status === 'success' ? 'success' : 'error');
    } catch (e) {
        showToast('İşlem hatası', 'error');
    }
}

/* DATA INSPECTOR */
async function loadDbData() {
    const collection = document.getElementById('dbCollectionSelect').value;
    const container = document.getElementById('jsonViewer'); // Using the same container but changing content

    container.innerHTML = '<div class="text-center" style="padding:20px;">Veriler yükleniyor...</div>';

    try {
        const res = await fetch(`${API_URL}/admin/db-preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                collection: collection,
                limit: 50
            })
        });
        const data = await res.json();

        if (data.status === 'success') {
            if (!data.data || data.data.length === 0) {
                container.innerHTML = '<div class="text-center" style="padding:20px;">Veri bulunamadı.</div>';
                return;
            }
            renderDataTable(data.data, collection, container);
        } else {
            container.innerHTML = `<div class="text-center text-danger" style="padding:20px;">Hata: ${data.message}</div>`;
        }
    } catch (e) {
        container.innerHTML = '<div class="text-center text-danger" style="padding:20px;">Bağlantı hatası.</div>';
    }
}

function renderDataTable(data, collection, container) {
    let columns = [];

    // Koleksiyona göre özel sütunlar belirle
    if (collection === 'listings') {
        columns = [
            { key: 'title', label: 'Başlık', render: val => `<span style="font-weight:600; color:white;">${val || '-'}</span>` },
            { key: 'price', label: 'Fiyat', render: val => val ? `${val.toLocaleString()} TL` : '-' },
            { key: 'location', label: 'Konum' },
            { key: 'year', label: 'Yıl' },
            { key: 'last_update', label: 'Tarih', render: val => val ? new Date(val).toLocaleDateString() : '-' }
        ];
    } else if (collection === 'users') {
        columns = [
            { key: 'name', label: 'İsim' },
            { key: 'email', label: 'E-posta' },
            { key: 'plan', label: 'Paket', render: val => `<span class="badge ${val}">${val}</span>` },
            { key: 'daily_usage', label: 'Kullanım' }
        ];
    } else {
        // Genel (Generic) Tablo: İlk kaydın anahtarlarını al (ID hariç)
        const keys = Object.keys(data[0]).filter(k => k !== '_id' && typeof data[0][k] !== 'object');
        columns = keys.slice(0, 5).map(k => ({ key: k, label: k.charAt(0).toUpperCase() + k.slice(1) }));
    }

    let html = `
        <table class="data-table" style="width:100%;">
            <thead>
                <tr>
                    ${columns.map(col => `<th>${col.label}</th>`).join('')}
                    <th>JSON</th>
                </tr>
            </thead>
            <tbody>
                ${data.map(row => `
                    <tr>
                        ${columns.map(col => {
        const val = row[col.key];
        return `<td>${col.render ? col.render(val) : (val || '-')}</td>`;
    }).join('')}
                        <td>
                            <button class="btn-sm" onclick='alert(${JSON.stringify(JSON.stringify(row, null, 2))})' style="font-size:10px; padding:4px 8px;">
                                🔍 Detay
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    container.innerHTML = html;
}

// UTILS
function showToast(msg, type = 'success') {
    toast.textContent = msg;
    toast.className = `toast show ${type}`;
    setTimeout(() => toast.className = 'toast', 3000);
}

function animateValue(id, end) {
    const obj = document.getElementById(id);
    if (!obj) return;
    if (end === undefined || end === null) { obj.textContent = '-'; return; }

    // Simple set for now
    obj.textContent = end.toLocaleString('tr-TR');
}
