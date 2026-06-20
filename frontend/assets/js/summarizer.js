const inputText = document.getElementById("inputText");
const outputBox = document.getElementById("outputBox");
const bulletCount = document.getElementById("bulletCount");
const formatStyle = document.getElementById("formatStyle");
const outputLanguage = document.getElementById("outputLanguage");
const contentType = document.getElementById("contentType");
const quickMode = document.getElementById("quickMode");
const fileInput = document.getElementById("fileInput");
const generateBtn = document.getElementById("generateBtn");
const fileChip = document.getElementById("fileChip");
const fileChipName = document.getElementById("fileChipName");
const fileChipSize = document.getElementById("fileChipSize");
const statusMessage = document.getElementById("statusMessage");
const statsPanel = document.getElementById("statsPanel");
const insightsPanel = document.getElementById("insightsPanel");
const summaryFlow = document.getElementById("summaryFlow");
const progressBarWrap = document.getElementById("progressBarWrap");
const progressBar = document.getElementById("progressBar");

let selectedFile = null;
let processingTimer = null;

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function setStatus(step, message, isError = false, flow = "text") {
  const uploadStep = document.querySelector('[data-step="upload"]');
  const order =
    flow === "file"
      ? ["idle", "upload", "processing", "done"]
      : ["idle", "processing", "done"];

  if (uploadStep) {
    uploadStep.classList.toggle("d-none", flow !== "file");
  }

  document.querySelectorAll(".status-step").forEach((el) => {
    const s = el.dataset.step;
    if (s === "upload" && flow !== "file") return;

    el.classList.remove("active", "done", "error");
    const current = order.indexOf(step);
    const thisIdx = order.indexOf(s);
    if (thisIdx === -1) return;

    if (isError && s === step) {
      el.classList.add("error");
    } else if (thisIdx < current) {
      el.classList.add("done");
    } else if (s === step) {
      el.classList.add(isError ? "error" : "active");
    }
  });

  statusMessage.textContent = message;
}

function showFileChip(file) {
  fileChip.classList.remove("d-none");
  fileChipName.textContent = file.name;
  fileChipSize.textContent = formatSize(file.size);
}

function hideFileChip() {
  selectedFile = null;
  fileChip.classList.add("d-none");
  fileInput.value = "";
}

function setOutputMessage(message, isError = false) {
  outputBox.innerHTML = `<p class="${isError ? "text-danger" : "text-muted"} mb-0">${escapeHtml(message)}</p>`;
  delete outputBox.dataset.plain;
}

function setFlowStep(step) {
  if (!summaryFlow) return;
  summaryFlow.classList.remove("d-none");
  const order = ["prepare", "parts", "merge", "done"];
  const idx = order.indexOf(step);
  summaryFlow.querySelectorAll(".flow-step").forEach((el) => {
    const s = el.dataset.flow;
    const i = order.indexOf(s);
    el.classList.remove("active", "done");
    if (i < idx) el.classList.add("done");
    else if (s === step) el.classList.add("active");
  });
}

function setProgressBar(pct) {
  if (!progressBarWrap || !progressBar) return;
  progressBarWrap.classList.remove("d-none");
  progressBar.style.width = `${Math.min(100, pct)}%`;
}

function hideProgressUi() {
  progressBarWrap?.classList.add("d-none");
  summaryFlow?.classList.add("d-none");
}

function updateProgressFromPct(pct, message) {
  if (pct < 15) setFlowStep("prepare");
  else if (pct < 80) setFlowStep("parts");
  else if (pct < 100) setFlowStep("merge");
  else setFlowStep("done");
  setProgressBar(pct);
  if (message) setOutputMessage(message);
}

function startProcessingUi(flow, quick = false) {
  if (quick) {
    hideProgressUi();
    setOutputMessage("Quick summary… usually 10–20 seconds.");
    return;
  }
  setFlowStep("prepare");
  setProgressBar(5);
  setOutputMessage("Reading your whole file (all parts), then building one summary…");
  let seconds = 0;
  clearInterval(processingTimer);
  processingTimer = setInterval(() => {
    seconds += 20;
    setStatus(
      "processing",
      `Still working… ${seconds}s. Very long chapters may take up to 2 minutes.`,
      false,
      flow
    );
  }, 20000);
}

function stopProcessingUi() {
  clearInterval(processingTimer);
  processingTimer = null;
}

async function pollJob(jobId, flow) {
  while (true) {
    await new Promise((r) => setTimeout(r, 1500));
    const res = await fetch(`${API_BASE}/api/notes/job/${jobId}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.success) {
      throw new Error(data.error || "Job status failed");
    }
    updateProgressFromPct(data.progress || 0, data.message);
    setStatus("processing", data.message || "Working…", false, flow);
    if (data.status === "done" && data.result) {
      setFlowStep("done");
      setProgressBar(100);
      renderResult(data.result, flow);
      recordModuleUse("summarizer");
      return;
    }
    if (data.status === "error") {
      throw new Error(data.error || "Summarization failed");
    }
  }
}

function setLoading(loading) {
  generateBtn.disabled = loading;
  generateBtn.innerHTML = loading
    ? '<i class="fas fa-spinner fa-spin me-2"></i>Summarizing...'
    : '<i class="fas fa-magic me-2"></i>Generate Summary';
}

function renderInsights(insights) {
  const removed = insights?.removed || [];
  const simplified = insights?.simplified || [];
  const kept = insights?.keptImportant || [];

  const removedList = document.getElementById("insightRemoved");
  const simplifiedList = document.getElementById("insightSimplified");
  const keptBox = document.getElementById("insightKept");

  removedList.innerHTML = removed.length
    ? removed.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>No major filler detected.</li>";

  simplifiedList.innerHTML = simplified.length
    ? simplified
        .map((item) => {
          const from = item.from || item.original || "";
          const to = item.to || item.simplified || "";
          return `<li class="simplify-pair">
            <span class="simplify-from">${escapeHtml(from)}</span>
            <span class="simplify-arrow">→</span>
            <span class="simplify-to">${escapeHtml(to)}</span>
          </li>`;
        })
        .join("")
    : "<li>Language was already simple.</li>";

  keptBox.innerHTML = kept.length
    ? kept
        .map(
          (t) =>
            `<span class="insight-tag">${escapeHtml(t)}</span>`
        )
        .join("")
    : '<span class="insight-tag">Core ideas preserved</span>';

  insightsPanel.classList.remove("d-none");
}

function renderStats(meta) {
  document.getElementById("statOriginal").textContent =
    meta?.originalWords ?? "—";
  document.getElementById("statSummary").textContent =
    meta?.summaryWords ?? "—";
  document.getElementById("statReduction").textContent =
    (meta?.reductionPercent ?? 0) + "%";
  statsPanel.classList.remove("d-none");
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = String(str);
  return d.innerHTML;
}

function formatSummaryText(summary) {
  const lines = String(summary || "")
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines
    .map((line) => (line.startsWith("•") ? line : `• ${line}`))
    .join("\n");
}

function renderChapterHtml(chapterTitle, sections) {
  let html = "";
  if (chapterTitle) {
    html += `<h2 class="chapter-main-title">${escapeHtml(chapterTitle)}</h2>`;
  }
  (sections || []).forEach((sec) => {
    html += `<h3 class="section-heading">${escapeHtml(sec.heading || "Section")}</h3>`;
    html += "<ul class='section-list'>";
    (sec.bullets || []).forEach((b) => {
      html += `<li>${escapeHtml(b)}</li>`;
    });
    html += "</ul>";
  });
  return html || "<p>No summary returned.</p>";
}

function getPlainFromOutput() {
  if (outputBox.dataset.plain) return outputBox.dataset.plain;
  return outputBox.textContent || "";
}

function renderResult(data, flow = "text") {
  const meta = data.meta || {};
  const isChapter =
    meta.formatStyle === "chapter" && data.sections && data.sections.length;

  if (isChapter) {
    outputBox.innerHTML = renderChapterHtml(
      data.chapterTitle,
      data.sections
    );
    outputBox.dataset.plain = data.summary || "";
  } else {
    const formatted = formatSummaryText(data.summary);
    outputBox.textContent = formatted || "No summary returned.";
    outputBox.dataset.plain = formatted;
  }
  renderStats(data.meta);
  renderInsights(data.insights);

  const pct = meta.reductionPercent ?? 0;
  const orig = meta.originalWords ?? "—";
  const sum = meta.summaryWords ?? "—";
  const bullets = meta.bulletCount ?? "—";
  let msg = `Summary ready — ${bullets} bullets, ${orig} → ${sum} words (${pct}% shorter).`;

  if (meta.bulletCountMatched === false) {
    msg += ` Adjusted to ${bullets} bullet points.`;
  }

  if (meta.source === "file" && meta.fileName) {
    msg = `File "${meta.fileName}" summarized — ${bullets} bullets, ${pct}% shorter.`;
  }
  if (meta.fastMode) {
    msg += " Quick mode: only the start of the file was used.";
  } else if (meta.fullDocument) {
    msg += ` Whole file: all ${meta.chunkCount} parts read and merged.`;
    if (meta.partialFile) {
      msg += ` (Cap: first ${meta.chunkCount} of ${meta.totalChunksInFile} parts — file extremely large.)`;
    }
  }
  if (meta.suggestedBulletCount && meta.suggestedBulletCount > bullets) {
    msg += ` Tip: for this length, try ${meta.suggestedBulletCount} bullets for better coverage.`;
  }
  setStatus("done", msg, false, flow);
  hideProgressUi();
  if (typeof refreshSummarizerHistory === "function") refreshSummarizerHistory();
}

async function requestSummary(url, options, flowLabel, flow = "text", quick = true) {
  setLoading(true);
  startProcessingUi(flow, quick);
  setStatus(
    "processing",
    `${flowLabel} — Processing your content…`,
    false,
    flow
  );

  try {
    const res = await fetch(url, options);
    let data = {};
    try {
      data = await res.json();
    } catch {
      data = { success: false, error: "Invalid response from server." };
    }

    if (data.async && data.jobId) {
      startProcessingUi(flow, false);
      await pollJob(data.jobId, flow);
      return;
    }

    if (!res.ok || !data.success) {
      const err = data.error || `Request failed (${res.status}).`;
      const friendly = /503|unavailable|high demand|busy|rate limit|quota/i.test(err)
        ? "The service is busy. Please wait a few minutes and try again."
        : typeof toUserMessage === "function"
          ? toUserMessage(new Error(err))
          : err;
      setStatus("processing", friendly, true, flow);
      setOutputMessage(friendly, true);
      hideProgressUi();
      return;
    }

    renderResult(data, flow);
    recordModuleUse("summarizer");
  } catch (err) {
    const msg =
      typeof toUserMessage === "function"
        ? toUserMessage(err)
        : "Unable to complete request. Please try again.";
    setStatus("processing", msg, true, flow);
    setOutputMessage(msg, true);
    hideProgressUi();
  } finally {
    stopProcessingUi();
    setLoading(false);
  }
}

generateBtn.onclick = async () => {
  if (!requireModuleAccess("summarizer", "Summarized Notes")) return;
  const bullets = parseInt(bulletCount.value, 10) || 5;
  const style = formatStyle?.value || "chapter";
  const lang = outputLanguage?.value || "same";
  const ctype = contentType?.value || "notes";
  const quick = quickMode?.checked === true;
  const pasted = inputText.value.trim();

  // If user pasted in box, use paste (not old imported file)
  if (pasted) {
    if (selectedFile) hideFileChip();

    await requestSummary(
      `${API_BASE}/api/notes/generate`,
      moduleHistoryFetchOpts({
        text: pasted,
        bulletCount: bullets,
        formatStyle: style,
        outputLanguage: lang,
        contentType: ctype,
        quickMode: quick,
      }),
      "Pasted text",
      "text",
      !quick
    );
    return;
  }

  if (selectedFile) {
    const ext = selectedFile.name.split(".").pop().toLowerCase();
    if (!["pdf", "docx", "txt"].includes(ext)) {
      setStatus(
        "idle",
        "Only PDF, DOCX, or TXT files. Or paste text in the box.",
        true
      );
      setOutputMessage(
        "Unsupported file type. Paste text in the box, or use PDF, DOCX, or TXT.",
        true
      );
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("bulletCount", bullets);
    formData.append("formatStyle", style);
    formData.append("outputLanguage", lang);
    formData.append("contentType", ctype);
    if (quick) formData.append("quickMode", "1");
    const uid = typeof getLoggedInUserId === "function" ? getLoggedInUserId() : null;
    if (uid) formData.append("userId", String(uid));

    await requestSummary(
      `${API_BASE}/api/notes/upload`,
      { method: "POST", headers: typeof moduleHistoryAuthHeaders === "function" ? moduleHistoryAuthHeaders() : {}, body: formData },
      `File "${selectedFile.name}"`,
      "file",
      false
    );
    return;
  }

  setStatus("idle", "Paste text in the box OR import a PDF/DOCX/TXT file.", true);
  setOutputMessage(
    "Nothing to summarize. Paste your chapter in the text box, then click Generate Summary.",
    true
  );
};

document.getElementById("clearBtn").onclick = () => {
  inputText.value = "";
  hideFileChip();
  hideProgressUi();
  outputBox.innerHTML = "Your summarized notes will appear here...";
  delete outputBox.dataset.plain;
  statsPanel.classList.add("d-none");
  insightsPanel.classList.add("d-none");
  setStatus("idle", "Cleared. Paste text or import a file.");
};

document.getElementById("clearFileBtn").onclick = hideFileChip;

document.getElementById("copyBtn").onclick = async () => {
  const text = getPlainFromOutput().trim();
  if (!text || text.startsWith("Your summarized") || text.startsWith("Please ")) {
    setStatus("idle", "Nothing to copy yet.", true);
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    setStatus("done", "Summary copied to clipboard.");
  } catch {
    setStatus("done", "Copy failed — select text manually.", true);
  }
};

document.getElementById("downloadBtn").onclick = () => {
  const b = new Blob([getPlainFromOutput()], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(b);
  a.download = "summary.txt";
  a.click();
};

document.getElementById("importBtn").onclick = () => fileInput.click();

fileInput.onchange = (e) => {
  const file = e.target.files[0];
  if (!file) return;

  selectedFile = file;
  inputText.value = "";
  showFileChip(file);
  setStatus(
    "upload",
    `"${file.name}" selected — now click the purple "Generate Summary" button.`,
    false,
    "file"
  );
  setOutputMessage(
    'File selected. Click "Generate Summary" above — result will appear here in about a minute.'
  );
  statsPanel.classList.add("d-none");
  insightsPanel.classList.add("d-none");
};

inputText.addEventListener("input", () => {
  if (inputText.value.trim()) {
    hideFileChip();
  }
});

setStatus("idle", "Paste text or import a file, then click Generate Summary.");

function refreshSummarizerHistory() {}

bootHistoryFromUrl((id) => `/api/records/${id}`, (row) => {
  if (row.result) renderResult(row.result, "text");
});
