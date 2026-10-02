const restoreForm = document.querySelector("#restore-database");

restoreForm?.addEventListener("submit", async event => {
    event.preventDefault();
    if (!confirm("恢复会覆盖当前数据。确认使用这个备份继续吗？")) return;
    const button = restoreForm.querySelector("button[type='submit']");
    button.disabled = true;
    try {
        const result = await api("/api/data/restore", {
            method: "POST",
            body: new FormData(restoreForm),
        });
        notify(`${result.message}；恢复前数据已自动备份`);
        restoreForm.reset();
    } catch (error) {
        notify(error.message, true);
    } finally {
        button.disabled = false;
    }
});
