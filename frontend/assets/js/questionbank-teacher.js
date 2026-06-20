/**
 * Mukabbir College Gujrat — Teacher Dashboard (Punjab Board)
 */
let metaCache = null;
let selectedBook = null;
let selectedSubject = null;
let boardId = null;
let classLevel = null;
let lastPaper = null;
let lastPaperFormat = "board";

const EXAM_INFO = {
  weekly:
    "Weekly Test — 30 marks. Section A: 6 MCQs (1 mark each). Section B: 12 short questions (1 mark each). Section C: 1 long question (12 marks). Time: 45 minutes.",
  monthly:
    "Monthly Test — same phased pattern as weekly (30 marks). Suitable for cumulative unit revision.",
  quarter:
    "Quarterly Test — 30 marks phased paper covering approximately one quarter of the syllabus.",
  half_book:
    "Half Book Exam — half syllabus coverage. Full board-style sections. 15 MCQs, 10 short, 5 long questions. 100 marks. 3 hours.",
  pre_board:
    "Pre-Board — Punjab Board official pattern (varies by subject). Science: 17 MCQs + Section I short blocks + Section II long. Computer: 15 MCQs + 75 marks.",
  class_assessment:
    "Class Assessment — flexible format. Choose MCQ-only, short-only, long-only, or mixed assessment.",
};

const ASSESSMENT_PRESETS = {
  mcq: { mcq: 10, short: 0, long: 0, marks: 10, time: "30 minutes" },
  short: { mcq: 0, short: 10, long: 0, marks: 10, time: "30 minutes" },
  long: { mcq: 0, short: 0, long: 2, marks: 16, time: "45 minutes" },
  mixed: { mcq: 6, short: 8, long: 1, marks: 30, time: "45 minutes" },
};

const DEMO_BOOK = "";

function $(id) {
  return document.getElementById(id);
}

function setStepActive(step) {
  document.querySelectorAll(".td-stepper li").forEach((li) => {
    li.classList.toggle("active", parseInt(li.dataset.step, 10) <= step);
    li.classList.toggle("done", parseInt(li.dataset.step, 10) < step);
  });
}

function enableCard(id, on) {
  const el = $(id);
  if (!el) return;
  el.classList.toggle("td-disabled", !on);
}

function selectedExamCode() {
  const opt = $("exam").selectedOptions[0];
  return opt ? opt.dataset.code || "" : "";
}

function selectedPaperFormat() {
  return document.querySelector('input[name="paperFormat"]:checked')?.value || "board";
}

function patternTableHtml(p) {
  if (!p) {
    return "<p class='text-muted mb-0'>Pattern not configured. Run Punjab Board setup in Admin.</p>";
  }
  return `
    <table class="table table-sm td-pattern-table mb-0">
      <thead><tr><th>Section A</th><th>Section B</th><th>Section C</th><th>Total</th><th>Time</th></tr></thead>
      <tbody><tr>
        <td>${p.mcqCount} MCQs</td>
        <td>${p.shortCount} Short</td>
        <td>${p.longCount} Long</td>
        <td><strong>${p.totalMarks}</strong></td>
        <td>${p.duration}</td>
      </tr></tbody>
    </table>`;
}

function syncSectionCountsFromPattern(p) {
  if (!p) return;
  $("secAMcq").value = p.mcqCount;
  $("secBShort").value = p.shortCount;
  $("secCLong").value = p.longCount;
  $("secAMarks").value = `${p.mcqCount} × 1 = ${p.mcqCount}`;

  const shortAtt = p.shortAttempt || p.shortCount;
  const longAtt = p.longAttempt || p.longCount;
  const isPreBoard = p.examCode === "pre_board" || (p.shortAttempt && p.totalMarks >= 85);

  if ($("secATitle")) {
    $("secATitle").value = isPreBoard
      ? "SECTION A — OBJECTIVE (MCQs)"
      : "SECTION A – MCQs";
  }
  if ($("secBTitle")) {
    $("secBTitle").value = isPreBoard
      ? "SECTION B — SHORT QUESTIONS"
      : "SECTION B – Short Questions";
  }
  if ($("secCTitle")) {
    $("secCTitle").value = isPreBoard
      ? "SECTION C — LONG QUESTIONS"
      : "SECTION C – Long Questions";
  }

  if (isPreBoard || p.totalMarks >= 100) {
    const shortMarks = shortAtt * 2;
    const longTotal = p.totalMarks - p.mcqCount - shortMarks;
    const eachLong = longAtt ? Math.round(longTotal / longAtt) : 13;
    $("secBMarks").value =
      shortAtt < p.shortCount
        ? `Attempt ${shortAtt} of ${p.shortCount} — ${shortAtt} × 2 = ${shortMarks}`
        : `${p.shortCount} × 2 = ${p.shortCount * 2}`;
    $("secCMarks").value = p.longCount
      ? longAtt < p.longCount
        ? `Attempt ${longAtt} of ${p.longCount} — ${longAtt} × ${eachLong} = ${longAtt * eachLong}`
        : `${p.longCount} × ${eachLong} = ${p.longCount * eachLong}`
      : "0";
  } else {
    $("secBMarks").value = `${p.shortCount} × 1 = ${p.shortCount}`;
    const longTotal = p.totalMarks - p.mcqCount - p.shortCount;
    const each = p.longCount ? Math.round(longTotal / p.longCount) : 12;
    $("secCMarks").value = p.longCount ? `${p.longCount} × ${each} = ${longTotal}` : "0";
  }
}

function updateAssessmentPreview() {
  const mcq = parseInt($("customMcq").value, 10) || 0;
  const short = parseInt($("customShort").value, 10) || 0;
  const long = parseInt($("customLong").value, 10) || 0;
  const marks = parseInt($("customMarks").value, 10) || mcq + short + long * 5;
  const time = $("customTime").value || "30 minutes";
  $("patternBox").innerHTML = patternTableHtml({
    mcqCount: mcq,
    shortCount: short,
    longCount: long,
    totalMarks: marks,
    duration: time,
  });
  $("patternSubtitle").textContent = "Your custom assessment pattern (counts below = paper)";
}

function applyAssessmentPreset(mode) {
  const p = ASSESSMENT_PRESETS[mode] || ASSESSMENT_PRESETS.mixed;
  $("customMcq").value = p.mcq;
  $("customShort").value = p.short;
  $("customLong").value = p.long;
  $("customMarks").value = p.marks;
  $("customTime").value = p.time;
  updateAssessmentPreview();
}

function toggleAssessmentPanel(examCode, pattern) {
  const panel = $("assessmentPanel");
  const sections = $("sectionsPanel");
  const isCustom = examCode === "class_assessment";
  panel.classList.toggle("d-none", !isCustom);
  if (sections) {
    sections.classList.toggle("d-none", isCustom);
    sections.style.display = isCustom ? "none" : "";
  }
  if (isCustom) {
    $("patternSubtitle").textContent = "Class Assessment — pick format A/B/C/D, then adjust counts";
    const mode = document.querySelector('input[name="assessMode"]:checked')?.value || "mcq";
    applyAssessmentPreset(mode);
    return;
  }
  if (pattern) {
    syncSectionCountsFromPattern(pattern);
    $("patternBox").innerHTML = patternTableHtml(pattern);
  }
}

function getSectionConfig() {
  const isAssessment = selectedExamCode() === "class_assessment";
  if (isAssessment) {
    const mcq = parseInt($("customMcq").value, 10) || 0;
    const short = parseInt($("customShort").value, 10) || 0;
    const long = parseInt($("customLong").value, 10) || 0;
    return {
      counts: { mcq, short, long },
      sections: {
        objective: mcq > 0,
        short: short > 0,
        long: long > 0,
        objectiveTitle: "SECTION A – MCQs",
        shortTitle: "SECTION B – Short Questions",
        longTitle: "SECTION C – Long Questions",
        objectiveMarksLine: mcq ? `${mcq} × 1 = ${mcq}` : "",
        shortMarksLine: short ? `${short} × 1 = ${short}` : "",
        longMarksLine: long
          ? `${long} × ${Math.max(1, Math.round(((parseInt($("customMarks").value, 10) || 30) - mcq - short) / long))} = ${(parseInt($("customMarks").value, 10) || 30) - mcq - short}`
          : "",
      },
    };
  }

  const mcq = $("secAEnabled").checked ? parseInt($("secAMcq").value, 10) || 0 : 0;
  const short = $("secBEnabled").checked ? parseInt($("secBShort").value, 10) || 0 : 0;
  const long = $("secCEnabled").checked ? parseInt($("secCLong").value, 10) || 0 : 0;
  return {
    counts: { mcq, short, long },
    sections: {
      objective: mcq > 0,
      short: short > 0,
      long: long > 0,
      objectiveTitle: $("secATitle").value.trim() || "SECTION A – MCQs",
      shortTitle: $("secBTitle").value.trim() || "SECTION B – Short Questions",
      longTitle: $("secCTitle").value.trim() || "SECTION C – Long Questions",
      objectiveMarksLine: $("secAMarks").value.trim(),
      shortMarksLine: $("secBMarks").value.trim(),
      longMarksLine: $("secCMarks").value.trim(),
    },
  };
}

function preBoardDetail(subject) {
  const s = (subject || "").toLowerCase();
  if (s === "computer") {
    return "15 MCQs (compulsory) · Section I: 3 blocks × (attempt 6 of 9 short) · Section II: attempt 3 of 5 long · 75 marks";
  }
  if (["physics", "chemistry", "biology"].includes(s)) {
    return "17 MCQs (compulsory) · Section I: Q2 (8/12) + Q3 (8/12) + Q4 (6/9) short · Section II: attempt 3 of 5 long · 85 marks";
  }
  return EXAM_INFO.pre_board;
}

async function refreshPattern() {
  const examId = $("exam").value;
  const examCode = selectedExamCode();
  if (examCode === "pre_board" && selectedSubject) {
    $("examInfo").textContent =
      preBoardDetail(selectedSubject) +
      " Pre-Board papers take longer to generate. Try Weekly Test for a quicker result.";
  } else {
    $("examInfo").textContent = EXAM_INFO[examCode] || "";
  }

  if (!boardId || !examId) {
    $("patternBox").innerHTML = "<p class='text-muted mb-0'>Select an exam type.</p>";
    return;
  }

  const subjectQ = selectedSubject
    ? `&subject=${encodeURIComponent(selectedSubject)}`
    : "";

  if (examCode === "class_assessment") {
    toggleAssessmentPanel(examCode, null);
    return;
  }

  try {
    const pattern = await apiFetch(
      `/api/questionbank/pattern?boardId=${boardId}&examTypeId=${examId}${subjectQ}`
    );
    $("patternBox").innerHTML = patternTableHtml(pattern);
    toggleAssessmentPanel(examCode, pattern);
  } catch {
    $("patternBox").innerHTML =
      "<p class='text-danger mb-0'>Pattern missing. Admin → Load Punjab Board setup.</p>";
    toggleAssessmentPanel(examCode, null);
  }
}

function populateBooks() {
  const sel = $("bookSelect");
  sel.innerHTML = '<option value="">Select a book</option>';
  if (!classLevel || !metaCache) {
    sel.disabled = true;
    return;
  }

  const books = (metaCache.books || []).filter((b) => b.classLevel === classLevel);
  books.forEach((b) => {
    const label = `${b.subjectName} — ${b.name}`;
    sel.innerHTML += `<option value="${b.name}" data-subject="${b.subjectName}" data-id="${b.id}">${label}</option>`;
  });
  sel.disabled = !books.length;
  $("bookHint").textContent = books.length
    ? `${books.length} book(s) available for class ${classLevel}.`
    : "No uploaded books for this class yet.";

  const demo = books.find((b) => b.name === DEMO_BOOK);
  if (demo) {
    sel.value = DEMO_BOOK;
    sel.dispatchEvent(new Event("change"));
  }
}

function populateExams() {
  const sel = $("exam");
  sel.innerHTML = '<option value="">Select exam type</option>';
  (metaCache.examTypes || []).forEach((e) => {
    if (e.isEnabled === false) return;
    sel.innerHTML += `<option value="${e.id}" data-code="${e.code}">${e.name}</option>`;
  });
  sel.disabled = !metaCache.examTypes?.length;
}

async function loadMetadata() {
  metaCache = await apiFetch("/api/questionbank/teacher/metadata");
  const board = metaCache.board;
  boardId = board ? board.id : null;
  $("boardId").value = boardId || "";
  if (board) $("boardLabel").textContent = board.name;

  populateExams();
  $("exam").disabled = false;
  enableCard("stepExam", true);
}

function onClassSelect(level, classId) {
  classLevel = level;
  $("classLevel").value = level;
  $("classId").value = classId || "";
  document.querySelectorAll(".td-class-btn").forEach((btn) => {
    btn.classList.toggle("selected", parseInt(btn.dataset.level, 10) === level);
  });

  setStepActive(2);
  enableCard("stepBook", true);
  enableCard("stepExam", true);
  enableCard("stepChapters", true);
  enableCard("stepPattern", true);
  $("btnGenerate").disabled = false;

  populateBooks();
  refreshPattern();
}

async function loadChapters(book, subject) {
  selectedBook = book;
  selectedSubject = subject;
  $("chapterContainer").innerHTML = "<p class='text-muted small'>Loading chapters…</p>";
  setStepActive(4);

  const chapters = await apiFetch(
    `/api/questionbank/chapters?book=${encodeURIComponent(book)}&subject=${encodeURIComponent(subject)}`
  );

  if (!chapters.length) {
    $("chapterContainer").innerHTML =
      "<p class='text-muted small'>No chapters found. Upload book content in Question Bank Admin.</p>";
    $("syllabusHint").textContent = "";
    return;
  }

  const sorted = [...chapters].sort((a, b) => {
    const na = parseInt((a.title || "").match(/chapter\s*(\d+)/i)?.[1] || a.sortOrder || 0, 10);
    const nb = parseInt((b.title || "").match(/chapter\s*(\d+)/i)?.[1] || b.sortOrder || 0, 10);
    return na !== nb ? na - nb : (a.title || "").localeCompare(b.title || "");
  });

  let html = "";
  sorted.forEach((c) => {
    let note = "no text — upload in Admin";
    if (c.textQuality === "watermark_only") {
      note = "corrupt PDF (watermark) — re-upload in Admin";
    } else if (c.textQuality === "ok" || ((c.charCount || 0) > 80 && c.textQuality !== "too_short")) {
      note = "syllabus ready";
    } else if ((c.charCount || 0) > 80) {
      note = "poor text — re-upload PDF";
    }
    html += `<label class="syllabus-item"><input type="checkbox" class="ch" value="${c.title}"> <span>${c.title}</span> <small class="text-muted">(${note})</small></label>`;
  });
  $("chapterContainer").innerHTML = html;
  document.querySelectorAll(".ch").forEach((cb) => (cb.checked = true));
  $("syllabusHint").textContent =
    `${sorted.length} chapter(s). Select syllabus → Create Paper (AI generates fresh questions from book text, like Student module).`;
}

async function generatePaper() {
  const examOpt = $("exam").selectedOptions[0];
  const examTypeId = parseInt($("exam").value, 10);
  const classOpt = metaCache.classes.find((c) => c.gradeLevel === classLevel);
  const chapters = [];
  document.querySelectorAll(".ch:checked").forEach((c) => chapters.push(c.value));

  if (!selectedBook || !selectedSubject || !chapters.length || !boardId || !examTypeId) {
    alert("Please complete all steps: class, book, exam type, and at least one chapter.");
    return;
  }

  const sec = getSectionConfig();
  if (!sec.sections.objective && !sec.sections.short && !sec.sections.long) {
    alert("Enable at least one paper section.");
    return;
  }

  const body = {
    subject: selectedSubject,
    book: selectedBook,
    chapters,
    boardId,
    examTypeId,
    className: classOpt ? classOpt.name : `${classLevel}th`,
    examName: examOpt ? examOpt.textContent : "",
    difficulty: $("difficulty").value.toLowerCase(),
    sections: sec.sections,
    varietySeed: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
    preferCachedQuestions: $("preferCached") ? $("preferCached").checked : false,
    cacheAfterGenerate: $("preferCached") ? $("preferCached").checked : false,
  };

  if (selectedExamCode() === "class_assessment") {
    body.customPattern = {
      mcq: sec.counts.mcq,
      short: sec.counts.short,
      long: sec.counts.long,
      marks: parseInt($("customMarks").value, 10) || 30,
      duration: $("customTime").value || "45 minutes",
    };
  } else {
    body.customPattern = {
      mcq: sec.counts.mcq,
      short: sec.counts.short,
      long: sec.counts.long,
    };
    const subjectQ = selectedSubject
      ? `&subject=${encodeURIComponent(selectedSubject)}`
      : "";
    try {
      const pat = await apiFetch(
        `/api/questionbank/pattern?boardId=${boardId}&examTypeId=${examTypeId}${subjectQ}`
      );
      body.customPattern.marks = pat.totalMarks;
      body.customPattern.duration = pat.duration;
    } catch {
      body.customPattern.marks = 30;
      body.customPattern.duration = "45 minutes";
    }
  }

  const isHeavy =
    selectedExamCode() === "pre_board" ||
    sec.counts.mcq + sec.counts.short + sec.counts.long > 25;
  $("previewStatus").textContent = isHeavy
    ? "Creating exam paper (AI)… Pre-Board can take 5–10 min — tab open rakhein"
    : "Creating exam paper (AI from book text)… 1–3 min";
  $("btnGenerate").disabled = true;

  try {
    const paper = await apiFetchLong(
      "/api/questionbank/papers/generate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
      isHeavy ? 900000 : 420000
    );

    lastPaper = paper;
    const examDate = $("paperDate").value || new Date().toISOString().slice(0, 10);
    const paperMeta = {
      subject: selectedSubject,
      examName: examOpt ? examOpt.textContent : "",
      className: classOpt ? classOpt.name : `${classLevel}th`,
      examDate,
      sectionMeta: paper.sectionMeta,
      sectionMarks: {
        objective: sec.sections.objectiveMarksLine,
        short: sec.sections.shortMarksLine,
        long: sec.sections.longMarksLine,
      },
    };
    const fmt = selectedPaperFormat();
    const html = buildPaperHtml(paper, paperMeta, fmt);
    lastPaperFormat = fmt;

    $("output").innerHTML = html;
    $("previewStatus").textContent = "Exam paper ready — print, download Word, or save";
    $("btnPrint").disabled = false;
    $("btnDownload").disabled = false;
    $("btnSavePaper").disabled = false;
    setStepActive(5);
  } catch (e) {
    $("previewStatus").textContent = "Could not generate paper. Please try again.";
    if (typeof maybeShowGeminiError === "function") maybeShowGeminiError(e);
    else if (typeof toUserMessage === "function") alert(toUserMessage(e));
    else alert("Please try again in a few minutes.");
  } finally {
    $("btnGenerate").disabled = false;
  }
}

function printPaper() {
  const out = $("output");
  if (!out || !out.querySelector(".college-paper")) return;
  const w = window.open("", "_blank");
  w.document.write(
    `<html><head><title>Exam Paper</title><style>${paperPrintStyles(lastPaperFormat)}</style></head><body>${out.innerHTML}</body></html>`
  );
  w.document.close();
  w.print();
}

async function savePaperToDb() {
  if (!lastPaper) return;
  const examOpt = $("exam").selectedOptions[0];
  const title = `${selectedSubject || "Subject"} — ${selectedBook || "Book"} — ${examOpt ? examOpt.textContent : "Exam"}`;
  try {
    const res = await apiFetch("/api/questionbank/papers/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        paper: lastPaper,
        filters: {
          subject: selectedSubject,
          book: selectedBook,
          classLevel,
          examTypeId: parseInt($("exam").value, 10),
        },
      }),
    });
    alert(`Paper saved (ID ${res.id}). You can load it later from saved papers.`);
  } catch (e) {
    alert("Save failed: " + e.message);
  }
}

async function downloadPaper() {
  if (!lastPaper) return;
  const examOpt = $("exam").selectedOptions[0];
  const classOpt = metaCache.classes.find((c) => c.gradeLevel === classLevel);
  const res = await fetch(`${API_BASE}/api/questionbank/papers/export-docx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      paper: lastPaper,
      meta: {
        institute: "MUKABBIR COLLEGE GUJRAT",
        sectionMeta: lastPaper.sectionMeta,
        examTitle: examOpt ? examOpt.textContent : "Examination Paper",
        subject: selectedSubject,
        className: classOpt ? classOpt.name : `${classLevel}th`,
        date: $("paperDate").value || new Date().toISOString().slice(0, 10),
        duration: lastPaper.duration,
        boardFormat: lastPaperFormat === "board",
        simpleLayout: lastPaperFormat === "simple",
        instructions:
          "Read all questions carefully. Write answers in the space provided. Mobile phones are not allowed.",
      },
    }),
  });
  const data = await res.blob();
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = "exam-paper.docx";
  a.click();
  URL.revokeObjectURL(url);
}

function bindEvents() {
  document.querySelectorAll(".td-class-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const level = parseInt(btn.dataset.level, 10);
      const cls = (metaCache.classes || []).find((c) => c.gradeLevel === level);
      onClassSelect(level, cls ? cls.id : null);
    });
  });

  $("bookSelect").addEventListener("change", function () {
    const opt = this.selectedOptions[0];
    if (!opt || !opt.value) {
      selectedBook = null;
      selectedSubject = null;
      $("chapterContainer").innerHTML = "<p class='text-muted small'>Select a book to load chapters.</p>";
      return;
    }
    loadChapters(opt.value, opt.dataset.subject);
    refreshPattern();
    setStepActive(3);
  });

  $("exam").addEventListener("change", () => {
    refreshPattern();
    setStepActive(3);
  });

  document.querySelectorAll('input[name="assessMode"]').forEach((r) => {
    r.addEventListener("change", () => applyAssessmentPreset(r.value));
  });

  ["customMcq", "customShort", "customLong", "customMarks", "customTime"].forEach((id) => {
    $(id)?.addEventListener("input", () => {
      if (selectedExamCode() === "class_assessment") updateAssessmentPreview();
    });
  });

  $("btnSelectAll").addEventListener("click", () => {
    document.querySelectorAll(".ch").forEach((c) => (c.checked = true));
  });
  $("btnClearChapters").addEventListener("click", () => {
    document.querySelectorAll(".ch").forEach((c) => (c.checked = false));
  });

  $("btnGenerate").addEventListener("click", generatePaper);
  $("btnPrint").addEventListener("click", printPaper);
  $("btnDownload").addEventListener("click", downloadPaper);
  $("btnSavePaper").addEventListener("click", savePaperToDb);

  $("paperDate").value = new Date().toISOString().slice(0, 10);
}

bindEvents();
loadMetadata().catch(() => {
  $("bookHint").textContent = "Unable to load books. Please refresh the page.";
});
