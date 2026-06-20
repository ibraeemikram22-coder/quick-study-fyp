/** Friendly toast when AI / paper generation is unavailable. */
function isAiServiceMessage(msg) {
  const m = String(msg || "").toLowerCase();
  return (
    m.includes("quota") ||
    m.includes("429") ||
    m.includes("503") ||
    m.includes("502") ||
    m.includes("504") ||
    m.includes("rate limit") ||
    m.includes("resource exhausted") ||
    m.includes("gemini") ||
    m.includes("unavailable") ||
    m.includes("high demand") ||
    m.includes("server busy") ||
    m.includes("try again later") ||
    m.includes("ai service")
  );
}

function showGeminiNotice(message, type) {
  const text =
    message && !isAiServiceMessage(message)
      ? message
      : "Paper generation is temporarily unavailable. Please try again in a few minutes.";
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
    <strong>Please try again</strong>
    <p>${String(text).replace(/</g, "&lt;")}</p>`;
  el.style.display = "block";
  el.querySelector(".gemini-notice-close").onclick = () => {
    el.style.display = "none";
  };
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => {
    el.style.display = "none";
  }, 8000);
}

function maybeShowGeminiError(err) {
  const msg = err?.message || String(err || "");
  if (isAiServiceMessage(msg) || typeof toUserMessage === "function") {
    showGeminiNotice(typeof toUserMessage === "function" ? toUserMessage(err) : msg, "warn");
    return true;
  }
  return false;
}
