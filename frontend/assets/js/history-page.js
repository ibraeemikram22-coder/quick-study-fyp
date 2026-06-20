(function initHistoryPage() {
  const params = new URLSearchParams(location.search);
  const moduleKey = params.get("module") || "quiz";
  const cfg = getHistoryModuleConfig(moduleKey);

  if (!cfg) {
    document.getElementById("historyPageList").innerHTML =
      '<p class="history-empty">Unknown module.</p>';
    return;
  }

  const moduleShort = cfg.title.replace(/^Your saved /i, "");
  document.title = `${cfg.title} — Quick Study Builder`;
  document.getElementById("historyPageTitle").textContent = cfg.title;
  document.getElementById("historyPageHint").textContent =
    `Click any saved ${moduleShort.toLowerCase()} to open it in a new tab.`;

  const load = () =>
    mountModuleHistory({
      containerId: "historyPageList",
      module: cfg.module,
      apiPath: cfg.apiPath,
      limit: cfg.limit || 30,
      emptyText: cfg.emptyText || `No saved ${moduleShort.toLowerCase()} yet.`,
      onLoad(row) {
        const id = row.id;
        if (!id || !cfg.page) return;
        window.open(`${cfg.page}?loadHistory=${encodeURIComponent(id)}`, "_blank", "noopener");
      },
    });

  load();

  document.getElementById("historyPageClear")?.addEventListener("click", async () => {
    if (!confirm(`Clear all saved ${moduleShort.toLowerCase()}?`)) return;
    try {
      await clearModuleHistory({ apiPath: cfg.apiPath, module: cfg.module });
      load();
    } catch (err) {
      alert(err.message || "Could not clear saved work.");
    }
  });
})();
