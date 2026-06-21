/**
 * AI quota notices — global banner + module toasts when Gemini daily limit is reached.
 */
let _aiQuotaState = { exhausted: false, resetsAt: null };

function isAiServiceMessage(msg) {
  return isQuotaExceededMessage(msg) || /503|502|504|unavailable|high demand|server busy|gemini|ai service/i.test(
    String(msg || "").toLowerCase()
  );
}

function aiQuotaMessage(resetsAt) {
  if (typeof quotaLimitMessage === "function") {
    return quotaLimitMessage(resetsAt || _aiQuotaState.resetsAt);
  }
  return typeof QUOTA_LIMIT_MESSAGE !== "undefined"
    ? QUOTA_LIMIT_MESSAGE
    : "Daily AI limit reached. Please try again tomorrow.";
}

function parseHealthAiQuota(data) {
  if (!data || typeof data !== "object") return { exhausted: false, resetsAt: null };
  const ai = data.aiQuota || {};
  const geminiKey = String(data.geminiKey || "");
  const exhausted =
    ai.exhausted === true ||
    geminiKey === "error_429" ||
    geminiKey.includes("429") ||
    ai.available === false;
  return {
    exhausted,
    resetsAt: ai.resetsAt || null,
    geminiKey,
  };
}

function ensureAiQuotaBannerEl() {
  let el = document.getElementById("aiQuotaBanner");
  if (el) return el;
  el = document.createElement("div");
  el.id = "aiQuotaBanner";
  el.className = "ai-quota-banner";
  el.setAttribute("role", "alert");
  el.style.display = "none";
  el.innerHTML = `
    <div class="ai-quota-banner-inner">
      <span class="ai-quota-banner-icon" aria-hidden="true"><i class="fas fa-hourglass-half"></i></span>
      <div class="ai-quota-banner-text">
        <strong class="ai-quota-banner-title">Daily AI limit reached</strong>
        <p class="ai-quota-banner-msg"></p>
      </div>
      <button type="button" class="ai-quota-banner-close" aria-label="Dismiss">&times;</button>
    </div>`;
  el.querySelector(".ai-quota-banner-close").onclick = () => {
    el.style.display = "none";
    try {
      sessionStorage.setItem("qsb_quota_banner_dismissed", String(Date.now()));
    } catch {
      /* ignore */
    }
  };
  const header = document.getElementById("main-header");
  if (header && header.parentNode) {
    header.parentNode.insertBefore(el, header.nextSibling);
  } else {
    document.body.prepend(el);
  }
  return el;
}

function showAiQuotaBanner(message, resetsAt) {
  if (resetsAt) _aiQuotaState.resetsAt = resetsAt;
  _aiQuotaState.exhausted = true;

  try {
    const dismissed = parseInt(sessionStorage.getItem("qsb_quota_banner_dismissed") || "0", 10);
    if (dismissed && Date.now() - dismissed < 30 * 60 * 1000) {
      return;
    }
  } catch {
    /* ignore */
  }

  const el = ensureAiQuotaBannerEl();
  const text = message || aiQuotaMessage(resetsAt);
  el.querySelector(".ai-quota-banner-msg").textContent = text;
  el.style.display = "block";
}

function hideAiQuotaBanner() {
  _aiQuotaState.exhausted = false;
  const el = document.getElementById("aiQuotaBanner");
  if (el) el.style.display = "none";
}

function showGeminiNotice(message, type) {
  const quota = isQuotaExceededMessage(message);
  const text = quota
    ? aiQuotaMessage(_aiQuotaState.resetsAt)
    : message && !isAiServiceMessage(message)
      ? message
      : "The AI service is temporarily unavailable. Please try again shortly.";

  if (quota) showAiQuotaBanner(text, _aiQuotaState.resetsAt);

  let el = document.getElementById("geminiNoticeToast");
  if (!el) {
    el = document.createElement("div");
    el.id = "geminiNoticeToast";
    el.setAttribute("role", "alert");
    document.body.appendChild(el);
  }
  el.className = `gemini-notice-toast gemini-notice-${type || "warn"}`;
  el.innerHTML = `
    <button type="button" class="gemini-notice-close" aria-label="Close">&times;</button>
    <strong>${quota ? "Daily limit reached" : "Please try again"}</strong>
    <p>${String(text).replace(/</g, "&lt;")}</p>`;
  el.style.display = "block";
  el.querySelector(".gemini-notice-close").onclick = () => {
    el.style.display = "none";
  };
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => {
    el.style.display = "none";
  }, quota ? 12000 : 8000);
}

function handleAiModuleError(err, data) {
  const payload = data && typeof data === "object" ? data : {};
  const raw = payload.error || err?.message || String(err || "");
  const combined = { message: raw, code: payload.code, error: raw };
  const msg = isQuotaExceededMessage(combined)
    ? aiQuotaMessage(_aiQuotaState.resetsAt)
    : typeof toUserMessage === "function"
      ? toUserMessage(combined)
      : raw;

  if (isQuotaExceededMessage(combined)) {
    showGeminiNotice(msg, "warn");
  } else if (isAiServiceMessage(msg)) {
    showGeminiNotice(msg, "warn");
  }
  return msg;
}

function maybeShowGeminiError(err) {
  handleAiModuleError(err);
  return isAiServiceMessage(err?.message || err) || isQuotaExceededMessage(err);
}

function handleHealthAiQuota(data) {
  const parsed = parseHealthAiQuota(data);
  _aiQuotaState.resetsAt = parsed.resetsAt || _aiQuotaState.resetsAt;
  if (parsed.exhausted) {
    showAiQuotaBanner(aiQuotaMessage(parsed.resetsAt), parsed.resetsAt);
  } else {
    hideAiQuotaBanner();
    try {
      sessionStorage.removeItem("qsb_quota_banner_dismissed");
    } catch {
      /* ignore */
    }
  }
  return parsed;
}

async function fetchAiQuotaStatus() {
  const base =
    typeof API_BASE !== "undefined"
      ? API_BASE
      : typeof resolveHealthApiBase === "function"
        ? resolveHealthApiBase()
        : window.location.origin;
  try {
    const res = await fetch(`${base}/api/health`, { method: "GET", cache: "no-store" });
    if (!res.ok) return { exhausted: false };
    const data = await res.json();
    return handleHealthAiQuota(data);
  } catch {
    return { exhausted: false };
  }
}

function initAiQuotaWatch() {
  fetchAiQuotaStatus();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initAiQuotaWatch);
} else {
  initAiQuotaWatch();
}
