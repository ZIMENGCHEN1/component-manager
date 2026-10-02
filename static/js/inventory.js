document.querySelectorAll("[data-reverse-movement]").forEach(button => {
    button.addEventListener("click", async () => {
        if (!confirm("确认撤销这次手动库存调整？系统会新增一条反向流水。")) return;
        button.disabled = true;
        try {
            await api(`/api/inventory/movements/${button.dataset.reverseMovement}/reverse`, {method: "POST"});
            notify("库存调整已撤销");
            setTimeout(() => location.reload(), 350);
        } catch (error) {
            notify(error.message, true);
            button.disabled = false;
        }
    });
});
