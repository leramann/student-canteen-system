const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor) tg.setHeaderColor('secondary_bg_color');
}

const state = {
    items: [],
    cart: [],
    activeCategory: 'all',
};

// ---------- Утилиты ----------
function fmtPrice(n) { return `${Number(n).toFixed(0)} ₽`; }

function getUserName() {
    const u = tg?.initDataUnsafe?.user;
    return u?.first_name || 'друг';
}

// Красивые картинки (если нет своей, берем по названию)
function getDishImage(name) {
    const n = name.toLowerCase();
    if (n.includes('борщ')) return 'https://images.pexels.com/photos/13015498/pexels-photo-13015498.jpeg?auto=compress&cs=tinysrgb&w=200&h=200&fit=crop';
    if (n.includes('плов')) return 'https://images.pexels.com/photos/12737657/pexels-photo-12737657.jpeg?auto=compress&cs=tinysrgb&w=200&h=200&fit=crop';
    if (n.includes('котлета')) return 'https://images.pexels.com/photos/12419160/pexels-photo-12419160.jpeg?auto=compress&cs=tinysrgb&w=200&h=200&fit=crop';
    if (n.includes('компот') || n.includes('чай')) return 'https://images.pexels.com/photos/128865/pexels-photo-128865.jpeg?auto=compress&cs=tinysrgb&w=200&h=200&fit=crop';
    // Если блюдо не найдено, ставим общую красивую картинку
    return 'https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=200&h=200&fit=crop'; 
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
        document.getElementById('menu').textContent = 'Ошибка загрузки меню: ' + err.message;
    }
}

function renderCategories() {
    const cats = ['all', ...new Set(state.items.map(i => i.category || 'Другое'))];
    const labels = { all: 'Всё' };
    const nav = document.getElementById('categories');
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
    menu.innerHTML = '';
    const filtered = state.activeCategory === 'all'
        ? state.items
        : state.items.filter(i => String(i.category) === String(state.activeCategory));

    filtered.forEach(item => {
        const card = document.createElement('div');
        card.className = 'card';
        const imgSrc = item.image_url || getDishImage(item.name);
        
        card.innerHTML = `
            <img src="${imgSrc}" alt="${item.name}" onerror="this.src='https://images.unsplash.com/photo-1498837167922-ddd27525d352?w=200&h=200&fit=crop'">
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
    const order = state.cart.map(i => `${i.name} × ${i.qty}`).join('\n');
    const total = state.cart.reduce((s, i) => s + i.price * i.qty, 0);
    if (tg) {
        tg.sendData(JSON.stringify({ action: 'order', items: state.cart, total }));
        tg.close();
    } else {
        alert(`Заказ:\n${order}\n\nИтого: ${total} ₽`);
    }
};

// ---------- ИИ-помощник (Шеф-повар) ----------
const aiToggle = document.getElementById('ai-toggle');
const aiPanel  = document.getElementById('ai-panel');
const aiClose  = document.getElementById('ai-close');
const aiForm   = document.getElementById('ai-form');
const aiInput  = document.getElementById('ai-input');
const aiMsgs   = document.getElementById('ai-messages');

aiToggle.onclick = () => aiPanel.classList.toggle('hidden');
aiClose.onclick  = () => aiPanel.classList.add('hidden');

function addMsg(text, from) {
    const div = document.createElement('div');
    div.className = `msg ${from}`;
    div.textContent = text;
    aiMsgs.appendChild(div);
    aiMsgs.scrollTop = aiMsgs.scrollHeight;
    return div;
}

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
        thinking.textContent = data.answer || data.error || 'Шеф устал, попробуйте позже :(';
    } catch (err) {
        thinking.textContent = 'Ошибка связи с шефом: ' + err.message;
    }
};

// ---------- Старт ----------
document.getElementById('greeting').textContent = `Привет, ${getUserName()}!`;
loadMenu();