/**
 * Premium module trial gate — SSO-aware.
 * Trial applies ONLY to premium modules. Logged-in users never see login again (SSO).
 */
const FREE_USES_PER_MODULE = 3;
const USAGE_STORAGE_KEY = "qsb_module_usage";

const MODULE_LABELS = {
  quiz: "Quiz Generator",
  summarizer: "Summarized Notes",
  grammar: "Grammar Check",
  humanizer: "AI Humanizer",
  transcript: "Video Transcript",
};

function hasUnlimitedAccess(moduleKey) {
  if (!isAuthenticated()) return false;
  if (moduleKey && typeof canAccessPremiumModule === "function") {
    return canAccessPremiumModule(moduleKey);
  }
  return hasGlobalPremiumAccess();
}

function readUsageMap() {
  try {
    return JSON.parse(localStorage.getItem(USAGE_STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function writeUsageMap(map) {
  localStorage.setItem(USAGE_STORAGE_KEY, JSON.stringify(map));
}

function getModuleUsage(moduleKey) {
  return readUsageMap()[moduleKey] || 0;
}

function getRemainingFreeUses(moduleKey) {
  if (hasUnlimitedAccess(moduleKey)) return FREE_USES_PER_MODULE;
  return Math.max(0, FREE_USES_PER_MODULE - getModuleUsage(moduleKey));
}

function recordModuleUse(moduleKey) {
  if (hasUnlimitedAccess(moduleKey)) return;
  const map = readUsageMap();
  map[moduleKey] = (map[moduleKey] || 0) + 1;
  writeUsageMap(map);
  renderUsageBanner(moduleKey);
}

function showLoginRequiredModal(moduleKey, label) {
  if (typeof setSSOReturnPath === "function") {
    setSSOReturnPath(typeof currentPageRedirect === "function" ? currentPageRedirect() : "");
  }

  if (typeof showLoginRequiredPortal === "function") {
    showLoginRequiredPortal(moduleKey, label || MODULE_LABELS[moduleKey] || "this tool");
    return;
  }

  if (typeof AuthPortal !== "undefined") {
    AuthPortal.show({
      mode: "modal",
      context: "module",
      moduleKey,
      moduleLabel: label || MODULE_LABELS[moduleKey] || "this tool",
      requiredRole: "",
      startSignup: true,
      allowClose: true,
      onSuccess: () => resumeAfterSSOLogin(moduleKey),
    });
    return;
  }

  const base = typeof getBasePath === "function" ? getBasePath() : "../../";
  const page = typeof currentPageRedirect === "function" ? currentPageRedirect() : "";
  const params = new URLSearchParams({ signup: "1" });
  if (page) params.set("redirect", page);
  window.location.href = `${base}login.html?${params.toString()}`;
}

function requireModuleAccess(moduleKey, label) {
  if (!moduleKey || !isPremiumModule(moduleKey)) return true;

  if (hasUnlimitedAccess(moduleKey)) return true;

  if (getModuleUsage(moduleKey) < FREE_USES_PER_MODULE) return true;

  showLoginRequiredModal(moduleKey, label);
  return false;
}

function renderUsageBanner(moduleKey) {
  const el = document.getElementById("usageBanner");
  if (!el) return;

  if (!moduleKey || !isPremiumModule(moduleKey)) {
    el.style.display = "none";
    el.innerHTML = "";
    return;
  }

  const user = typeof getUser === "function" ? getUser() : null;

  if (user && hasUnlimitedAccess(moduleKey)) {
    const firstName = (user.name || "User").split(" ")[0];
    el.className = "usage-banner usage-banner-logged";
    el.innerHTML = `
      <span><i class="fas fa-user-check me-2"></i>Signed in as <strong>${firstName}</strong></span>
      <a href="#" class="usage-banner-logout" id="usageBannerLogout">Sign out</a>`;
    el.style.display = "flex";
    const logoutLink = document.getElementById("usageBannerLogout");
    if (logoutLink) {
      logoutLink.onclick = (e) => {
        e.preventDefault();
        if (typeof logoutUser === "function") logoutUser();
      };
    }
    return;
  }

  const left = getRemainingFreeUses(moduleKey);
  if (left <= 0) {
    el.className = "usage-banner usage-banner-limit";
    el.innerHTML = `<i class="fas fa-lock me-2"></i>Free trial finished. <a href="#" id="usageBannerLoginLink">Sign in to continue</a>`;
    el.style.display = "block";
    const link = document.getElementById("usageBannerLoginLink");
    if (link) {
      link.onclick = (e) => {
        e.preventDefault();
        showLoginRequiredModal(moduleKey, MODULE_LABELS[moduleKey]);
      };
    }
    return;
  }

  el.className = "usage-banner usage-banner-free";
  el.innerHTML = `<i class="fas fa-gift me-2"></i>Free trial: <strong>${left}</strong> use${left === 1 ? "" : "s"} left — <a href="#" id="usageBannerSignIn">Sign in once</a> for unlimited access on all tools`;
  el.style.display = "block";
  const signIn = document.getElementById("usageBannerSignIn");
  if (signIn) {
    signIn.onclick = (e) => {
      e.preventDefault();
      showLoginRequiredModal(moduleKey, MODULE_LABELS[moduleKey]);
    };
  }
}

function initModuleAuth(moduleKey) {
  if (!moduleKey || !isPremiumModule(moduleKey)) return;

  const refresh = () => {
    if (typeof syncAuthUI === "function") syncAuthUI(moduleKey);
    else {
      if (typeof updateAuthNav === "function") updateAuthNav(document);
      renderUsageBanner(moduleKey);
    }
  };
  refresh();
  window.addEventListener("qsb-auth-change", refresh);
  window.addEventListener("qsb-sso-ready", refresh);
  window.addEventListener("storage", (e) => {
    if (e.key === "qsb_user" || e.key === "qsb_session_meta") refresh();
  });
}

function autoInitModuleAuth() {
  const body = document.body;
  if (!body || body.dataset.skipUsageBanner === "1") return;
  if (!body.hasAttribute("data-auth-module")) return;
  const key = body.getAttribute("data-auth-module");
  if (!key || !isPremiumModule(key)) return;
  initModuleAuth(key);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", autoInitModuleAuth);
} else {
  autoInitModuleAuth();
}
