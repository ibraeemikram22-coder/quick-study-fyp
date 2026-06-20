/**
 * Full-page login — uses shared auth-portal logic and messaging.
 */
const authEmail = document.getElementById("authEmail");
const authPassword = document.getElementById("authPassword");
const signupName = document.getElementById("signupName");
const signupSchool = document.getElementById("signupSchool");
const signupFields = document.getElementById("signupFields");
const teacherSchoolWrap = document.getElementById("teacherSchoolWrap");
const authMsg = document.getElementById("authMsg");
const formTitle = document.getElementById("formTitle");
const formSub = document.getElementById("formSub");
const mainActionBtn = document.getElementById("mainActionBtn");
const tabLogin = document.getElementById("tabLogin");
const tabSignup = document.getElementById("tabSignup");
const loginForm = document.getElementById("loginForm");
const backendStatus = document.getElementById("backendStatus");
const loginBrand = document.querySelector(".login-brand");

let isSignup = false;

function normalizeUser(user) {
  return typeof authPortalNormalizeUser === "function"
    ? authPortalNormalizeUser(user)
    : user;
}

function loginPageIsDashboardFlow(params) {
  const role = params.get("role") || "";
  const redirect = params.get("redirect") || "";
  if (role === "student" && redirect.includes("questionbank/student")) return true;
  if (role === "teacher" && redirect.includes("questionbank/teacher")) return true;
  if (role === "admin") return true;
  return false;
}

function loginPageCopyKey(params) {
  if (loginPageIsDashboardFlow(params)) {
    const role = params.get("role") || "";
    if (role === "student" || role === "teacher" || role === "admin") return role;
  }
  const redirect = params.get("redirect") || "";
  if (redirect && !loginPageIsDashboardFlow(params)) return "module";
  return "general";
}

function showUserMsg(text, isError) {
  if (authMsg) {
    authMsg.textContent = text;
    authMsg.style.color = isError ? "#c0392b" : "#1e8449";
  }
}

function clearAuthFields() {
  if (authEmail) authEmail.value = "";
  if (authPassword) authPassword.value = "";
}

function applyPortalBranding(params) {
  const isDashboard = loginPageIsDashboardFlow(params);
  const key = loginPageCopyKey(params);
  const copy = AUTH_PORTAL_COPY[key];
  if (loginBrand) {
    const old = loginBrand.querySelector(".auth-portal-badge");
    if (old) old.remove();
    if (isDashboard) {
      const badge = document.createElement("div");
      badge.className = "auth-portal-badge";
      badge.style.marginTop = "0.5rem";
      badge.innerHTML = `<i class="fas ${copy.icon}"></i> ${copy.badge}`;
      loginBrand.appendChild(badge);
    }
  }
}

function setSignupMode(on) {
  isSignup = on;
  tabLogin?.classList.toggle("active", !on);
  tabSignup?.classList.toggle("active", on);
  signupFields?.classList.toggle("visible", on);
  const params = new URLSearchParams(window.location.search);
  const isDashboard = loginPageIsDashboardFlow(params);
  const key = loginPageCopyKey(params);
  const copy = AUTH_PORTAL_COPY[key];

  if (formTitle) formTitle.textContent = on ? copy.signupTitle : copy.loginTitle;
  if (formSub) formSub.textContent = on ? copy.signupSub : copy.loginSub;
  if (mainActionBtn) mainActionBtn.textContent = on ? "Create account" : "Log in";
  if (authPassword) {
    authPassword.placeholder = on ? "At least 6 characters" : "Enter your password";
  }

  const requiredRole = params.get("role") || "";
  const showTeacherSchool = on && isDashboard && requiredRole === "teacher";
  teacherSchoolWrap?.classList.toggle("visible", showTeacherSchool);
}

function goAfterLogin(user) {
  const params = new URLSearchParams(window.location.search);
  const isDashboard = loginPageIsDashboardFlow(params);
  const requiredRole = isDashboard ? params.get("role") || "" : "";
  const normalized = normalizeUser(user);

  const url =
    typeof authPortalResolveRedirect === "function"
      ? authPortalResolveRedirect(normalized, {
          requiredRole,
          redirect: params.get("redirect") || "",
          context: isDashboard ? "dashboard" : "module",
        })
      : null;

  if (isDashboard && !url && requiredRole && normalized.role !== requiredRole && normalized.role !== "admin") {
    clearAuthSession();
    showUserMsg(authPortalRoleMismatchMessage(normalized.role, requiredRole), true);
    if (requiredRole === "teacher") {
      teacherSchoolWrap?.classList.add("visible");
      setSignupMode(true);
    } else if (requiredRole === "student") {
      teacherSchoolWrap?.classList.remove("visible");
      setSignupMode(true);
    }
    return;
  }

  if (url) {
    window.location.href = url.startsWith("http") ? url : url.replace(/^\.\//, "./");
    return;
  }

  if (params.get("redirect")) {
    const redirect = params.get("redirect");
    window.location.href = redirect.startsWith("http") ? redirect : `./${redirect.replace(/^\.\//, "")}`;
    return;
  }

  window.location.href = "index.html";
}

async function handleUserAction() {
  const email = authEmail?.value.trim().toLowerCase() || "";
  const password = authPassword?.value || "";
  const params = new URLSearchParams(window.location.search);
  const isDashboard = loginPageIsDashboardFlow(params);
  const requiredRole = isDashboard ? params.get("role") || "" : "";

  if (!email.includes("@")) {
    showUserMsg("Please enter a valid email address.", true);
    return;
  }
  if (!password || password.length < 6) {
    showUserMsg("Password must be at least 6 characters.", true);
    return;
  }

  if (isSignup) {
    const name = signupName?.value.trim() || "";
    if (!name) {
      showUserMsg("Please enter your name.", true);
      return;
    }
    const role = isDashboard && requiredRole === "teacher" ? "teacher" : "student";
    const payload = { name, email, password, role };
    if (role === "teacher") {
      payload.schoolName = signupSchool?.value.trim() || "";
      if (!payload.schoolName) {
        showUserMsg("Please enter your school or college name.", true);
        return;
      }
    }
    try {
      const data = await apiAuth("/api/auth/signup", payload);
      const user = normalizeUser(data.user);
      if (isDashboard && requiredRole && user.role !== requiredRole && user.role !== "admin") {
        clearAuthSession();
        showUserMsg(authPortalRoleMismatchMessage(user.role, requiredRole), true);
        return;
      }
      saveUser(user);
      showUserMsg("Account created successfully. Redirecting…");
      setTimeout(() => goAfterLogin(user), 400);
    } catch (e) {
      showUserMsg(authPortalFormatError(e), true);
    }
    return;
  }

  try {
    const data = await apiAuth("/api/auth/login", { email, password });
    const user = normalizeUser(data.user);

    if (isDashboard && requiredRole && user.role !== requiredRole && user.role !== "admin") {
      clearAuthSession();
      showUserMsg(authPortalRoleMismatchMessage(user.role, requiredRole), true);
      if (requiredRole === "teacher") {
        teacherSchoolWrap?.classList.add("visible");
        setSignupMode(true);
      } else if (requiredRole === "student") {
        teacherSchoolWrap?.classList.remove("visible");
        setSignupMode(true);
      }
      return;
    }

    saveUser(user);
    showUserMsg("Signed in successfully. Redirecting…");
    setTimeout(() => goAfterLogin(user), 400);
  } catch (e) {
    showUserMsg(authPortalFormatError(e), true);
  }
}

tabLogin?.addEventListener("click", () => setSignupMode(false));
tabSignup?.addEventListener("click", () => setSignupMode(true));
mainActionBtn?.addEventListener("click", handleUserAction);
loginForm?.addEventListener("submit", (e) => {
  e.preventDefault();
  handleUserAction();
});

authPassword?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") handleUserAction();
});

function bindPortalSwitchLinks(params) {
  const shell = document.querySelector(".login-shell");
  if (!shell || shell.querySelector(".auth-portal-switch")) return;
  if (!loginPageIsDashboardFlow(params)) return;
  const role = params.get("role");
  if (role !== "student" && role !== "teacher") return;
  const p = document.createElement("p");
  p.className = "auth-portal-switch";
  p.style.marginTop = "1rem";
  if (role === "student") {
    p.innerHTML = `<a href="login.html?role=teacher&redirect=${encodeURIComponent("module/questionbank/teacher.html")}&signup=1">Need a Teacher account? Teacher Portal</a>`;
  } else if (role === "teacher") {
    p.innerHTML = `<a href="login.html?role=student&redirect=${encodeURIComponent("module/questionbank/student.html")}&signup=1">Need a Student account? Student Portal</a>`;
  }
  document.getElementById("userCard")?.appendChild(p);
}

(async function initLoginPage() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("reset") === "1") {
    if (typeof clearAuthSession === "function") clearAuthSession();
    else localStorage.removeItem("qsb_user");
    ["qsb_module_usage", "qsb_avatars", "qsb_admin_tab", "qsb_session_meta"].forEach((k) => {
      try {
        localStorage.removeItem(k);
      } catch {
        /* ignore */
      }
    });
    try {
      sessionStorage.removeItem("qsb_auth_block");
      sessionStorage.removeItem("qsb_sso_return");
      sessionStorage.removeItem("geminiCheck");
    } catch {
      /* ignore */
    }
  }

  clearAuthFields();

  const isDashboard = loginPageIsDashboardFlow(params);
  applyPortalBranding(params);
  bindPortalSwitchLinks(params);

  const online = await checkBackendOnline();
  if (backendStatus) {
    if (!online) {
      backendStatus.textContent = "Unable to connect. Please make sure the application is running.";
      backendStatus.className = "login-backend-status is-offline";
    } else {
      backendStatus.style.display = "none";
    }
  }

  if (isDashboard && params.get("role") === "teacher") {
    teacherSchoolWrap?.classList.add("visible");
    setSignupMode(true);
  } else if (isDashboard && (params.get("signup") === "1" || params.get("role") === "student")) {
    teacherSchoolWrap?.classList.remove("visible");
    setSignupMode(true);
  } else if (!isDashboard && params.get("signup") === "1") {
    teacherSchoolWrap?.classList.remove("visible");
    setSignupMode(true);
  } else {
    teacherSchoolWrap?.classList.remove("visible");
    setSignupMode(false);
  }

  const blockRaw = sessionStorage.getItem("qsb_auth_block");
  if (blockRaw) {
    try {
      const block = JSON.parse(blockRaw);
      sessionStorage.removeItem("qsb_auth_block");
      if (block.requiredRoles?.[0] && block.currentRole) {
        showUserMsg(
          authPortalRoleMismatchMessage(block.currentRole, block.requiredRoles[0]),
          true
        );
      }
    } catch {
      /* ignore */
    }
  }

  const existing = typeof getUser === "function" ? normalizeUser(getUser()) : null;
  const redirect = params.get("redirect");
  if (existing && redirect) {
    const requiredRole = isDashboard ? params.get("role") || "" : "";
    if (isDashboard && requiredRole && existing.role !== requiredRole && existing.role !== "admin") {
      clearAuthSession();
      showUserMsg(authPortalRoleMismatchMessage(existing.role, requiredRole), true);
    } else {
      goAfterLogin(existing);
    }
  }
})();
