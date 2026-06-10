/** Backend base URL — must match: python app.py (port 3000) */
const API_BASE = "http://localhost:3000";
const MAX_UPLOAD_MB = 80;
const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

function formatFileSize(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileTooLargeMessage(fileSizeBytes) {
  const size = formatFileSize(fileSizeBytes);
  return (
    `File bahut bara hai (${size}). Maximum ${MAX_UPLOAD_MB} MB upload ho sakta hai. ` +
    `Your file is too large (${size}). Limit is ${MAX_UPLOAD_MB} MB.`
  );
}

const FILE_TOO_LARGE_TIPS = [
  "PDF compress karein — ilovepdf.com ya smallpdf.com use karein",
  "Poori book ki jagah sirf 1–2 chapters upload karein",
  "Ya chapter ka text neeche wale box mein paste karein",
];

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  const contentType = res.headers.get("content-type") || "";
  let data = {};

  if (contentType.includes("application/json")) {
    data = await res.json().catch(() => ({}));
  } else if (!res.ok) {
    const text = await res.text().catch(() => "");
    if (res.status === 413) {
      const err = new Error(fileTooLargeMessage(0));
      err.code = "file_too_large";
      err.tips = FILE_TOO_LARGE_TIPS;
      throw err;
    }
    throw new Error(text.slice(0, 200) || `Request failed (${res.status})`);
  }

  if (!res.ok || data.success === false) {
    if (res.status === 413 || data.error === "file_too_large") {
      const err = new Error(data.message || fileTooLargeMessage(0));
      err.code = "file_too_large";
      err.tips = data.tips || FILE_TOO_LARGE_TIPS;
      err.maxUploadMb = data.maxUploadMb || MAX_UPLOAD_MB;
      throw err;
    }
    throw new Error(data.message || data.error || `Request failed (${res.status})`);
  }
  return data.data !== undefined ? data.data : data;
}
