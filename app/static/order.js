const categories = window.ORDER_CATEGORIES || [];
const menu = window.ORDER_MENU || [];
const seats = ["창가 1번", "창가 2번", "테이블 1번", "테이블 2번", "테이블 3번", "테이크아웃"];
const options = ["얼음 적게", "얼음 많이", "얼음 없이", "연하게", "샷 추가", "시럽 추가", "덜 달게", "빨대 필요", "캐리어 필요", "따뜻하게"];
const cart = new Map();
const state = { category: categories[0]?.id || "coffee", seat: "", options: new Set() };
const $ = (selector) => document.querySelector(selector);

function formatWon(value) {
  return `${Number(value).toLocaleString("ko-KR")}원`;
}

function showToast(message, isError = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.className = `toast show${isError ? " error" : ""}`;
  setTimeout(() => { toast.className = "toast"; }, 2600);
}

function optionText() {
  return state.options.size ? [...state.options].join(", ") : "기본";
}

function renderChoices() {
  const seatText = state.seat || "선택 안 함";
  const optText = optionText();
  $("#seat-label").textContent = seatText;
  $("#option-label").textContent = optText;
  $("#cart-seat").textContent = `자리: ${seatText}`;
  $("#cart-options").textContent = `옵션: ${optText}`;
}

function renderTabs() {
  $("#category-tabs").innerHTML = categories.map((category) => `
    <button class="tab ${category.id === state.category ? "active" : ""}" data-category="${category.id}" type="button">
      <strong>${category.name}</strong><span>${category.hint}</span>
    </button>
  `).join("");
}

function renderMenu() {
  const category = categories.find((item) => item.id === state.category) || categories[0];
  const items = menu.filter((item) => item.category === state.category);
  $("#category-title").textContent = category?.name || "메뉴";
  $("#category-hint").textContent = category?.hint || "";
  $("#category-count").textContent = `${items.length} items`;
  $("#menu-list").innerHTML = items.map((item) => `
    <article class="item">
      <div><span class="badge">${item.badge}</span><strong>${item.name}</strong></div>
      <p class="price">${formatWon(item.price)}</p>
      <button class="add" data-menu-id="${item.id}" type="button">담기</button>
    </article>
  `).join("");
}

function renderCart() {
  let count = 0;
  let total = 0;
  cart.forEach((item) => {
    count += item.quantity;
    total += item.price * item.quantity;
  });
  $("#cart-total").textContent = formatWon(total);
  $("#submit-order").disabled = count === 0;

  if (count === 0) {
    $("#cart-list").innerHTML = '<p class="empty">메뉴를 담아 주세요.</p>';
    return;
  }

  $("#cart-list").innerHTML = [...cart.values()].map((item) => `
    <div class="cart-item">
      <div><strong>${item.name}</strong><span>${formatWon(item.price)} x ${item.quantity}</span></div>
      <div class="qty">
        <button data-action="minus" data-menu-id="${item.id}" type="button">-</button>
        <span>${item.quantity}</span>
        <button data-action="plus" data-menu-id="${item.id}" type="button">+</button>
      </div>
    </div>
  `).join("");
}

function addToCart(menuId) {
  const item = menu.find((entry) => entry.id === menuId);
  if (!item) return;
  const existing = cart.get(menuId);
  if (existing) existing.quantity += 1;
  else cart.set(menuId, { ...item, quantity: 1 });
  renderCart();
  showToast(`${item.name} 담았습니다.`);
}

function changeQuantity(menuId, delta) {
  const item = cart.get(menuId);
  if (!item) return;
  item.quantity += delta;
  if (item.quantity <= 0) cart.delete(menuId);
  renderCart();
}

async function sendOrder() {
  const items = [...cart.values()].map((item) => ({ menu_id: item.id, quantity: item.quantity }));
  const submit = $("#submit-order");
  submit.disabled = true;
  submit.textContent = "전송 중";
  try {
    const response = await fetch("/api/v1/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items,
        customer_name: state.seat || "자리 미선택",
        note: optionText() === "기본" ? "" : optionText(),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "주문 실패");
    cart.clear();
    renderCart();
    showToast(`주문 완료 #${data.order_no}`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    submit.textContent = "주문 보내기";
    submit.disabled = cart.size === 0;
  }
}

function setup() {
  $("#seat-grid").innerHTML = seats.map((seat) => `<button class="chip seat" data-seat="${seat}" type="button">${seat}</button>`).join("");
  $("#option-grid").innerHTML = options.map((option) => `<button class="chip option" data-option="${option}" type="button">${option}</button>`).join("");
  renderTabs();
  renderMenu();
  renderChoices();
  renderCart();
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button) return;

  if (button.dataset.category) {
    state.category = button.dataset.category;
    renderTabs();
    renderMenu();
  }
  if (button.dataset.seat) {
    state.seat = button.dataset.seat;
    document.querySelectorAll(".seat").forEach((item) => item.classList.toggle("active", item === button));
    renderChoices();
  }
  if (button.dataset.option) {
    if (state.options.has(button.dataset.option)) state.options.delete(button.dataset.option);
    else state.options.add(button.dataset.option);
    button.classList.toggle("active");
    renderChoices();
  }
  if (button.dataset.menuId && button.classList.contains("add")) addToCart(button.dataset.menuId);
  if (button.dataset.action) changeQuantity(button.dataset.menuId, button.dataset.action === "plus" ? 1 : -1);
});

$("#clear-cart").addEventListener("click", () => { cart.clear(); renderCart(); });
$("#submit-order").addEventListener("click", sendOrder);
$("#copy-url").addEventListener("click", async () => {
  await navigator.clipboard.writeText(location.href);
  showToast("주소 복사 완료");
});

setup();
