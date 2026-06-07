"use strict";

// ---------------------------------------------------------------------------
// Состояние и утилиты
// ---------------------------------------------------------------------------
const state = {
  user: null,
  page: "suppliers",
  suppliers: [],
  orders: [],
  fruits: [],
};

const POLL_MS = 15000; // автообновление каждые 15 секунд (polling)
let pollTimer = null;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (res.status === 401) { showLogin(); throw new Error("Не авторизован"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Ошибка запроса");
  return data;
}

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("ru-RU", { maximumFractionDigits: 2 }));
const fmtDate = (iso) => { if (!iso) return "—"; const [y,m,d]=iso.split("-"); return `${d}.${m}.${y}`; };

function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg; t.classList.toggle("err", isErr); t.hidden = false;
  clearTimeout(t._t); t._t = setTimeout(() => (t.hidden = true), 2600);
}

// ---------------------------------------------------------------------------
// Авторизация
// ---------------------------------------------------------------------------
function showLogin() {
  stopPolling();
  state.user = null;
  $("#app").hidden = true;
  $("#login-screen").hidden = false;
}

async function doLogin(username, password) {
  const err = $("#login-error");
  err.hidden = true;
  try {
    state.user = await api("/api/login", { method: "POST", body: JSON.stringify({ username, password }) });
    enterApp();
  } catch (e) {
    err.textContent = e.message; err.hidden = false;
  }
}

async function bootstrap() {
  try {
    state.user = await api("/api/me");
    enterApp();
  } catch {
    showLogin();
  }
}

function enterApp() {
  $("#login-screen").hidden = true;
  $("#app").hidden = false;
  $("#user-name").textContent = state.user.full_name;
  $("#user-role").textContent = state.user.role_label;
  buildTabs();
  // Выбрать первую доступную страницу.
  const order = ["suppliers", "orders", "finance", "audit"];
  state.page = order.find((p) => tabVisible(p)) || "suppliers";
  switchPage(state.page);
  startPolling();
}

// ---------------------------------------------------------------------------
// Навигация по ролям
// ---------------------------------------------------------------------------
function tabVisible(page) {
  const p = state.user.perms;
  if (page === "suppliers") return p.suppliers !== "none";
  if (page === "orders")    return p.orders !== "none";
  if (page === "finance")   return p.finance !== "none";
  if (page === "audit")     return state.user.role === "director";
  return false;
}

const TAB_LABELS = { suppliers: "Поставщики", orders: "Заказы", finance: "Финансы", audit: "История" };

function buildTabs() {
  const nav = $("#tabs");
  nav.innerHTML = "";
  ["suppliers", "orders", "finance", "audit"].forEach((page) => {
    if (!tabVisible(page)) return;
    const b = document.createElement("button");
    b.className = "tab"; b.textContent = TAB_LABELS[page]; b.dataset.page = page;
    b.onclick = () => switchPage(page);
    nav.appendChild(b);
  });
}

function switchPage(page) {
  state.page = page;
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.page === page));
  $$(".page").forEach((p) => (p.hidden = true));
  $(`#page-${page}`).hidden = false;
  refresh();
}

// ---------------------------------------------------------------------------
// Загрузка данных (используется и при polling)
// ---------------------------------------------------------------------------
async function refresh() {
  const p = state.user.perms;
  try {
    if (state.page === "suppliers") {
      state.suppliers = await api("/api/suppliers");
      renderSuppliers();
    } else if (state.page === "orders") {
      [state.orders, state.fruits, state.suppliers] = await Promise.all([
        api("/api/orders"),
        api("/api/fruits"),
        p.suppliers !== "none" ? api("/api/suppliers") : Promise.resolve(state.suppliers),
      ]);
      renderOrders();
    } else if (state.page === "finance") {
      renderFinance(await api("/api/finance"));
    } else if (state.page === "audit") {
      renderAudit(await api("/api/audit"));
    }
    markSync();
  } catch (e) {
    if (e.message !== "Не авторизован") toast(e.message, true);
  }
}

function markSync() {
  const now = new Date();
  $("#sync-time").textContent = now.toLocaleTimeString("ru-RU");
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(refresh, POLL_MS);
}
function stopPolling() { if (pollTimer) clearInterval(pollTimer); pollTimer = null; }

// ---------------------------------------------------------------------------
// Рендер: Поставщики
// ---------------------------------------------------------------------------
function renderSuppliers() {
  const canWrite = state.user.perms.suppliers === "write";
  $("#add-supplier").hidden = !canWrite;
  const tb = $("#suppliers-table tbody");
  tb.innerHTML = "";
  state.suppliers.forEach((s) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="muted">${s.id}</td>
      <td>${esc(s.fruit)}</td>
      <td class="num">${fmt(s.purchase_price)}</td>
      <td class="num">${fmt(s.stock)}</td>
      <td>${esc(s.name)}</td>
      <td class="num">${s.delivery_days}</td>
      <td class="actions-col">${canWrite ? `
        <div class="row-actions">
          <button class="btn btn-ghost btn-sm" data-edit="${s.id}">Изм.</button>
          <button class="btn btn-danger btn-sm" data-del="${s.id}">Удал.</button>
        </div>` : ""}</td>`;
    tb.appendChild(tr);
  });
  if (canWrite) {
    tb.querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => openSupplierForm(+b.dataset.edit));
    tb.querySelectorAll("[data-del]").forEach((b) => b.onclick = () => deleteSupplier(+b.dataset.del));
  }
}

// ---------------------------------------------------------------------------
// Рендер: Заказы
// ---------------------------------------------------------------------------
function renderOrders() {
  const canWrite = state.user.perms.orders === "write";
  $("#add-order").hidden = !canWrite;
  const tb = $("#orders-table tbody");
  tb.innerHTML = "";
  state.orders.forEach((o) => {
    const matched = o.status === "Подобран поставщик";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="muted">${o.id}</td>
      <td>${esc(o.restaurant)}</td>
      <td>${esc(o.fruit)}</td>
      <td class="num">${fmt(o.quantity)}</td>
      <td class="num">${o.sale_price != null ? fmt(o.sale_price) : "—"}</td>
      <td class="num">${o.order_sum != null ? fmt(o.order_sum) : "—"}</td>
      <td>${fmtDate(o.order_date)}</td>
      <td>${fmtDate(o.client_due_date)}</td>
      <td>${o.supplier_name ? esc(o.supplier_name) : '<span class="muted">—</span>'}</td>
      <td><span class="status ${matched ? "ok" : "manual"}" ${o.reason ? `title="${esc(o.reason)}"` : ""}>${esc(o.status)}</span></td>
      <td class="actions-col">${canWrite ? `
        <div class="row-actions">
          <button class="btn btn-ghost btn-sm" data-edit="${o.id}">Изм.</button>
          <button class="btn btn-danger btn-sm" data-del="${o.id}">Удал.</button>
        </div>` : ""}</td>`;
    tb.appendChild(tr);
  });
  if (canWrite) {
    tb.querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => openOrderForm(+b.dataset.edit));
    tb.querySelectorAll("[data-del]").forEach((b) => b.onclick = () => deleteOrder(+b.dataset.del));
  }
}

// ---------------------------------------------------------------------------
// Рендер: Финансы
// ---------------------------------------------------------------------------
function renderFinance(data) {
  const cards = $("#finance-cards");
  const breakdowns = $("#finance-breakdowns");
  cards.innerHTML = ""; breakdowns.innerHTML = "";

  if (data.scope === "full") {
    $("#finance-sub").textContent = "Общая финансовая сводка компании.";
    cards.innerHTML = `
      <div class="card accent">
        <div class="card-label">Общая выручка</div>
        <div class="card-value">${fmt(data.total_revenue)} ₸</div>
      </div>
      <div class="card amber">
        <div class="card-label">Общая прибыль</div>
        <div class="card-value">${fmt(data.total_profit)} ₸</div>
      </div>
      <div class="card">
        <div class="card-label">Закрытых заказов</div>
        <div class="card-value">${data.orders_count}</div>
      </div>`;
    breakdowns.innerHTML = `
      <div class="breakdown">${renderBars("Прибыль по фруктам", data.by_fruit)}</div>
      <div class="breakdown">${renderBars("Прибыль по клиентам", data.by_client)}</div>`;
  } else {
    // Менеджер: только финансы по заказам, без общей сводки компании.
    $("#finance-sub").textContent = "Финансы по вашим заказам. Общая сводка компании доступна руководителю.";
  }

  const tb = $("#finance-orders-table tbody");
  tb.innerHTML = "";
  (data.per_order || []).forEach((o) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="muted">${o.id}</td><td>${esc(o.restaurant)}</td><td>${esc(o.fruit)}</td>
      <td class="num">${fmt(o.quantity)}</td><td class="num">${fmt(o.revenue)}</td><td class="num">${fmt(o.profit)}</td>`;
    tb.appendChild(tr);
  });
}

function renderBars(title, rows) {
  if (!rows || !rows.length) return `<h3>${title}</h3><p class="muted">Нет данных.</p>`;
  const max = Math.max(...rows.map((r) => r.profit), 1);
  const bars = rows.map((r) => `
    <div class="bar-row">
      <span>${esc(r.key)}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${Math.max(4, (r.profit / max) * 100)}%"></span></span>
      <span class="val">${fmt(r.profit)} ₸</span>
    </div>`).join("");
  return `<h3>${title}</h3>${bars}`;
}

// ---------------------------------------------------------------------------
// Рендер: История
// ---------------------------------------------------------------------------
function renderAudit(rows) {
  const tb = $("#audit-table tbody");
  tb.innerHTML = "";
  const ent = { supplier: "Поставщик", order: "Заказ" };
  const act = { create: "создание", update: "изменение", delete: "удаление" };
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="muted">${esc(r.ts.replace("T", " "))}</td><td>${esc(r.username)}</td>
      <td>${ent[r.entity] || r.entity}${r.entity_id ? " #" + r.entity_id : ""}</td>
      <td>${act[r.action] || r.action}</td><td class="muted">${esc(r.details || "")}</td>`;
    tb.appendChild(tr);
  });
  if (!rows.length) tb.innerHTML = `<tr><td colspan="5" class="empty">Изменений пока нет.</td></tr>`;
}

// ---------------------------------------------------------------------------
// Модальное окно + формы
// ---------------------------------------------------------------------------
function openModal(title, fieldsHtml, onSubmit) {
  $("#modal-title").textContent = title;
  $("#modal-result").hidden = true;
  const form = $("#modal-form");
  form.innerHTML = fieldsHtml + `
    <div class="modal-actions">
      <button type="button" class="btn btn-ghost" id="modal-cancel">Отмена</button>
      <button type="submit" class="btn btn-primary">Сохранить</button>
    </div>`;
  $("#modal-backdrop").hidden = false;
  $("#modal-cancel").onclick = closeModal;
  form.onsubmit = async (e) => { e.preventDefault(); await onSubmit(new FormData(form)); };
}
function closeModal() { $("#modal-backdrop").hidden = true; $("#modal-form").onsubmit = null; }

function fruitOptions(selected) {
  return state.fruits.map((f) => `<option value="${esc(f)}" ${f === selected ? "selected" : ""}>${esc(f)}</option>`).join("");
}

// --- Поставщик ---
function openSupplierForm(id) {
  const s = id ? state.suppliers.find((x) => x.id === id) : {};
  openModal(id ? "Изменить поставщика" : "Новый поставщик", `
    <label class="field"><span>Фрукт</span><input name="fruit" required value="${esc(s.fruit || "")}"></label>
    <label class="field"><span>Цена закупки, ₸/кг</span><input name="purchase_price" type="number" step="0.01" min="0" required value="${s.purchase_price ?? ""}"></label>
    <label class="field"><span>Остаток на складе, кг</span><input name="stock" type="number" step="0.01" min="0" required value="${s.stock ?? ""}"></label>
    <label class="field"><span>Поставщик</span><input name="name" required value="${esc(s.name || "")}"></label>
    <label class="field"><span>Срок поставки, дней</span><input name="delivery_days" type="number" min="0" required value="${s.delivery_days ?? ""}"></label>`,
    async (fd) => {
      const body = JSON.stringify(Object.fromEntries(fd));
      try {
        if (id) await api(`/api/suppliers/${id}`, { method: "PUT", body });
        else await api("/api/suppliers", { method: "POST", body });
        closeModal(); toast(id ? "Поставщик обновлён" : "Поставщик добавлен"); refresh();
      } catch (e) { toast(e.message, true); }
    });
}

async function deleteSupplier(id) {
  if (!confirm("Удалить поставщика?")) return;
  try { await api(`/api/suppliers/${id}`, { method: "DELETE" }); toast("Поставщик удалён"); refresh(); }
  catch (e) { toast(e.message, true); }
}

// --- Заказ ---
function openOrderForm(id) {
  const o = id ? state.orders.find((x) => x.id === id) : {};
  openModal(id ? "Изменить заказ" : "Новый заказ", `
    <label class="field"><span>Ресторан / клиент</span><input name="restaurant" required value="${esc(o.restaurant || "")}"></label>
    <label class="field"><span>Фрукт</span><select name="fruit" required>${fruitOptions(o.fruit)}</select></label>
    <label class="field"><span>Количество, кг</span><input name="quantity" type="number" step="0.01" min="0" required value="${o.quantity ?? ""}"></label>
    <label class="field"><span>Дата заказа</span><input name="order_date" type="date" required value="${o.order_date || ""}"></label>
    <label class="field"><span>Срок поставки клиенту</span><input name="client_due_date" type="date" required value="${o.client_due_date || ""}"></label>`,
    async (fd) => {
      const body = JSON.stringify(Object.fromEntries(fd));
      try {
        const r = id
          ? await api(`/api/orders/${id}`, { method: "PUT", body })
          : await api("/api/orders", { method: "POST", body });
        showOrderResult(r.result);
        toast(id ? "Заказ пересчитан" : "Заказ создан"); refresh();
      } catch (e) { toast(e.message, true); }
    });
}

function showOrderResult(res) {
  const box = $("#modal-result");
  if (!res) { closeModal(); return; }
  const matched = res.status === "Подобран поставщик";
  box.className = "modal-result " + (matched ? "ok" : "manual");
  const sName = matched
    ? (state.suppliers.find((s) => s.id === res.supplier_id) || {}).name || "—"
    : "";
  box.innerHTML = matched
    ? `<strong>✓ ${res.status}</strong>Поставщик: ${esc(sName)} · закупка ${fmt(res.purchase_price)} ₸/кг.<br>
       Цена продажи: <b>${fmt(res.sale_price)} ₸/кг</b> · сумма заказа: <b>${fmt(res.order_sum)} ₸</b>.`
    : `<strong>⚠ ${res.status}</strong>Причина: ${esc(res.reason)}.`;
  box.hidden = false;
  // Через секунду закрываем форму, оставив результат видимым в таблице.
  setTimeout(closeModal, 1800);
}

async function deleteOrder(id) {
  if (!confirm("Удалить заказ? Зарезервированный остаток вернётся поставщику.")) return;
  try { await api(`/api/orders/${id}`, { method: "DELETE" }); toast("Заказ удалён"); refresh(); }
  catch (e) { toast(e.message, true); }
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// ---------------------------------------------------------------------------
// Слушатели
// ---------------------------------------------------------------------------
$("#login-form").onsubmit = (e) => {
  e.preventDefault();
  doLogin($("#login-username").value.trim(), $("#login-password").value);
};
$$(".chip").forEach((c) => c.onclick = () => {
  $("#login-username").value = c.dataset.u;
  $("#login-password").value = c.dataset.p;
});
$("#logout-btn").onclick = async () => { await api("/api/logout", { method: "POST" }); showLogin(); };
$("#add-supplier").onclick = () => openSupplierForm(null);
$("#add-order").onclick = () => openOrderForm(null);
$("#modal-close").onclick = closeModal;
$("#modal-backdrop").onclick = (e) => { if (e.target.id === "modal-backdrop") closeModal(); };

bootstrap();
