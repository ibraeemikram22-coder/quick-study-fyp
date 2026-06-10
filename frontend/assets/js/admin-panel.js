const PANEL_TITLES = {
  overview: "Overview",
  contact: "Contact messages",
  users: "Users",
  papers: "Saved papers",
  modulehistory: "Module history",
  activity: "Activity log",
  modules: "Site modules",
};

const SITE_MODULES = [
  { name: "Home", desc: "Main landing page", url: "../index.html", icon: "fa-home" },
  { name: "Student Dashboard", desc: "Question bank — student", url: "../module/questionbank/student.html", icon: "fa-user-graduate" },
  { name: "Teacher Dashboard", desc: "Question bank — teacher", url: "../module/questionbank/teacher.html", icon: "fa-chalkboard-teacher" },
  { name: "Question Bank Admin", desc: "Setup boards, chapters, AI questions", url: "../module/questionbank/admin.html", icon: "fa-database" },
  { name: "Grammar Checker", desc: "Grammar module", url: "../module/grammer/grammar.html", icon: "fa-spell-check" },
  { name: "Quiz Generator", desc: "Quiz module", url: "../module/quiz/quiz.html", icon: "fa-list-check" },
  { name: "Summarizer", desc: "Notes from text/PDF", url: "../module/summarizer/summarizer-notes.html", icon: "fa-file-alt" },
  { name: "Humanizer", desc: "Text humanizer", url: "../module/humanizer/humanize.html", icon: "fa-wand-magic-sparkles" },
  { name: "Video Transcript", desc: "YouTube + Whisper", url: "../module/transcript/videotranscript.html", icon: "fa-closed-captioning" },
  { name: "Contact Page", desc: "Public contact form", url: "../contactus.html", icon: "fa-envelope" },
  { name: "Login / Signup", desc: "User authentication", url: "../login.html", icon: "fa-right-to-bracket" },
];

function setStatus(msg, isError = false) {
  const el = document.getElementById("adminStatus");
  if (!el) return;
  el.textContent = msg;
  el.className = (isError ? "admin-status-err" : "admin-status-ok") + " mb-3";
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

function showPanel(name) {
  document.querySelectorAll(".admin-panel-section").forEach((el) => {
    el.classList.toggle("active", el.dataset.panel === name);
  });
  document.querySelectorAll("#adminNav a[data-panel]").forEach((a) => {
    a.classList.toggle("active", a.dataset.panel === name);
  });
  const title = document.getElementById("panelTitle");
  if (title) title.textContent = PANEL_TITLES[name] || "Admin";
  if (location.hash !== `#${name}`) {
    history.replaceState(null, "", `#${name}`);
  }
}

function initNav() {
  document.querySelectorAll("#adminNav a[data-panel]").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      showPanel(a.dataset.panel);
    });
  });
  const hash = (location.hash || "#overview").replace("#", "");
  showPanel(PANEL_TITLES[hash] ? hash : "overview");
}

function renderModuleGrid() {
  const grid = document.getElementById("moduleGrid");
  if (!grid) return;
  grid.innerHTML = SITE_MODULES.map(
    (m) => `
    <a class="admin-module-tile" href="${m.url}" target="_blank">
      <strong><i class="fas ${m.icon} me-1"></i>${esc(m.name)}</strong>
      <span>${esc(m.desc)}</span>
    </a>`
  ).join("");
}

async function loadStats() {
  const stats = await apiFetch("/api/admin/stats");
  document.getElementById("statUsers").textContent = stats.users ?? 0;
  document.getElementById("statStudents").textContent = stats.students ?? 0;
  document.getElementById("statTeachers").textContent = stats.teachers ?? 0;
  document.getElementById("statQuestions").textContent = stats.questions ?? 0;
  document.getElementById("statPapers").textContent = stats.savedPapers ?? 0;
  document.getElementById("statContact").textContent = stats.contactMessages ?? 0;
  document.getElementById("statActivity").textContent = stats.activityLogs ?? 0;
  const statTr = document.getElementById("statTranscripts");
  if (statTr) statTr.textContent = (stats.moduleRecords ?? 0) + (stats.transcripts ?? 0);
  const db = stats.database || {};
  const badge = document.getElementById("dbBadge");
  if (badge) {
    badge.textContent = db.driver === "mysql" ? "MySQL" : "SQLite";
    badge.className = `badge ${db.driver === "mysql" ? "text-bg-success" : "text-bg-warning"}`;
  }
  document.getElementById("dbInfo").textContent =
    db.driver === "mysql"
      ? `Connected to MySQL (${db.url || "localhost"}). All modules share this database.`
      : `Using SQLite file: ${db.path || "local"}. Add MYSQL_* to .env for MySQL.`;
}

let msgModal;

async function loadContact() {
  const data = await apiFetch("/api/contact/feedback");
  const items = (data.items || []).slice().reverse();
  const body = document.getElementById("contactTableBody");
  if (!items.length) {
    body.innerHTML = '<tr><td colspan="6" class="text-muted">No messages yet.</td></tr>';
    return;
  }
  body.innerHTML = items
    .map(
      (m, i) => `
    <tr>
      <td>${esc(fmtDate(m.createdAt))}</td>
      <td>${esc(m.name)}</td>
      <td>${esc(m.email)}</td>
      <td>${esc(m.subject)}</td>
      <td class="msg-preview">${esc(m.message)}</td>
      <td><button class="btn btn-sm btn-link view-msg-btn" data-idx="${i}">View</button></td>
    </tr>`
    )
    .join("");
  const byIdx = items;
  body.querySelectorAll(".view-msg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const m = byIdx[Number(btn.dataset.idx)];
      document.getElementById("msgModalBody").innerHTML = `
        <p><strong>From:</strong> ${esc(m.name)} &lt;${esc(m.email)}&gt;</p>
        <p><strong>Subject:</strong> ${esc(m.subject)}</p>
        <p><strong>Date:</strong> ${esc(fmtDate(m.createdAt))}</p>
        <hr>
        <pre style="white-space:pre-wrap;font-family:inherit">${esc(m.message)}</pre>`;
      msgModal.show();
    });
  });
}

async function loadUsers() {
  const data = await apiFetch("/api/admin/users");
  const body = document.getElementById("usersTableBody");
  const items = data.items || [];
  if (!items.length) {
    body.innerHTML =
      '<tr><td colspan="4" class="text-muted">No users. Run: python scripts/create_admin.py</td></tr>';
    return;
  }
  body.innerHTML = items
    .map(
      (u) => `
    <tr>
      <td>${esc(u.name)}</td>
      <td>${esc(u.email)}</td>
      <td><span class="badge text-bg-${u.role === "admin" ? "danger" : u.role === "teacher" ? "primary" : "secondary"}">${esc(u.role)}</span></td>
      <td>${esc(fmtDate(u.createdAt))}</td>
    </tr>`
    )
    .join("");
}

let moduleHistoryCache = [];

function renderModuleDetail(mod, full) {
  document.getElementById("detailModalTitle").textContent = `${mod} #${full.id}`;
  if (mod === "transcript") {
    document.getElementById("msgModalBody").innerHTML = `
      <p><strong>Source:</strong> ${esc(full.sourceLabel)}</p>
      <p><strong>Engine:</strong> ${esc(full.sourceEngine)} · <strong>Words:</strong> ${full.wordCount}</p>
      <hr>
      <pre style="white-space:pre-wrap;font-family:inherit;max-height:400px;overflow:auto">${esc(full.transcript)}</pre>`;
    return;
  }
  const r = full.result || {};
  let body = `<p><strong>Title:</strong> ${esc(full.title)}</p><p class="small text-muted">${esc(full.inputPreview || "")}</p><hr>`;
  if (r.summary) body += `<pre style="white-space:pre-wrap;max-height:400px;overflow:auto">${esc(r.summary)}</pre>`;
  else if (r.corrected) body += `<pre style="white-space:pre-wrap;max-height:400px;overflow:auto">${esc(r.corrected)}</pre>`;
  else if (r.result) body += `<pre style="white-space:pre-wrap;max-height:400px;overflow:auto">${esc(r.result)}</pre>`;
  else if (r.questions) body += `<pre style="white-space:pre-wrap;max-height:400px;overflow:auto">${esc(JSON.stringify(r.questions, null, 2))}</pre>`;
  else body += `<pre style="white-space:pre-wrap;max-height:400px;overflow:auto">${esc(JSON.stringify(r, null, 2))}</pre>`;
  document.getElementById("msgModalBody").innerHTML = body;
}

async function loadModuleHistory() {
  const mod = document.getElementById("moduleHistoryFilter")?.value || "";
  const body = document.getElementById("moduleHistoryBody");
  moduleHistoryCache = [];

  if (!mod || mod === "transcript") {
    const tr = await apiFetch(`/api/admin/transcripts?limit=50`);
    (tr.items || []).forEach((t) =>
      moduleHistoryCache.push({
        kind: "transcript",
        id: t.id,
        module: "transcript",
        title: t.sourceLabel,
        preview: `${t.wordCount} words · ${t.sourceEngine}`,
        createdAt: t.createdAt,
      })
    );
  }
  if (!mod || mod !== "transcript") {
    const q = mod && mod !== "transcript" ? `?module=${encodeURIComponent(mod)}&limit=50` : "?limit=50";
    const rec = await apiFetch(`/api/admin/records${q}`);
    (rec.items || []).forEach((r) =>
      moduleHistoryCache.push({
        kind: "record",
        id: r.id,
        module: r.module,
        title: r.title,
        preview: r.preview || r.inputPreview,
        createdAt: r.createdAt,
      })
    );
  }

  moduleHistoryCache.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

  if (!moduleHistoryCache.length) {
    body.innerHTML = '<tr><td colspan="5" class="text-muted">No history yet. Use any module on the website.</td></tr>';
    return;
  }

  body.innerHTML = moduleHistoryCache
    .slice(0, 80)
    .map(
      (t, i) => `
    <tr>
      <td>${esc(fmtDate(t.createdAt))}</td>
      <td><span class="badge text-bg-light border">${esc(t.module)}</span></td>
      <td class="msg-preview">${esc(t.title)}</td>
      <td class="msg-preview">${esc(t.preview)}</td>
      <td><button class="btn btn-sm btn-link view-mod-btn" data-idx="${i}">View</button></td>
    </tr>`
    )
    .join("");

  body.querySelectorAll(".view-mod-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const row = moduleHistoryCache[Number(btn.dataset.idx)];
      try {
        const full =
          row.kind === "transcript"
            ? await apiFetch(`/api/admin/transcripts/${row.id}`)
            : await apiFetch(`/api/admin/records/${row.id}`);
        renderModuleDetail(row.module, full);
        msgModal.show();
      } catch (e) {
        setStatus(e.message, true);
      }
    });
  });
}

async function loadPapers() {
  const data = await apiFetch("/api/admin/papers?limit=50");
  const body = document.getElementById("papersTableBody");
  const items = data.items || [];
  if (!items.length) {
    body.innerHTML = '<tr><td colspan="5" class="text-muted">No saved papers yet.</td></tr>';
    return;
  }
  body.innerHTML = items
    .map(
      (p) => `
    <tr>
      <td>${esc(fmtDate(p.createdAt))}</td>
      <td>${esc(p.title)}</td>
      <td>${esc(p.module)}</td>
      <td>${esc(p.mode || "—")}</td>
      <td>${p.userId ?? "—"}</td>
    </tr>`
    )
    .join("");
}

async function loadHistory() {
  const mod = document.getElementById("activityModuleFilter")?.value || "";
  const q = mod ? `?limit=30&module=${encodeURIComponent(mod)}` : "?limit=30";
  const data = await apiFetch(`/api/history${q}`);
  const list = document.getElementById("historyList");
  const items = data.items || [];
  if (!items.length) {
    list.innerHTML = '<li class="list-group-item text-muted">No activity logged yet.</li>';
    return;
  }
  list.innerHTML = items
    .map((h) => {
      const det = h.details && Object.keys(h.details).length ? JSON.stringify(h.details) : "";
      return `
    <li class="list-group-item">
      <div class="d-flex justify-content-between gap-2 flex-wrap">
        <span><span class="badge text-bg-light border">${esc(h.module)}</span> <strong>${esc(h.action)}</strong></span>
        <span class="text-muted">${esc(fmtDate(h.createdAt))}</span>
      </div>
      ${det ? `<div class="text-muted mt-1" style="font-size:0.75rem">${esc(det)}</div>` : ""}
    </li>`;
    })
    .join("");
}

async function refreshAll() {
  setStatus("Refreshing from database...");
  await Promise.all([
    loadStats(),
    loadContact(),
    loadUsers(),
    loadPapers(),
    loadModuleHistory(),
    loadHistory(),
  ]);
  setStatus("All data loaded from database.");
}

const user = requireLogin(["admin"]);
if (!user) {
  /* redirect handled */
} else {
  document.getElementById("adminUserLabel").textContent = `${user.name} (${user.email})`;
  document.getElementById("adminLogout")?.addEventListener("click", (e) => {
    e.preventDefault();
    logoutUser();
  });
  msgModal = new bootstrap.Modal(document.getElementById("msgModal"));
  initNav();
  renderModuleGrid();
  document.getElementById("refreshAllBtn")?.addEventListener("click", () =>
    refreshAll().catch((e) => setStatus(e.message, true))
  );
  document.getElementById("refreshContactBtn")?.addEventListener("click", () =>
    loadContact().catch((e) => setStatus(e.message, true))
  );
  document.getElementById("refreshPapersBtn")?.addEventListener("click", () =>
    loadPapers().catch((e) => setStatus(e.message, true))
  );
  document.getElementById("refreshModuleHistoryBtn")?.addEventListener("click", () =>
    loadModuleHistory().catch((e) => setStatus(e.message, true))
  );
  document.getElementById("moduleHistoryFilter")?.addEventListener("change", () =>
    loadModuleHistory().catch((e) => setStatus(e.message, true))
  );
  document.getElementById("refreshHistoryBtn")?.addEventListener("click", () =>
    loadHistory().catch((e) => setStatus(e.message, true))
  );
  document.getElementById("activityModuleFilter")?.addEventListener("change", () =>
    loadHistory().catch((e) => setStatus(e.message, true))
  );
  refreshAll().catch((e) => setStatus(e.message, true));
}
