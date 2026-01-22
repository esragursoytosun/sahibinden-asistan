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
    document.getElementById('refreshDbBtn').addEventListener('click', () => loadDbData(1));

    // Login on Enter
    document.getElementById('adminKey').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') login();
    });

    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => applyFilter(btn.dataset.filter));
    });

    // Save Edit button
    document.getElementById('saveEditBtn').addEventListener('click', saveEditRecord);

    // View Mode Toggles (Table vs Tree)
    document.getElementById('viewTableBtn').addEventListener('click', () => setViewMode('table'));
    document.getElementById('viewTreeBtn').addEventListener('click', () => setViewMode('tree'));

    // Password Change
    document.getElementById('changePasswordBtn').addEventListener('click', changePassword);
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
    if (tabId === 'data') loadDbData(1);
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
        showToast('Bağlantı hatası: ' + e.message, 'error');
    } finally {
        loginBtn.innerHTML = 'Giriş Yap';
        loginBtn.disabled = false;
    }
}

function logout() {
    localStorage.removeItem('bai_admin');
    currentAdmin = null;
    loginScreen.style.display = 'flex';
    adminPanel.style.display = 'none';
    showToast('Çıkış yapıldı', 'info');
}

function showAdminPanel() {
    loginScreen.style.display = 'none';
    adminPanel.style.display = 'flex';
    document.getElementById('adminNameDisplay').innerText = currentAdmin.name;
    loadStats();
}

// DATA FUNCTIONS
async function loadStats() {
    try {
        const res = await fetch(`${API_URL}/admin/stats`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ admin_email: currentAdmin.email }) // Auth check
        });
        const data = await res.json();

        if (data.status === 'success') {
            const stats = data.stats;
            animateValue('totalUsers', 0, stats.total_users, 1000);
            animateValue('premiumUsers', 0, stats.premium_users, 1000);
            animateValue('activeToday', 0, stats.active_today, 1000);
            animateValue('totalListings', 0, stats.total_listings, 1000);

            document.getElementById('lastUpdated').innerText = `Son güncelleme: ${new Date().toLocaleTimeString()}`;

            renderCharts(data.history);
        }
    } catch (e) {
        console.error("Stats load error:", e);
    }
}

async function loadUsers(page = 1) {
    const tbody = document.getElementById('usersTableBody');
    tbody.innerHTML = '<tr><td colspan="5" class="text-center">Yükleniyor...</td></tr>';

    try {
        const res = await fetch(`${API_URL}/admin/users?page=${page}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ admin_email: currentAdmin.email })
        });
        const data = await res.json();

        if (data.status === 'success') {
            tbody.innerHTML = '';
            data.users.forEach(user => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>
                        <div class="user-cell">
                            <div class="avatar">${user.name.charAt(0).toUpperCase()}</div>
                            <div>
                                <div class="font-medium">${user.name}</div>
                                <div class="text-muted">${user.email}</div>
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="badge ${user.is_premium ? 'badge-premium' : 'badge-free'}">
                            ${user.is_premium ? 'Premium' : 'Ücretsiz'}
                        </span>
                    </td>
                    <td>${user.usage_count || 0} / ${user.daily_limit || 5}</td>
                    <td>${formatDate(user.last_login)}</td>
                    <td>
                        <button class="btn-icon-sm" onclick="editUser('${user.user_id}')">✏️</button>
                        <button class="btn-icon-sm delete" onclick="deleteUser('${user.user_id}')">🗑️</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
            // Update pagination buttons if needed
        }
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center error">Hata: ${e.message}</td></tr>`;
    }
}

// --- DATA MANAGEMENT & CRUD (Listings) ---

let currentDbPage = 1;
let currentDbData = [];
let currentViewMode = 'table'; // 'table' or 'tree'

// View Mode Toggle
function setViewMode(mode) {
    currentViewMode = mode;
    document.querySelectorAll('.view-mode-btn').forEach(btn => btn.classList.remove('active'));

    if (mode === 'table') {
        document.getElementById('viewTableBtn').classList.add('active');
        renderDataTable(currentDbData); // Re-render table
        document.querySelector('.pagination').style.display = 'flex'; // Show pagination
    } else {
        document.getElementById('viewTreeBtn').classList.add('active');
        // Tree view için veriyi işle
        const tree = buildCategoryTree(currentDbData);
        const container = document.getElementById('jsonViewer');

        // Tree yapısını oluştur (tree_functions.js'den gelir)
        renderCategoryTree(tree, container);
        document.querySelector('.pagination').style.display = 'none'; // Tree modunda sayfalama gizle (opsiyonel)
    }
}

async function loadDbData(page = 1) {
    const collection = document.getElementById('dbCollectionSelect').value;
    const container = document.getElementById('jsonViewer');

    // Toggle Buttons Display Logic
    const viewToggle = document.getElementById('viewModeToggle');
    const filters = document.getElementById('listingFilters');

    if (collection === 'listings') {
        viewToggle.style.display = 'flex';
        filters.style.display = 'block';
    } else {
        viewToggle.style.display = 'none';
        filters.style.display = 'none';
        currentViewMode = 'table'; // Reset to table for non-listings
    }

    container.innerHTML = '<div class="text-center" style="padding:20px;">Veriler yükleniyor...</div>';

    try {
        const res = await fetch(`${API_URL}/admin/data`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                collection: collection,
                page: page,
                limit: 50 // Fetch 50 records
            })
        });
        const data = await res.json();

        if (data.status === 'success') {
            currentDbData = data.data; // Store for switching views
            currentDbPage = page;
            updateDbPagination(data.pagination);

            if (currentViewMode === 'tree' && collection === 'listings') {
                const tree = buildCategoryTree(currentDbData);
                renderCategoryTree(tree, container);
            } else {
                renderDataTable(currentDbData);
            }
        } else {
            container.innerText = JSON.stringify(data, null, 2);
        }
    } catch (e) {
        container.innerHTML = `<div class="text-center error">Hata: ${e.message}</div>`;
    }
}

function renderDataTable(items) {
    const container = document.getElementById('jsonViewer');
    const collection = document.getElementById('dbCollectionSelect').value;

    if (items.length === 0) {
        container.innerHTML = '<div class="text-center" style="padding:20px; color:#8899a6;">Kayıt bulunamadı.</div>';
        return;
    }

    let html = '<table class="data-table" style="width:100%; font-size:13px;"><thead><tr>';

    // Headers
    // Basit bir başlık belirleme mantığı
    let headers = [];
    if (collection === 'listings') {
        headers = ['Başlık', 'Fiyat', 'Kategori', 'Konum', 'Yıl/Km', 'İşlem'];
    } else if (collection === 'users') {
        headers = ['Ad', 'Email', 'Plan', 'Son Giriş', 'İşlem'];
    } else {
        headers = Object.keys(items[0]).slice(0, 5); // İlk 5 alan
        headers.push('İşlem');
    }

    headers.forEach(h => html += `<th>${h}</th>`);
    html += '</tr></thead><tbody>';

    // Rows
    items.forEach(item => {
        html += '<tr>';

        if (collection === 'listings') {
            const price = item.price ? item.price.toLocaleString('tr-TR') + ' TL' : '<span style="color:#e0245e">Fiyat Yok</span>';
            const title = item.title ? (item.title.length > 30 ? item.title.substring(0, 30) + '...' : item.title) : '-';

            html += `
                <td style="color:#1da1f2; font-weight:500;">${title}</td>
                <td style="font-weight:bold;">${price}</td>
                <td style="color:#8899a6; font-size:11px;">${item.category_path ? '...' + item.category_path.split('>').pop() : '-'}</td>
                <td>${item.location || '-'}</td>
                <td>${item.year || '-'} / ${item.km || '-'}</td>
             `;
        } else if (collection === 'users') {
            html += `
                <td>${item.name}</td>
                <td>${item.email}</td>
                <td>${item.is_premium ? 'Premium' : 'Free'}</td>
                <td>${formatDate(item.last_login)}</td>
             `;
        } else {
            // Generic rendering
            Object.keys(item).slice(0, 5).forEach(k => {
                let val = item[k];
                if (typeof val === 'object') val = JSON.stringify(val);
                html += `<td>${val}</td>`;
            });
        }

        // Actions Column (Edit/Delete)
        const id = item.id || item._id; // MongoDB _id or id
        html += `
            <td style="display:flex; gap:5px;">
                <button onclick='window.openEditModal(${JSON.stringify(item).replace(/'/g, "&#39;")})' 
                    style="background:#1da1f2; border:none; color:white; padding:4px 8px; border-radius:4px; cursor:pointer;" title="Düzenle">✏️</button>
                <button onclick='window.deleteRecord("${id}")' 
                    style="background:#e0245e; border:none; color:white; padding:4px 8px; border-radius:4px; cursor:pointer;" title="Sil">🗑️</button>
            </td>
        `;

        html += '</tr>';
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

// --- CRUD OPERATIONS ---

// 1. DELETE
window.deleteRecord = async function (id) {
    if (!confirm('Bu kaydı silmek istediğinize emin misiniz?')) return;

    const collection = document.getElementById('dbCollectionSelect').value;

    try {
        const res = await fetch(`${API_URL}/admin/data/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                collection: collection,
                id: id
            })
        });
        const data = await res.json();

        if (data.status === 'success') {
            showToast('Kayıt silindi.', 'success');
            loadDbData(currentDbPage); // Refresh
        } else {
            showToast('Hata: ' + data.message, 'error');
        }
    } catch (e) {
        showToast('Silme hatası: ' + e.message, 'error');
    }
};

// 2. EDIT (Modal & Save)
let currentEditId = null;

window.openEditModal = function (item) {
    const modal = document.getElementById('editModal');
    const form = document.getElementById('editForm');
    form.innerHTML = ''; // Clear previous
    currentEditId = item.id || item._id;

    // Create inputs for important fields
    // İlanlar için özel alanlar, diğerleri için generic
    const fields = ['title', 'price', 'year', 'km', 'location', 'description'];

    // Generic approach used for now, filtering common large objects
    Object.keys(item).forEach(key => {
        if (key === '_id' || key === 'id' || key === 'created_at') return; // Skip non-editable
        if (typeof item[key] === 'object') return; // Skip complex objects for simple edit

        const div = document.createElement('div');
        div.style.display = 'flex';
        div.style.flexDirection = 'column';

        const label = document.createElement('label');
        label.innerText = key.charAt(0).toUpperCase() + key.slice(1);
        label.style.color = '#8899a6';
        label.style.fontSize = '12px';

        let input;
        if (item[key] && item[key].length > 50) {
            input = document.createElement('textarea');
            input.rows = 3;
        } else {
            input = document.createElement('input');
            input.type = (typeof item[key] === 'number') ? 'number' : 'text';
        }

        input.value = item[key];
        input.id = `edit_${key}`;
        input.className = 'edit-input'; // Styling class
        input.style.background = '#253341';
        input.style.border = '1px solid #38444d';
        input.style.color = 'white';
        input.style.padding = '8px';
        input.style.borderRadius = '4px';

        div.appendChild(label);
        div.appendChild(input);
        form.appendChild(div);
    });

    modal.style.display = 'flex';
};

async function saveEditRecord() {
    const collection = document.getElementById('dbCollectionSelect').value;
    const inputs = document.querySelectorAll('.edit-input');
    const updateData = {};

    inputs.forEach(input => {
        const key = input.id.replace('edit_', '');
        let val = input.value;
        if (input.type === 'number') val = Number(val);
        updateData[key] = val;
    });

    if (!currentEditId) return;

    try {
        const btn = document.getElementById('saveEditBtn');
        btn.innerHTML = 'Kaydediliyor...';
        btn.disabled = true;

        const res = await fetch(`${API_URL}/admin/data/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                collection: collection,
                id: currentEditId,
                data: updateData
            })
        });

        const data = await res.json();

        if (data.status === 'success') {
            showToast('Kayıt güncellendi!', 'success');
            document.getElementById('editModal').style.display = 'none';
            loadDbData(currentDbPage);
        } else {
            showToast('Hata: ' + data.message, 'error');
        }
    } catch (e) {
        showToast('Güncelleme hatası: ' + e.message, 'error');
    } finally {
        const btn = document.getElementById('saveEditBtn');
        btn.innerHTML = 'Kaydet';
        btn.disabled = false;
    }
}

// Pagination Helpers
function updateDbPagination(info) {
    if (!info) return;
    document.getElementById('dbPageIndicator').innerText = `Sayfa ${info.current_page} / ${info.total_pages}`;
    document.getElementById('prevDbPage').disabled = !info.has_prev;
    document.getElementById('nextDbPage').disabled = !info.has_next;

    // Remove old listeners to prevent stacking
    const newPrev = document.getElementById('prevDbPage').cloneNode(true);
    const newNext = document.getElementById('nextDbPage').cloneNode(true);

    document.getElementById('prevDbPage').parentNode.replaceChild(newPrev, document.getElementById('prevDbPage'));
    document.getElementById('nextDbPage').parentNode.replaceChild(newNext, document.getElementById('nextDbPage'));

    newPrev.addEventListener('click', () => loadDbData(info.current_page - 1));
    newNext.addEventListener('click', () => loadDbData(info.current_page + 1));
}

// Client-side filtering logic
function applyFilter(filterType) {
    // UI update
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.filter-btn[data-filter="${filterType}"]`).classList.add('active');

    // Since we are doing server-side pagination, real filtering should be server-side.
    // For now, let's filter the CURRENT page data only for immediate feedback
    if (!currentDbData.length) return;

    let filtered = currentDbData;
    if (filterType === 'konut') {
        filtered = currentDbData.filter(i => i.category_path && i.category_path.toLowerCase().includes('konut'));
    } else if (filterType === 'araba') {
        filtered = currentDbData.filter(i => i.category_path && (i.category_path.toLowerCase().includes('otomobil') || i.category_path.toLowerCase().includes('vasıta')));
    }

    // Count
    document.getElementById('filterCount').innerText = `${filtered.length} sonuç (bu sayfada)`;

    if (currentViewMode === 'table') {
        renderDataTable(filtered);
    } else {
        const tree = buildCategoryTree(filtered);
        renderCategoryTree(tree, document.getElementById('jsonViewer'));
    }
}

// SETTINGS
async function loadSettings() {
    // ... existing ...
}

async function saveSettings() {
    // ... existing ...
    showToast('Ayarlar kaydedildi (Demo)', 'success');
}

async function changePassword() {
    const currentPass = document.getElementById('currentPassword').value;
    const newPass = document.getElementById('newPassword').value;
    const confirmPass = document.getElementById('confirmPassword').value;

    if (!currentPass || !newPass || !confirmPass) {
        return showToast('Tüm alanları doldurun', 'error');
    }

    if (newPass !== confirmPass) {
        return showToast('Yeni şifreler eşleşmiyor', 'error');
    }

    const btn = document.getElementById('changePasswordBtn');
    btn.disabled = true;
    btn.innerHTML = 'İşleniyor...';

    try {
        const res = await fetch(`${API_URL}/admin/change-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                current_password: currentPass,
                new_password: newPass
            })
        });

        const data = await res.json();

        if (data.status === 'success') {
            showToast('Şifre başarıyla değiştirildi!', 'success');
            document.getElementById('currentPassword').value = '';
            document.getElementById('newPassword').value = '';
            document.getElementById('confirmPassword').value = '';
        } else {
            showToast(data.message || 'Hata oluştu', 'error');
        }
    } catch (e) {
        showToast('Bağlantı hatası: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Şifreyi Değiştir';
    }
}

async function triggerJob(jobName) {
    showToast(`${jobName} tetiklendi (Demo)`, 'info');
}

// UTILS
function showToast(msg, type = 'info') {
    toast.innerText = msg;
    toast.className = `toast show ${type}`;
    setTimeout(() => {
        toast.className = toast.className.replace('show', '');
    }, 3000);
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('tr-TR');
}

function animateValue(id, start, end, duration) {
    if (start === end) return;
    const range = end - start;
    const current = start;
    const increment = end > start ? 1 : -1;
    const stepTime = Math.abs(Math.floor(duration / range));
    const obj = document.getElementById(id);
    let timer = setInterval(function () {
        start += increment;
        obj.innerHTML = start;
        if (start == end) {
            clearInterval(timer);
        }
    }, stepTime);
}

function renderCharts(history) {
    const ctx1 = document.getElementById('queriesChart').getContext('2d');
    const ctx2 = document.getElementById('usersChart').getContext('2d');

    // Destroy old if exists
    if (charts.q) charts.q.destroy();
    if (charts.u) charts.u.destroy();

    charts.q = new Chart(ctx1, {
        type: 'line',
        data: {
            labels: history.dates,
            datasets: [{
                label: 'Günlük Sorgular',
                data: history.queries,
                borderColor: '#1da1f2',
                tension: 0.4
            }]
        },
        options: { responsive: true, plugins: { legend: { display: false } } }
    });

    charts.u = new Chart(ctx2, {
        type: 'bar',
        data: {
            labels: history.dates,
            datasets: [{
                label: 'Yeni Kullanıcılar',
                data: history.new_users,
                backgroundColor: '#17bf63'
            }]
        },
        options: { responsive: true, plugins: { legend: { display: false } } }
    });
}
