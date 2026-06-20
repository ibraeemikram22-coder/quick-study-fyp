/**
 * Global Single Sign-On (SSO) — one login, shared across the entire application.
 * Session: localStorage qsb_user + qsb_session_meta (synced on all pages via events).
 */
const SSO_SESSION_META_KEY = "qsb_session_meta";
const SSO_PENDING_RETURN_KEY = "qsb_sso_return";
const SSO_SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

/** Premium modules that use the free-trial gate (not dashboards). */
const SSO_PREMIUM_MODULES = new Set([
  "quiz",
  "summarizer",
  "grammar",
  "humanizer",
  "transcript",
]);

/** Which roles may use each premium module once signed in. */
const SSO_MODULE_ROLES = {
  quiz: ["student", "teacher", "admin"],
  summarizer: ["student", "teacher", "admin"],
  grammar: ["student", "teacher", "admin"],
  humanizer: ["student", "teacher", "admin"],
  transcript: ["student", "teacher", "admin"],
};

const SSO_DASHBOARD_ROLES = {
  "questionbank/student.html": "student",
  "questionbank/teacher.html": "teacher",
  "questionbank/admin.html": "admin",
  "admin/dashboard.html": "admin",
};

function ssoNormalizeRole(role) {
  const r = String(role || "student").toLowerCase().trim();
  return ["student", "teacher", "admin"].includes(r) ? r : "student";
}

function ssoGetSessionMeta() {
  try {
    return JSON.parse(localStorage.getItem(SSO_SESSION_META_KEY) || "null");
  } catch {
    return null;
  }
}

function ssoIsSessionValid() {
  const raw = (() => {
    try {
      return JSON.parse(localStorage.getItem("qsb_user") || "null");
    } catch {
      return null;
    }
  })();
  if (!raw || !raw.id) return false;
  const meta = ssoGetSessionMeta();
  if (!meta || !meta.expiresAt) return true;
  return Date.now() < meta.expiresAt;
}

function ssoGetUser() {
  if (!ssoIsSessionValid()) return null;
  try {
    const raw = JSON.parse(localStorage.getItem("qsb_user") || "null");
    if (!raw) return null;
    return { ...raw, role: ssoNormalizeRole(raw.role) };
  } catch {
    return null;
  }
}

function establishSession(user) {
  const normalized = {
    ...user,
    role: ssoNormalizeRole(user.role),
  };
  localStorage.setItem("qsb_user", JSON.stringify(normalized));
  localStorage.setItem(
    SSO_SESSION_META_KEY,
    JSON.stringify({
      loggedInAt: Date.now(),
      expiresAt: Date.now() + SSO_SESSION_TTL_MS,
      role: normalized.role,
      userId: normalized.id,
    })
  );
  window.dispatchEvent(new CustomEvent("qsb-auth-change", { detail: { user: normalized } }));
  window.dispatchEvent(new CustomEvent("qsb-sso-ready", { detail: { user: normalized } }));
  return normalized;
}

function endSession() {
  localStorage.removeItem("qsb_user");
  localStorage.removeItem(SSO_SESSION_META_KEY);
  sessionStorage.removeItem("qsb_auth_block");
  sessionStorage.removeItem(SSO_PENDING_RETURN_KEY);
  window.dispatchEvent(new CustomEvent("qsb-auth-change", { detail: { user: null } }));
  window.dispatchEvent(new CustomEvent("qsb-sso-ended"));
}

function isAuthenticated() {
  return !!ssoGetUser();
}

function isPremiumModule(moduleKey) {
  return SSO_PREMIUM_MODULES.has(moduleKey);
}

function canAccessPremiumModule(moduleKey) {
  const user = ssoGetUser();
  if (!user) return false;
  const allowed = SSO_MODULE_ROLES[moduleKey] || ["student", "teacher", "admin"];
  return allowed.includes(user.role);
}

function hasGlobalPremiumAccess() {
  return isAuthenticated();
}

function setSSOReturnPath(path) {
  if (path) sessionStorage.setItem(SSO_PENDING_RETURN_KEY, path);
}

function consumeSSOReturnPath() {
  const p = sessionStorage.getItem(SSO_PENDING_RETURN_KEY) || "";
  sessionStorage.removeItem(SSO_PENDING_RETURN_KEY);
  return p;
}

function resumeAfterSSOLogin(moduleKey) {
  if (typeof syncAuthUI === "function") syncAuthUI(moduleKey);
  const pending = consumeSSOReturnPath();
  if (pending && pending !== (typeof currentPageRedirect === "function" ? currentPageRedirect() : "")) {
    const base = typeof getBasePath === "function" ? getBasePath() : "./";
    window.location.href = `${base}${pending.replace(/^\.\//, "")}`;
    return;
  }
  window.location.reload();
}

function initGlobalSSO() {
  if (!ssoIsSessionValid()) {
    endSession();
    return;
  }
  const user = ssoGetUser();
  if (user && !ssoGetSessionMeta()) {
    establishSession(user);
  }
  if (typeof syncUserFromServer === "function") {
    syncUserFromServer();
  }
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", initGlobalSSO);
  window.addEventListener("storage", (e) => {
    if (e.key === "qsb_user" || e.key === SSO_SESSION_META_KEY) {
      window.dispatchEvent(new CustomEvent("qsb-auth-change", { detail: { user: ssoGetUser() } }));
    }
  });
}
