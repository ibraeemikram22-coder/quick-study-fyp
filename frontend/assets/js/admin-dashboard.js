function setStatus(msg, isError = false) {
  const el = document.getElementById("adminDashStatus");
  if (!el) return;
  el.textContent = msg;
  el.className = "status-bar mb-3 " + (isError ? "error" : "ok");
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

async function loadStats() {
  const stats = await apiFetch("/api/admin/stats");
  document.getElementById("statUsers").textContent = stats.users ?? 0;
  document.getElementById("statQuestions").textContent = stats.questions ?? 0;
  document.getElementById("statPapers").textContent = stats.savedPapers ?? 0;
  document.getElementById("statContact").textContent = stats.contactMessages ?? 0;
  const db = stats.database || {};
  document.getElementById("dbInfo").textContent =
    db.driver === "mysql"
      ? `Connected: MySQL (${db.url || "localhost"})`
      : `Connected: SQLite (${db.path || "local file"})`;
}

async function loadContact() {
  const data = await apiFetch("/api/contact/feedback");
  const items = (data.items || []).slice().reverse();
  const body = document.getElementById("contactTableBody");
  if (!items.length) {
    body.innerHTML = '<tr><td colspan="5" class="text-muted">No messages yet.</td></tr>';
    return;
  }
  body.innerHTML = items
    .slice(0, 20)
    .map(
      (m) => `
    <tr>
      <td>${esc(fmtDate(m.createdAt))}</td>
      <td>${esc(m.name)}</td>
      <td>${esc(m.email)}</td>
      <td>${esc(m.subject)}</td>
      <td>${esc((m.message || "").slice(0, 120))}${(m.message || "").length > 120 ? "…" : ""}</td>
    </tr>`
    )
    .join("");
}

async function loadHistory() {
  const data = await apiFetch("/api/history?limit=15");
  const list = document.getElementById("historyList");
  const items = data.items || [];
  if (!items.length) {
    list.innerHTML = '<li class="list-group-item text-muted">No activity yet.</li>';
    return;
  }
  list.innerHTML = items
    .map(
      (h) => `
    <li class="list-group-item d-flex justify-content-between gap-2">
      <span><strong>${esc(h.module)}</strong> — ${esc(h.action)}</span>
      <span class="text-muted">${esc(fmtDate(h.createdAt))}</span>
    </li>`
    )
    .join("");
}

async function loadUsers() {
  const data = await apiFetch("/api/admin/users");
  const body = document.getElementById("usersTableBody");
  const items = data.items || [];
  if (!items.length) {
    body.innerHTML = '<tr><td colspan="4" class="text-muted">No users yet. Run create_admin.py</td></tr>';
    return;
  }
  body.innerHTML = items
    .map(
      (u) => `
    <tr>
      <td>${esc(u.name)}</td>
      <td>${esc(u.email)}</td>
      <td><span class="badge text-bg-secondary">${esc(u.role)}</span></td>
      <td>${esc(fmtDate(u.createdAt))}</td>
    </tr>`
    )
    .join("");
}

async function initDashboard() {
  try {
    setStatus("Loading from database...");
    await Promise.all([loadStats(), loadContact(), loadHistory(), loadUsers()]);
    setStatus("Dashboard ready — data loaded from MySQL.");
  } catch (e) {
    setStatus(e.message || "Failed to load dashboard", true);
  }
}

document.getElementById("refreshContactBtn")?.addEventListener("click", () =>
  loadContact().catch((e) => setStatus(e.message, true))
);
document.getElementById("refreshHistoryBtn")?.addEventListener("click", () =>
  loadHistory().catch((e) => setStatus(e.message, true))
);

const user = requireLogin(["admin"]);
if (user) {
  showDashboardBar(user, "Admin");
  initDashboard();
}
