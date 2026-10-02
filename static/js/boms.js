let bomPreviewToken = null;
let bomPreviewName = "";

const bomUrl = new URL(location.href);
if (bomUrl.searchParams.get("expanded") === "1") {
    bomUrl.searchParams.delete("expanded");
    history.replaceState(null, "", `${bomUrl.pathname}${bomUrl.search}`);
}

document.querySelector("#bom-preview-form")?.addEventListener("submit", async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    bomPreviewName = form.get("name");
    const target = document.querySelector("#bom-preview");
    try {
        const result = await api("/api/boms/preview", {method: "POST", body: form});
        bomPreviewToken = result.token;
        target.innerHTML = `<div class="preview-head"><strong>识别到 ${result.items.length} 种元件</strong><button id="confirm-bom" class="button primary">确认导入</button></div><div class="preview-list">${result.items.map(item => `<span><b>${item.supplier_part}</b><small>${item.comment} · ${item.footprint}</small><em>× ${item.quantity}</em></span>`).join("")}</div>`;
        target.hidden = false;
        document.querySelector("#confirm-bom").addEventListener("click", confirmBom);
    } catch (error) { notify(error.message, true); }
});

async function confirmBom() {
    try {
        const result = await api("/api/boms/confirm", jsonOptions("POST", {token: bomPreviewToken, name: bomPreviewName}));
        notify("领料 BOM 已确认，尚未扣减库存");
        location.href = `/boms?bom_id=${result.id}&expanded=1`;
    } catch (error) { notify(error.message, true); }
}

function closePickOverlays(except = null) {
    document.querySelectorAll(".pick-overlay").forEach(overlay => {
        if (overlay !== except) overlay.hidden = true;
    });
}

function openCellOverlay(cell) {
    const overlay = cell.querySelector(".pick-overlay");
    closePickOverlays(overlay);
    overlay.hidden = false;
}

document.querySelectorAll("[data-pick-item]").forEach(cell => {
    cell.addEventListener("click", event => {
        if (event.target.closest("button")) return;
        openCellOverlay(cell);
    });
    cell.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openCellOverlay(cell);
        }
    });
});

document.querySelectorAll("[data-cancel-pick]").forEach(button => button.addEventListener("click", event => {
    event.stopPropagation();
    button.closest(".pick-overlay").hidden = true;
}));

document.querySelectorAll("[data-confirm-pick]").forEach(button => button.addEventListener("click", async event => {
    event.stopPropagation();
    button.disabled = true;
    try {
        const result = await api(`/api/boms/items/${button.dataset.confirmPick}/pick`, {method: "POST"});
        notify("该格元件已领取，库存已扣减");
        location.href = `/boms?bom_id=${result.bom_id}`;
    } catch (error) {
        button.disabled = false;
        notify(error.message, true);
    }
}));

document.querySelectorAll("[data-delete-bom]").forEach(button => button.addEventListener("click", async () => {
    if (!confirm(`确认删除 BOM“${button.dataset.name}”？已经发生领料的 BOM 不能删除。`)) return;
    try {
        await api(`/api/boms/${button.dataset.deleteBom}`, {method: "DELETE"});
        notify("BOM 已删除");
        location.href = "/boms";
    } catch (error) { notify(error.message, true); }
}));

document.querySelectorAll("[data-substitute-item]").forEach(button => button.addEventListener("click", async () => {
    if (button.textContent.trim() === "已选择") return;
    if (!confirm("确认本次 BOM 使用这个参数匹配候选？请核对 Footprint。")) return;
    button.disabled = true;
    try {
        const result = await api(
            `/api/boms/items/${button.dataset.substituteItem}/substitute`,
            jsonOptions("POST", {component_id: Number(button.dataset.componentId)}),
        );
        notify(`已选择 ${result.selected_supplier_part}，尚未扣减库存`);
        location.href = `/boms?bom_id=${result.bom_id}&expanded=1`;
    } catch (error) {
        button.disabled = false;
        notify(error.message, true);
    }
}));
