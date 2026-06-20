/**
 * Unified authentication portal — same UI for login page, modules, and dashboards.
 */
const AUTH_PORTAL_COPY = {
  student: {
    badge: "Student Portal",
    icon: "fa-user-graduate",
    loginTitle: "Welcome back",
    loginSub: "Sign in with your student account to continue.",
    signupTitle: "Create student account",
    signupSub: "Register to access papers, quizzes, and all learning tools.",
  },
  teacher: {
    badge: "Teacher Portal",
    icon: "fa-chalkboard-teacher",
    loginTitle: "Teacher sign in",
    loginSub: "Sign in with your teacher account to continue.",
    signupTitle: "Create teacher account",
    signupSub: "Register with your school or college to create exam papers.",
  },
  admin: {
    badge: "Admin",
    icon: "fa-shield-halved",
    loginTitle: "Admin sign in",
    loginSub: "Administrator access only.",
    signupTitle: "Admin",
    signupSub: "Contact system administrator.",
  },
  general: {
    badge: "Sign in",
    icon: "fa-user",
    loginTitle: "Welcome back",
    loginSub: "Sign in with your email to continue.",
    signupTitle: "Create account",
    signupSub: "One account works across all tools on this site.",
  },
  module: {
    badge: "Sign in",
    icon: "fa-unlock",
    loginTitle: "Sign in to continue",
    loginSub: "Use the same email and password as your other tools.",
    signupTitle: "Create account",
    signupSub: "Register once — access all modules without signing in again.",
  },
};

let _portalState = null;

function authPortalNormalizeUser(user) {
  if (!user) return null;
  const role = String(user.role || "student").toLowerCase().trim();
  const valid = ["student", "teacher", "admin"];
  return { ...user, role: valid.includes(role) ? role : "student" };
}

function authPortalRoleMismatchMessage(actualRole, requiredRole) {
  if (actualRole === "student" && requiredRole === "teacher") {
    return "This account is registered as a Student. Please sign in through the Student Portal.";
  }
  if (actualRole === "teacher" && requiredRole === "student") {
    return "This account is registered as a Teacher. Please use the Teacher Portal.";
  }
  if (requiredRole === "admin") {
    return "Administrator access only. Please sign in with an admin account.";
  }
  if (requiredRole === "student") {
    return "Please sign in with your Student account.";
  }
  if (requiredRole === "teacher") {
    return "Please sign in with your Teacher account.";
  }
  return "Please sign in with the correct account type.";
}

function authPortalFormatError(err) {
  const msg = String(err?.message || err || "").trim();
  if (!msg) return "Unable to sign in. Please try again.";
  if (/incorrect password/i.test(msg)) return "Invalid email or password.";
  if (/no account found/i.test(msg)) return "Account not found.";
  if (/email already/i.test(msg)) return msg;
  if (/session|expired|unauthorized/i.test(msg)) return "Session expired. Please sign in again.";
  if (typeof toUserMessage === "function") return toUserMessage(err);
  return msg.length > 120 ? "Unable to sign in. Please try again." : msg;
}

function authPortalResolveRedirect(user, options) {
  const requiredRole = options.requiredRole || "";
  const redirect = options.redirect || "";
  const normalized = authPortalNormalizeUser(user);

  if (normalized.role === "admin") {
    return options.adminRedirect || "admin/dashboard.html";
  }

  if (requiredRole && normalized.role !== requiredRole) {
    return null;
  }

  if (redirect) {
    const base = typeof getBasePath === "function" ? getBasePath() : "./";
    if (redirect.startsWith("http")) return redirect;
    if (redirect.startsWith("/")) return redirect;
    return `${base}${redirect.replace(/^\.\//, "")}`;
  }

  if (options.moduleKey || options.context === "module") {
    return null;
  }

  if (normalized.role === "student") {
    return (typeof getBasePath === "function" ? getBasePath() : "./") + "module/questionbank/student.html";
  }
  if (normalized.role === "teacher") {
    return (typeof getBasePath === "function" ? getBasePath() : "./") + "module/questionbank/teacher.html";
  }
  return (typeof getBasePath === "function" ? getBasePath() : "./") + "profile.html";
}

function authPortalCopyKey(requiredRole, context) {
  if (context === "module") return "module";
  if (context === "dashboard") {
    if (requiredRole === "student" || requiredRole === "teacher" || requiredRole === "admin") {
      return requiredRole;
    }
  }
  if (requiredRole === "admin") return "admin";
  return "general";
}

function authPortalIsDashboardContext(options) {
  if (options.context === "dashboard") return true;
  if (options.context === "module") return false;
  const role = options.requiredRole || "";
  const redirect = String(options.redirect || "");
  if (role === "student" && redirect.includes("questionbank/student")) return true;
  if (role === "teacher" && redirect.includes("questionbank/teacher")) return true;
  if (role === "admin" && redirect.includes("admin")) return true;
  return role === "student" || role === "teacher";
}

function authPortalBuildHtml(options) {
  const isDashboard = authPortalIsDashboardContext(options);
  const context = options.moduleKey ? "module" : isDashboard ? "dashboard" : options.context || "general";
  const key = authPortalCopyKey(options.requiredRole, context);
  const copy = AUTH_PORTAL_COPY[key];
  const showSwitch = isDashboard && (options.requiredRole === "student" || options.requiredRole === "teacher");
  const allowSignup = options.allowSignup !== false && key !== "admin";
  const allowClose = options.allowClose === true && options.mode === "modal";
  const showRoleBadge = isDashboard && key !== "general" && key !== "module";

  const switchLinks = [];
  if (showSwitch && options.requiredRole !== "student") {
    switchLinks.push({ role: "student", label: "Student Portal" });
  }
  if (showSwitch && options.requiredRole !== "teacher") {
    switchLinks.push({ role: "teacher", label: "Teacher Portal" });
  }
  const switchHtml = switchLinks.length
    ? `<p class="auth-portal-switch">${switchLinks
        .map((s) => `<a href="#" data-portal-role="${s.role}">${s.label}</a>`)
        .join(" · ")}</p>`
    : "";

  return `
    <div class="auth-portal-shell" role="dialog" aria-modal="true" aria-labelledby="authPortalTitle">
      <header class="auth-portal-brand">
        <h1 class="auth-portal-logo">Quick Study <span>Builder</span></h1>
        ${showRoleBadge ? `<div class="auth-portal-badge"><i class="fas ${copy.icon}"></i> ${copy.badge}</div>` : ""}
      </header>
      <div class="auth-portal-card">
        <h2 class="auth-portal-title" id="authPortalTitle">${copy.loginTitle}</h2>
        <p class="auth-portal-sub" id="authPortalSub">${copy.loginSub}</p>
        ${options.reason ? `<p class="auth-portal-reason" id="authPortalReason">${options.reason}</p>` : ""}
        ${
          allowSignup
            ? `<div class="auth-portal-tabs" id="authPortalTabs">
            <button type="button" class="auth-portal-tab active" data-tab="login">Log in</button>
            <button type="button" class="auth-portal-tab" data-tab="signup">Sign up</button>
          </div>`
            : ""
        }
        <form class="auth-portal-form" id="authPortalForm" autocomplete="off">
          <div class="auth-portal-signup" id="authPortalSignupFields">
            <label class="auth-portal-label" for="authPortalName">Full name</label>
            <input type="text" id="authPortalName" class="auth-portal-input" placeholder="Your name" autocomplete="name">
            <div class="auth-portal-teacher-school" id="authPortalSchoolWrap">
              <label class="auth-portal-label" for="authPortalSchool">School / college</label>
              <input type="text" id="authPortalSchool" class="auth-portal-input" placeholder="Institution name">
            </div>
          </div>
          <label class="auth-portal-label" for="authPortalEmail">Email</label>
          <input type="email" id="authPortalEmail" class="auth-portal-input" placeholder="Enter your email" autocomplete="email" spellcheck="false">
          <label class="auth-portal-label" for="authPortalPassword">Password</label>
          <input type="password" id="authPortalPassword" class="auth-portal-input" placeholder="Enter your password" autocomplete="current-password">
          <button type="submit" class="auth-portal-submit" id="authPortalSubmit">Log in</button>
        </form>
        <p class="auth-portal-msg" id="authPortalMsg" role="status"></p>
        ${switchHtml}
        ${allowClose ? '<button type="button" class="auth-portal-close" id="authPortalClose">Continue browsing</button>' : ""}
      </div>
    </div>`;
}

function authPortalShowMsg(el, text, isError) {
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("is-error", !!isError);
  el.classList.toggle("is-success", !!text && !isError);
}

function authPortalSetSignupMode(root, on, requiredRole, context) {
  const tabs = root.querySelectorAll(".auth-portal-tab");
  const signupFields = root.querySelector("#authPortalSignupFields");
  const schoolWrap = root.querySelector("#authPortalSchoolWrap");
  const title = root.querySelector("#authPortalTitle");
  const sub = root.querySelector("#authPortalSub");
  const submit = root.querySelector("#authPortalSubmit");
  const key = authPortalCopyKey(requiredRole, context);
  const copy = AUTH_PORTAL_COPY[key];

  tabs.forEach((t) => t.classList.toggle("active", (t.dataset.tab === "login") !== on));
  signupFields?.classList.toggle("visible", on);

  const isTeacherSignup = on && requiredRole === "teacher" && context === "dashboard";
  schoolWrap?.classList.toggle("visible", isTeacherSignup);

  if (title) title.textContent = on ? copy.signupTitle : copy.loginTitle;
  if (sub) sub.textContent = on ? copy.signupSub : copy.loginSub;
  if (submit) submit.textContent = on ? "Create account" : "Log in";
}

function authPortalBind(root, options) {
  let isSignup = options.startSignup === true;
  const requiredRole = options.requiredRole || "";
  const isDashboard = authPortalIsDashboardContext(options);
  const context = options.moduleKey ? "module" : isDashboard ? "dashboard" : options.context || "general";
  const msgEl = root.querySelector("#authPortalMsg");
  const form = root.querySelector("#authPortalForm");
  const submitBtn = root.querySelector("#authPortalSubmit");

  authPortalSetSignupMode(root, isSignup, requiredRole, context);

  root.querySelectorAll(".auth-portal-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      isSignup = tab.dataset.tab === "signup";
      authPortalSetSignupMode(root, isSignup, requiredRole, context);
      authPortalShowMsg(msgEl, "", false);
    });
  });

  root.querySelectorAll("[data-portal-role]").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const role = link.dataset.portalRole;
      AuthPortal.hide();
      AuthPortal.show({
        ...options,
        context: "dashboard",
        requiredRole: role,
        reason: "",
        startSignup: true,
      });
    });
  });

  root.querySelector("#authPortalClose")?.addEventListener("click", () => AuthPortal.hide());

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    authPortalShowMsg(msgEl, "", false);

    const email = root.querySelector("#authPortalEmail")?.value.trim().toLowerCase() || "";
    const password = root.querySelector("#authPortalPassword")?.value || "";

    if (!email.includes("@")) {
      authPortalShowMsg(msgEl, "Please enter a valid email address.", true);
      return;
    }
    if (!password || password.length < 6) {
      authPortalShowMsg(msgEl, "Password must be at least 6 characters.", true);
      return;
    }

    submitBtn.disabled = true;

    try {
      if (isSignup) {
        const name = root.querySelector("#authPortalName")?.value.trim() || "";
        if (!name) {
          authPortalShowMsg(msgEl, "Please enter your name.", true);
          return;
        }
        const role = context === "dashboard" && requiredRole === "teacher" ? "teacher" : "student";
        const payload = { name, email, password, role };
        if (role === "teacher") {
          payload.schoolName = root.querySelector("#authPortalSchool")?.value.trim() || "";
          if (!payload.schoolName) {
            authPortalShowMsg(msgEl, "Please enter your school or college name.", true);
            return;
          }
        }
        const data = await apiAuth("/api/auth/signup", payload);
        const user = authPortalNormalizeUser(data.user);
        if (isDashboard && requiredRole && user.role !== requiredRole && user.role !== "admin") {
          authPortalShowMsg(msgEl, authPortalRoleMismatchMessage(user.role, requiredRole), true);
          return;
        }
        saveUser(user);
        authPortalShowMsg(msgEl, "Account created successfully.", false);
        AuthPortal._finishSuccess(user, options);
        return;
      }

      const data = await apiAuth("/api/auth/login", { email, password });
      const user = authPortalNormalizeUser(data.user);

      if (isDashboard && requiredRole && user.role !== requiredRole && user.role !== "admin") {
        authPortalShowMsg(msgEl, authPortalRoleMismatchMessage(user.role, requiredRole), true);
        return;
      }

      saveUser(user);
      authPortalShowMsg(msgEl, "Signed in successfully.", false);
      AuthPortal._finishSuccess(user, options);
    } catch (err) {
      authPortalShowMsg(msgEl, authPortalFormatError(err), true);
    } finally {
      submitBtn.disabled = false;
    }
  });
}

const AuthPortal = {
  isVisible() {
    return !!document.getElementById("authPortalOverlay")?.classList.contains("is-open");
  },

  hide() {
    const overlay = document.getElementById("authPortalOverlay");
    if (overlay) {
      overlay.classList.remove("is-open");
      overlay.innerHTML = "";
    }
    document.body.classList.remove("auth-portal-locked");
    _portalState = null;
  },

  _finishSuccess(user, options) {
    if (typeof options.onSuccess === "function") {
      AuthPortal.hide();
      options.onSuccess(user);
      return;
    }

    const url = authPortalResolveRedirect(user, options);
    if (url && options.mode !== "modal") {
      setTimeout(() => {
        window.location.href = url;
      }, 350);
      return;
    }

    AuthPortal.hide();
    if (options.moduleKey && typeof resumeAfterSSOLogin === "function") {
      resumeAfterSSOLogin(options.moduleKey);
      return;
    }
    if (typeof syncAuthUI === "function") syncAuthUI(options.moduleKey);
    else if (typeof renderUsageBanner === "function") renderUsageBanner(options.moduleKey);
    if (options.reloadOnSuccess) window.location.reload();
  },

  show(options = {}) {
    const isDashboard =
      options.context === "dashboard" ||
      (options.requiredRole &&
        (options.requiredRole === "student" || options.requiredRole === "teacher") &&
        !options.moduleKey);
    const opts = {
      mode: options.mode || "fullscreen",
      context: options.context || (options.moduleKey ? "module" : isDashboard ? "dashboard" : "general"),
      requiredRole: isDashboard ? options.requiredRole || "" : "",
      redirect: options.redirect || (typeof currentPageRedirect === "function" ? currentPageRedirect() : ""),
      reason: options.reason || "",
      moduleKey: options.moduleKey || "",
      moduleLabel: options.moduleLabel || "",
      allowSignup: options.allowSignup !== false,
      allowClose: options.allowClose === true,
      startSignup: options.startSignup === true,
      onSuccess: options.onSuccess || null,
      reloadOnSuccess: options.reloadOnSuccess === true,
      adminRedirect: options.adminRedirect || "",
    };

    if (!opts.reason && opts.moduleLabel && opts.mode === "modal") {
      opts.reason = `Sign in to continue using ${opts.moduleLabel}. Your free trial has ended.`;
    }

    let overlay = document.getElementById("authPortalOverlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "authPortalOverlay";
      document.body.appendChild(overlay);
    }

    overlay.className = `auth-portal-overlay ${opts.mode === "modal" ? "is-modal" : ""} is-open`;
    overlay.innerHTML = authPortalBuildHtml(opts);
    document.body.classList.add("auth-portal-locked");

    authPortalBind(overlay, opts);
    _portalState = opts;

    setTimeout(() => overlay.querySelector("#authPortalEmail")?.focus(), 80);
    return overlay;
  },
};

function showAuthPortal(options) {
  return AuthPortal.show(options);
}

function showLoginRequiredPortal(moduleKey, moduleLabel) {
  if (typeof setSSOReturnPath === "function") {
    setSSOReturnPath(typeof currentPageRedirect === "function" ? currentPageRedirect() : "");
  }
  return AuthPortal.show({
    mode: "modal",
    context: "module",
    moduleKey,
    moduleLabel,
    requiredRole: "",
    startSignup: true,
    allowClose: true,
    onSuccess: () => {
      if (typeof resumeAfterSSOLogin === "function") resumeAfterSSOLogin(moduleKey);
      else if (typeof syncAuthUI === "function") syncAuthUI(moduleKey);
      else renderUsageBanner(moduleKey);
    },
  });
}
