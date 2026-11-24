const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
}

const state = {
    items: [],
    cart: [],
    orders: JSON.parse(localStorage.getItem('canteen_orders')) || [],
    stopList: JSON.parse(localStorage.getItem('canteen_stoplist')) || [],
    favorites: JSON.parse(localStorage.getItem('canteen_favorites')) || [],
    activeCategory: 'all',
    role: 'student',
};

function fmtPrice(n) { return `${Number(n).toFixed(0)} ₽`; }
function getUserName() { return tg?.initDataUnsafe?.user?.first_name || 'друг'; }

// Переключение ролей
const roleBtn = document.getElementById('role-toggle');
roleBtn.onclick = () => {
    if (state.role === 'student') {
        state.role = 'worker';
        roleBtn.textContent = 'Я студент';
        document.getElementById('tab-admin').classList.remove('hidden');
        switchView('admin');
    } else {
        state.role = 'student';
        roleBtn.textContent = 'Я сотрудник';
        document.getElementById('tab-admin').classList.add('hidden');
        switchView('menu');
    }
    renderMenu();
};

async function loadMenu() {
    try {
        const res = await fetch('/api/menu');
        const data = await res.json();
        state.items = data.items || [];
        renderCategories();
        renderMenu();
    } catch (err) {
        document.getElementById('menu').textContent = 'Ошибка загрузки меню';
    }
}

function renderCategories() {
    const cats = ['all', 'favorites', ...new Set(state.items.map(i => i.category || 'Другое'))];
    const labels = { all: 'Все', favorites: '❤️ Избранное' };
    const nav = document.getElementById('categories');
    if (!nav) return;
    nav.innerHTML = '';
    cats.forEach(cat => {
        const btn = document.createElement('button');
        btn.textContent = labels[cat] || cat;
        btn.className = state.activeCategory === cat ? 'active' : '';
        btn.onclick = () => {
            state.activeCategory = cat;
            renderCategories();
            renderMenu();
        };
        nav.appendChild(btn);
    });
}

function renderMenu() {
    const menu = document.getElementById('menu');
    if (!menu) return;
    menu.innerHTML = '';
    
    let filtered = state.items;
    if (state.activeCategory === 'favorites') {
        filtered = filtered.filter(i => state.favorites.includes(i.id));
    } else if (state.activeCategory !== 'all') {
        filtered = filtered.filter(i => String(i.category) === String(state.activeCategory));
    }

    // МЫ УБРАЛИ ФИЛЬТРАЦИЮ СТОП-ЛИСТА ДЛЯ СТУДЕНТОВ. Теперь они видят всё.

    filtered.forEach(item => {
        const card = document.createElement('div');
        card.className = 'card';
        
        const isStopped = state.stopList.includes(item.id);
        const imgSrc = item.image_url || 'https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=150';
        const isFavorite = state.favorites.includes(item.id);
        
        // Если блюдо в стоп-листе, делаем карточку серой
        if (isStopped) {
            card.classList.add('out-of-stock');
        }

        let stopBtnHtml = '';
        if (state.role === 'worker') {
            stopBtnHtml = `<button class="stop-btn" data-id="${item.id}" style="background: ${isStopped ? '#e74c3c' : '#f39c12'};">
                ${isStopped ? 'Вернуть' : 'В стоп'}
            </button>`;
        }

        // Кнопка "В корзину" или "Нет в наличии"
        let cartBtnHtml = '';
        if (isStopped) {
            cartBtnHtml = `<button class="add-to-cart-btn disabled" disabled>Нет в наличии</button>`;
        } else {
            cartBtnHtml = `<button class="add-to-cart-btn" data-id="${item.id}">В корзину</button>`;
        }

        card.innerHTML = `
            <img src="${imgSrc}" onerror="this.src='https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=150'" alt="${item.name}">
            <div class="card-body">
                <div class="card-title-row">
                    <div>
                        <div class="card-name">${item.name}</div>
                        <div class="card-desc">${item.description || ''}</div>
                    </div>
                    <button class="heart-btn" data-id="${item.id}">
                        ${isFavorite ? '❤️' : '🤍'}
                    </button>
                </div>
                <div class="card-footer">
                    <span class="card-price">${fmtPrice(item.price)}</span>
                    <div style="display:flex; gap: 8px; align-items:center;">
                        ${stopBtnHtml}
                        ${cartBtnHtml}
                    </div>
                </div>
            </div>
        `;
        
        // Обработчик добавления в корзину (только если не в стоп-листе)
        const addBtn = card.querySelector('.add-to-cart-btn');
        if (!isStopped) {
            addBtn.onclick = () => addToCart(item);
        }

        card.querySelector('.heart-btn').onclick = () => toggleFavorite(item.id);
        if (state.role === 'worker') {
            card.querySelector('.stop-btn').onclick = () => toggleStopList(item.id);
        }
        
        menu.appendChild(card);
    });
}

function toggleFavorite(itemId) {
    if (state.favorites.includes(itemId)) {
        state.favorites = state.favorites.filter(id => id !== itemId);
    } else {
        state.favorites.push(itemId);
    }
    localStorage.setItem('canteen_favorites', JSON.stringify(state.favorites));
    renderMenu();
}

function toggleStopList(itemId) {
    if (state.stopList.includes(itemId)) {
        state.stopList = state.stopList.filter(id => id !== itemId);
    } else {
        state.stopList.push(itemId);
    }
    localStorage.setItem('canteen_stoplist', JSON.stringify(state.stopList));
    renderMenu();
}

function addToCart(item) {
    const existing = state.cart.find(i => i.id === item.id);
    if (existing) existing.qty += 1;
    else state.cart.push({ ...item, qty: 1 });
    renderCart();
}

function renderCart() {
    const cart = document.getElementById('cart');
    const list = document.getElementById('cart-items');
    const total = document.getElementById('cart-total');
    if (!cart) return;

    if (state.cart.length === 0) {
        cart.classList.add('hidden');
        return;
    }
    cart.classList.remove('hidden');
    list.innerHTML = '';
    let sum = 0;
    state.cart.forEach(ci => {
        sum += ci.price * ci.qty;
        const li = document.createElement('li');
        li.innerHTML = `<span>${ci.name} × ${ci.qty}</span><span>${fmtPrice(ci.price * ci.qty)}</span>`;
        list.appendChild(li);
    });
    total.textContent = sum.toFixed(0);
}

document.getElementById('checkout-btn').onclick = () => {
    if (state.cart.length === 0) return;
    const total = state.cart.reduce((s, i) => s + i.price * i.qty, 0);
    
    const newOrder = {
        id: Math.floor(Math.random() * 9000) + 1000,
        items: JSON.parse(JSON.stringify(state.cart)),
        total: total,
        status: 'new',
        date: new Date().toLocaleString('ru-RU')
    };

    state.orders.unshift(newOrder);
    localStorage.setItem('canteen_orders', JSON.stringify(state.orders));

    state.cart = [];
    renderCart();
    switchView('orders');
    if (tg) tg.showAlert(`Заказ #${newOrder.id} оформлен!`);
    
    // ВОТ ЭТА СТРОЧКА ЗАПУСКАЕТ СМЕНУ СТАТУСОВ!
    simulateStatus(newOrder.id); 
};
// Функция смены статусов по таймеру
function simulateStatus(orderId) {
    // Расписание: через сколько секунд какой статус поставить
    const timeline = [
        { status: 'accepted', delay: 5000 },    // Через 5 сек - Принят
        { status: 'cooking', delay: 10000 },    // Через 10 сек - Готовится
        { status: 'ready', delay: 15000 },      // Через 15 сек - Готов
        { status: 'picked_up', delay: 25000 }   // Через 25 сек (15+10) - Выдан
    ];

    timeline.forEach(item => {
        setTimeout(() => {
            const order = state.orders.find(o => o.id === orderId);
            if (order && order.status !== 'picked_up') {
                order.status = item.status;
                localStorage.setItem('canteen_orders', JSON.stringify(state.orders));
                
                // Перерисовываем экраны, если они открыты
                if (!document.getElementById('orders-section').classList.contains('hidden')) {
                    renderOrders(state.orders);
                }
                if (!document.getElementById('admin-section').classList.contains('hidden')) {
                    renderAdminOrders();
                }
            }
        }, item.delay);
    });
}
document.getElementById('tab-menu').onclick = () => switchView('menu');
document.getElementById('tab-orders').onclick = () => switchView('orders');
document.getElementById('tab-admin').onclick = () => switchView('admin');

function switchView(view) {
    const menuSection = document.getElementById('menu');
    const ordersSection = document.getElementById('orders-section');
    const adminSection = document.getElementById('admin-section');
    const tabMenu = document.getElementById('tab-menu');
    const tabOrders = document.getElementById('tab-orders');
    const tabAdmin = document.getElementById('tab-admin');
    
    menuSection.classList.add('hidden');
    ordersSection.classList.add('hidden');
    adminSection.classList.add('hidden');
    tabMenu.classList.remove('active');
    tabOrders.classList.remove('active');
    tabAdmin.classList.remove('active');
    
    if (view === 'menu') {
        menuSection.classList.remove('hidden');
        tabMenu.classList.add('active');
    } else if (view === 'orders') {
        ordersSection.classList.remove('hidden');
        tabOrders.classList.add('active');
        renderOrders(state.orders);
    } else if (view === 'admin') {
        adminSection.classList.remove('hidden');
        tabAdmin.classList.add('active');
        renderAdminOrders();
    }
}

function renderOrders(orders) {
    const list = document.getElementById('orders-list');
    if (!list) return;
    if (orders.length === 0) { list.innerHTML = '<p>У вас пока нет заказов.</p>'; return; }

    list.innerHTML = orders.map(order => {
        const statusMap = {
            'new': { label: 'Новый', class: 'dot-new' },
            'accepted': { label: 'Принят', class: 'dot-accepted' },
            'cooking': { label: 'Готовится', class: 'dot-cooking' },
            'ready': { label: 'Готов', class: 'dot-ready' },
            'picked_up': { label: 'Выдан', class: 'dot-picked_up' }
        };
        const currentStatus = statusMap[order.status] || statusMap['new'];
        const itemsHtml = order.items.map(i => `<div class="order-item"><span>${i.name} × ${i.qty}</span><span>${fmtPrice(i.price * i.qty)}</span></div>`).join('');

        return `
            <div class="order-card">
                 <div class="order-card ${order.status === 'picked_up' ? 'order-completed' : ''}">
                    <span>Заказ #${order.id} <br><small style="font-weight:normal; color:var(--hint); font-size:12px;">${order.date}</small></span>
                    <div class="order-status"><span class="status-dot ${currentStatus.class}"></span>${currentStatus.label}</div>
                </div>
                ${itemsHtml}
                <div class="order-item" style="margin-top:12px; font-weight:bold; color: var(--text); font-size: 15px;"><span>Итого:</span><span>${fmtPrice(order.total)}</span></div>
                <button class="repeat-btn" data-order-id="${order.id}">Повторить заказ</button>
            </div>
        `;
    }).join('');

    document.querySelectorAll('.repeat-btn').forEach(btn => {
        btn.onclick = () => {
            const orderId = Number(btn.dataset.orderId);
            const order = state.orders.find(o => o.id === orderId);
            if (order) {
                state.cart = JSON.parse(JSON.stringify(order.items));
                renderCart();
                switchView('menu');
                if (tg) tg.showAlert('Блюда добавлены в корзину!');
            }
        };
    });
}

function renderAdminOrders() {
    const list = document.getElementById('admin-orders-list');
    if (!list) return;
    if (state.orders.length === 0) { list.innerHTML = '<p>Заказов нет.</p>'; return; }

    list.innerHTML = state.orders.map(order => {
        const itemsHtml = order.items.map(i => `<div class="order-item"><span>${i.name} × ${i.qty}</span></div>`).join('');
        const statusOptions = [
            { val: 'new', label: 'Новый' }, { val: 'accepted', label: 'Принят' },
            { val: 'cooking', label: 'Готовится' }, { val: 'ready', label: 'Готов' }, { val: 'picked_up', label: 'Выдан' }
        ];
        const selectHtml = `<select class="status-select" data-order-id="${order.id}">${statusOptions.map(opt => `<option value="${opt.val}" ${order.status === opt.val ? 'selected' : ''}>${opt.label}</option>`).join('')}</select>`;

        return `
            <div class="order-card" style="border-left: 4px solid #e74c3c;">
                <div class="order-header"><span>Заказ #${order.id}</span><span>${order.total} ₽</span></div>
                ${itemsHtml}
                <div style="margin-top: 10px;"><label style="font-size: 12px; color: var(--hint);">Изменить статус:</label>${selectHtml}</div>
            </div>
        `;
    }).join('');

    document.querySelectorAll('.status-select').forEach(select => {
        select.onchange = (e) => {
            const orderId = Number(e.target.dataset.orderId);
            const order = state.orders.find(o => o.id === orderId);
            if (order) {
                order.status = e.target.value;
                localStorage.setItem('canteen_orders', JSON.stringify(state.orders));
            }
        };
    });
}

// Старт
document.getElementById('greeting').textContent = `Привет, ${getUserName()}!`;
loadMenu();