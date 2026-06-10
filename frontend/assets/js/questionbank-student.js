let selectedTypes = ["mcq", "short"];
let lastPaper = null;
let paperMode = "practice";
let timerId = null;
let timerSeconds = 0;
let processingTimerId = null;
let processingSeconds = 0;
let processingTargetPct = 0;
let testSubmitted = false;

const PROGRESS_STAGES = [
  { afterSec: 0, pct: 6, step: "Uploading & reading your file…" },
  { afterSec: 2, pct: 14, step: "Scanning full document…" },
  { afterSec: 5, pct: 26, step: "Picking topics from different sections…" },
  { afterSec: 10, pct: 40, step: "AI is analyzing your notes…" },
  { afterSec: 18, pct: 55, step: "Writing MCQ questions…" },
  { afterSec: 30, pct: 70, step: "Writing short & long questions…" },
  { afterSec: 45, pct: 82, step: "Checking variety & coverage…" },
  { afterSec: 60, pct: 90, step: "Almost done — building your paper…" },
  { afterSec: 90, pct: 95, step: "Still working — large files take longer…" },
];

const MCQ_LABELS = ["A", "B", "C", "D"];

function showUploadError(message, tips) {
  const box = document.getElementById("uploadErrorBox");
  const tipList = (tips || FILE_TOO_LARGE_TIPS)
    .map((t) => `<li>${escapeHtml(t)}</li>`)
    .join("");
  box.innerHTML = `
    <h6><i class="fas fa-exclamation-triangle me-1"></i>File upload nahi ho sakti</h6>
    <p class="error-main mb-2">${escapeHtml(message)}</p>
    <p class="small fw-semibold mb-1">Kya karein:</p>
    <ul>${tipList}</ul>
  `;
  box.style.display = "block";
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function hideUploadError() {
  const box = document.getElementById("uploadErrorBox");
  if (box) {
    box.style.display = "none";
    box.innerHTML = "";
  }
}

function updateFileSizeHint(file) {
  const hint = document.getElementById("fileSizeHint");
  if (!file) {
    hint.style.display = "none";
    hint.className = "small text-muted mb-2";
    return;
  }
  const tooLarge = file.size > MAX_UPLOAD_BYTES;
  hint.style.display = "block";
  hint.className = `small mb-2 ${tooLarge ? "file-too-large" : "file-ok"}`;
  hint.textContent = tooLarge
    ? `⚠ ${file.name} — ${formatFileSize(file.size)} (limit ${MAX_UPLOAD_MB} MB — file bara hai)`
    : `✓ ${file.name} — ${formatFileSize(file.size)}`;
  if (tooLarge) {
    showUploadError(fileTooLargeMessage(file.size), FILE_TOO_LARGE_TIPS);
  } else {
    hideUploadError();
  }
}

document.getElementById("fileInput").addEventListener("change", (e) => {
  updateFileSizeHint(e.target.files[0] || null);
});

document.querySelectorAll(".select-btn[data-type]").forEach((btn) => {
  btn.addEventListener("click", () => {
    btn.classList.toggle("active");
    const type = btn.dataset.type;
    if (selectedTypes.includes(type)) {
      selectedTypes = selectedTypes.filter((t) => t !== type);
    } else {
      selectedTypes.push(type);
    }
    updateTimeEstimate();
  });
});

document.querySelectorAll(".mode-card").forEach((card) => {
  card.addEventListener("click", () => {
    document.querySelectorAll(".mode-card").forEach((c) => c.classList.remove("active"));
    card.classList.add("active");
    paperMode = card.dataset.mode;
    updateTimeEstimate();
    document.getElementById("generateBtn").textContent =
      paperMode === "test" ? "Start timed test" : "Generate practice paper";
  });
});

document.querySelectorAll(".count-input").forEach((inp) => {
  inp.addEventListener("input", updateTimeEstimate);
});

function getCounts() {
  const counts = { mcq: 0, short: 0, long: 0 };
  document.querySelectorAll(".count-input").forEach((inp) => {
    const type = inp.dataset.type;
    if (selectedTypes.includes(type)) {
      counts[type] = parseInt(inp.value, 10) || 0;
    }
  });
  return counts;
}

function computeTestMinutes(counts) {
  const mcq = counts.mcq || 0;
  const short = counts.short || 0;
  const long = counts.long || 0;
  const mins = Math.ceil(mcq * 1.5 + short * 4 + long * 10);
  return Math.max(15, Math.min(180, mins));
}

function updateTimeEstimate() {
  const el = document.getElementById("timeEstimate");
  if (paperMode !== "test") {
    el.style.display = "none";
    return;
  }
  const counts = getCounts();
  const mins = computeTestMinutes(counts);
  el.style.display = "block";
  el.textContent = `Estimated time for this test: ${mins} minutes (auto-set when you start)`;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s || "";
  return d.innerHTML;
}

/** Remove A) B) c) prefixes — labels added in UI */
function cleanMcqOption(opt) {
  let s = String(opt || "").trim();
  s = s.replace(/^\(?[A-Da-d]\)?[.):\-\s]+/, "");
  s = s.replace(/^[A-Da-d]\s+/, "");
  if (/^[A-Da-d]$/i.test(s)) return "";
  return s;
}

function getQuestionsFlat(paper) {
  const list = [];
  (paper?.sections || []).forEach((sec) => {
    (sec.questions || []).forEach((q) => list.push(q));
  });
  return list;
}

function resolveMcqLetter(correctAnswer, options) {
  const ans = String(correctAnswer || "").trim();
  if (/^[A-D]$/i.test(ans)) return ans.toUpperCase();

  const cleaned = (options || []).map((o) => cleanMcqOption(o));
  for (let i = 0; i < cleaned.length; i++) {
    const raw = String(options[i] || "").trim().toLowerCase();
    const cl = cleaned[i].toLowerCase();
    if (ans.toLowerCase() === raw || ans.toLowerCase() === cl) {
      return MCQ_LABELS[i];
    }
  }
  const m = ans.match(/^([A-D])/i);
  return m ? m[1].toUpperCase() : ans.toUpperCase().charAt(0);
}

function buildSourceLine(paper) {
  const info = paper?.sourceInfo;
  if (!info) return "";
  const parts = [];
  if (info.pageCount) parts.push(`${info.pageCount.toLocaleString()} pages`);
  if (info.totalCharacters) parts.push(`${info.totalCharacters.toLocaleString()} characters`);
  else if (info.wordCount) parts.push(`${info.wordCount.toLocaleString()} words`);
  const note =
    info.coverageNote ||
    (info.fullFileRead
      ? "Full document used — questions cover your whole notes."
      : `Large file: ${info.sampleWindows || "several"} sections sampled (~${info.coveragePercent || "?"}%). Generate again for questions from other parts.`);
  return `<p class="source-info small text-muted mb-3"><i class="fas fa-file-alt me-1"></i>${escapeHtml(parts.join(" · "))} — ${escapeHtml(note)}</p>`;
}

function buildPaperTop(paper, showTime) {
  const timeLine = showTime
    ? ` · Time allowed: ${escapeHtml(paper.duration || "—")}`
    : "";
  return `
    <div class="paper-simple-header">
      <h3 class="fw-bold mb-1">${escapeHtml(paper.title || "Practice Paper")}</h3>
      <p class="text-muted small mb-1">Total marks: ${paper.marks || "—"}${timeLine}</p>
      ${buildSourceLine(paper)}
    </div>
  `;
}

function sectionBlockClass(sec) {
  const title = (sec.title || "").toLowerCase();
  if (title.includes("short")) return "section-short section-new-page";
  if (title.includes("long")) return "section-long section-new-page";
  return "section-mcq";
}

function getMcqOptionText(q, letter) {
  const i = MCQ_LABELS.indexOf(letter);
  if (i < 0 || !q.options) return letter;
  const text = cleanMcqOption(q.options[i]);
  return text ? `(${letter}) ${text}` : `(${letter})`;
}

function renderPaper(paper, mode) {
  let flatIndex = 0;
  const interactive = mode === "test";
  const practiceOnly = mode === "practice";
  let html = buildPaperTop(paper, mode === "test");

  (paper.sections || []).forEach((sec) => {
    let sectionNum = 0;
    html += `<div class="exam-section-block ${sectionBlockClass(sec)}">`;
    html += `<div class="exam-section-title">${escapeHtml(sec.title)}</div>`;
    (sec.questions || []).forEach((q) => {
      sectionNum += 1;
      flatIndex += 1;
      const n = sectionNum;
      const idx = flatIndex - 1;
      const qtype = (q.questionType || "").toLowerCase();
      html += `<div class="exam-question" data-idx="${idx}" data-type="${qtype}">`;
      html += `<p><span class="q-label">Q${n}.</span> ${escapeHtml(q.questionText)}</p>`;

      if (qtype === "mcq" && q.options && q.options.length) {
        html += '<div class="mcq-options">';
        q.options.slice(0, 4).forEach((opt, i) => {
          const label = MCQ_LABELS[i];
          const text = cleanMcqOption(opt) || `Option ${label}`;
          if (interactive) {
            html += `<label class="mcq-opt-label" data-opt="${label}"><input type="radio" name="q${idx}" value="${label}"> (${label}) ${escapeHtml(text)}</label>`;
          } else {
            html += `<div class="mcq-line">(${label}) ${escapeHtml(text)}</div>`;
          }
        });
        html += "</div>";
      } else if (!practiceOnly) {
        if (interactive) {
          const rows = qtype === "long" ? 4 : 2;
          html += `<textarea class="form-control mt-2" rows="${rows}" placeholder="Your answer..." data-written="1"></textarea>`;
        } else {
          html += '<div class="answer-lines"></div><div class="answer-lines"></div>';
        }
      }
      html += '<div class="q-feedback" style="display:none;"></div>';
      html += "</div>";
    });
    html += "</div>";
  });

  html += '<div id="answerKeyArea" class="answer-key-block" style="display:none;"></div>';
  return html;
}

function updateToolbar() {
  const practice = paperMode === "practice";
  document.querySelectorAll(".tb-practice").forEach((el) => {
    el.classList.toggle("is-hidden", !practice);
  });
  document.querySelectorAll(".tb-test").forEach((el) => {
    el.classList.toggle("is-hidden", practice);
  });

  const submitBtn = document.getElementById("btnSubmitTest");
  submitBtn.disabled = testSubmitted;
  submitBtn.innerHTML = testSubmitted
    ? '<i class="fas fa-check me-1"></i>Test submitted'
    : '<i class="fas fa-check-circle me-1"></i>Submit test';

  const keyBtn = document.getElementById("btnToggleKey");
  keyBtn.classList.toggle("is-hidden", practice || !testSubmitted);
}

function showPaper(mode) {
  if (!lastPaper) return;
  const sheet = document.getElementById("paperSheet");
  const isUrdu = lastPaper?.sourceInfo?.contentLanguage === "urdu";
  sheet.innerHTML = renderPaper(lastPaper, mode);
  sheet.dir = isUrdu ? "rtl" : "ltr";
  sheet.classList.toggle("urdu-paper", isUrdu);
  sheet.classList.toggle("test-mode", mode === "test");
  sheet.classList.remove("test-locked");
  updateToolbar();
  if (mode !== "test") {
    stopTimer();
    document.getElementById("timerBar").style.display = "none";
    document.getElementById("scorePanel").style.display = "none";
  }
}

function setQuestionFeedback(block, type, message) {
  const fb = block.querySelector(".q-feedback");
  if (!fb) return;
  fb.className = `q-feedback q-feedback-${type}`;
  fb.innerHTML = message;
  fb.style.display = "block";
}

function lockTestInputs() {
  document.querySelectorAll("#paperSheet input, #paperSheet textarea").forEach((el) => {
    el.disabled = true;
  });
  document.querySelectorAll("#paperSheet .mcq-opt-label").forEach((lab) => {
    lab.style.cursor = "default";
  });
  document.getElementById("paperSheet").classList.add("test-locked");
}

function startTimer(minutes) {
  stopTimer();
  timerSeconds = minutes * 60;
  const bar = document.getElementById("timerBar");
  const disp = document.getElementById("timerDisplay");
  bar.style.display = "flex";

  const tick = () => {
    const m = Math.floor(timerSeconds / 60);
    const s = timerSeconds % 60;
    disp.textContent = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    bar.classList.toggle("warning", timerSeconds <= 300);
    if (timerSeconds <= 0) {
      stopTimer();
      submitTest(true);
      return;
    }
    timerSeconds -= 1;
  };
  tick();
  timerId = setInterval(tick, 1000);
}

function stopTimer() {
  if (timerId) clearInterval(timerId);
  timerId = null;
  document.getElementById("timerBar").classList.remove("warning");
}

function updateProcessingDisplay() {
  const m = Math.floor(processingSeconds / 60);
  const s = processingSeconds % 60;
  document.getElementById("processingTimer").textContent =
    `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;

  let stage = PROGRESS_STAGES[0];
  for (let i = PROGRESS_STAGES.length - 1; i >= 0; i -= 1) {
    if (processingSeconds >= PROGRESS_STAGES[i].afterSec) {
      stage = PROGRESS_STAGES[i];
      break;
    }
  }
  if (stage.pct > processingTargetPct) {
    processingTargetPct = stage.pct;
    document.getElementById("processingProgressFill").style.width = `${processingTargetPct}%`;
    document.getElementById("processingPercent").textContent = `${processingTargetPct}%`;
    document.getElementById("processingStep").textContent = stage.step;
    const track = document.querySelector("#processingBar .progress-track");
    if (track) track.setAttribute("aria-valuenow", String(processingTargetPct));
  }
}

function setProcessingComplete() {
  processingTargetPct = 100;
  document.getElementById("processingProgressFill").style.width = "100%";
  document.getElementById("processingPercent").textContent = "100%";
  document.getElementById("processingStep").textContent = "Paper ready!";
  const track = document.querySelector("#processingBar .progress-track");
  if (track) track.setAttribute("aria-valuenow", "100");
}

function showProcessingOverlay(message) {
  const bar = document.getElementById("processingBar");
  document.getElementById("processingMessage").textContent = message;
  processingSeconds = 0;
  processingTargetPct = 0;
  document.getElementById("processingProgressFill").style.width = "0%";
  document.getElementById("processingPercent").textContent = "0%";
  document.getElementById("processingStep").textContent = PROGRESS_STAGES[0].step;
  updateProcessingDisplay();
  bar.style.display = "block";
  if (processingTimerId) clearInterval(processingTimerId);
  processingTimerId = setInterval(() => {
    processingSeconds += 1;
    updateProcessingDisplay();
  }, 1000);
  bar.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function hideProcessingOverlay() {
  if (processingTimerId) clearInterval(processingTimerId);
  processingTimerId = null;
  document.getElementById("processingBar").style.display = "none";
  processingTargetPct = 0;
}

function showAnswerKey(paper) {
  let key = "<h5>Answer key</h5>";
  (paper.sections || []).forEach((sec) => {
    key += `<p class="fw-bold mb-1 mt-2">${escapeHtml(sec.title || "Section")}</p><ul class='mb-0'>`;
    (sec.questions || []).forEach((q, i) => {
      let ans = q.correctAnswer || "—";
      if ((q.questionType || "").toLowerCase() === "mcq") {
        const letter = resolveMcqLetter(q.correctAnswer, q.options);
        ans = letter + (q.correctAnswer && q.correctAnswer !== letter ? ` (${q.correctAnswer})` : "");
      }
      key += `<li><strong>Q${i + 1}</strong> (${q.questionType}): ${escapeHtml(String(ans))}</li>`;
    });
    key += "</ul>";
  });
  const area = document.getElementById("answerKeyArea");
  area.innerHTML = key;
  area.style.display = "block";
}

function submitTest(auto = false) {
  if (!lastPaper || testSubmitted) return;

  const questions = getQuestionsFlat(lastPaper);
  let mcqTotal = 0;
  let mcqCorrect = 0;
  let mcqWrong = 0;
  let mcqSkipped = 0;
  let written = 0;
  let writtenSkipped = 0;

  document.querySelectorAll(".exam-question").forEach((block) => {
    const idx = parseInt(block.dataset.idx, 10);
    const q = questions[idx];
    if (!q) return;

    const type = (q.questionType || "").toLowerCase();
    const correctText = escapeHtml(getMcqOptionText(q, resolveMcqLetter(q.correctAnswer, q.options)));

    if (type === "mcq") {
      mcqTotal += 1;
      const expected = resolveMcqLetter(q.correctAnswer, q.options);

      block.querySelectorAll(".mcq-opt-label").forEach((lab) => {
        if (lab.dataset.opt === expected) lab.classList.add("correct-opt");
      });

      const picked = block.querySelector('input[type="radio"]:checked');
      const val = picked ? picked.value.toUpperCase() : "";

      if (!val) {
        mcqSkipped += 1;
        block.classList.add("result-skipped");
        setQuestionFeedback(
          block,
          "skipped",
          `<i class="fas fa-minus-circle me-1"></i><strong>Not attempted.</strong> Correct answer: ${correctText}`
        );
      } else if (val === expected) {
        mcqCorrect += 1;
        block.classList.add("result-correct");
        if (picked.parentElement) picked.parentElement.classList.add("correct-opt");
        setQuestionFeedback(
          block,
          "correct",
          `<i class="fas fa-check-circle me-1"></i><strong>Correct!</strong> You selected ${correctText}`
        );
      } else {
        mcqWrong += 1;
        block.classList.add("result-wrong");
        if (picked.parentElement) picked.parentElement.classList.add("wrong-opt");
        const yours = escapeHtml(getMcqOptionText(q, val));
        setQuestionFeedback(
          block,
          "wrong",
          `<i class="fas fa-times-circle me-1"></i><strong>Wrong.</strong> You chose ${yours} — Correct: ${correctText}`
        );
      }
    } else {
      const ta = block.querySelector("[data-written]");
      const answered = ta && ta.value.trim();
      if (answered) {
        written += 1;
        block.classList.add("result-answered");
        setQuestionFeedback(
          block,
          "answered",
          `<i class="fas fa-pen me-1"></i><strong>Answered.</strong> Compare with the answer key below.`
        );
      } else {
        writtenSkipped += 1;
        block.classList.add("result-skipped");
        const model = escapeHtml(q.correctAnswer || "See answer key");
        setQuestionFeedback(
          block,
          "skipped",
          `<i class="fas fa-minus-circle me-1"></i><strong>Not attempted.</strong> Model answer: ${model}`
        );
      }
    }
  });

  lockTestInputs();
  testSubmitted = true;
  stopTimer();

  const pct = mcqTotal ? Math.round((mcqCorrect / mcqTotal) * 100) : 0;
  const panel = document.getElementById("scorePanel");
  panel.style.display = "block";
  panel.className = "score-panel no-print" + (pct >= 50 ? "" : " fail");
  panel.innerHTML = `
    <h5 class="fw-bold mb-2">${auto ? "Time is up!" : "Test submitted"}</h5>
    <p class="mb-1">MCQs: <strong>${mcqCorrect} correct</strong> · <span class="text-danger">${mcqWrong} wrong</span> · <span style="color:#b45309">${mcqSkipped} skipped</span> (${mcqTotal} total)</p>
    <p class="mb-1">Score: <strong>${pct}%</strong> on MCQs</p>
    <p class="mb-0 small text-muted">Short/Long: ${written} answered, ${writtenSkipped} skipped — green = correct, red = wrong, orange = skipped</p>
  `;

  showAnswerKey(lastPaper);
  updateToolbar();
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function generatePaper() {
  const file = document.getElementById("fileInput").files[0];
  const text = document.getElementById("textInput").value.trim();
  const counts = getCounts();

  if (!file && !text) {
    alert("Upload PDF/DOCX/TXT or paste your notes.");
    return;
  }
  if (selectedTypes.length === 0) {
    alert("Select at least one question type.");
    return;
  }
  if (counts.mcq + counts.short + counts.long < 1) {
    alert("Set count greater than 0 for selected types.");
    return;
  }
  if (file && file.size > MAX_UPLOAD_BYTES) {
    showUploadError(fileTooLargeMessage(file.size), FILE_TOO_LARGE_TIPS);
    return;
  }

  hideUploadError();
  const btn = document.getElementById("generateBtn");
  btn.disabled = true;
  btn.textContent = paperMode === "test" ? "Preparing test..." : "Generating paper...";
  showProcessingOverlay(
    paperMode === "test" ? "Preparing your timed test…" : "Generating your practice paper…"
  );

  try {
    let paper;
    if (file) {
      const form = new FormData();
      form.append("file", file);
      form.append("mcq", counts.mcq);
      form.append("short", counts.short);
      form.append("long", counts.long);
      paper = await apiFetch("/api/questionbank/student/generate", { method: "POST", body: form });
    } else {
      paper = await apiFetch("/api/questionbank/student/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, counts }),
      });
    }

    if (paperMode === "test") {
      const mins = computeTestMinutes(counts);
      paper.duration = `${mins} minutes`;
    }

    setProcessingComplete();
    await new Promise((r) => setTimeout(r, 400));

    testSubmitted = false;
    lastPaper = paper;
    lastPaper._mode = paperMode;
    lastPaper._counts = counts;

    document.getElementById("paperWrap").style.display = "block";
    document.getElementById("toolbarBox").style.display = "block";
    document.getElementById("scorePanel").style.display = "none";
    showPaper(paperMode);

    if (paperMode === "test") {
      document.getElementById("answerKeyArea").style.display = "none";
      startTimer(computeTestMinutes(counts));
    }

    document.getElementById("paperWrap").scrollIntoView({ behavior: "smooth" });
  } catch (e) {
    const isTooLarge =
      e.code === "file_too_large" ||
      e.message?.includes("413") ||
      /too large|entity too large/i.test(e.message || "");
    if (isTooLarge) {
      const size = file ? file.size : 0;
      showUploadError(
        e.message && e.message !== "file_too_large" ? e.message : fileTooLargeMessage(size),
        e.tips || FILE_TOO_LARGE_TIPS
      );
    } else {
      alert(e.message || "Failed. Start backend: python app.py");
    }
  } finally {
    hideProcessingOverlay();
    btn.disabled = false;
    btn.textContent = paperMode === "test" ? "Start timed test" : "Generate practice paper";
  }
}

async function downloadWord(includeKey) {
  if (!lastPaper) {
    alert("Generate a paper first.");
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/api/questionbank/student/export-docx`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        paper: lastPaper,
        meta: {
          simpleLayout: true,
          examTitle: lastPaper.title,
          questionsOnly: true,
        },
        includeAnswerKey: includeKey,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Word export failed");
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (lastPaper.title || "student-paper").replace(/\s+/g, "-").slice(0, 40) + ".docx";
    a.click();
  } catch (e) {
    alert(e.message + "\n\nTip: pip install python-docx in backend folder");
  }
}

async function savePaper() {
  if (!lastPaper) return;
  try {
    await apiFetch("/api/questionbank/papers/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: lastPaper.title,
        paper: lastPaper,
        filters: { source: "student", mode: paperMode },
      }),
    });
    alert("Paper saved.");
  } catch (e) {
    alert(e.message);
  }
}

document.getElementById("generateBtn").addEventListener("click", generatePaper);
document.getElementById("btnWord").addEventListener("click", () => downloadWord(false));
document.getElementById("btnWordKey").addEventListener("click", () => downloadWord(true));
document.getElementById("btnPrint").addEventListener("click", () => window.print());
document.getElementById("btnSave").addEventListener("click", savePaper);
document.getElementById("btnSubmitTest").addEventListener("click", () => submitTest(false));
document.getElementById("btnToggleKey").addEventListener("click", () => {
  const area = document.getElementById("answerKeyArea");
  if (lastPaper) showAnswerKey(lastPaper);
  area.style.display = area.style.display === "none" ? "block" : "none";
});

updateTimeEstimate();
