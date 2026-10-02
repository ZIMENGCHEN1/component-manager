document.querySelector("#add-component")?.addEventListener("submit", async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
        await api("/api/components", jsonOptions("POST", Object.fromEntries(form)));
        notify("元件已添加");
        location.reload();
    } catch (error) { notify(error.message, true); }
});

if (new URLSearchParams(location.search).get("show_bom_import") === "1") {
    document.querySelector("#bom-library-import")?.removeAttribute("hidden");
}

document.querySelectorAll("[data-edit-component]").forEach(button => button.addEventListener("click", () => {
    const panel = document.querySelector("#component-edit-panel");
    const form = document.querySelector("#edit-component");
    form.elements.id.value = button.dataset.editComponent;
    form.elements.supplier.value = button.dataset.supplier;
    form.elements.supplier_part.value = button.dataset.part;
    form.elements.comment.value = button.dataset.comment;
    form.elements.footprint.value = button.dataset.footprint;
    form.elements.manufacturer.value = button.dataset.manufacturer;
    form.elements.manufacturer_part.value = button.dataset.manufacturerPart;
    form.elements.secondary_category.value = button.dataset.secondaryCategory;
    form.elements.description.value = button.dataset.description;
    panel.hidden = false;
    panel.scrollIntoView({behavior: "smooth", block: "start"});
}));

document.querySelector("[data-close-component-edit]")?.addEventListener("click", () => {
    document.querySelector("#component-edit-panel").hidden = true;
});

document.querySelector("#edit-component")?.addEventListener("submit", async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const id = form.get("id");
    form.delete("id");
    try {
        await api(`/api/components/${id}`, jsonOptions("PATCH", Object.fromEntries(form)));
        notify("元件信息已更新");
        location.reload();
    } catch (error) { notify(error.message, true); }
});

document.querySelectorAll("[data-delete-component]").forEach(button => button.addEventListener("click", async () => {
    if (!confirm(`确认删除元件 ${button.dataset.name}？有库存或被引用的元件不能删除。`)) return;
    try {
        await api(`/api/components/${button.dataset.deleteComponent}`, {method: "DELETE"});
        notify("元件已删除");
        location.reload();
    } catch (error) { notify(error.message, true); }
}));

document.querySelectorAll("[data-adjust]").forEach(button => button.addEventListener("click", async () => {
    const raw = prompt(`调整 ${button.dataset.name} 库存\n正数为入库，负数为扣减：`, "1");
    if (raw === null) return;
    const delta = Number.parseInt(raw, 10);
    if (!Number.isInteger(delta) || delta === 0) return notify("请输入非 0 整数", true);
    try {
        await api(`/api/components/${button.dataset.adjust}/adjust-stock`, jsonOptions("POST", {delta, note: "手动调整"}));
        notify("库存已更新");
        location.reload();
    } catch (error) { notify(error.message, true); }
}));
