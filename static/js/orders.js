let orderPreviewToken = null;

document.querySelector("#order-preview-form")?.addEventListener("submit", async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const target = document.querySelector("#order-preview");
    try {
        const result = await api("/api/orders/preview", {method: "POST", body: form});
        orderPreviewToken = result.token;
        target.innerHTML = `<div class="preview-head"><strong>订单 ${result.order_number} · ${result.items.length} 项</strong><button id="confirm-order" class="button primary">确认导入</button></div><div class="preview-list">${result.items.map(item => `<span><b>${item.supplier_part}</b><small>${item.manufacturer_part} · ${item.product_name}</small><em>发货 ${item.shipped_quantity}</em></span>`).join("")}</div>`;
        target.hidden = false;
        document.querySelector("#confirm-order").addEventListener("click", confirmOrder);
    } catch (error) { notify(error.message, true); }
});

async function confirmOrder() {
    try {
        await api("/api/orders/confirm", jsonOptions("POST", {token: orderPreviewToken}));
        notify("订单已导入");
        location.reload();
    } catch (error) { notify(error.message, true); }
}

document.querySelectorAll("[data-link-item]").forEach(button => button.addEventListener("click", async () => {
    const itemId = button.dataset.linkItem;
    const componentId = document.querySelector(`[data-link-select="${itemId}"]`).value;
    if (!componentId) return notify("请选择元件", true);
    try {
        await api(`/api/orders/items/${itemId}/link`, jsonOptions("POST", {component_id: Number(componentId)}));
        notify("已建立关联");
        location.reload();
    } catch (error) { notify(error.message, true); }
}));

document.querySelectorAll("[data-select-order-item]").forEach(button => button.addEventListener("click", () => {
    const card = button.closest("[data-order-card]");
    card.dataset.pendingItem = button.dataset.selectOrderItem;
    card.dataset.pendingLabel = button.dataset.label;
    card.querySelectorAll("[data-select-order-item]").forEach(value => value.classList.toggle("selected", value === button));
    card.querySelector("[data-selected-order-label]").textContent = `当前归位：${button.dataset.label}`;
    card.querySelector("[data-order-storage-panel]").scrollIntoView({behavior: "smooth", block: "center"});
}));

document.querySelectorAll("[data-order-cell]").forEach(cell => cell.addEventListener("click", async () => {
    const card = cell.closest("[data-order-card]");
    const itemId = card.dataset.pendingItem;
    if (!itemId) return notify("请先选择一个待归位元件", true);
    if (!confirm(`将 ${card.dataset.pendingLabel} 放入格位 ${cell.querySelector(".cell-label").textContent}，并按发货数量入库？`)) return;
    try {
        await api(`/api/orders/items/${itemId}/place`, jsonOptions("POST", {cell_id: Number(cell.dataset.orderCell)}));
        notify("已归位，发货数量已入库");
        location.reload();
    } catch (error) { notify(error.message, true); }
}));
