const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor) tg.setHeaderColor('secondary_bg_color');
}

const state = {
    items: [],
    cart: [],
    orders: [], // Массив для заказов
    activeCategory: 'all',
};

function fmtPrice(n) { return `${Number(n).toFixed(0)} ₽`; }
function getUserName() {
    const u = tg?.initDataUnsafe?.user;
    return u?.first_name || 'друг';
}

// ---------- Загрузка меню ----------
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
    const cats = ['all', ...new Set(state.items.map(i => i.category || 'Другое'))];
    const labels = { all: 'Все' };
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
    const filtered = state.activeCategory === 'all'
        ? state.items
        : state.items.filter(i => String(i.category) === String(state.activeCategory));

    filtered.forEach(item => {
        const card = document.createElement('div');
        card.className = 'card';
        // Берем картинку из API, либо ставим заглушку
        const imgSrc = item.image_url || 'https://via.placeholder.com/150';
        
        card.innerHTML = `
            <img src="${imgSrc}" alt="${item.name}">
            <div class="card-body">
                <div class="card-name">${item.name}</div>
                <div class="card-desc">${item.description || ''}</div>
                <div class="card-footer">
                    <span class="card-price">${fmtPrice(item.price)}</span>
                    <button data-id="${item.id}">В корзину</button>
                </div>
            </div>
        `;
        card.querySelector('button').onclick = () => addToCart(item);
        menu.appendChild(card);
    });
}

// ---------- Корзина ----------
function addToCart(item) {
    const existing = state.cart.find(i => i.id === item.id);
    if (existing) existing.qty += 1;
    else state.cart.push({ ...item, qty: 1 });
    if (tg) tg.HapticFeedback?.impactOccurred('light');
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

// ---------- Оформление заказа и Статусы ----------
document.getElementById('checkout-btn').onclick = () => {
    if (state.cart.length === 0) return;
    const total = state.cart.reduce((s, i) => s + i.price * i.qty, 0);
    
    // Создаем заказ
    const newOrder = {
        id: Math.floor(Math.random() * 9000) + 1000,
        items: JSON.parse(JSON.stringify(state.cart)),
        total: total,
        status: 'new'
    };

    state.orders.unshift(newOrder);
    state.cart = [];
    renderCart();
    
    // Переключаемся на вкладку заказов
    switchView('orders');
    
    // Отправляем в Телеграм (чтобы бот прислал сообщение)
    if (tg) {
        tg.sendData(JSON.stringify({ action: 'order', items: newOrder.items, total }));
    } else {
        alert(`Заказ #${newOrder.id} оформлен!`);
    }

    // ЗАПУСКАЕМ СМЕНУ СТАТУСОВ
    simulateStatus(newOrder.id);
};

function simulateStatus(orderId) {
    const statuses = ['new', 'accepted', 'cooking', 'ready', 'picked_up'];
    let step = 0;
    const interval = setInterval(() => {
        step++;
        if (step >= statuses.length) { clearInterval(interval); return; }
        const order = state.orders.find(o => o.id === orderId);
        if (order) {
            order.status = statuses[step];
            renderOrders(state.orders); // Обновляем экран
        }
    }, 5000); // Каждые 5 секунд
}

// ---------- Вкладки и Рендер заказов ----------
const tabMenu = document.getElementById('tab-menu');
const tabOrders = document.getElementById('tab-orders');
if (tabMenu) tabMenu.onclick = () => switchView('menu');
if (tabOrders) tabOrders.onclick = () => switchView('orders');

function switchView(view) {
    const menuSection = document.getElementById('menu');
    const ordersSection = document.getElementById('orders-section');
    
    if (view === 'menu') {
        menuSection.classList.remove('hidden');
        ordersSection.classList.add('hidden');
        tabMenu.classList.add('active');
        tabOrders.classList.remove('active');
    } else {
        menuSection.classList.add('hidden');
        ordersSection.classList.remove('hidden');
        tabMenu.classList.remove('active');
        tabOrders.classList.add('active');
        renderOrders(state.orders);
    }
}

function renderOrders(orders) {
    const list = document.getElementById('orders-list');
    if (!list) return;
    
    if (orders.length === 0) {
        list.innerHTML = '<p>У вас пока нет заказов.</p>';
        return;
    }

    list.innerHTML = orders.map(order => {
        const statusClass = `status-${order.status || 'new'}`;
        const statusLabels = {
            'new': 'Новый', 'accepted': 'Принят', 'cooking': 'Готовится',
            'ready': 'Готов', 'picked_up': 'Выдан'
        };
        
        const itemsHtml = order.items.map(i => `
            <div class="order-item">
                <span>${i.name} × ${i.qty}</span>
                <span>${fmtPrice(i.price * i.qty)}</span>
            </div>
        `).join('');

        return `
            <div class="order-card ${statusClass}">
                <div class="order-header">
                    <span>Заказ #${order.id}</span>
                    <span class="order-status">${statusLabels[order.status] || order.status}</span>
                </div>
                ${itemsHtml}
                <div class="order-item" style="margin-top:8px; font-weight:bold; color: var(--text);">
                    <span>Итого:</span>
                    <span>${fmtPrice(order.total)}</span>
                </div>
            </div>
        `;
    }).join('');
}

// ---------- ИИ-помощник ----------
const aiToggle = document.getElementById('ai-toggle');
const aiPanel  = document.getElementById('ai-panel');
const aiClose  = document.getElementById('ai-close');
const aiForm   = document.getElementById('ai-form');
const aiInput  = document.getElementById('ai-input');
const aiMsgs   = document.getElementById('ai-messages');

if (aiToggle) aiToggle.onclick = () => aiPanel.classList.toggle('hidden');
if (aiClose) aiClose.onclick  = () => aiPanel.classList.add('hidden');

function addMsg(text, from) {
    const div = document.createElement('div');
    div.className = `msg ${from}`;
    div.textContent = text;
    aiMsgs.appendChild(div);
    aiMsgs.scrollTop = aiMsgs.scrollHeight;
    return div;
}

if (aiForm) {
    aiForm.onsubmit = async (e) => {
        e.preventDefault();
        const q = aiInput.value.trim();
        if (!q) return;
        addMsg(q, 'user');
        aiInput.value = '';
        const thinking = addMsg('Шеф думает...', 'bot');

        try {
            const res = await fetch('/api/ai/recommend', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: q, cart: state.cart }),
            });
            const data = await res.json();
            thinking.textContent = data.answer || 'Шеф устал :(';
        } catch (err) {
            thinking.textContent = 'Ошибка связи';
        }
    };
}

// ---------- Старт ----------
document.getElementById('greeting').textContent = `Привет, ${getUserName()}!`;
loadMenu();