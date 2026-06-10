const AUTH_KEY = "qsb_user";
const AUTH_BLOCK_KEY = "qsb_auth_block";

function saveUser(user) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(user));
}

function getUser() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_KEY) || "null");
  } catch {
    return null;
  }
}

function logoutUser() {
  localStorage.removeItem(AUTH_KEY);
  sessionStorage.removeItem(AUTH_BLOCK_KEY);
  const base = window.location.pathname.includes("/module/") ? "../../" : "./";
  window.location.href = base + "login.html";
}

function getBasePath() {
  const p = window.location.pathname;
  if (p.includes("/module/")) return "../../";
  if (p.includes("/admin/")) return "../";
  return "./";
}

function currentPageRedirect() {
  const p = window.location.pathname;
  const i = p.indexOf("/module/");
  if (i >= 0) return p.slice(i + 1);
  const j = p.indexOf("/admin/");
  if (j >= 0) return p.slice(j + 1);
  return "";
}

function getLoginUrl(redirectAfter) {
  const base = getBasePath();
  let url = `${base}login.html`;
  const target = redirectAfter || currentPageRedirect();
  if (target) {
    url += `?redirect=${encodeURIComponent(target)}`;
  }
  return url;
}

/**
 * Only the listed roles may open this page.
 * student.html → ["student"] only
 * teacher.html → ["teacher"] only
 * admin.html   → ["admin"] only
 */
function requireLogin(allowedRoles) {
  const user = getUser();
  const page = currentPageRedirect();

  if (!user) {
    window.location.href = getLoginUrl(page);
    return null;
  }

  if (allowedRoles && allowedRoles.length && !allowedRoles.includes(user.role)) {
    sessionStorage.setItem(
      AUTH_BLOCK_KEY,
      JSON.stringify({
        currentRole: user.role,
        requiredRoles: allowedRoles,
        redirect: page,
      })
    );
    window.location.href = getLoginUrl(page);
    return null;
  }

  return user;
}

function showDashboardBar(user, roleLabel) {
  const container = document.querySelector("section.py-5 .container");
  if (!container || !user) return;

  const bar = document.createElement("div");
  bar.className = "dashboard-user-bar";
  bar.innerHTML = `
    <span><strong>${user.name}</strong> — ${roleLabel}</span>
    <a href="#" class="logout-link" id="dashboardLogout">Logout</a>
  `;
  container.prepend(bar);
  document.getElementById("dashboardLogout").onclick = (e) => {
    e.preventDefault();
    logoutUser();
  };
}

async function apiAuth(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok || data.success === false) {
    throw new Error(data.error || "Auth failed");
  }
  return data;
}
