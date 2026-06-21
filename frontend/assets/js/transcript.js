const dropArea = document.getElementById("dropArea");
const videoFile = document.getElementById("videoFile");
const videoLink = document.getElementById("videoLink");
const outputBox = document.getElementById("outputBox");
const generateBtn = document.getElementById("generateBtn");
const statusAlert = document.getElementById("status-alert");
const metaBadge = document.getElementById("metaBadge");
const wordCountEl = document.getElementById("wordCount");
const sourceLabel = document.getElementById("sourceLabel");
const copyBtn = document.getElementById("copyBtn");
const downloadBtn = document.getElementById("downloadBtn");
const fileNameEl = document.getElementById("fileName");
const panelLink = document.getElementById("panel-link");
const panelUpload = document.getElementById("panel-upload");

let currentMode = "link";
let selectedFile = null;

function getLoggedInUserId() {
  try {
    const u = JSON.parse(localStorage.getItem("qsb_user") || "null");
    return u && u.id ? u.id : null;
  } catch {
    return null;
  }
}

function authHeaders() {
  const uid = getLoggedInUserId();
  return uid ? { "X-User-Id": String(uid) } : {};
}

document.querySelectorAll(".mode-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    currentMode = tab.dataset.mode;
    document.querySelectorAll(".mode-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    panelLink.classList.toggle("d-none", currentMode !== "link");
    panelUpload.classList.toggle("d-none", currentMode !== "upload");
    setStatus("", "");
  });
});

function setStatus(msg, type) {
  if (!statusAlert) return;
  statusAlert.textContent = msg;
  statusAlert.className = "status-alert mt-3" + (type ? ` ${type}` : "");
}

function setMeta(label, type) {
  if (!metaBadge) return;
  metaBadge.textContent = label;
  metaBadge.className = "meta-badge" + (type ? ` ${type}` : "");
}

function setOutput(text, state) {
  outputBox.textContent = text;
  outputBox.className = "output-box" + (state ? ` ${state}` : "");
  const hasText = text && !text.startsWith("Your transcript");
  copyBtn.disabled = !hasText || state === "error-state";
  downloadBtn.disabled = copyBtn.disabled;
}

function sourceLabelText(source) {
  const map = {
    youtube_captions: "YouTube subtitles",
    gemini: "AI transcription",
    whisper: "AI transcription",
  };
  return map[source] || source || "—";
}

if (dropArea && videoFile) {
  dropArea.onclick = () => videoFile.click();

  videoFile.onchange = () => {
    selectedFile = videoFile.files[0] || null;
    fileNameEl.textContent = selectedFile
      ? `${selectedFile.name} (${(selectedFile.size / 1024 / 1024).toFixed(1)} MB)`
      : "No file selected";
  };

  dropArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropArea.classList.add("dragover");
  });
  dropArea.addEventListener("dragleave", () => dropArea.classList.remove("dragover"));
  dropArea.addEventListener("drop", (e) => {
    e.preventDefault();
    dropArea.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file) {
      selectedFile = file;
      const dt = new DataTransfer();
      dt.items.add(file);
      videoFile.files = dt.files;
      fileNameEl.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
    }
  });
}

generateBtn.onclick = async () => {
  if (!requireModuleAccess("transcript", "Video Transcript")) return;
  generateBtn.disabled = true;
  setMeta("Processing", "loading");
  setStatus("Generating transcript… this may take 1–2 minutes.", "loading");
  setOutput("Please wait while we process your video…", "");
  wordCountEl.textContent = "0";
  sourceLabel.textContent = "—";

  try {
    let res;

    if (currentMode === "upload") {
      if (!selectedFile) {
        setStatus("Select a video or audio file first.", "error");
        setMeta("Error", "error");
        setOutput("Upload a video file (MP4, WebM, MP3, etc.) up to 20 MB.", "error-state");
        return;
      }

      const form = new FormData();
      form.append("video", selectedFile);

      res = await fetch(`${API_BASE}/transcript/generate`, {
        method: "POST",
        headers: authHeaders(),
        body: form,
      });
    } else {
      const url = videoLink.value.trim();
      if (!url) {
        setStatus("Paste a YouTube link first.", "error");
        setMeta("Error", "error");
        setOutput("Enter a valid YouTube URL.", "error-state");
        return;
      }

      res = await fetch(`${API_BASE}/transcript/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ text: url, userId: getLoggedInUserId() }),
      });
    }

    const data = await res.json();

    if (data.success === false || data.error) {
      const isCopyright = data.error === "copyright";
      const errText = data.message || data.transcript || data.error || "Transcription failed.";
      const msg = !isCopyright && typeof handleAiModuleError === "function"
        ? handleAiModuleError(new Error(errText), data)
        : errText;
      setStatus(
        isCopyright ? "Copyright restriction" : isQuotaExceededMessage(data) ? "Daily limit reached" : "Could not transcribe",
        isCopyright ? "copyright" : "error"
      );
      setMeta(isCopyright ? "Blocked" : "Error", "error");
      setOutput(msg, "error-state");
      return;
    }

    recordModuleUse("transcript");
    const text = data.transcript || "";
    setOutput(text, "success-state");
    const savedNote = data.id ? ` Saved to history (#${data.id}).` : "";
    setStatus("Transcript ready!" + savedNote, "success");
    setMeta("Done", "done");
    wordCountEl.textContent = data.wordCount || text.split(/\s+/).filter(Boolean).length;
    sourceLabel.textContent = sourceLabelText(data.source);
    refreshTranscriptHistory();
  } catch (err) {
    console.error(err);
    const msg = typeof handleAiModuleError === "function"
      ? handleAiModuleError(err)
      : "Could not reach the server. Check your connection and try again.";
    setStatus("Connection problem — please try again.", "error");
    setMeta("Offline", "error");
    setOutput(msg, "error-state");
  } finally {
    generateBtn.disabled = false;
  }
};

document.getElementById("clearBtn").onclick = () => {
  videoLink.value = "";
  selectedFile = null;
  videoFile.value = "";
  fileNameEl.textContent = "No file selected";
  setOutput("Your transcript will appear here...", "");
  setStatus("", "");
  setMeta("Waiting", "");
  wordCountEl.textContent = "0";
  sourceLabel.textContent = "—";
  copyBtn.disabled = true;
  downloadBtn.disabled = true;
};

copyBtn.onclick = () => {
  navigator.clipboard.writeText(outputBox.textContent);
  setStatus("Copied to clipboard!", "success");
};

downloadBtn.onclick = () => {
  const blob = new Blob([outputBox.textContent], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "transcript.txt";
  a.click();
};

function refreshTranscriptHistory() {}

bootHistoryFromUrl((id) => `/transcript/history/${id}`, (row) => {
  setOutput(row.transcript || "", "success-state");
  wordCountEl.textContent = row.wordCount || 0;
  sourceLabel.textContent = sourceLabelText(row.sourceEngine);
  setStatus("Loaded from your saved transcripts.", "success");
});
