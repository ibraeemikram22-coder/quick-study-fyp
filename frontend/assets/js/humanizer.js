const humanizeBtn = document.getElementById("humanize-btn");
const aiInput = document.getElementById("ai-input");
const outputBox = document.getElementById("output-box");
const copyBtn = document.getElementById("copy-btn");
const clearBtn = document.getElementById("clear-btn");

const MIN = 20;
const MAX = 500;

function setStatus(msg, type) {
  const el = document.getElementById("status-alert");
  if (!el) return;
  el.textContent = msg;
  el.className = type || "";
}

aiInput.addEventListener("input", () => {
  const words = aiInput.value.trim().split(/\s+/).filter(Boolean).length;
  document.getElementById("input-stats").textContent = words + " words";
  document.getElementById("input-word-count").textContent = words;
});

humanizeBtn.addEventListener("click", async () => {
  const text = aiInput.value.trim();
  const words = text.split(/\s+/).filter(Boolean).length;

  if (words < MIN || words > MAX) {
    setStatus(`Text must be ${MIN}-${MAX} words`, "error");
    return;
  }

  humanizeBtn.disabled = true;
  setStatus("Processing...", "loading");
  outputBox.textContent = "Humanizing...";

  try {
    const res = await fetch(`${API_BASE}/humanizer/humanize`, moduleHistoryFetchOpts({ text }));

    const data = await res.json();

    if (!res.ok || data.error) {
      setStatus("Error", "error");
      outputBox.textContent = data.error || "Humanize failed.";
      return;
    }

    const result = data.result || "";
    outputBox.textContent = result;
    const outWords = result.split(/\s+/).filter(Boolean).length;
    document.getElementById("output-word-count").textContent = outWords;
    document.getElementById("replace-info").textContent =
      "AI text rewritten into human tone";
    document.getElementById("status-text").textContent = "Completed";
    const pct = document.getElementById("ai-percentage");
    if (pct) pct.textContent = "Status: Done";
    setStatus(data.id ? `Humanized — saved #${data.id}` : "Humanized successfully", "success");
    refreshHumanizerHistory();
  } catch (err) {
    console.error(err);
    setStatus("Cannot reach backend", "error");
    outputBox.textContent =
      "Failed to connect. Start backend: cd backend → python app.py (port 3000).";
  }

  humanizeBtn.disabled = false;
});

copyBtn.addEventListener("click", () => {
  navigator.clipboard.writeText(outputBox.textContent);
  setStatus("Copied!", "success");
});

clearBtn.addEventListener("click", () => {
  aiInput.value = "";
  outputBox.textContent = "Result will appear here...";
  document.getElementById("input-stats").textContent = "0 words";
  document.getElementById("input-word-count").textContent = "0";
  document.getElementById("output-word-count").textContent = "0";
  document.getElementById("replace-info").textContent = "-";
  document.getElementById("status-text").textContent = "Waiting";
  const pct = document.getElementById("ai-percentage");
  if (pct) pct.textContent = "Status: Waiting...";
  setStatus("Cleared", "success");
});

function refreshHumanizerHistory() {
  if (typeof mountModuleHistory !== "function") return;
  mountModuleHistory({
    containerId: "moduleHistoryList",
    module: "humanizer",
    onLoad(row) {
      const r = (row.result || {}).result;
      if (r) {
        outputBox.textContent = r;
        setStatus(`Loaded history #${row.id}`, "success");
      }
    },
  });
}

refreshHumanizerHistory();
