/**
 * Shared saved-work history — opens in new tab via history/saved.html.
 */
const HISTORY_MODULES = {
  quiz: {
    title: "Your saved quizzes",
    page: "../quiz/quiz.html",
    apiPath: "/api/records",
    module: "quiz",
    emptyText: "No saved quizzes yet.",
  },
  summarizer: {
    title: "Your saved summaries",
    page: "../summarizer/summarizer-notes.html",
    apiPath: "/api/records",
    module: "summarizer",
    emptyText: "No saved summaries yet.",
  },
  grammar: {
    title: "Your saved grammar checks",
    page: "../grammer/grammar.html",
    apiPath: "/api/records",
    module: "grammar",
    emptyText: "No saved grammar checks yet.",
  },
  humanizer: {
    title: "Your saved humanized text",
    page: "../humanizer/humanize.html",
    apiPath: "/api/records",
    module: "humanizer",
    emptyText: "No saved text yet.",
  },
  transcript: {
    title: "Your saved transcripts",
    page: "../transcript/videotranscript.html",
    apiPath: "/transcript/history",
    module: "",
    emptyText: "No saved transcripts yet.",
  },
  questionbank: {
    title: "Your saved papers",
    page: "../questionbank/student.html",
    apiPath: "/api/questionbank/papers",
    module: "questionbank",
    limit: 30,
    emptyText: "No saved papers yet.",
  },
};

function getHistoryModuleConfig(key) {
  return HISTORY_MODULES[key] || null;
}

function historyPageUrl(moduleKey) {
  return `../history/saved.html?module=${encodeURIComponent(moduleKey)}`;
}

async function bootHistoryFromUrl(detailPath, onLoad) {
  const id = new URLSearchParams(location.search).get("loadHistory");
  if (!id || typeof onLoad !== "function") return;

  const path =
    typeof detailPath === "function" ? detailPath(id) : String(detailPath).replace("{id}", id);
  try {
    const r = await fetch(`${API_BASE}${path}`);
    const d = await r.json();
    const row = d.data || d;
    if (!r.ok || d.success === false) {
      throw new Error(d.error || "Could not load saved item.");
    }
    onLoad(row);
    history.replaceState({}, "", location.pathname);
  } catch (err) {
    console.error(err);
  }
}

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

function formatHistoryDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function historyItemTitle(item) {
  return (
    item.title ||
    item.sourceLabel ||
    item.preview ||
    item.inputPreview ||
    `Saved item #${item.id}`
  );
}

function historyItemSubtitle(item) {
  if (item.subtitle) return item.subtitle;
  if (item.mode) return String(item.mode).replace(/_/g, " ");
  if (item.filters?.mode) return String(item.filters.mode).replace(/_/g, " ");
  if (item.preview && item.preview !== item.title) return item.preview;
  if (item.inputPreview) return item.inputPreview;
  if (item.questionCount) return `${item.questionCount} questions`;
  if (item.wordCount) return `${item.wordCount} words`;
  return "";
}

function resolveHistoryPath(template, id) {
  if (typeof template === "function") return template(id);
  return String(template || "").replace("{id}", id);
}

function historyClearPath(apiPath, module) {
  const uid = getLoggedInUserId();
  const params = new URLSearchParams();
  if (module) params.set("module", module);
  if (uid) params.set("userId", String(uid));
  const q = params.toString();

  if (apiPath === "/api/questionbank/papers") {
    return `/api/questionbank/papers/clear${q ? `?${q}` : ""}`;
  }
  if (apiPath === "/transcript/history") {
    return `/transcript/history/clear${q ? `?${q}` : ""}`;
  }
  return `/api/records/clear${q ? `?${q}` : ""}`;
}

async function clearModuleHistory({ apiPath = "/api/records", module } = {}) {
  const r = await fetch(`${API_BASE}${historyClearPath(apiPath, module)}`, {
    method: "DELETE",
    headers: moduleHistoryAuthHeaders(),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok || d.success === false) {
    throw new Error(d.error || "Could not clear saved work.");
  }
  return d;
}

async function mountModuleHistory({
  containerId,
  module,
  onLoad,
  apiPath = "/api/records",
  detailPath,
  deletePath,
  limit = 8,
  emptyText = "Nothing saved yet. Your work will appear here after you save or generate.",
}) {
  const box = document.getElementById(containerId);
  if (!box) return;

  const uid = getLoggedInUserId();
  const params = new URLSearchParams({ limit: String(limit) });
  if (module) params.set("module", module);
  if (uid) params.set("userId", String(uid));

  const detailTpl =
    detailPath ||
    (apiPath === "/api/records"
      ? (id) => `/api/records/${id}`
      : apiPath === "/api/questionbank/papers"
        ? (id) => `/api/questionbank/papers/${id}`
        : (id) => `/transcript/history/${id}`);

  const deleteTpl =
    deletePath ||
    (apiPath === "/api/records"
      ? (id) => `/api/records/${id}`
      : apiPath === "/api/questionbank/papers"
        ? (id) => `/api/questionbank/papers/${id}`
        : (id) => `/transcript/history/${id}`);

  try {
    const res = await fetch(`${API_BASE}${apiPath}?${params}`);
    const data = await res.json();
    const items = data.items || data.data?.items || [];
    if (!items.length) {
      box.innerHTML = `<p class="history-empty">${escHtml(emptyText)}</p>`;
      return;
    }

    box.innerHTML = `<div class="history-list">${items
      .map((item) => {
        const title = escHtml(String(historyItemTitle(item)).slice(0, 80));
        const sub = escHtml(String(historyItemSubtitle(item)).slice(0, 120));
        const when = escHtml(formatHistoryDate(item.createdAt));
        return `
          <div class="history-item" data-id="${item.id}">
            <button type="button" class="history-item-open" data-id="${item.id}">
              <span class="history-item-title">${title}</span>
              ${when ? `<span class="history-item-date">${when}</span>` : ""}
            </button>
            <button type="button" class="history-item-delete" data-id="${item.id}" title="Remove" aria-label="Remove">×</button>
          </div>`;
      })
      .join("")}</div>`;

    box.querySelectorAll(".history-item-open").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          const r = await fetch(`${API_BASE}${resolveHistoryPath(detailTpl, btn.dataset.id)}`);
          const d = await r.json();
          const row = d.data || d;
          if (!r.ok || d.success === false) {
            throw new Error(d.error || "Could not open saved item.");
          }
          if (onLoad && row) onLoad(row);
        } catch (err) {
          alert(err.message || "Could not open saved item.");
        }
      });
    });

    box.querySelectorAll(".history-item-delete").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm("Remove this item?")) return;
        try {
          const r = await fetch(`${API_BASE}${resolveHistoryPath(deleteTpl, btn.dataset.id)}`, {
            method: "DELETE",
            headers: moduleHistoryAuthHeaders(),
          });
          const d = await r.json().catch(() => ({}));
          if (!r.ok || d.success === false) {
            throw new Error(d.error || "Could not delete.");
          }
          btn.closest(".history-item")?.remove();
          if (!box.querySelector(".history-item")) {
            box.innerHTML = `<p class="history-empty">${escHtml(emptyText)}</p>`;
          }
        } catch (err) {
          alert(err.message || "Could not delete item.");
        }
      });
    });
  } catch {
    box.innerHTML =
      '<p class="history-empty">Saved work is unavailable right now. Please try again.</p>';
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
