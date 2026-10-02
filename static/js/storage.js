document.querySelector("#add-box")?.addEventListener("submit", async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
        await api("/api/storage/boxes", jsonOptions("POST", {name: form.get("name"), rows: Number(form.get("rows")), columns: Number(form.get("columns"))}));
        notify("收纳盒已创建");
        location.reload();
    } catch (error) { notify(error.message, true); }
});

document.querySelectorAll("[data-edit-box]").forEach(button => button.addEventListener("click", () => {
    document.querySelector(`[data-box-edit-form="${button.dataset.editBox}"]`).hidden = false;
}));

document.querySelectorAll("[data-cancel-box-edit]").forEach(button => button.addEventListener("click", () => {
    document.querySelector(`[data-box-edit-form="${button.dataset.cancelBoxEdit}"]`).hidden = true;
}));

document.querySelectorAll("[data-box-edit-form]").forEach(form => form.addEventListener("submit", async event => {
    event.preventDefault();
    const data = new FormData(form);
    try {
        await api(`/api/storage/boxes/${form.dataset.boxEditForm}`, jsonOptions("PATCH", {name: data.get("name"), rows: Number(data.get("rows")), columns: Number(data.get("columns"))}));
        notify("收纳盒已更新");
        location.reload();
    } catch (error) { notify(error.message, true); }
}));

document.querySelectorAll("[data-delete-box]").forEach(button => button.addEventListener("click", async () => {
    if (!confirm(`确认删除收纳盒“${button.dataset.name}”？盒内有元件时不允许删除。`)) return;
    try {
        await api(`/api/storage/boxes/${button.dataset.deleteBox}`, {method: "DELETE"});
        notify("收纳盒已删除");
        location.reload();
    } catch (error) { notify(error.message, true); }
}));

document.querySelectorAll("[data-edit-cell]").forEach(button => button.addEventListener("click", () => {
    const id = button.dataset.editCell;
    document.querySelector(`[data-cell-display="${id}"]`).hidden = true;
    document.querySelector(`[data-cell-edit-form="${id}"]`).hidden = false;
}));

document.querySelectorAll("[data-cancel-cell-edit]").forEach(button => button.addEventListener("click", () => {
    const id = button.dataset.cancelCellEdit;
    document.querySelector(`[data-cell-display="${id}"]`).hidden = false;
    document.querySelector(`[data-cell-edit-form="${id}"]`).hidden = true;
}));

document.querySelectorAll("[data-cell-edit-form]").forEach(form => form.addEventListener("submit", async event => {
    event.preventDefault();
    const data = new FormData(form);
    const rawComponentId = data.get("component_id");
    try {
        await api(`/api/storage/cells/${form.dataset.cellEditForm}`, jsonOptions("PATCH", {label: data.get("label"), component_id: rawComponentId ? Number(rawComponentId) : null}));
        notify("格位已更新");
        location.reload();
    } catch (error) { notify(error.message, true); }
}));
