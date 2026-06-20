/**
 * Backend API URL
 * Local: START_PROJECT.bat (port 3000)
 * Live: set PRODUCTION_API_URL below after deploying backend on Render/Railway
 */
const PRODUCTION_API_URL = ""; // e.g. "https://your-app.onrender.com"

const API_BASE = (() => {
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") {
    return "http://localhost:3000";
  }
  if (PRODUCTION_API_URL) {
    return PRODUCTION_API_URL.replace(/\/$/, "");
  }
  return window.location.origin;
})();

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.success === false) {
    const raw = data.error || `Request failed (${res.status})`;
    throw new Error(typeof toUserMessage === "function" ? toUserMessage(raw) : raw);
  }
  return data.data !== undefined ? data.data : data;
}

/** Long-running AI calls (paper generate, bulk OCR). Default 15 minutes. */
async function apiFetchLong(path, options = {}, timeoutMs = 900000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}`, { ...options, signal: controller.signal });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.success === false) {
      const raw = data.error || `Request failed (${res.status})`;
      throw new Error(typeof toUserMessage === "function" ? toUserMessage(raw) : raw);
    }
    return data.data !== undefined ? data.data : data;
  } catch (e) {
    if (e.name === "AbortError") {
      throw new Error(
        typeof toUserMessage === "function"
          ? toUserMessage("timeout")
          : "Request timed out — try fewer chapters or Weekly Test first."
      );
    }
    if (typeof toUserMessage === "function" && e.message) {
      throw new Error(toUserMessage(e));
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}
