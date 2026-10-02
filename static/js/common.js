window.api = async function (url, options = {}) {
    const response = await fetch(url, options);
    const body = response.status === 204 ? null : await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `请求失败 (${response.status})`);
    return body;
};

window.jsonOptions = function (method, data) {
    return {method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)};
};

window.escapeHtml = function (value) {
    return String(value ?? "").replace(/[&<>'"]/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    })[character]);
};

window.notify = function (message, error = false) {
    const toast = document.querySelector("#toast");
    toast.textContent = message;
    toast.className = `toast ${error ? "error" : "success"}`;
    toast.hidden = false;
    clearTimeout(window.toastTimer);
    window.toastTimer = setTimeout(() => { toast.hidden = true; }, 2800);
};

document.querySelectorAll("[data-toggle]").forEach(button => {
    button.addEventListener("click", () => {
        const target = document.querySelector(`#${button.dataset.toggle}`);
        target.hidden = !target.hidden;
    });
});
