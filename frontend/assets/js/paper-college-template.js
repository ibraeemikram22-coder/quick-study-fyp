/** Mukabbir College Gujrat — Punjab Board examination paper layout */

const PAPER_HEADER_KEY = "qsb_paper_header_mukabbir";

const DEFAULT_HEADER = {
  collegeName: "MUKABBIR COLLEGE GUJRAT",
  boardName: "Punjab Board",
};

function loadPaperHeader() {
  try {
    return { ...DEFAULT_HEADER, ...JSON.parse(localStorage.getItem(PAPER_HEADER_KEY) || "{}") };
  } catch {
    return { ...DEFAULT_HEADER };
  }
}

function savePaperHeader(fields) {
  localStorage.setItem(PAPER_HEADER_KEY, JSON.stringify(fields));
}

function programFromClass(className) {
  if (!className) return "Intermediate Part 1";
  if (/12|2nd|second|part\s*2/i.test(className)) return "Intermediate Part 2";
  return "Intermediate Part 1";
}

function formatMcqOptions(options) {
  const labels = ["A", "B", "C", "D", "E", "F"];
  return (options || [])
    .slice(0, 6)
    .map((opt, i) => {
      const text = String(opt).trim();
      const label = labels[i] || String.fromCharCode(65 + i);
      const prefixed = /^\([A-D]\)/i.test(text) ? text : `(${label}) ${text}`;
      return `<span class="mcq-opt">${prefixed}</span>`;
    })
    .join("");
}

function sectionMetaKey(sec) {
  const qType = (sec.questionType || "").toLowerCase();
  const title = (sec.title || "").toLowerCase();
  if (qType === "short" || /short|section b/i.test(title)) return "short";
  if (qType === "long" || /long|section c/i.test(title)) return "long";
  return "objective";
}

const ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"];

function renderShortBlocks(qs, shortMeta) {
  const blocks = shortMeta.blocks || [];
  let offset = 0;
  let html = "";
  blocks.forEach((blk) => {
    const slice = qs.slice(offset, offset + (blk.printed || 0));
    offset += blk.printed || 0;
    html += `<div class="paper-short-block">`;
    html += `<div class="paper-block-head"><strong>${escapeHtml(blk.title || "")}</strong> — ${escapeHtml(blk.instruction || "")} <span class="paper-marks-line"><strong>${escapeHtml(blk.marksLine || "")}</strong></span></div>`;
    slice.forEach((q, i) => {
      const roman = ROMAN[i] || String(i + 1);
      html += `<div class="paper-question"><div class="paper-q-text"><strong>${roman}</strong> — ${q.questionText}</div></div>`;
    });
    html += `</div>`;
  });
  if (offset < qs.length) {
    qs.slice(offset).forEach((q, i) => {
      html += `<div class="paper-question"><div class="paper-q-text"><strong>${i + 1}.</strong> ${q.questionText}</div></div>`;
    });
  }
  return html;
}

function renderLongQuestionBody(q, index, startNo = 5) {
  const num = startNo + index;
  const text = String(q.questionText || "");
  const partMatch = text.match(/\(\s*[ab]\s*\)/gi);
  if (!partMatch || partMatch.length < 2) {
    return `<div class="paper-q-text"><strong>${num}.</strong> ${text}</div>`;
  }
  const parts = text.split(/(?=\(\s*[ab]\s*\))/i).filter(Boolean);
  let html = `<div class="paper-q-text"><strong>${num}.</strong></div>`;
  parts.forEach((part) => {
    html += `<div class="paper-long-part">${part.trim()}</div>`;
  });
  return html;
}

function sectionBlock(sec, sectionIndex, opts = {}) {
  const qs = sec.questions || [];
  if (!qs.length) return "";

  const marksPerMcq = opts.marksPerMcq ?? 1;
  const customMarks = opts.customMarks || {};
  const sectionMeta = opts.sectionMeta || {};
  const metaKey = sectionMetaKey(sec);
  const sm = sectionMeta[metaKey] || {};
  const title = (sec.title || "").toUpperCase();
  const isMcq = metaKey === "objective";
  const isShort = metaKey === "short";
  const isLong = metaKey === "long";

  let label = sm.title || title || "SECTION A – MCQs";
  let instruction = sm.instruction || "";
  let marksLine = customMarks[metaKey] || sm.marksLine || "";

  if (!instruction) {
    if (isMcq) {
      instruction = "Attempt all questions. Each question carries one mark.";
      marksLine = marksLine || `${qs.length} × ${marksPerMcq} = ${qs.length * marksPerMcq}`;
    } else if (isShort) {
      instruction = "Attempt all short questions.";
      marksLine = marksLine || `${qs.length} × 1 = ${qs.length}`;
    } else if (isLong) {
      instruction = "Attempt the long question(s). Each may have parts (a) and (b) with internal choice.";
      marksLine = marksLine || `${qs.length} question(s)`;
    }
  }

  let body = `
    <div class="paper-section">
      <div class="paper-section-label">${escapeHtml(label)}</div>
      <div class="paper-section-meta">
        <span class="paper-instruction">${instruction}</span>
        ${marksLine ? `<span class="paper-marks-line"><strong>${marksLine}</strong></span>` : ""}
      </div>`;

  if (isShort && sm.blocks && sm.blocks.length) {
    body += renderShortBlocks(qs, sm);
  } else {
    qs.forEach((q, i) => {
      body += `<div class="paper-question">`;
      if (isLong) {
        body += renderLongQuestionBody(q, i, opts.longStartNo ?? 5);
      } else {
        body += `<div class="paper-q-text"><strong>${i + 1}.</strong> ${q.questionText}</div>`;
      }
      if (q.options && q.options.length) {
        body += `<div class="paper-mcq-row">${formatMcqOptions(q.options)}</div>`;
      }
      body += `</div>`;
    });
  }

  body += `</div>`;
  return body;
}

function buildCollegePaperHtml(paper, meta) {
  const h = loadPaperHeader();
  const subject = meta.subject || "";
  const className = meta.className || "11th";
  const examName = meta.examName || paper.title || "Examination Paper";
  const examDate = meta.examDate || new Date().toISOString().slice(0, 10);
  const marks = paper.marks || 0;
  const duration = paper.duration || "";

  const instructions =
    meta.instructions ||
    "Read all questions carefully. Write your answers in the space provided. Use a blue or black pen. Mobile phones and unauthorized material are not allowed.";

  let html = `<div class="college-paper">`;

  html += `
    <div class="paper-college-name">${escapeHtml(h.collegeName)}</div>
    <div class="paper-board-line">${escapeHtml(h.boardName || "Punjab Board")}</div>
    <div class="paper-exam-title">${escapeHtml(examName)}</div>
    <table class="paper-meta-table">
      <tr>
        <td><strong>Class:</strong> ${escapeHtml(className)}</td>
        <td><strong>Subject:</strong> ${escapeHtml(subject)}</td>
      </tr>
      <tr>
        <td><strong>Exam Type:</strong> ${escapeHtml(examName)}</td>
        <td><strong>Date:</strong> ${escapeHtml(examDate)}</td>
      </tr>
      <tr>
        <td><strong>Time Allowed:</strong> ${escapeHtml(duration)}</td>
        <td><strong>Total Marks:</strong> ${marks}</td>
      </tr>
    </table>
    <div class="paper-student-line">
      <span>Name: ....................................................................</span>
      <span>Roll No: ............................</span>
    </div>
    <div class="paper-instructions"><strong>Instructions:</strong> ${escapeHtml(instructions)}</div>
    ${(meta.sectionMeta || paper.sectionMeta || {}).paperNote ? `<div class="paper-note"><strong>Note:</strong> ${escapeHtml((meta.sectionMeta || paper.sectionMeta).paperNote)}</div>` : ""}
  `;

  const customMarks = meta.sectionMarks || {};
  let secNum = 1;
  (paper.sections || []).forEach((sec) => {
    if ((sec.questions || []).length) {
      const t = (sec.title || "").toLowerCase();
      const marks = { ...customMarks };
      if (/short/i.test(t) && customMarks.short) marks.short = customMarks.short;
      if (/long/i.test(t) && customMarks.long) marks.long = customMarks.long;
      if (/objective|mcq|section a/i.test(t) && customMarks.objective) {
        marks.objective = customMarks.objective;
      }
      html += sectionBlock(sec, secNum, {
        marksPerMcq: 1,
        customMarks: marks,
        sectionMeta: meta.sectionMeta || paper.sectionMeta || {},
      });
      secNum += 1;
    }
  });

  html += `</div>`;
  return html;
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function collegePaperPrintStyles() {
  return `
    body { font-family: "Times New Roman", Times, serif; font-size: 13px; color: #000; margin: 20px 28px; }
    .college-paper { max-width: 800px; margin: 0 auto; }
    .paper-college-name { text-align: center; font-weight: bold; font-size: 18px; letter-spacing: 0.5px; margin-bottom: 2px; }
    .paper-board-line { text-align: center; font-size: 12px; margin-bottom: 4px; }
    .paper-exam-title { text-align: center; font-size: 14px; margin-bottom: 10px; font-weight: 600; }
    .paper-meta-table { width: 100%; border-collapse: collapse; margin-bottom: 10px; font-size: 12px; }
    .paper-meta-table td { border: 1px solid #000; padding: 5px 8px; width: 50%; }
    .paper-student-line { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 10px; }
    .paper-instructions { font-size: 11px; font-style: italic; border: 1px solid #999; padding: 8px; margin-bottom: 14px; }
    .paper-section { margin-top: 14px; }
    .paper-section-label {
      border: 2px solid #000; padding: 2px 24px; font-weight: bold; font-size: 12px;
      display: table; margin: 12px auto 8px;
    }
    .paper-section-meta { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 10px; }
    .paper-question { margin-bottom: 12px; page-break-inside: avoid; }
    .paper-q-text { margin-bottom: 4px; line-height: 1.35; }
    .paper-mcq-row { display: flex; flex-wrap: wrap; gap: 8px 20px; font-size: 12px; padding-left: 16px; }
    .paper-long-part { margin-left: 20px; margin-bottom: 6px; line-height: 1.35; }
    .paper-short-block { margin-bottom: 14px; }
    .paper-block-head { font-size: 12px; margin-bottom: 8px; line-height: 1.4; }
    .paper-note { font-size: 11px; margin-bottom: 12px; font-weight: 600; }
    @media print { body { margin: 12mm; } }
  `;
}

function classYearLabel(className) {
  if (/12|2nd|second|part\s*2/i.test(className || "")) return "2nd year";
  return "1st year";
}

function boardPaperHeader(meta, paper, h) {
  const subject = meta.subject || "";
  const className = meta.className || "11th";
  const examName = meta.examName || paper.title || "Preboard Examination";
  const marks = paper.marks || 0;
  const duration = paper.duration || paper.duration || "";
  const program = programFromClass(className);

  return `
    <div class="board-college-name">${escapeHtml(h.collegeName)}</div>
    <div class="board-exam-title">${escapeHtml(examName)}</div>
    <table class="board-meta-table">
      <tr>
        <td><strong>Program</strong><br>${escapeHtml(program)}</td>
        <td><strong>Class</strong><br>${escapeHtml(classYearLabel(className))}</td>
      </tr>
      <tr>
        <td><strong>Subject</strong><br>${escapeHtml(subject)}</td>
        <td><strong>Time Allowed</strong><br>${escapeHtml(duration)}</td>
      </tr>
      <tr>
        <td><strong>Teacher</strong><br>${escapeHtml(meta.teacherName || "................................")}</td>
        <td><strong>Maximum Marks</strong><br>${marks}</td>
      </tr>
    </table>
    <div class="board-student-line">
      <span>Name: ....................................................................</span>
      <span>Roll No: ............................</span>
    </div>`;
}

function boardMcqTable(sec, objMeta) {
  const qs = sec.questions || [];
  if (!qs.length) return "";
  const head = objMeta.boardHead || "Q.No.1: Encircle the Correct Option.";
  const marks = objMeta.marksLine || `(1×${qs.length}=${qs.length})`;
  let html = `<table class="board-table board-mcq-table">`;
  html += `<tr class="board-section-head"><td colspan="2"><strong>${escapeHtml(head)}</strong> ${escapeHtml(marks)}</td></tr>`;
  qs.forEach((q, i) => {
    html += `<tr><td class="board-num">${i + 1}</td><td class="board-qcell">`;
    html += `<div class="board-q-text">${q.questionText || ""}</div>`;
    const opts = (q.options || []).slice(0, 4);
    if (opts.length) {
      html += `<table class="board-opt-row"><tr>`;
      opts.forEach((opt, j) => {
        const letter = String.fromCharCode(97 + j);
        html += `<td>(${letter}) ${escapeHtml(String(opt).trim())}</td>`;
      });
      html += `</tr></table>`;
    }
    html += `</td></tr>`;
  });
  html += `</table>`;
  return html;
}

function boardShortTable(sec, shortMeta) {
  const qs = sec.questions || [];
  if (!qs.length) return "";
  let blocks = shortMeta.blocks || [];
  if (!blocks.length) {
    blocks = [
      {
        questionNo: 2,
        boardHead: "Q.No.2: Write Short Answers to the following questions.",
        marksLine: shortMeta.marksLine || "",
        printed: qs.length,
      },
    ];
  }

  let html = `<div class="board-subjective-title">(Subjective Section)</div>`;
  html += `<table class="board-table board-short-table">`;
  let offset = 0;
  blocks.forEach((blk) => {
    const slice = qs.slice(offset, offset + (blk.printed || 0));
    offset += blk.printed || 0;
    const head = blk.boardHead || `Q.No.${blk.questionNo || 2}:`;
    const marks = blk.marksLine ? ` ${blk.marksLine}` : "";
    html += `<tr class="board-section-head"><td colspan="2"><strong>${escapeHtml(head)}</strong>${escapeHtml(marks)}</td></tr>`;
    slice.forEach((q, i) => {
      const roman = ROMAN[i] || String(i + 1);
      html += `<tr><td class="board-roman">${roman}.</td><td class="board-q-text">${q.questionText || ""}</td></tr>`;
    });
  });
  if (offset < qs.length) {
    qs.slice(offset).forEach((q, i) => {
      const roman = ROMAN[i] || String(i + 1);
      html += `<tr><td class="board-roman">${roman}.</td><td class="board-q-text">${q.questionText || ""}</td></tr>`;
    });
  }
  html += `</table>`;
  return html;
}

function boardLongTable(sec, longMeta, startNo) {
  const qs = sec.questions || [];
  if (!qs.length) return "";
  const head = longMeta.boardHead || longMeta.title || "SECTION — II (Long Questions)";
  const inst = longMeta.instruction || "";
  const marks = longMeta.marksLine || "";
  let html = `<table class="board-table board-long-table">`;
  html += `<tr class="board-section-head"><td colspan="2"><strong>${escapeHtml(head)}</strong> ${escapeHtml(inst)} <span class="board-marks">${escapeHtml(marks)}</span></td></tr>`;
  qs.forEach((q, i) => {
    const num = startNo + i;
    const text = String(q.questionText || "");
    html += `<tr><td class="board-num">${num}</td><td class="board-q-text"><strong>Q.No.${num}:</strong> ${text}</td></tr>`;
  });
  html += `</table>`;
  return html;
}

function buildBoardFormatPaperHtml(paper, meta) {
  const h = loadPaperHeader();
  const sectionMeta = meta.sectionMeta || paper.sectionMeta || {};
  const shortMeta = sectionMeta.short || {};
  const longMeta = sectionMeta.long || {};
  const longStart = longMeta.longStartNo || 2 + (shortMeta.blocks || []).length || 5;

  let html = `<div class="college-paper board-format-paper">`;
  html += boardPaperHeader(meta, paper, h);

  (paper.sections || []).forEach((sec) => {
    const key = sectionMetaKey(sec);
    if (key === "objective") {
      html += boardMcqTable(sec, sectionMeta.objective || {});
    } else if (key === "short") {
      html += boardShortTable(sec, shortMeta);
    } else if (key === "long") {
      html += boardLongTable(sec, longMeta, longStart);
    }
  });

  html += `</div>`;
  return html;
}

function boardFormatPrintStyles() {
  return `
    .board-format-paper { font-family: "Times New Roman", Times, serif; font-size: 13px; color: #000; }
    .board-college-name { text-align: center; font-weight: bold; font-size: 17px; margin-bottom: 2px; }
    .board-exam-title { text-align: center; font-size: 14px; font-weight: 600; margin-bottom: 8px; }
    .board-meta-table { width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 12px; }
    .board-meta-table td { border: 1px solid #000; padding: 5px 8px; width: 50%; vertical-align: top; }
    .board-student-line { display: flex; justify-content: space-between; font-size: 12px; margin: 8px 0 12px; }
    .board-subjective-title { text-align: center; font-weight: bold; margin: 14px 0 6px; }
    .board-table { width: 100%; border-collapse: collapse; margin-bottom: 14px; font-size: 12px; }
    .board-table td { border: 1px solid #000; padding: 5px 8px; vertical-align: top; }
    .board-section-head td { font-weight: bold; background: #f0f0f0; }
    .board-num { width: 36px; text-align: center; font-weight: bold; }
    .board-roman { width: 36px; text-align: center; font-weight: bold; text-transform: lowercase; }
    .board-qcell { line-height: 1.35; }
    .board-q-text { line-height: 1.4; }
    .board-opt-row { width: 100%; border-collapse: collapse; margin-top: 4px; }
    .board-opt-row td { border: 1px solid #ccc; padding: 3px 6px; font-size: 11px; }
    .board-marks { float: right; font-weight: bold; }
    @media print { .board-section-head td { background: #eee !important; -webkit-print-color-adjust: exact; } }
  `;
}

function buildPaperHtml(paper, meta, format) {
  if (format === "board") {
    return buildBoardFormatPaperHtml(paper, meta);
  }
  return buildCollegePaperHtml(paper, meta);
}

function paperPrintStyles(format) {
  const base = collegePaperPrintStyles();
  if (format === "board") {
    return base + boardFormatPrintStyles();
  }
  return base;
}

window.loadPaperHeader = loadPaperHeader;
window.savePaperHeader = savePaperHeader;
window.buildCollegePaperHtml = buildCollegePaperHtml;
window.buildBoardFormatPaperHtml = buildBoardFormatPaperHtml;
window.buildPaperHtml = buildPaperHtml;
window.paperPrintStyles = paperPrintStyles;
window.collegePaperPrintStyles = collegePaperPrintStyles;
window.programFromClass = programFromClass;
