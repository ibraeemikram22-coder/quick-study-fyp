function getBasePath() {
  const path = window.location.pathname;
  if (path.includes("/module/")) {
    return "../../";
  }
  return "./";
}

function applyNavLinks(root) {
  const base = getBasePath();
  root.querySelectorAll("a[data-nav]").forEach((a) => {
    const target = a.getAttribute("data-nav");
    const redirect = a.getAttribute("data-redirect");
    if (redirect) {
      a.href = `${base}${target}?redirect=${encodeURIComponent(redirect)}`;
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
  });

fetch(getBasePath() + "layout/footer.html")
  .then((res) => res.text())
  .then((data) => {
    document.getElementById("footer").innerHTML = data;
    const footer = document.getElementById("footer");
    if (footer) applyNavLinks(footer);
  });
