const AUTH_KEY = "qsb_user";
const AUTH_BLOCK_KEY = "qsb_auth_block";
const AVATAR_KEY = "qsb_avatars";

function saveUser(user) {
  if (typeof establishSession === "function") {
    establishSession(user);
    return;
  }
  localStorage.setItem(AUTH_KEY, JSON.stringify(user));
  window.dispatchEvent(new CustomEvent("qsb-auth-change", { detail: { user } }));
}

function notifyAuthChange(user) {
  window.dispatchEvent(new CustomEvent("qsb-auth-change", { detail: { user: user ?? null } }));
}

function syncAuthUI(moduleKey) {
  if (typeof updateAuthNav === "function") updateAuthNav(document);
  if (typeof renderUsageBanner === "function" && moduleKey && isPremiumModule(moduleKey)) {
    renderUsageBanner(moduleKey);
  }
}

function getAvatarMap() {
  try {
    return JSON.parse(localStorage.getItem(AVATAR_KEY) || "{}");
  } catch {
    return {};
  }
}

function getUserAvatar(userId) {
  if (!userId) return "";
  return getAvatarMap()[String(userId)] || "";
}

function setUserAvatar(userId, dataUrl) {
  if (!userId) return;
  const map = getAvatarMap();
  if (dataUrl) map[String(userId)] = dataUrl;
  else delete map[String(userId)];
  localStorage.setItem(AVATAR_KEY, JSON.stringify(map));
}

function userInitial(user) {
  const n = user?.name || user?.email || "?";
  return String(n).charAt(0).toUpperCase();
}

function buildAvatarEl(user, extraClass) {
  const cls = `user-avatar-circle ${extraClass || ""}`.trim();
  const avatar = getUserAvatar(user?.id);
  if (avatar) {
    return `<span class="${cls}"><img src="${avatar}" alt="Profile"></span>`;
  }
  return `<span class="${cls} user-avatar-initial">${userInitial(user)}</span>`;
}

function getUser() {
  if (typeof ssoGetUser === "function") {
    const u = ssoGetUser();
    if (u) return u;
  }
  try {
    const raw = JSON.parse(localStorage.getItem(AUTH_KEY) || "null");
    if (!raw) return null;
    const role = String(raw.role || "student").toLowerCase().trim();
    const valid = ["student", "teacher", "admin"];
    return { ...raw, role: valid.includes(role) ? role : "student" };
  } catch {
    return null;
  }
}

function clearAuthSession() {
  if (typeof endSession === "function") {
    endSession();
    return;
  }
  localStorage.removeItem(AUTH_KEY);
  sessionStorage.removeItem(AUTH_BLOCK_KEY);
  notifyAuthChange(null);
}

async function syncUserFromServer() {
  const user = getUser();
  if (!user || !user.id || !user.email) return null;
  try {
    const res = await fetch(`${API_BASE}/api/auth/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ userId: user.id, email: user.email }),
    });
    const data = await res.json();
    if (!data.valid) {
      clearAuthSession();
      return null;
    }
    if (data.user) {
      saveUser(data.user);
      return data.user;
    }
    return user;
  } catch {
    return user;
  }
}

function logoutToPortal(requiredRole, redirect) {
  clearAuthSession();
  const base = getBasePath();
  const params = new URLSearchParams();
  if (redirect) params.set("redirect", redirect);
  if (requiredRole) params.set("role", requiredRole);
  if (requiredRole === "student" || requiredRole === "teacher") {
    params.set("signup", "1");
  }
  params.set("reset", "1");
  window.location.href = `${base}login.html?${params.toString()}`;
}

function logoutUser() {
  clearAuthSession();
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

function getLoginUrl(redirectAfter, requiredRole) {
  const base = getBasePath();
  const params = new URLSearchParams();
  const target = redirectAfter || currentPageRedirect();
  if (target) params.set("redirect", target);
  if (requiredRole) params.set("role", requiredRole);
  const qs = params.toString();
  return qs ? `${base}login.html?${qs}` : `${base}login.html`;
}

/**
 * Dashboard SSO — recognizes existing global session; no trial prompts on dashboards.
 */
function requireDashboardAccess(expectedRole) {
  const user = getUser();

  if (user && (user.role === expectedRole || user.role === "admin")) {
    return user;
  }

  const page = currentPageRedirect();

  if (!user) {
    if (typeof AuthPortal !== "undefined") {
      AuthPortal.show({
        mode: "fullscreen",
        context: "dashboard",
        requiredRole: expectedRole,
        redirect: page,
        startSignup: true,
        reloadOnSuccess: true,
      });
    } else {
      logoutToPortal(expectedRole, page);
    }
    return null;
  }

  if (typeof AuthPortal !== "undefined") {
    AuthPortal.show({
      mode: "fullscreen",
      context: "dashboard",
      requiredRole: expectedRole,
      redirect: page,
      reason:
        typeof authPortalRoleMismatchMessage === "function"
          ? authPortalRoleMismatchMessage(user.role, expectedRole)
          : `Please sign in with your ${expectedRole} account.`,
      startSignup: true,
      reloadOnSuccess: true,
    });
  } else {
    logoutToPortal(expectedRole, page);
  }
  return null;
}

/** @deprecated Use requireDashboardAccess — kept for admin panel compatibility */
function requireLogin(allowedRoles) {
  const role = allowedRoles && allowedRoles.length === 1 ? allowedRoles[0] : "";
  if (!role) return getUser();
  return requireDashboardAccess(role);
}

function mountDashboardRoleBar(slotId, expectedRole) {
  const bar = document.getElementById(slotId);
  if (!bar) return;
  const user = getUser();
  if (!user) {
    bar.style.display = "none";
    return;
  }
  const first = (user.name || user.email || "User").split(" ")[0];
  let roleLabel = expectedRole === "teacher" ? "Teacher" : "Student";
  if (user.role === "admin") roleLabel = "Admin";
  else if (user.role === "teacher" && expectedRole === "teacher") roleLabel = "Teacher";
  else if (user.role === "student" && expectedRole === "student") roleLabel = "Student";
  bar.style.display = "flex";
  bar.innerHTML = `
    <span><i class="fas fa-user-circle me-2"></i>Signed in as <strong>${first}</strong> (${roleLabel})</span>
    <a href="#" class="module-role-logout" data-role-logout>Sign out</a>`;
  bar.querySelector("[data-role-logout]").onclick = (e) => {
    e.preventDefault();
    logoutUser();
  };
}

async function apiAuth(path, body) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Unable to connect. Please make sure the application is running.");
  }

  let data = {};
  try {
    data = await res.json();
  } catch {
    throw new Error("Unable to complete request. Please try again.");
  }

  if (!res.ok || data.success === false) {
    throw new Error(data.error || "Auth failed");
  }
  return data;
}

async function checkBackendOnline() {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { method: "GET" });
    return res.ok;
  } catch {
    return false;
  }
}
