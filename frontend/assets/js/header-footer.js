function getBasePath() {
  const path = window.location.pathname;
  if (path.includes("/module/")) {
    return "../../";
  }
  if (path.includes("/admin/")) {
    return "../";
  }
  return "./";
}

function applyNavLinks(root) {
  const base = getBasePath();
  root.querySelectorAll("a[data-nav]").forEach((a) => {
    const target = a.getAttribute("data-nav");
    if (!target) return;
    const redirect = a.getAttribute("data-redirect");
    const loginRole = a.getAttribute("data-login-role");
    if (redirect) {
      let href = `${base}${target}?redirect=${encodeURIComponent(redirect)}`;
      if (loginRole) href += `&role=${encodeURIComponent(loginRole)}`;
      a.href = href;
    } else {
      a.href = `${base}${target}`;
    }
  });
}

fetch(getBasePath() + "layout/header.html")
  .then((res) => res.text())
  .then((data) => {
    document.getElementById("header").innerHTML = data;

    const headerRoot = document.getElementById("header");
    applyNavLinks(headerRoot);

    const overlay = document.getElementById("mobileOverlay");
    if (overlay) {
      applyNavLinks(overlay);
    }

    const hamburger = document.getElementById("hamburgerBtn");
    const closeBtn = document.getElementById("mobileClose");

    if (hamburger && overlay) {
      hamburger.addEventListener("click", () => overlay.classList.add("active"));
    }
    if (closeBtn && overlay) {
      closeBtn.addEventListener("click", () => overlay.classList.remove("active"));
    }
    if (overlay) {
      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) overlay.classList.remove("active");
      });
      overlay.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => overlay.classList.remove("active"));
      });
    }

    updateAuthNav(document);
  });

window.addEventListener("qsb-auth-change", () => {
  if (typeof updateAuthNav === "function") updateAuthNav(document);
});
window.addEventListener("storage", (e) => {
  if ((e.key === "qsb_user" || e.key === "qsb_session_meta") && typeof updateAuthNav === "function") {
    updateAuthNav(document);
  }
});

function readStoredUser() {
  if (typeof getUser === "function") return getUser();
  try {
    return JSON.parse(localStorage.getItem("qsb_user") || "null");
  } catch {
    return null;
  }
}

function headerAvatarHtml(user) {
  if (typeof buildAvatarEl === "function") {
    return buildAvatarEl(user, "");
  }
  let avatar = "";
  try {
    const map = JSON.parse(localStorage.getItem("qsb_avatars") || "{}");
    avatar = map[String(user.id)] || "";
  } catch {
    /* ignore */
  }
  if (avatar) {
    return `<span class="user-avatar-circle"><img src="${avatar}" alt=""></span>`;
  }
  const initial = String(user.name || user.email || "?")
    .charAt(0)
    .toUpperCase();
  return `<span class="user-avatar-circle user-avatar-initial">${initial}</span>`;
}

function updateAuthNav(root) {
  if (!root) return;
  const user = readStoredUser();
  const base = getBasePath();
  const studentLogin = `${base}login.html?redirect=${encodeURIComponent("module/questionbank/student.html")}&role=student&signup=1`;
  const teacherLogin = `${base}login.html?redirect=${encodeURIComponent("module/questionbank/teacher.html")}&role=teacher&signup=1`;

  root.querySelectorAll(".js-nav-teacher").forEach((link) => {
    link.removeAttribute("data-nav");
    if (user?.role === "teacher") {
      link.href = `${base}module/questionbank/teacher.html`;
    } else {
      link.href = teacherLogin;
    }
  });

  root.querySelectorAll("a[data-nav]").forEach((link) => {
    const nav = link.getAttribute("data-nav") || "";
    if (!nav.includes("role=student")) return;
    link.removeAttribute("data-nav");
    if (user?.role === "student") {
      link.href = `${base}module/questionbank/student.html`;
    } else {
      link.href = studentLogin;
    }
  });

  root.querySelectorAll(".js-nav-profile").forEach((link) => {
    const slot = link.querySelector(".js-header-avatar-slot");
    if (user && user.role !== "admin") {
      link.style.display = "inline-flex";
      if (user.role === "teacher") {
        link.href = `${base}module/questionbank/teacher.html`;
      } else {
        link.href = base + "profile.html";
      }
      link.removeAttribute("data-nav");
      if (slot) slot.innerHTML = headerAvatarHtml(user);
    } else {
      link.style.display = "none";
    }
  });

  root.querySelectorAll(".js-nav-auth").forEach((authBtn) => {
    authBtn.onclick = null;
    authBtn.classList.add("cta-button");
    if (user && user.role !== "admin") {
      authBtn.textContent = "Logout";
      authBtn.removeAttribute("data-nav");
      authBtn.removeAttribute("data-redirect");
      authBtn.href = "#";
      authBtn.onclick = (e) => {
        e.preventDefault();
        if (typeof logoutUser === "function") logoutUser();
        else {
          if (typeof clearAuthSession === "function") clearAuthSession();
          else localStorage.removeItem("qsb_user");
          window.location.href = base + "login.html";
        }
      };
    } else if (user && user.role === "admin") {
      authBtn.textContent = "Admin";
      authBtn.setAttribute("data-nav", "admin/dashboard.html");
      applyNavLinks(authBtn.closest("nav") || root);
    } else {
      authBtn.textContent = "Login / Signup";
      authBtn.setAttribute("data-nav", "login.html?role=student&signup=1");
      applyNavLinks(authBtn.closest("nav") || root);
    }
  });
}

fetch(getBasePath() + "layout/footer.html")
  .then((res) => res.text())
  .then((data) => {
    document.getElementById("footer").innerHTML = data;
    const footer = document.getElementById("footer");
    if (footer) applyNavLinks(footer);
    loadFooterContactEmail();
  });

function loadFooterContactEmail() {
  const el = document.getElementById("footerContactEmail");
  if (!el) return;
  const apiBase = typeof API_BASE !== "undefined" ? API_BASE : "http://localhost:3000";
  fetch(`${apiBase}/api/contact/info`)
    .then((r) => r.json())
    .then((d) => {
      const email = d.data?.contactEmail || d.contactEmail;
      if (email) el.textContent = email;
    })
    .catch(() => {});
}

function loadChatbotWidget() {
  if (document.getElementById("chatbot-icon") || document.body.dataset.chatbotOff === "1") return;

  const base = getBasePath();

  if (!document.querySelector('link[href*="chatbot-widget.css"]')) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `${base}assets/css/chatbot-widget.css`;
    document.head.appendChild(link);
  }

  const icon = document.createElement("div");
  icon.id = "chatbot-icon";
  icon.title = "Ask Quick Study Assistant";
  icon.innerHTML = '<i class="fas fa-comment-dots"></i>';

  const box = document.createElement("div");
  box.id = "chatbot-box";
  box.innerHTML = `
    <button type="button" id="chatbot-close" aria-label="Close">×</button>
    <div class="cb-header">
      <div class="cb-header-icon"><i class="fas fa-robot"></i></div>
      <div class="cb-header-text">
        <h3>Quick Study Assistant</h3>
        <p>Pick a question below</p>
      </div>
    </div>
    <div class="cb-messages" id="cbMessages"></div>
    <div class="cb-panel">
      <div class="cb-search-wrap">
        <input type="search" id="cbSearch" placeholder="Search topics…" autocomplete="off" aria-label="Search topics">
      </div>
      <div class="cb-quick-bar" id="cbQuick"></div>
      <div class="cb-categories" id="cbCategories"></div>
      <div class="cb-faq-label">Questions</div>
      <div class="cb-topics" id="cbTopics"></div>
    </div>
  `;

  document.body.appendChild(icon);
  document.body.appendChild(box);

  const boot = () => {
    if (!window.FAQ_TOPICS) return;
    const s2 = document.createElement("script");
    s2.src = `${base}assets/js/chatbot-widget.js`;
    document.body.appendChild(s2);
  };

  if (window.FAQ_TOPICS) {
    boot();
  } else {
    const s1 = document.createElement("script");
    s1.src = `${base}assets/js/chatbot-assistant.js`;
    s1.onload = boot;
    document.body.appendChild(s1);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", loadChatbotWidget);
} else {
  loadChatbotWidget();
}

function showBackendOfflineBanner() {
  if (document.getElementById("backend-offline-banner")) return;
  const bar = document.createElement("div");
  bar.id = "backend-offline-banner";
  bar.setAttribute("role", "alert");
  bar.style.cssText =
    "position:fixed;top:0;left:0;right:0;z-index:99999;background:#b91c1c;color:#fff;" +
    "padding:12px 16px;text-align:center;font-size:14px;font-family:system-ui,sans-serif;" +
    "box-shadow:0 2px 8px rgba(0,0,0,.25);";
  bar.innerHTML =
    "<strong>Service unavailable</strong> — Please run <strong>START_PROJECT.bat</strong> " +
    "and keep the application window open.";
  document.body.prepend(bar);
  document.body.style.paddingTop = "52px";
}

function checkBackendAndWarn() {
  const apiBase = typeof API_BASE !== "undefined" ? API_BASE : "http://localhost:3000";
  fetch(`${apiBase}/api/health`, { method: "GET", cache: "no-store" })
    .then((r) => {
      if (r.ok) {
        const el = document.getElementById("backend-offline-banner");
        if (el) el.remove();
        return;
      }
      showBackendOfflineBanner();
    })
    .catch(() => showBackendOfflineBanner());
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => setTimeout(checkBackendAndWarn, 400));
} else {
  setTimeout(checkBackendAndWarn, 400);
}
