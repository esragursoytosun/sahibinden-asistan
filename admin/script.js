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

    if (!email || !key) return showToast('TÃ¼m alanlarÄ± doldurun', 'error');

    loginBtn.innerHTML = 'ğŸ”„ Kontrol ediliyor...';
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
            showToast('GiriÅŸ baÅŸarÄ±lÄ±!', 'success');
            showAdminPanel();
        } else {
            showToast(data.message || 'GiriÅŸ baÅŸarÄ±sÄ±z', 'error');
        }
    } catch (e) {
        showToast('Sunucu hatasÄ±', 'error');
    } finally {
        loginBtn.innerHTML = 'GiriÅŸ Yap';
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
            document.getElementById('lastUpdated').textContent = `Son gÃ¼ncelleme: ${now.toLocaleTimeString()}`;

            // Render Charts
            if (data.charts) {
                renderCharts(data.charts);
            }
        }
    } catch (e) {
        console.error(e);
        showToast('Veriler yÃ¼klenemedi', 'error');
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
                label: 'GÃ¼nlÃ¼k Sorgu',
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
                label: 'Aktif KullanÄ±cÄ±',
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
    tbody.innerHTML = '<tr><td colspan="5" class="text-center">YÃ¼kleniyor...</td></tr>';

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
                tbody.innerHTML = '<tr><td colspan="5" class="text-center">KullanÄ±cÄ± bulunamadÄ±.</td></tr>';
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
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Hata oluÅŸtu.</td></tr>';
    }
}

// ACTIONS
async function togglePlan(userId, currentPlan) {
    const newPlan = currentPlan === 'premium' ? 'free' : 'premium';
    if (!confirm(`KullanÄ±cÄ±yÄ± ${newPlan} paketine geÃ§irmek istiyor musunuz?`)) return;

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
            showToast('Paket gÃ¼ncellendi', 'success');
            loadUsers(1); // Reload table
            loadStats();  // Reload KPIs
        }
    } catch (e) {
        showToast('Ä°ÅŸlem baÅŸarÄ±sÄ±z', 'error');
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
        showToast('Ayarlar yÃ¼klenemedi', 'error');
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
    if (!confirm('Bu iÅŸlemi manuel baÅŸlatmak istediÄŸinize emin misiniz?')) return;

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
        showToast('Ä°ÅŸlem hatasÄ±', 'error');
    }
}

/* DATA INSPECTOR - COMPLETE REWRITE WITH CRUD */
let allListingsData = [];
let currentDbPage = 1;
let totalDbRecords = 0;
const DB_PAGE_LIMIT = 50;
let currentEditId = null;
let currentEditCollection = null;
let currentViewMode = 'table'; // 'table' or 'tree'

// View Mode Switcher
function switchViewMode(mode) {
    currentViewMode = mode;
    const tableBtn = document.getElementById('viewTableBtn');
    const treeBtn = document.getElementById('viewTreeBtn');

    if (mode === 'table') {
        tableBtn.style.background = '#1da1f2';
        tableBtn.style.color = 'white';
        tableBtn.classList.add('active');
        treeBtn.style.background = '#253341';
        treeBtn.style.color = '#8899a6';
        treeBtn.classList.remove('active');
    } else {
        treeBtn.style.background = '#1da1f2';
        treeBtn.style.color = 'white';
        treeBtn.classList.add('active');
        tableBtn.style.background = '#253341';
        tableBtn.style.color = '#8899a6';
        tableBtn.classList.remove('active');
    }

    // Re-render with current data
    const collection = document.getElementById('dbCollectionSelect').value;
    const container = document.getElementById('jsonViewer');

    if (mode === 'tree' && collection === 'listings') {
        renderCategoryTree(allListingsData, container);
    } else {
        const activeFilter = document.querySelector('.filter-btn.active')?.dataset.filter || 'all';
        applyFilter(activeFilter);
    }
}


async function loadDbData(page = 1) {
    currentDbPage = page;
    const collection = document.getElementById('dbCollectionSelect').value;
    const container = document.getElementById('jsonViewer');
    const filterBar = document.getElementById('listingFilters');
    const viewModeToggle = document.getElementById('viewModeToggle');

    // Show/hide filter bar and view toggle based on collection
    filterBar.style.display = collection === 'listings' ? 'block' : 'none';
    if (viewModeToggle) {
        viewModeToggle.style.display = collection === 'listings' ? 'inline-block' : 'none';
    }

    container.innerHTML = '<div class="text-center" style="padding:20px;">Veriler yÃ¼kleniyor...</div>';

    try {
        const res = await fetch(`${API_URL}/admin/db-preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                collection: collection,
                limit: DB_PAGE_LIMIT,
                skip: (page - 1) * DB_PAGE_LIMIT
            })
        });
        const data = await res.json();

        if (data.status === 'success') {
            totalDbRecords = data.total || 0;

            if (!data.data || data.data.length === 0) {
                container.innerHTML = '<div class="text-center" style="padding:20px;">Veri bulunamadÄ±.</div>';
                updatePaginationControls(0, page);
                return;
            }

            allListingsData = data.data;

            // Render based on current view mode
            if (currentViewMode === 'tree' && collection === 'listings') {
                renderCategoryTree(allListingsData, container);
            } else {
                applyFilter('all');
            }

            updatePaginationControls(totalDbRecords, page);

        } else {
            container.innerHTML = `<div class="text-center text-danger" style="padding:20px;">Hata: ${data.message}</div>`;
        }
    } catch (e) {
        container.innerHTML = '<div class="text-center text-danger" style="padding:20px;">BaÄŸlantÄ± hatasÄ±.</div>';
    }
}

function updatePaginationControls(total, page) {
    const totalPages = Math.ceil(total / DB_PAGE_LIMIT);
    const indicator = document.getElementById('dbPageIndicator');
    if (indicator) indicator.textContent = `Sayfa ${page} / ${totalPages || 1} (Toplam: ${total})`;

    const prevBtn = document.getElementById('prevDbPage');
    const nextBtn = document.getElementById('nextDbPage');

    if (prevBtn) {
        prevBtn.disabled = page <= 1;
        prevBtn.onclick = () => loadDbData(page - 1);
    }
    if (nextBtn) {
        nextBtn.disabled = page >= totalPages;
        nextBtn.onclick = () => loadDbData(page + 1);
    }
}

function applyFilter(filterType) {
    const collection = document.getElementById('dbCollectionSelect').value;
    const container = document.getElementById('jsonViewer');

    // Update active button style
    document.querySelectorAll('.filter-btn').forEach(btn => {
        if (btn.dataset.filter === filterType) {
            btn.style.background = '#1da1f2';
            btn.style.color = 'white';
            btn.classList.add('active');
        } else {
            btn.style.background = '#253341';
            btn.style.color = '#8899a6';
            btn.classList.remove('active');
        }
    });

    let filteredData = allListingsData;

    if (collection === 'listings' && filterType !== 'all') {
        filteredData = allListingsData.filter(item => {
            const type = (item.listing_type || '').toLowerCase();
            const category = (item.category_path || '').toLowerCase();

            if (filterType === 'konut') {
                return type.includes('konut') || category.includes('konut') || category.includes('daire') || category.includes('emlak');
            } else if (filterType === 'araba') {
                return type.includes('araba') || type === 'araba' || category.includes('vasÄ±ta') || category.includes('otomobil');
            }
            return true;
        });
    }

    const countEl = document.getElementById('filterCount');
    if (countEl) {
        countEl.textContent = `(${filteredData.length} / ${allListingsData.length} kayÄ±t)`;
    }

    renderDataTable(filteredData, collection, container);
}

// DELETE RECORD
window.deleteRecord = async function (id, collection) {
    if (!confirm("Bu kaydÄ± kalÄ±cÄ± olarak silmek istediÄŸinize emin misiniz?")) return;

    try {
        const res = await fetch(`${API_URL}/admin/delete-record`, {
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
            showToast('KayÄ±t silindi.', 'success');
            loadDbData(currentDbPage); // Reload
        } else {
            showToast(data.message, 'error');
        }
    } catch (e) {
        showToast('Silme hatasÄ±', 'error');
    }
}

// EDIT RECORD
window.openEditModal = function (row, collection) {
    currentEditId = row._id;
    currentEditCollection = collection;

    const form = document.getElementById('editForm');
    form.innerHTML = '';

    const fields = collection === 'listings' ? ['title', 'price', 'year', 'km', 'category_path', 'location'] : ['name', 'email', 'plan'];

    fields.forEach(field => {
        const val = row[field] !== undefined && row[field] !== null ? row[field] : '';
        const displayVal = String(val).replace(/"/g, '&quot;');
        form.innerHTML += `
            <div style="display:flex; flex-direction:column;">
                <label style="color:#8899a6; font-size:11px; margin-bottom:4px;">${field.toUpperCase()}</label>
                <input id="edit_${field}" value="${displayVal}" style="padding:8px; background:#253341; border:1px solid #38444d; color:white; border-radius:4px;">
            </div>
        `;
    });

    document.getElementById('editModal').style.display = 'flex';
}

async function saveEditRecord() {
    const fields = currentEditCollection === 'listings' ? ['title', 'price', 'year', 'km', 'category_path', 'location'] : ['name', 'email', 'plan'];
    const updateData = {};

    fields.forEach(f => {
        let val = document.getElementById(`edit_${f}`).value;
        if ((f === 'price' || f === 'year') && val !== '') val = parseInt(val) || 0;
        updateData[f] = val;
    });

    try {
        const res = await fetch(`${API_URL}/admin/update-record`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_email: currentAdmin.email,
                collection: currentEditCollection,
                id: currentEditId,
                data: updateData
            })
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('BaÅŸarÄ±yla gÃ¼ncellendi.', 'success');
            document.getElementById('editModal').style.display = 'none';
            loadDbData(currentDbPage);
        } else {
            showToast(data.message, 'error');
        }
    } catch (e) {
        showToast('GÃ¼ncelleme hatasÄ±', 'error');
    }
}

function renderDataTable(data, collection, container) {
    let columns = [];

    const formatCategory = (path) => {
        if (!path || path === "TÃ¼mÃ¼" || path === "null") return '<span style="color:#e74c3c;">(BoÅŸ)</span>';
        const parts = path.split(' > ');
        return parts.length > 2 ? `...${parts.slice(-2).join(' > ')}` : path;
    };

    const formatTitle = (row) => {
        let text = row.title ? row.title.trim() : '';
        if (!text && row.category_path) {
            const parts = row.category_path.split(' > ');
            text = parts[parts.length - 1] || 'Ä°lan';
        }
        if (!text) text = `Ä°lan #${row._id}`;

        if (row.url) return `<a href="${row.url}" target="_blank" style="color:#64b5f6;text-decoration:none;font-weight:600;">${text}</a>`;
        return `<span style="color:#e0e0e0;font-weight:600;">${text}</span>`;
    };

    if (collection === 'listings') {
        columns = [
            { key: 'title', label: 'BaÅŸlÄ±k', render: (val, row) => formatTitle(row) },
            {
                key: 'price', label: 'Fiyat', render: val => {
                    if (!val || val === 0) return '<span style="color:#e74c3c;">Fiyat Yok</span>';
                    return `<span style="color:#00e676;font-weight:bold;">${val.toLocaleString('tr-TR')} TL</span>`;
                }
            },
            { key: 'category_path', label: 'Kategori', render: val => `<span style="font-size:11px;color:#aaa;">${formatCategory(val)}</span>` },
            { key: 'location', label: 'Konum', render: val => `<span style="font-size:11px;">${val || '-'}</span>` },
            { key: 'year', label: 'YÄ±l/Km', render: (val, row) => `<span style="font-size:11px;">${row.year || '-'} / ${row.km || '-'}</span>` }
        ];
    } else if (collection === 'users') {
        columns = [
            {
                key: 'name', label: 'Ä°sim', render: (val, row) => `
                <div style="display:flex;align-items:center;gap:8px;">
                    <img src="${row.picture || ''}" style="width:24px;height:24px;border-radius:50%;">
                    <span>${val}</span>
                </div>`
            },
            { key: 'email', label: 'E-posta' },
            { key: 'plan', label: 'Paket', render: val => `<span class="badge ${val}">${val}</span>` },
            { key: 'daily_usage', label: 'KullanÄ±m' }
        ];
    } else {
        const keys = Object.keys(data[0] || {}).filter(k => k !== '_id' && typeof data[0][k] !== 'object');
        columns = keys.slice(0, 5).map(k => ({ key: k, label: k.charAt(0).toUpperCase() + k.slice(1) }));
    }

    let html = `
        <table class="data-table" style="width:100%; border-collapse: separate; border-spacing: 0 4px;">
            <thead>
                <tr style="text-align:left; color:#8899a6; font-size:12px;">
                    ${columns.map(col => `<th style="padding:10px;">${col.label}</th>`).join('')}
                    <th style="padding:10px; text-align:right;">Ä°ÅŸlem</th>
                </tr>
            </thead>
            <tbody>
                ${data.map(row => {
        const rowJson = JSON.stringify(row).replace(/'/g, "&#39;").replace(/"/g, '&quot;');
        return `
                    <tr style="background:#192734; transition:background 0.2s;">
                        ${columns.map(col => {
            const val = row[col.key];
            return `<td style="padding:10px; border-top:1px solid #253341; border-bottom:1px solid #253341;">${col.render ? col.render(val, row) : (val || '-')}</td>`;
        }).join('')}
                        <td style="padding:10px; text-align:right; border-top:1px solid #253341; border-bottom:1px solid #253341; width:90px;">
                             <button class="btn-sm" onclick='openEditModal(JSON.parse("${rowJson}"), "${collection}");' style="font-size:10px; padding:4px 8px; background:#1da1f2; border:none; color:white; cursor:pointer; border-radius:4px; margin-right:5px;">
                                âœï¸
                            </button>
                            <button class="btn-sm" onclick='deleteRecord("${row._id}", "${collection}")' style="font-size:10px; padding:4px 8px; background:#e74c3c; border:none; color:white; cursor:pointer; border-radius:4px;">
                                ğŸ—‘ï¸
                            </button>
                        </td>
                    </tr>
                `;
    }).join('')}
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

// Category Tree Rendering
function renderCategoryTree(data, container) {
    const tree = {};

    data.forEach(item => {
        const path = item.category_path || 'Kategorisiz';
        if (!tree[path]) {
            tree[path] = [];
        }
        tree[path].push(item);
    });

    const sortedCategories = Object.keys(tree).sort();

    let html = '<div class="category-tree" style="font-family:sans-serif;">';

    sortedCategories.forEach((category, index) => {
        const items = tree[category];
        const categoryId = `cat-${index}`;
        const isFirst = index === 0;

        html += `
            <div class="category-folder" style="margin-bottom:8px; border:1px solid #38444d; border-radius:8px; overflow:hidden; background:#192734;">
                <div class="category-header" onclick="toggleCategory('${categoryId}')" style="padding:12px 15px; background:#253341; cursor:pointer; display:flex; justify-content:space-between; align-items:center; user-select:none;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span class="arrow" id="arrow-${categoryId}" style="font-size:12px; color:#8899a6; transition:transform 0.2s;">${isFirst ? 'â–¼' : 'â–¶'}</span>
                        <span style="font-size:13px; font-weight:600; color:#fff;">ğŸ“ ${category}</span>
                    </div>
                    <span class="count-badge" style="background:#1da1f2; color:white; padding:4px 10px; border-radius:12px; font-size:11px; font-weight:bold;">${items.length}</span>
                </div>
                <div class="category-content" id="content-${categoryId}" style="max-height:${isFirst ? '400px' : '0'}; overflow:hidden; transition:max-height 0.3s ease;">
                    <div style="padding:10px;">
                        ${renderCategoryItems(items, category)}
                    </div>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

function renderCategoryItems(items, category) {
    return items.map(item => {
        const price = item.price ? `<span style="color:#00e676;font-weight:bold;">${item.price.toLocaleString('tr-TR')} TL</span>` : '<span style="color:#e74c3c;">Fiyat Yok</span>';
        const title = item.title || item.id || 'Ä°lan';
        const itemJson = JSON.stringify(item).replace(/'/g, "&#39;").replace(/"/g, '&quot;');

        return `
            <div style="padding:8px; margin-bottom:4px; background:#15202b; border-radius:6px; border-left:3px solid #1da1f2; display:flex; justify-content:space-between; align-items:center;">
                <div style="flex:1;">
                    <div style="font-size:12px; font-weight:600; color:#e0e0e0; margin-bottom:4px;">
                        ${item.url ? `<a href="${item.url}" target="_blank" style="color:#64b5f6;text-decoration:none;">${title}</a>` : title}
                    </div>
                    <div style="font-size:11px; color:#8899a6;">
                        ${price} ${item.location ? `â€¢ ${item.location}` : ''} ${item.year ? `â€¢ ${item.year}` : ''} ${item.km ? `â€¢ ${item.km} km` : ''}
                    </div>
                </div>
                <div style="display:flex; gap:5px;">
                    <button onclick='openEditModal(JSON.parse("${itemJson}"), "listings");' style="font-size:10px; padding:4px 8px; background:#1da1f2; border:none; color:white; cursor:pointer; border-radius:4px;">âœï¸</button>
                    <button onclick='deleteRecord("${item._id}", "listings")' style="font-size:10px; padding:4px 8px; background:#e74c3c; border:none; color:white; cursor:pointer; border-radius:4px;">ğŸ—‘ï¸</button>
                </div>
            </div>
        `;
    }).join('');
}

window.toggleCategory = function (categoryId) {
    const content = document.getElementById(`content-${categoryId}`);
    const arrow = document.getElementById(`arrow-${categoryId}`);

    if (content.style.maxHeight === '0px' || content.style.maxHeight === '') {
        content.style.maxHeight = '400px';
        arrow.textContent = 'â–¼';
    } else {
        content.style.maxHeight = '0';
        arrow.textContent = 'â–¶';
    }
}
