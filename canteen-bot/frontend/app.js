const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor) tg.setHeaderColor('secondary_bg_color');
}

const savedFavorites = (() => {
    try { return JSON.parse(localStorage.getItem('canteen_favorites') || '[]'); }
    catch { return []; }
})();
const state = { items: [], cart: [], orders: [], adminItems: [], editingMenuItem: null, role: null, view: 'menu', activeCategory: 'all', favorites: savedFavorites };
const STATUS_LABELS = {
    new: 'Новый', accepted: 'Принят', cooking: 'Готовится', ready: 'Готов',
    picked_up: 'Выдан', cancelled: 'Отменён',
};
const NEXT_STATUSES = {
    new: ['accepted', 'cancelled'], accepted: ['cooking', 'cancelled'],
    cooking: ['ready'], ready: ['picked_up'], picked_up: [], cancelled: [],
};

function fmtPrice(value) { return `${Number(value || 0).toFixed(2).replace(/\.00$/, '')} ₽`; }
function byId(id) { return document.getElementById(id); }
function showMessage(message, kind = 'info') {
    const box = byId('app-message');
    if (!box) return;
    box.textContent = message || '';
    box.className = message ? `message ${kind}` : 'message hidden';
}

async function apiFetch(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (tg?.initData) headers['X-Telegram-Init-Data'] = tg.initData;
    if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, { ...options, headers });
    const raw = await response.text();
    let data = {};
    try { data = raw ? JSON.parse(raw) : {}; } catch { data = { message: raw }; }
    if (!response.ok) throw new Error(data.message || data.error || `Ошибка HTTP ${response.status}`);
    return data;
}

function getUserName() {
    const user = tg?.initDataUnsafe?.user;
    return user?.first_name || 'друг';
}

async function initialize() {
    byId('greeting').textContent = `Привет, ${getUserName()}!`;
    if (!tg?.initData) {
        showMessage('Откройте приложение кнопкой в Telegram, чтобы войти и оформить заказ.', 'warning');
    } else {
        try {
            const data = await apiFetch('/api/me');
            state.role = data.user.role;
            configureTabs();
        } catch (error) {
            showMessage(error.message, 'error');
        }
    }
    await loadMenu();
}

function configureTabs() {
    const staffTab = byId('tab-staff');
    const adminTab = byId('tab-admin-menu');
    if (['staff', 'admin'].includes(state.role)) staffTab.classList.remove('hidden');
    if (state.role === 'admin') adminTab.classList.remove('hidden');
    const roleLabels = { student: 'Студент', staff: 'Сотрудник столовой', admin: 'Администратор' };
    const roleIndicator = byId('role-indicator');
    if (roleIndicator && roleLabels[state.role]) {
        roleIndicator.textContent = `Вы вошли как: ${roleLabels[state.role]}`;
        roleIndicator.classList.remove('hidden');
    }
}

async function loadMenu() {
    try {
        const data = await apiFetch('/api/menu');
        state.items = data.items || [];
        renderCategories();
        renderMenu();
    } catch (error) {
        byId('menu').textContent = 'Не удалось загрузить меню. Проверьте подключение к базе данных.';
        showMessage(error.message, 'error');
    }
}

function renderCategories() {
    const nav = byId('categories');
    if (!nav) return;
    nav.replaceChildren();
    const categories = ['all', 'favorites', ...new Set(state.items.map(item => item.category || 'Другое'))];
    const labels = { all: 'Все', favorites: '❤️ Избранное' };
    for (const category of categories) {
        const button = document.createElement('button');
        button.textContent = labels[category] || category;
        button.classList.toggle('active', state.activeCategory === category);
        button.addEventListener('click', () => {
            state.activeCategory = category;
            renderCategories();
            renderMenu();
        });
        nav.appendChild(button);
    }
}

function renderMenu() {
    const menu = byId('menu');
    menu.replaceChildren();
    const items = state.activeCategory === 'all'
        ? state.items
        : state.activeCategory === 'favorites'
            ? state.items.filter(item => state.favorites.includes(Number(item.id)))
            : state.items.filter(item => item.category === state.activeCategory);
    if (!items.length) {
        menu.textContent = 'В этой категории пока нет блюд.';
        return;
    }
    for (const item of items) {
        const card = document.createElement('article');
        card.className = 'card';
        const image = document.createElement('img');
        image.src = item.image_url || 'https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=150';
        image.alt = item.name;
        image.onerror = () => { image.removeAttribute('src'); };
        const body = document.createElement('div');
        body.className = 'card-body';
        const titleRow = document.createElement('div');
        titleRow.className = 'card-title-row';
        const name = document.createElement('div');
        name.className = 'card-name';
        name.textContent = item.name;
        const favorite = document.createElement('button');
        favorite.type = 'button';
        favorite.className = 'heart-btn';
        favorite.textContent = state.favorites.includes(Number(item.id)) ? '❤️' : '🤍';
        favorite.setAttribute('aria-label', state.favorites.includes(Number(item.id)) ? 'Убрать из избранного' : 'Добавить в избранное');
        favorite.addEventListener('click', () => toggleFavorite(Number(item.id)));
        titleRow.append(name, favorite);
        const description = document.createElement('div');
        description.className = 'card-desc';
        description.textContent = item.description || '';
        const footer = document.createElement('div');
        footer.className = 'card-footer';
        const price = document.createElement('span');
        price.className = 'card-price';
        price.textContent = fmtPrice(item.price);
        const addButton = document.createElement('button');
        addButton.textContent = 'В корзину';
        addButton.addEventListener('click', () => addToCart(item));
        footer.append(price, addButton);
        body.append(titleRow, description, footer);
        card.append(image, body);
        menu.appendChild(card);
    }
}

function toggleFavorite(itemId) {
    state.favorites = state.favorites.includes(itemId)
        ? state.favorites.filter(id => id !== itemId)
        : [...state.favorites, itemId];
    localStorage.setItem('canteen_favorites', JSON.stringify(state.favorites));
    renderMenu();
    renderCategories();
}

function addToCart(item) {
    const existing = state.cart.find(row => row.id === item.id);
    if (existing) existing.qty += 1;
    else state.cart.push({ ...item, qty: 1 });
    tg?.HapticFeedback?.impactOccurred('light');
    renderCart();
}

function renderCart() {
    const cart = byId('cart');
    const list = byId('cart-items');
    list.replaceChildren();
    if (!state.cart.length) {
        cart.classList.add('hidden');
        return;
    }
    cart.classList.remove('hidden');
    const total = state.cart.reduce((sum, row) => sum + Number(row.price) * row.qty, 0);
    for (const row of state.cart) {
        const li = document.createElement('li');
        const label = document.createElement('span');
        label.textContent = `${row.name} × ${row.qty}`;
        const amount = document.createElement('span');
        amount.textContent = fmtPrice(Number(row.price) * row.qty);
        li.append(label, amount);
        list.appendChild(li);
    }
    byId('cart-total').textContent = total.toFixed(2).replace(/\.00$/, '');
}

async function checkout() {
    if (!state.cart.length) return;
    if (!tg?.initData) {
        showMessage('Оформление заказа доступно при запуске приложения из Telegram.', 'warning');
        return;
    }
    const button = byId('checkout-btn');
    button.disabled = true;
    try {
        const result = await apiFetch('/api/orders', {
            method: 'POST',
            body: JSON.stringify({ items: state.cart.map(row => ({ item_id: Number(row.id), quantity: row.qty })) }),
        });
        const order = result.order;
        state.cart = [];
        renderCart();
        showMessage(`Заказ №${order.order_id} создан. Вы №${order.queue_number} в очереди; ожидание примерно ${order.estimated_wait_minutes} мин.`, 'success');
        switchView('orders');
        await loadMyOrders();
    } catch (error) {
        showMessage(error.message, 'error');
    } finally {
        button.disabled = false;
    }
}

function addOrderCard(container, order, { canRepeat = false, canChange = false } = {}) {
    const card = document.createElement('article');
    card.className = `order-card status-${order.status}`;
    const header = document.createElement('div');
    header.className = 'order-header';
    const orderTitle = document.createElement('span');
    orderTitle.textContent = `Заказ №${order.order_id}`;
    const status = document.createElement('span');
    status.className = 'order-status';
    status.textContent = STATUS_LABELS[order.status] || order.status;
    header.append(orderTitle, status);
    card.appendChild(header);
    if (canChange && order.customer_name) {
        const customer = document.createElement('p');
        customer.className = 'order-customer';
        customer.textContent = order.customer_name;
        card.appendChild(customer);
    }
    for (const item of order.items || []) {
        const line = document.createElement('div');
        line.className = 'order-item';
        const itemName = document.createElement('span');
        itemName.textContent = `${item.name} × ${item.quantity}`;
        const lineTotal = document.createElement('span');
        lineTotal.textContent = fmtPrice(item.line_total);
        line.append(itemName, lineTotal);
        card.appendChild(line);
    }
    const total = document.createElement('div');
    total.className = 'order-total';
    total.textContent = `Итого: ${fmtPrice(order.total_amount)}`;
    card.appendChild(total);
    const payment = document.createElement('small');
    payment.className = 'payment-placeholder';
    payment.textContent = 'Оплата через приложение появится позже.';
    card.appendChild(payment);
    if (order.created_at) {
        const created = document.createElement('small');
        created.textContent = new Date(order.created_at).toLocaleString('ru-RU');
        card.appendChild(created);
    }
    if (canRepeat) {
        const repeat = document.createElement('button');
        repeat.textContent = 'Повторить заказ';
        repeat.addEventListener('click', () => repeatOrder(order.order_id));
        card.appendChild(repeat);
    }
    if (canChange) {
        const allowed = NEXT_STATUSES[order.status] || [];
        if (allowed.length) {
            const controls = document.createElement('div');
            controls.className = 'status-controls';
            const select = document.createElement('select');
            for (const value of allowed) {
                const option = document.createElement('option');
                option.value = value;
                option.textContent = STATUS_LABELS[value];
                select.appendChild(option);
            }
            const update = document.createElement('button');
            update.textContent = 'Изменить статус';
            update.addEventListener('click', () => updateStatus(order.order_id, select.value));
            controls.append(select, update);
            card.appendChild(controls);
        }
    }
    container.appendChild(card);
}

async function loadMyOrders() {
    const list = byId('orders-list');
    list.textContent = 'Загрузка заказов…';
    try {
        const data = await apiFetch('/api/my/orders');
        state.orders = data.orders || [];
        list.replaceChildren();
        if (!state.orders.length) list.textContent = 'У вас пока нет заказов.';
        for (const order of state.orders) addOrderCard(list, order, { canRepeat: state.role === 'student' });
    } catch (error) {
        list.textContent = error.message;
    }
}

async function repeatOrder(orderId) {
    try {
        const data = await apiFetch(`/api/my/orders/${orderId}/repeat`, { method: 'POST', body: '{}' });
        showMessage(`Создан повторный заказ №${data.order.order_id}.`, 'success');
        await loadMyOrders();
    } catch (error) {
        showMessage(error.message, 'error');
    }
}

async function loadManagedOrders() {
    const list = byId('staff-orders-list');
    list.textContent = 'Загрузка заказов…';
    const endpoint = state.role === 'admin' ? '/api/admin/orders' : '/api/staff/orders';
    try {
        const data = await apiFetch(endpoint);
        list.replaceChildren();
        const orders = data.orders || [];
        if (!orders.length) list.textContent = 'Активных заказов нет.';
        for (const order of orders) addOrderCard(list, order, { canChange: true });
        if (state.role === 'staff' || state.role === 'admin') await loadQueueForecast();
    } catch (error) {
        list.textContent = error.message;
    }
}

async function loadQueueForecast() {
    const box = byId('queue-forecast');
    try {
        const data = await apiFetch('/api/staff/queue/forecast');
        const mae = data.mae_minutes == null ? 'пока нет данных для MAE' : `MAE ${data.mae_minutes} мин`;
        box.textContent = `Прогноз на ${data.hour}:00 — около ${data.estimated_wait_minutes} мин; ${mae} (${data.training_samples} наблюдений).`;
    } catch (error) {
        box.textContent = error.message;
    }
}

async function updateStatus(orderId, status) {
    try {
        await apiFetch(`/api/staff/orders/${orderId}/status`, {
            method: 'PATCH', body: JSON.stringify({ status }),
        });
        showMessage(`Статус заказа №${orderId} обновлён.`, 'success');
        await loadManagedOrders();
        if (state.role === 'student') await loadMyOrders();
    } catch (error) {
        showMessage(error.message, 'error');
    }
}

async function loadAdminMenu() {
    const list = byId('admin-menu-list');
    list.textContent = 'Загрузка меню…';
    try {
        const data = await apiFetch('/api/admin/menu');
        state.adminItems = data.items || [];
        list.replaceChildren();
        for (const item of state.adminItems) {
            const row = document.createElement('div');
            row.className = 'admin-menu-row';
            const label = document.createElement('span');
            label.textContent = `${item.name} — ${fmtPrice(item.price)}${item.is_available ? '' : ' (снято с продажи)'}`;
            const toggle = document.createElement('button');
            toggle.textContent = item.is_available ? 'Снять с продажи' : 'Вернуть в меню';
            toggle.addEventListener('click', () => saveMenuItem(item, !item.is_available));
            const edit = document.createElement('button');
            edit.textContent = 'Изменить';
            edit.addEventListener('click', () => beginEditMenuItem(item));
            const remove = document.createElement('button');
            remove.textContent = 'Удалить';
            remove.addEventListener('click', () => removeMenuItem(item.id));
            row.append(label, edit, toggle, remove);
            list.appendChild(row);
        }
    } catch (error) {
        list.textContent = error.message;
    }
}

function menuPayloadFromForm(availability = true) {
    return {
        name: byId('menu-name').value.trim(),
        description: byId('menu-description').value.trim(),
        price: byId('menu-price').value,
        category_id: Number(byId('menu-category').value),
        avg_prep_time_mins: Number(byId('menu-prep').value || 5),
        image_url: byId('menu-image').value.trim(),
        is_available: availability,
    };
}

async function saveMenuItem(item, availability = true) {
    try {
        const editing = Boolean(item);
        const payload = item && item._fromForm ? {
            ...menuPayloadFromForm(availability),
        } : item ? {
            name: item.name, description: item.description || '', price: item.price,
            category_id: item.category_id, avg_prep_time_mins: item.avg_prep_time_mins || 5,
            image_url: item.image_url || '', is_available: availability,
        } : menuPayloadFromForm();
        const itemId = editing ? (item.id || state.editingMenuItem?.id) : null;
        await apiFetch(editing ? `/api/admin/menu/${itemId}` : '/api/admin/menu', {
            method: editing ? 'PATCH' : 'POST', body: JSON.stringify(payload),
        });
        byId('admin-menu-form').reset();
        state.editingMenuItem = null;
        byId('admin-menu-submit').textContent = 'Добавить блюдо';
        showMessage('Меню обновлено.', 'success');
        await Promise.all([loadAdminMenu(), loadMenu()]);
    } catch (error) {
        showMessage(error.message, 'error');
    }
}

function beginEditMenuItem(item) {
    state.editingMenuItem = item;
    byId('menu-name').value = item.name || '';
    byId('menu-description').value = item.description || '';
    byId('menu-price').value = item.price;
    byId('menu-category').value = item.category_id;
    byId('menu-prep').value = item.avg_prep_time_mins || 5;
    byId('menu-image').value = item.image_url || '';
    byId('admin-menu-submit').textContent = 'Сохранить изменения';
    switchView('admin-menu');
    byId('menu-name').focus();
}

async function removeMenuItem(itemId) {
    if (!window.confirm('Удалить блюдо? Если оно есть в истории заказов, MySQL не даст удалить запись.')) return;
    try {
        await apiFetch(`/api/admin/menu/${itemId}`, { method: 'DELETE' });
        showMessage('Блюдо удалено.', 'success');
        await Promise.all([loadAdminMenu(), loadMenu()]);
    } catch (error) {
        showMessage(error.message, 'error');
    }
}

function switchView(view) {
    state.view = view;
    for (const section of document.querySelectorAll('[data-section]')) {
        section.classList.toggle('hidden', section.dataset.section !== view);
    }
    for (const button of document.querySelectorAll('[data-view]')) {
        button.classList.toggle('active', button.dataset.view === view);
    }
    byId('categories').classList.toggle('hidden', view !== 'menu');
    byId('cart').classList.toggle('hidden', view !== 'menu' || state.cart.length === 0);
    if (view === 'orders') loadMyOrders();
    if (view === 'staff') loadManagedOrders();
    if (view === 'admin-menu') loadAdminMenu();
}

document.querySelectorAll('[data-view]').forEach(button => {
    button.addEventListener('click', () => switchView(button.dataset.view));
});
byId('checkout-btn').addEventListener('click', checkout);
byId('admin-menu-form').addEventListener('submit', event => {
    event.preventDefault();
    if (state.editingMenuItem) {
        saveMenuItem({ ...state.editingMenuItem, _fromForm: true }, state.editingMenuItem.is_available);
    } else {
        saveMenuItem(null);
    }
});

const aiToggle = byId('ai-toggle');
const aiPanel = byId('ai-panel');
byId('ai-toggle').addEventListener('click', () => aiPanel.classList.toggle('hidden'));
byId('ai-close').addEventListener('click', () => aiPanel.classList.add('hidden'));
function addMessage(text, from) {
    const div = document.createElement('div');
    div.className = `msg ${from}`;
    div.textContent = text;
    byId('ai-messages').appendChild(div);
    byId('ai-messages').scrollTop = byId('ai-messages').scrollHeight;
    return div;
}
byId('ai-form').addEventListener('submit', async event => {
    event.preventDefault();
    const input = byId('ai-input');
    const query = input.value.trim();
    if (!query) return;
    addMessage(query, 'user');
    input.value = '';
    const reply = addMessage('Шеф думает…', 'bot');
    try {
        const data = await apiFetch('/api/ai/recommend', {
            method: 'POST', body: JSON.stringify({ query, cart: state.cart }),
        });
        reply.textContent = data.answer || 'Пока нет рекомендаций.';
    } catch (error) {
        reply.textContent = error.message || 'Ошибка связи';
    }
});

setInterval(() => {
    if (state.view === 'orders') loadMyOrders();
    if (state.view === 'staff') loadManagedOrders();
}, 5000);
initialize();
