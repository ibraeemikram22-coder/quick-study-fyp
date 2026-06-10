/**
 * Shared DB history UI for tool modules.
 * mountModuleHistory({ containerId, module, onLoad })
 */
function getLoggedInUserId() {
  try {
    const u = JSON.parse(localStorage.getItem("qsb_user") || "null");
    return u && u.id ? u.id : null;
  } catch {
    return null;
  }
}

function moduleHistoryAuthHeaders() {
  const uid = getLoggedInUserId();
  return uid ? { "X-User-Id": String(uid) } : {};
}

function escHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

async function mountModuleHistory({ containerId, module, onLoad, apiPath }) {
  const box = document.getElementById(containerId);
  if (!box) return;

  const base = apiPath || "/api/records";
  const uid = getLoggedInUserId();
  const q = uid
    ? `?module=${encodeURIComponent(module)}&limit=5&userId=${uid}`
    : `?module=${encodeURIComponent(module)}&limit=5`;

  try {
    const res = await fetch(`${API_BASE}${base}${q}`);
    const data = await res.json();
    const items = data.items || [];
    if (!items.length) {
      box.innerHTML =
        '<p class="small text-muted mb-0">No saved history yet. Use the tool — results save to MySQL automatically.</p>';
      return;
    }
    box.innerHTML = items
      .map((t) => {
        const label =
          t.title ||
          t.sourceLabel ||
          t.preview ||
          t.inputPreview ||
          `#${t.id}`;
        return `<button type="button" class="btn btn-sm btn-outline-secondary me-1 mb-1 module-history-pick" data-id="${t.id}">#${t.id} · ${escHtml(String(label).slice(0, 36))}</button>`;
      })
      .join("");

    box.querySelectorAll(".module-history-pick").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const detailPath =
          base === "/api/records"
            ? `/api/records/${btn.dataset.id}`
            : `/transcript/history/${btn.dataset.id}`;
        const r = await fetch(`${API_BASE}${detailPath}`);
        const d = await r.json();
        const row = d.data || d;
        if (onLoad && row) onLoad(row);
      });
    });
  } catch {
    box.innerHTML = '<p class="small text-muted mb-0">History unavailable (start backend).</p>';
  }
}

function moduleHistoryFetchOpts(body) {
  return {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...moduleHistoryAuthHeaders(),
    },
    body: JSON.stringify({ ...(body || {}), userId: getLoggedInUserId() }),
  };
}
