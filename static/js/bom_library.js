let libraryPreviewToken = null;
let libraryConflicts = [];

document.querySelector("#bom-library-preview-form")?.addEventListener("submit", async event => {
    event.preventDefault();
    const target = document.querySelector("#bom-library-preview");
    try {
        const result = await api("/api/bom-library/preview", {method: "POST", body: new FormData(event.currentTarget)});
        libraryPreviewToken = result.token;
        target.innerHTML = `<div class="preview-head"><strong>识别到 ${result.items.length} 种元件</strong><button id="confirm-library" class="button primary">确认建库</button></div><div class="preview-list">${result.items.map(item => `<span><b>${escapeHtml(item.supplier_part)}</b><small>${escapeHtml(item.comment)} · ${escapeHtml(item.footprint)}</small><em>× ${item.quantity}</em></span>`).join("")}</div><p class="muted">建库只录入元件规格，数量不会进入库存。</p>`;
        target.hidden = false;

        libraryConflicts = result.conflicts;
        const conflictPanel = document.querySelector("#bom-library-conflicts");
        const conflictList = conflictPanel.querySelector("[data-conflict-list]");
        const labels = {secondary_category: "Secondary Category", description: "Description"};
        conflictList.innerHTML = libraryConflicts.map((conflict, index) => `
            <label class="conflict-item">
                <input type="checkbox" data-overwrite-conflict="${index}" checked>
                <span><b>${escapeHtml(conflict.supplier_part)}</b> · ${escapeHtml(labels[conflict.field])}</span>
                <small>${escapeHtml(conflict.current_value)} → ${escapeHtml(conflict.incoming_value)}</small>
            </label>
        `).join("");
        conflictPanel.hidden = libraryConflicts.length === 0;
        document.querySelector("#confirm-library").addEventListener("click", confirmLibrary);
    } catch (error) { notify(error.message, true); }
});

function setAllConflictChecks(checked) {
    document.querySelectorAll("[data-overwrite-conflict]").forEach(input => {
        input.checked = checked;
    });
}

document.querySelector("[data-select-all-conflicts]")?.addEventListener(
    "click",
    () => setAllConflictChecks(true),
);
document.querySelector("[data-clear-all-conflicts]")?.addEventListener(
    "click",
    () => setAllConflictChecks(false),
);

async function confirmLibrary() {
    const overwriteMap = new Map();
    document.querySelectorAll("[data-overwrite-conflict]:checked").forEach(input => {
        const conflict = libraryConflicts[Number(input.dataset.overwriteConflict)];
        if (!overwriteMap.has(conflict.supplier_part)) overwriteMap.set(conflict.supplier_part, []);
        overwriteMap.get(conflict.supplier_part).push(conflict.field);
    });
    const overwrites = [...overwriteMap].map(([supplier_part, fields]) => ({supplier_part, fields}));
    try {
        const result = await api("/api/bom-library/confirm", jsonOptions("POST", {token: libraryPreviewToken, overwrites}));
        const warningText = result.warnings.length ? `，${result.warnings.length} 项规格需核对` : "";
        notify(`建库完成：新增 ${result.created_count} 种，复用 ${result.reused_count} 种${warningText}`);
        location.reload();
    } catch (error) { notify(error.message, true); }
}
