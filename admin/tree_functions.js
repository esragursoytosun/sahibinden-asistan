/**
 * Hiyerarşik Kategori Ağacı Oluşturma ve Yönetme Fonksiyonları
 */

// Kategorileri hiyerarşik yapıya dönüştürür (category_path üzerinden)
function buildCategoryTree(listings) {
    const tree = {};

    listings.forEach(listing => {
        // category_path örneği: "Vasıta > Otomobil > Renault > Megane"
        // veya bazen null/undefined olabilir.
        if (!listing.category_path) return;

        const parts = listing.category_path.split(' > ').map(p => p.trim());
        let currentLevel = tree;

        parts.forEach((part, index) => {
            if (!currentLevel[part]) {
                currentLevel[part] = {
                    name: part,
                    children: {},
                    count: 0,
                    listings: []
                };
            }

            // O kategorideki ilan sayısını artır
            currentLevel[part].count++;

            // Eğer son seviyeyse ilanı listeye ekle
            if (index === parts.length - 1) {
                currentLevel[part].listings.push(listing);
            }

            // Bir alt seviyeye geç
            currentLevel = currentLevel[part].children;
        });
    });

    return tree;
}

// Ağaç yapısını HTML olarak render eder
function renderCategoryTree(tree, container) {
    if (!container) return;
    container.innerHTML = '';

    const uiList = document.createElement('ul');
    uiList.className = 'tree-list';

    // Kök seviyesindeki kategoriler
    Object.keys(tree).sort().forEach(key => {
        const node = tree[key];
        uiList.appendChild(createTreeNode(node));
    });

    container.appendChild(uiList);
}

// Tek bir ağaç düğümü oluşturur
function createTreeNode(node) {
    const li = document.createElement('li');
    li.className = 'tree-node';

    // Düğüm Başlığı (Klasör/Kategori) -> Tıklanınca açılır/kapanır
    const titleClickable = document.createElement('div');
    titleClickable.className = 'tree-node-title';
    titleClickable.innerHTML = `
        <span class="toggle-icon">▶</span> 
        <span class="folder-icon">📂</span> 
        ${node.name} 
        <span class="badge">${node.count}</span>
    `;

    // Alt içerik konteynerı (gizli başlar)
    const contentDiv = document.createElement('div');
    contentDiv.className = 'tree-node-content';
    contentDiv.style.display = 'none';

    // Tıklama Olayı
    titleClickable.addEventListener('click', (e) => {
        e.stopPropagation(); // Üst tıklamayı engelle
        const isExpanded = contentDiv.style.display === 'block';
        contentDiv.style.display = isExpanded ? 'none' : 'block';
        titleClickable.querySelector('.toggle-icon').textContent = isExpanded ? '▶' : '▼';
        titleClickable.querySelector('.folder-icon').textContent = isExpanded ? '📂' : '📂'; // İstenirse açık klasör ikonu
    });

    li.appendChild(titleClickable);
    li.appendChild(contentDiv);

    // Eğer alt kategoriler (children) varsa onları ekle
    const childKeys = Object.keys(node.children);
    if (childKeys.length > 0) {
        const childUl = document.createElement('ul');
        childUl.className = 'tree-child-list';
        childKeys.sort().forEach(childKey => {
            childUl.appendChild(createTreeNode(node.children[childKey]));
        });
        contentDiv.appendChild(childUl);
    }

    // Eğer bu seviyede direkt ilanlar varsa onları listele
    if (node.listings.length > 0) {
        const listingUl = document.createElement('ul');
        listingUl.className = 'tree-listing-li';

        node.listings.forEach(listing => {
            const itemLi = document.createElement('li');
            itemLi.className = 'tree-listing-item';

            // Fiyat formatlama
            let priceDisplay = "Fiyat Yok";
            if (listing.price) {
                priceDisplay = listing.price.toLocaleString('tr-TR') + " TL";
            } else if (listing.price === 0) {
                priceDisplay = "Fiyat Yok";
            }

            // Düzenle/Sil butonları
            itemLi.innerHTML = `
                <div class="listing-row">
                     <span class="listing-title">📄 <a href="${listing.url}" target="_blank">${listing.title || 'Başlıksız İlan'}</a></span>
                     <span class="listing-price">${priceDisplay}</span>
                     <div class="listing-actions">
                        <button onclick='window.openEditModal(${JSON.stringify(listing)})' class="btn-icon-sm">✏️</button>
                        <button onclick='window.deleteRecord("${listing.id || listing._id}")' class="btn-icon-sm delete">🗑️</button>
                     </div>
                </div>
            `;
            listingUl.appendChild(itemLi);
        });
        contentDiv.appendChild(listingUl);
    }

    return li;
}
