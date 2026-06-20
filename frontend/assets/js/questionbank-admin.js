let cache = { boards: [], subjects: [], books: [], chapters: [] };
const FULL_BOOK_TITLE = "Full Book";
let activeUploadAbort = null;
let uploadInProgress = false;
const ADMIN_TAB_KEY = "qsb_admin_tab";

const EXPECTED_CHAPTERS = {
  "Physics 11": 11,
  "Physics 12": 11,
  "Chemistry 11": 11,
  "Chemistry 12": 16,
  "Biology 11": 14,
  "Biology 12": 15,
  "Computer 11": 10,
  "Computer 12": 14,
};

window.addEventListener("beforeunload", (e) => {
  if (uploadInProgress) {
    e.preventDefault();
    e.returnValue = "Upload/OCR in progress — leaving will cancel it.";
  }
});

function switchAdminTab(tab) {
  document.querySelectorAll("#adminTabs .nav-link").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tab);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("d-none", p.dataset.panel !== tab);
  });
  try {
    sessionStorage.setItem(ADMIN_TAB_KEY, tab);
  } catch {
    /* ignore */
  }
}

function restoreAdminTab() {
  try {
    const tab = sessionStorage.getItem(ADMIN_TAB_KEY);
    if (tab) switchAdminTab(tab);
  } catch {
    /* ignore */
  }
}

function listRow(label, onRemove) {
  return `<li class="admin-list-row"><span>${label}</span><button type="button" class="btn btn-sm btn-outline-danger admin-remove-btn" data-action="${onRemove}">Remove</button></li>`;
}

async function removeItem(url, label) {
  if (!confirm(`Remove ${label}?`)) return;
  try {
    await apiFetch(url, { method: "DELETE" });
    await loadAll();
    setStatus(`${label} removed.`);
  } catch (e) {
    setStatus(e.message, true);
  }
}

function wrapClearableInput(el) {
  if (!el || el.closest(".input-clear-wrap") || el.readOnly || el.disabled) return;
  const wrap = document.createElement("div");
  wrap.className = "input-clear-wrap";
  if (el.classList.contains("mb-2")) {
    wrap.classList.add("mb-2");
    el.classList.remove("mb-2");
  }
  el.parentNode.insertBefore(wrap, el);
  wrap.appendChild(el);
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "input-clear-btn";
  btn.setAttribute("aria-label", "Clear");
  btn.innerHTML = "×";
  btn.addEventListener("click", () => {
    if (el.tagName === "SELECT") el.selectedIndex = 0;
    else el.value = "";
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.focus();
  });
  wrap.appendChild(btn);
}

function initSetupClearButtons() {
  [
    "className",
    "examName",
    "examCode",
    "subjectName",
    "bookName",
    "chapterTitle",
    "patMcq",
    "patShort",
    "patLong",
    "importJsonText",
  ].forEach((id) => wrapClearableInput(document.getElementById(id)));
  wrapClearableInput(document.getElementById("chapterContent"));
}

function setStatus(msg, isError = false) {
  const el = document.getElementById("adminStatus");
  const text = isError && typeof toAdminMessage === "function" ? toAdminMessage(msg) : msg;
  el.textContent = text;
  el.className = "status-bar " + (isError ? "error" : "ok");
}

function adminAlert(err, prefix = "") {
  let msg;
  if (typeof err === "string") msg = err;
  else if (typeof toAdminMessage === "function") msg = toAdminMessage(err);
  else msg = err?.message || String(err);
  alert(prefix ? `${prefix}${msg}` : msg);
}

let adminUploadSeconds = 0;
let adminUploadTimerId = null;
let adminUploadPct = 0;
let adminUploadOcrTicker = null;

function friendlyUploadError(msg) {
  const m = String(msg || "");
  if (/quota|429|exceeded|rate limit/i.test(m)) {
    return (
      "Gemini daily limit reached (429). The PDF may already be saved — retry OCR or Fix Chapters " +
      "after updating GEMINI_API_KEY in backend/.env and restarting the server."
    );
  }
  if (/watermark|studyplusplus|educatedzone/i.test(m)) {
    return (
      "This PDF contains only watermarks. Upload an official Punjab textbook PDF " +
      "(ptb.punjab.gov.pk or elearn.punjab.gov.pk), then run Fix Chapters."
    );
  }
  if (/text corrupt|repetitive_garbage|repetitive/i.test(m)) {
    return "Book text could not be read. Upload a clean official PDF and run Fix Chapters.";
  }
  return m
    .replace(/^[^:]+:\s*Database save failed:\s*/i, "")
    .replace(/^[^:]+:\s*[^:]+:\s*/i, "")
    .trim();
}

function setAdminUploadPct(pct, stepText) {
  adminUploadPct = Math.min(100, Math.max(0, pct));
  const fill = document.getElementById("adminUploadProgressFill");
  const pctEl = document.getElementById("adminUploadPercent");
  const stepEl = document.getElementById("adminUploadStep");
  const track = document.querySelector("#adminUploadBar .progress-track");
  if (fill) fill.style.width = `${adminUploadPct}%`;
  if (pctEl) pctEl.textContent = `${adminUploadPct}%`;
  if (stepText && stepEl) stepEl.textContent = stepText;
  if (track) track.setAttribute("aria-valuenow", String(adminUploadPct));
}

function tickAdminUploadTimer() {
  adminUploadSeconds += 1;
  const m = Math.floor(adminUploadSeconds / 60);
  const s = adminUploadSeconds % 60;
  const el = document.getElementById("adminUploadTimer");
  if (el) el.textContent = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function showAdminUploadProgress(bookName, title = "Book upload") {
  const bar = document.getElementById("adminUploadBar");
  if (!bar) return;
  bar.classList.remove("is-error");
  bar.style.display = "block";
  document.getElementById("adminUploadMessage").textContent = `${title}: ${bookName}`;
  adminUploadSeconds = 0;
  adminUploadPct = 0;
  setAdminUploadPct(0, "Saving PDF to server…");
  tickAdminUploadTimer();
  if (adminUploadTimerId) clearInterval(adminUploadTimerId);
  adminUploadTimerId = setInterval(tickAdminUploadTimer, 1000);
  bar.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function startAdminOcrProgress() {
  if (adminUploadOcrTicker) clearInterval(adminUploadOcrTicker);
  adminUploadOcrTicker = setInterval(() => {
    if (adminUploadPct < 70) setAdminUploadPct(adminUploadPct + 1);
  }, 8000);
}

function stopAdminOcrProgress() {
  if (adminUploadOcrTicker) {
    clearInterval(adminUploadOcrTicker);
    adminUploadOcrTicker = null;
  }
}

function setAdminUploadError(bookName, msg) {
  const bar = document.getElementById("adminUploadBar");
  if (!bar) return;
  bar.classList.add("is-error");
  const friendly = friendlyUploadError(msg);
  const atOcr = adminUploadPct >= 35;
  document.getElementById("adminUploadMessage").textContent = atOcr
    ? `${bookName}: Step 2/4 fail (OCR / Gemini)`
    : `${bookName}: upload fail`;
  setAdminUploadPct(adminUploadPct || 15, friendly);
  const spinner = bar.querySelector(".admin-upload-spinner");
  if (spinner) spinner.style.display = "none";
}

function hideAdminUploadProgress(delayMs = 0) {
  stopAdminOcrProgress();
  const hide = () => {
    if (adminUploadTimerId) clearInterval(adminUploadTimerId);
    adminUploadTimerId = null;
    const bar = document.getElementById("adminUploadBar");
    if (bar) {
      bar.style.display = "none";
      bar.classList.remove("is-error");
      const spinner = bar.querySelector(".admin-upload-spinner");
      if (spinner) spinner.style.display = "";
    }
    adminUploadPct = 0;
  };
  if (delayMs > 0) setTimeout(hide, delayMs);
  else hide();
}

function showJson(data) {
  document.getElementById("jsonPreview").textContent = JSON.stringify(data, null, 2);
}

function fillSelect(id, items, valueKey = "id", labelFn) {
  const sel = document.getElementById(id);
  if (!sel) return;
  sel.innerHTML = '<option value="">— select —</option>';
  items.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = item[valueKey];
    opt.textContent = labelFn ? labelFn(item) : item.name || item.title;
    sel.appendChild(opt);
  });
}

function checkSetupState() {
  const alertEl = document.getElementById("setupAlert");
  const hint = document.getElementById("pdfBookHint");
  const noBoards = !(cache.boards || []).some((b) => b.code === "punjab");
  const noBooks = !(cache.books || []).length;

  if (noBoards || noBooks) {
    alertEl.classList.remove("d-none");
    alertEl.innerHTML =
      "<strong>Punjab Board setup required.</strong> Click <em>Load Punjab Board setup</em> above to create boards, classes, and books.";
  } else {
    alertEl.classList.add("d-none");
  }

  if (hint) {
    hint.textContent = noBooks
      ? "No books yet — run Load Punjab Board setup first."
      : `${cache.books.length} books ready. Use official watermark-free Punjab PDFs for best results.`;
  }
}

function fullBookChapter(bookId) {
  return (cache.chapters || []).find(
    (c) => c.bookId === bookId && c.title === FULL_BOOK_TITLE
  );
}

function bookChapterStats(bookId) {
  const named = (cache.chapters || []).filter(
    (c) => c.bookId === bookId && c.title !== FULL_BOOK_TITLE
  );
  const chapters = named.length
    ? named
    : (cache.chapters || []).filter((c) => c.bookId === bookId);
  const totalQ = chapters.reduce((s, c) => s + (c.questionCount || 0), 0);
  const withText = chapters.filter(
    (c) => c.textQuality === "ok" || ((c.charCount || 0) > 80 && c.textQuality !== "watermark_only")
  ).length;
  const corrupt = chapters.some((c) => c.textQuality === "watermark_only");
  const hasText = withText > 0 || chapters.some((c) => (c.charCount || 0) > 30);
  return { chapters, count: chapters.length, totalQ, hasText, withText, corrupt };
}

function formatChars(n) {
  if (!n) return "0";
  if (n >= 1000) return Math.round(n / 1000) + "k";
  return String(n);
}

function expectedChaptersForBook(book) {
  if (EXPECTED_CHAPTERS[book.name]) return EXPECTED_CHAPTERS[book.name];
  const lvl = book.classLevel || (book.name || "").match(/\b(1[12])\b/)?.[1];
  return lvl ? 11 : null;
}

function suggestUploadBookName() {
  const subIn = document.getElementById("uploadSubjectName");
  const nameIn = document.getElementById("uploadBookName");
  const classSel = document.getElementById("uploadClassLevel");
  if (!subIn || !nameIn || !classSel) return;
  const sub = subIn.value.trim();
  const lvl = classSel.value;
  if (sub && lvl && !nameIn.dataset.userEdited) {
    nameIn.value = `${sub} ${lvl}`;
  }
}

function fillUploadSubjects() {
  const list = document.getElementById("subjectNameSuggestions");
  if (list) {
    list.innerHTML = (cache.subjects || [])
      .map((s) => `<option value="${s.name}"></option>`)
      .join("");
  }
  suggestUploadBookName();
}

function bookIsUploaded(book) {
  const stats = bookChapterStats(book.id);
  return stats.hasText && !stats.corrupt;
}

function bookPdfPending(book) {
  if (bookIsUploaded(book)) return false;
  const fb = fullBookChapter(book.id);
  if (fb && (fb.charCount || 0) <= 30) return true;
  return !!book.hasPdfOnDisk;
}

function bookShowsInManageTable(book) {
  return bookIsUploaded(book) || bookPdfPending(book);
}

async function ensureBookRecord(classLevel, subjectName, bookName) {
  return apiFetch("/api/questionbank/admin/books/ensure", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      classLevel: parseInt(classLevel, 10),
      subjectName: subjectName.trim(),
      name: bookName.trim(),
    }),
  });
}

function bookStatusLabel(book) {
  const stats = bookChapterStats(book.id);
  const expected = expectedChaptersForBook(book);
  const ready = stats.hasText && !stats.corrupt && (!expected || stats.count >= expected);
  if (bookPdfPending(book)) {
    return '<span class="text-info">PDF saved — OCR pending</span>';
  }
  if (stats.corrupt) return '<span class="text-danger">Corrupt (watermark)</span>';
  if (ready) return `<span class="text-success">${stats.count} ch — ready</span>`;
  if (stats.hasText) return `<span class="text-warning">${stats.count} ch — Fix Chapters</span>`;
  return '<span class="text-muted">Not uploaded</span>';
}

function renderBooksManageTable() {
  const wrap = document.getElementById("booksManageTable");
  if (!wrap) return;
  if (!cache.books.length) {
    wrap.innerHTML = "<p class='text-muted small mb-0'>Run Load Punjab Board setup first.</p>";
    return;
  }
  const sorted = [...cache.books].filter(bookShowsInManageTable).sort((a, b) => {
    const la = a.classLevel || 0;
    const lb = b.classLevel || 0;
    if (la !== lb) return la - lb;
    const s = (a.subjectName || "").localeCompare(b.subjectName || "");
    return s !== 0 ? s : (a.name || "").localeCompare(b.name || "");
  });
  if (!sorted.length) {
    wrap.innerHTML =
      "<p class='text-muted small mb-0'>No uploaded books yet. Use the form above with an official Punjab PDF.</p>";
    return;
  }
  wrap.innerHTML = `
    <table class="table table-sm table-bordered align-middle mb-0 books-manage-table">
      <thead><tr>
        <th>Class</th><th>Subject</th><th>Book</th><th>Status</th><th>Actions</th>
      </tr></thead>
      <tbody>
        ${sorted
          .map((book) => {
            const stats = bookChapterStats(book.id);
            const hasText = stats.hasText;
            return `<tr data-book-id="${book.id}">
              <td>${book.classLevel ? book.classLevel + "th" : "—"}</td>
              <td>${book.subjectName || ""}</td>
              <td><strong>${book.name}</strong></td>
              <td>${bookStatusLabel(book)}</td>
              <td class="text-nowrap">
                <button type="button" class="btn btn-outline-warning btn-sm book-resplit-btn" data-book-id="${book.id}" data-book-name="${book.name}" ${hasText ? "" : "disabled"}>Fix</button>
                <button type="button" class="btn btn-outline-info btn-sm book-ocr-btn" data-book-id="${book.id}" data-book-name="${book.name}">OCR</button>
                <button type="button" class="btn btn-outline-danger btn-sm book-remove-btn" data-book-id="${book.id}" data-book-name="${book.name}">Clear</button>
              </td>
            </tr>`;
          })
          .join("")}
      </tbody>
    </table>`;

  wrap.querySelectorAll(".book-ocr-btn").forEach((btn) => {
    btn.onclick = () => runBookOcr(btn.dataset.bookId, btn.dataset.bookName, btn);
  });
  wrap.querySelectorAll(".book-resplit-btn").forEach((btn) => {
    btn.onclick = () => resplitBook(btn.dataset.bookId, btn.dataset.bookName, btn);
  });
  wrap.querySelectorAll(".book-remove-btn").forEach((btn) => {
    btn.onclick = async () => {
      const bookName = btn.dataset.bookName;
      if (
        !confirm(
          `Clear "${bookName}" completely?\n\nChapters, questions, and saved PDF on server will be removed.`
        )
      ) {
        return;
      }
      try {
        await apiFetch(`/api/questionbank/admin/books/${btn.dataset.bookId}`, {
          method: "DELETE",
        });
        await loadAll();
        renderBooksManageTable();
        setStatus(`${bookName} cleared from the database.`);
      } catch (e) {
        setStatus(e.message, true);
      }
    };
  });
}

function initUnifiedBookUpload() {
  const subIn = document.getElementById("uploadSubjectName");
  const classSel = document.getElementById("uploadClassLevel");
  const nameIn = document.getElementById("uploadBookName");
  const uploadBtn = document.getElementById("unifiedUploadBtn");
  if (!uploadBtn) return;

  subIn?.addEventListener("input", () => {
    if (nameIn) delete nameIn.dataset.userEdited;
    suggestUploadBookName();
  });
  classSel?.addEventListener("change", () => {
    if (nameIn) delete nameIn.dataset.userEdited;
    suggestUploadBookName();
  });
  nameIn?.addEventListener("input", () => {
    if (nameIn) nameIn.dataset.userEdited = "1";
  });

  uploadBtn.addEventListener("click", async () => {
    const classLevel = classSel?.value;
    const subjectName = subIn?.value?.trim();
    const bookName = nameIn?.value?.trim();
    const fileIn = document.getElementById("uploadPdfFile");
    const file = fileIn?.files?.[0];
    if (!subjectName) {
      setStatus("Enter subject name (e.g. Physics).", true);
      return;
    }
    if (!bookName) {
      setStatus("Enter book name (e.g. Physics 11).", true);
      return;
    }
    if (!file) {
      setStatus("Choose a PDF file.", true);
      return;
    }
    try {
      uploadBtn.disabled = true;
      setStatus(`Creating/finding book "${bookName}"…`);
      const book = await ensureBookRecord(classLevel, subjectName, bookName);
      try {
        sessionStorage.setItem(ADMIN_TAB_KEY, "chapters");
      } catch {
        /* ignore */
      }
      await uploadFullBookPdf(book.id, file, bookName, uploadBtn, fileIn, null);
      await loadAll();
    } catch (e) {
      setStatus(e.message, true);
      adminAlert(e);
    } finally {
      uploadBtn.disabled = false;
    }
  });
}

function renderBookUploadGrid() {
  renderBooksManageTable();
}

async function runBookOcr(bookId, bookName, btn) {
  try {
    if (btn) btn.disabled = true;
    showAdminUploadProgress(bookName, "OCR / text extract");
    setAdminUploadPct(20, "Extracting text from PDF (may take 10–30 minutes)…");
    startAdminOcrProgress();
    setStatus(`${bookName}: extracting text from saved PDF (OCR may take 10–30 min)…`);
    uploadInProgress = true;
    const result = await apiFetch(`/api/questionbank/admin/books/${bookId}/process-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    stopAdminOcrProgress();
    setAdminUploadPct(85, "Splitting chapters…");
    showJson(result);
    setStatus(`${bookName}: text extracted — now click Fix Chapters.`);
    await apiFetch(`/api/questionbank/admin/books/${bookId}/resplit-chapters`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    await loadChapters();
    renderBookUploadGrid();
    setAdminUploadPct(100, "Ready — teachers can create papers.");
    setStatus(`${bookName} ready — teachers can create papers now.`);
    hideAdminUploadProgress(4000);
  } catch (e) {
    setAdminUploadError(bookName, e.message);
    setStatus(friendlyUploadError(e.message), true);
    adminAlert(e, `${bookName}: `);
  } finally {
    uploadInProgress = false;
    if (btn) btn.disabled = false;
  }
}

async function resplitBook(bookId, bookName, btn) {
  try {
    if (btn) btn.disabled = true;
    setStatus(`Re-splitting ${bookName} into all chapters (e.g. 11 for Physics 11)...`);
    const result = await apiFetch(`/api/questionbank/admin/books/${bookId}/resplit-chapters`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    showJson(result);
    await loadChapters();
    renderBookUploadGrid();
    const n = (result.titles || []).length;
    setStatus(`${bookName}: now ${n} chapters — ready for Teacher Dashboard.`);
  } catch (e) {
    setStatus(e.message, true);
    adminAlert(e, `${bookName}: `);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function bulkGenerateBook(bookId, bookName, btn, skipConfirm = false, onlyMissing = false) {
  if (
    !skipConfirm &&
    !confirm(
      `Re-build all questions for ${bookName}?\n\nUses Gemini AI — 1–3 min per chapter. Keep this tab open.`
    )
  ) {
    return;
  }
  try {
    if (btn) btn.disabled = true;
    setStatus(
      `Building questions for ${bookName} — 1–3 min per chapter. Do NOT close this tab.`
    );
    const result = await apiFetch(
      `/api/questionbank/admin/books/${bookId}/generate-questions`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force: !onlyMissing, onlyMissing }),
      }
    );
    showJson(result);
    await loadChapters();
    renderBookUploadGrid();
    const failed = (result.chapters || []).filter((c) => c.error);
    if (failed.length) {
      setStatus(`${bookName}: some chapters could not be processed. Try again later.`, true);
      adminAlert("Some chapters could not be processed. Try again later.", `${bookName}: `);
    } else {
      setStatus(`${bookName}: ${result.totalGenerated || 0} questions in database.`);
    }
  } catch (e) {
    setStatus(e.message, true);
    adminAlert(e, `${bookName}: `);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function uploadFullBookPdf(bookId, file, bookName, btn, fileInput, cancelBtn) {
  uploadInProgress = true;
  let timer = null;
  try {
    btn.disabled = true;
    showAdminUploadProgress(bookName, "Step 1/4");
    setAdminUploadPct(12, "Saving PDF — keep this tab open.");
    setStatus(`Step 1/4: Saving ${bookName} PDF on server…`);
    const fd = new FormData();
    fd.append("bookId", String(bookId));
    fd.append("title", FULL_BOOK_TITLE);
    fd.append("file", file);
    fd.append("quick", "true");
    const controller = new AbortController();
    activeUploadAbort = controller;
    timer = setTimeout(() => controller.abort(), 1200000);
    let res;
    try {
      res = await fetch(`${API_BASE}/api/questionbank/admin/chapters/upload`, {
        method: "POST",
        body: fd,
        signal: controller.signal,
      });
    } catch (netErr) {
      if (netErr.name === "AbortError") {
        throw new Error(`${bookName}: timeout — try again. Do not refresh during upload.`);
      }
      throw new Error(
        `${bookName}: Cannot reach backend — run python app.py in backend folder.`
      );
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.success === false) {
      throw new Error(data.error || `Upload failed (${res.status})`);
    }
    let saved = data.data || {};
    showJson(saved);
    if (fileInput) fileInput.value = "";

    if (saved.needsOcr) {
      document.getElementById("adminUploadMessage").textContent = `Step 2/4: ${bookName}`;
      setAdminUploadPct(35, "PDF saved — OCR in progress (10–30 min). Keep this tab open.");
      startAdminOcrProgress();
      setStatus(
        `Step 2/4: PDF saved. OCR running for ${bookName} — 10–30 min. DO NOT refresh or close this tab!`
      );
      const ocrRes = await fetch(
        `${API_BASE}/api/questionbank/admin/books/${bookId}/process-pdf`,
        { method: "POST", signal: controller.signal }
      );
      const ocrData = await ocrRes.json().catch(() => ({}));
      if (!ocrRes.ok || ocrData.success === false) {
        throw new Error(
          ocrData.error ||
            "OCR failed — set GEMINI_API_KEY in backend/.env then click Fix Chapters."
        );
      }
      stopAdminOcrProgress();
      saved = { ...saved, ...ocrData.data, chaptersSplit: (ocrData.data?.split?.titles || []).length };
      showJson(ocrData.data);
    } else {
      document.getElementById("adminUploadMessage").textContent = `Step 2/4: ${bookName}`;
      setAdminUploadPct(45, "Text extracted from PDF.");
      setStatus(`Step 2/4: Text extracted for ${bookName}.`);
    }

    document.getElementById("adminUploadMessage").textContent = `Step 3/4: ${bookName}`;
    setAdminUploadPct(78, "Splitting into chapters…");
    setStatus(`Step 3/4: Splitting ${bookName} into all chapters…`);
    await apiFetch(`/api/questionbank/admin/books/${bookId}/resplit-chapters`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    await loadChapters();
    renderBookUploadGrid();

    switchAdminTab("chapters");
    document.getElementById("adminUploadMessage").textContent = `Step 4/4: ${bookName}`;
    const chN = saved.chaptersSplit || "?";
    setAdminUploadPct(100, `Complete — ${chN} chapters ready for teachers.`);
    setStatus(
      `${bookName} ready — ${chN} chapters. Teacher can create papers now (no Re-build needed).`
    );
    hideAdminUploadProgress(5000);
  } catch (e) {
    stopAdminOcrProgress();
    setAdminUploadError(bookName, e.message);
    setStatus(friendlyUploadError(e.message), true);
    adminAlert(e, `${bookName}: `);
  } finally {
    clearTimeout(timer);
    activeUploadAbort = null;
    uploadInProgress = false;
    if (cancelBtn) cancelBtn.style.display = "none";
    btn.disabled = false;
  }
}

async function loadAll() {
  setStatus("Loading from database...");
  const meta = await apiFetch("/api/questionbank/metadata");
  cache.boards = meta.boards || [];
  cache.subjects = meta.subjects || [];
  cache.examTypes = meta.examTypes || [];
  cache.patterns = meta.patterns || [];

  const books = await apiFetch("/api/questionbank/admin/books");
  const classes = await apiFetch("/api/questionbank/admin/classes");
  cache.books = books;
  cache.classes = classes;

  fillSelect("classBoardId", cache.boards, "id", (b) => b.name);
  fillSelect("patternBoardId", cache.boards, "id", (b) => b.name);
  fillSelect("patternExamId", cache.examTypes, "id", (e) => e.name);
  fillSelect("bookSubjectId", cache.subjects, "id", (s) => s.name);
  fillSelect("chapterBookId", cache.books, "id", (b) => `${b.name} (${b.subjectName})`);
  fillUploadSubjects();

  document.getElementById("boardList").innerHTML = cache.boards
    .map((b) => `<li>${b.name} <code>${b.code}</code></li>`)
    .join("");
  document.getElementById("classList").innerHTML = (classes || [])
    .map((c) =>
      listRow(`${c.name}${c.boardName ? " — " + c.boardName : ""}`, `class:${c.id}`)
    )
    .join("");
  document.getElementById("examList").innerHTML = (cache.examTypes || [])
    .map((e) => listRow(`${e.name} <code>${e.code}</code>`, `exam:${e.id}`))
    .join("");
  document.getElementById("subjectList").innerHTML = cache.subjects
    .map((s) => listRow(s.name, `subject:${s.id}`))
    .join("");
  document.getElementById("bookList").innerHTML = books
    .map((b) => listRow(`${b.name} — ${b.subjectName}`, `book:${b.id}`))
    .join("");
  document.getElementById("patternList").innerHTML = (cache.patterns || [])
    .map((p) =>
      listRow(
        `${p.boardCode}/${p.examCode}: MCQ ${p.mcqCount}, Short ${p.shortCount}, Long ${p.longCount}`,
        `pattern:${p.id}`
      )
    )
    .join("");

  document.querySelectorAll(".admin-remove-btn").forEach((btn) => {
    btn.onclick = () => {
      const [kind, id] = (btn.dataset.action || "").split(":");
      const paths = {
        class: `/api/questionbank/admin/classes/${id}`,
        exam: `/api/questionbank/admin/exam-types/${id}`,
        subject: `/api/questionbank/admin/subjects/${id}`,
        book: `/api/questionbank/admin/books/${id}`,
        pattern: `/api/questionbank/admin/patterns/${id}`,
      };
      if (paths[kind]) removeItem(paths[kind], kind);
    };
  });

  await loadChapters();
  checkSetupState();
  await checkGeminiStatus();
  await renderApiUsage();
  setStatus(
    `Ready — ${cache.boards.length} boards, ${(cache.classes || []).length} classes, ${cache.books.length} books.`
  );
}

async function renderApiUsage() {
  const alertEl = document.getElementById("setupAlert");
  if (!alertEl) return;
  try {
    const usage = await apiFetch("/api/questionbank/gemini-usage");
    if (!usage.apiKeyConfigured) {
      alertEl.classList.remove("d-none");
      alertEl.className = "alert alert-secondary mb-3";
      alertEl.innerHTML =
        "<strong>AI Service:</strong> Not configured. Set your API key in <code>backend/.env</code> (server only).";
      return;
    }
    const note = document.createElement("div");
    note.className = "small text-muted mb-2";
    note.id = "apiUsageNote";
    note.textContent = `AI requests today: ${usage.used} / ${usage.limit} (${usage.remaining} remaining)`;
    const existing = document.getElementById("apiUsageNote");
    if (existing) existing.replaceWith(note);
    else alertEl.parentNode?.insertBefore(note, alertEl);
  } catch {
    /* ignore */
  }
}

async function checkGeminiStatus() {
  const alertEl = document.getElementById("setupAlert");
  if (!alertEl) return;
  try {
    const cached = sessionStorage.getItem("geminiCheck");
    if (cached) {
      const g = JSON.parse(cached);
      if (g.ts && Date.now() - g.ts < 600000 && g.data) {
        if (!g.data.ok || g.data.demoFallback) showGeminiAlert(alertEl, g.data);
        return;
      }
    }
    const g = await apiFetch("/api/questionbank/gemini-check");
    sessionStorage.setItem("geminiCheck", JSON.stringify({ ts: Date.now(), data: g }));
    if (g.ok && !g.demoFallback) return;
    showGeminiAlert(alertEl, g);
  } catch {
    /* backend offline — loadAll already shows error */
  }
}

function showGeminiAlert(alertEl, g) {
  if (g.ok && g.demoFallback) {
    alertEl.classList.remove("d-none");
    alertEl.className = "alert alert-warning mb-3";
    alertEl.innerHTML = `<strong>Notice:</strong> ${g.message || "Using saved book content until quota resets."}`;
    return;
  }
  if (!g.ok) {
    alertEl.classList.remove("d-none");
    alertEl.className = "alert alert-warning mb-3";
    alertEl.innerHTML = `<strong>AI Service:</strong> ${g.message || "Please try again later."}`;
  }
}

function selectedChapterBookId() {
  const sel = document.getElementById("chapterBookId");
  if (!sel || !sel.value) return cache.books[0]?.id || null;
  return parseInt(sel.value, 10) || null;
}

function bookLabel(bookId) {
  const b = (cache.books || []).find((x) => x.id === bookId);
  return b ? b.name : `Book #${bookId}`;
}

function renderChapterList() {
  const listEl = document.getElementById("chapterList");
  if (!listEl) return;
  const bookId = selectedChapterBookId();
  if (!bookId) {
    listEl.innerHTML = "<p class='text-muted small mb-0'>Select a book above.</p>";
    return;
  }
  const chapters = (cache.chapters || [])
    .filter((c) => c.bookId === bookId && c.title !== FULL_BOOK_TITLE)
    .sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0) || a.title.localeCompare(b.title));
  if (!chapters.length) {
    listEl.innerHTML = `<p class="text-muted small mb-0">No chapters yet for <strong>${bookLabel(bookId)}</strong>. Upload a PDF and run <strong>Fix Chapters</strong>.</p>`;
    return;
  }
  listEl.innerHTML = `
    <table class="table table-sm table-bordered align-middle mb-0 chapter-mini-table">
      <thead><tr><th>Chapter</th><th>Status</th></tr></thead>
      <tbody>
        ${chapters
          .map((c) => {
            const bad = c.textQuality === "watermark_only";
            const ok = c.textQuality === "ok" || (c.charCount || 0) > 80;
            const status = bad
              ? '<span class="badge bg-danger">Review PDF</span>'
              : ok
                ? '<span class="badge bg-success">Ready</span>'
                : '<span class="badge bg-secondary">Pending</span>';
            return `<tr><td>${c.title}</td><td>${status}</td></tr>`;
          })
          .join("")}
      </tbody>
    </table>`;
}

async function loadChapters() {
  const chapters = await apiFetch("/api/questionbank/admin/chapters");
  cache.chapters = chapters;
  const bookName = (c) => {
    const b = cache.books.find((x) => x.id === c.bookId);
    return b ? `${b.name}: ${c.title}` : c.title;
  };
  fillSelect("genChapterId", chapters, "id", (c) => `${bookName(c)} (${c.questionCount} Q)`);
  fillSelect("viewChapterId", chapters, "id", bookName);
  fillSelect("importChapterId", chapters, "id", bookName);
  renderChapterList();
  renderBookUploadGrid();
}

document.querySelectorAll("#adminTabs .nav-link").forEach((btn) => {
  btn.onclick = () => switchAdminTab(btn.dataset.tab);
});

const addBoardBtn = document.getElementById("addBoardBtn");
if (addBoardBtn) {
  addBoardBtn.onclick = async () => {
    try {
      const data = await apiFetch("/api/questionbank/admin/boards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: document.getElementById("boardName").value,
          code: document.getElementById("boardCode").value,
        }),
      });
      showJson(data);
      await loadAll();
    } catch (e) {
      setStatus(e.message, true);
    }
  };
}

document.getElementById("addClassBtn").onclick = async () => {
  try {
    const data = await apiFetch("/api/questionbank/admin/classes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.getElementById("className").value,
        boardId: parseInt(document.getElementById("classBoardId").value, 10) || null,
      }),
    });
    showJson(data);
    document.getElementById("className").value = "";
    await loadAll();
  } catch (e) {
    setStatus(e.message, true);
  }
};

document.getElementById("addExamBtn").onclick = async () => {
  try {
    const data = await apiFetch("/api/questionbank/admin/exam-types", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.getElementById("examName").value,
        code: document.getElementById("examCode").value,
      }),
    });
    showJson(data);
    document.getElementById("examName").value = "";
    document.getElementById("examCode").value = "";
    await loadAll();
  } catch (e) {
    setStatus(e.message, true);
  }
};

document.getElementById("addSubjectBtn").onclick = async () => {
  try {
    const data = await apiFetch("/api/questionbank/admin/subjects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: document.getElementById("subjectName").value }),
    });
    showJson(data);
    document.getElementById("subjectName").value = "";
    await loadAll();
  } catch (e) {
    setStatus(e.message, true);
  }
};

document.getElementById("addBookBtn").onclick = async () => {
  try {
    const data = await apiFetch("/api/questionbank/admin/books", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.getElementById("bookName").value,
        subjectId: parseInt(document.getElementById("bookSubjectId").value, 10),
      }),
    });
    showJson(data);
    document.getElementById("bookName").value = "";
    await loadAll();
  } catch (e) {
    setStatus(e.message, true);
  }
};

document.getElementById("addPatternBtn").onclick = async () => {
  try {
    const data = await apiFetch("/api/questionbank/admin/patterns", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        boardId: parseInt(document.getElementById("patternBoardId").value, 10),
        examTypeId: parseInt(document.getElementById("patternExamId").value, 10),
        mcqCount: parseInt(document.getElementById("patMcq").value, 10),
        shortCount: parseInt(document.getElementById("patShort").value, 10),
        longCount: parseInt(document.getElementById("patLong").value, 10),
      }),
    });
    showJson(data);
    await loadAll();
  } catch (e) {
    setStatus(e.message, true);
  }
};

document.getElementById("cancelChapterBtn").onclick = () => {
  document.getElementById("chapterTitle").value = "";
  document.getElementById("chapterContent").value = "";
  setStatus("Form cleared.");
};

document.getElementById("saveChapterBtn").onclick = async () => {
  try {
    setStatus("Saving chapter...");
    const data = await apiFetch("/api/questionbank/admin/chapters", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        bookId: parseInt(document.getElementById("chapterBookId").value, 10),
        title: document.getElementById("chapterTitle").value,
        contentText: document.getElementById("chapterContent").value,
      }),
    });
    showJson(data);
    document.getElementById("chapterContent").value = "";
    await loadChapters();
    setStatus("Chapter saved in database.");
  } catch (e) {
    setStatus(e.message, true);
  }
};

document.getElementById("generateQuestionsBtn").onclick = async () => {
  const chapterId = document.getElementById("genChapterId").value;
  if (!chapterId) {
    setStatus("Select a chapter first.", true);
    return;
  }
  try {
    setStatus("Generating questions (may take 30–60 sec)...");
    const data = await apiFetch(
      `/api/questionbank/admin/chapters/${chapterId}/generate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mcqCount: parseInt(document.getElementById("genMcq").value, 10),
          shortCount: parseInt(document.getElementById("genShort").value, 10),
          longCount: parseInt(document.getElementById("genLong").value, 10),
          useN8n: document.getElementById("useN8n").checked,
        }),
      }
    );
    showJson(data);
    await loadChapters();
    setStatus(
      data.mode === "n8n"
        ? "Sent to n8n. Questions will appear when webhook returns."
        : `Saved ${data.generated} questions to database.`
    );
  } catch (e) {
    setStatus(e.message, true);
  }
};

async function loadQuestions() {
  const chapterId = document.getElementById("viewChapterId").value;
  if (!chapterId) return;
  const rows = await apiFetch(`/api/questionbank/questions?chapterId=${chapterId}`);
  showJson(rows);
  document.getElementById("questionsTable").innerHTML = rows
    .map(
      (q, i) =>
        `<div class="border-bottom py-2"><strong>${i + 1}. [${q.questionType}]</strong> ${q.questionText}<br><span class="text-muted">Ans: ${q.correctAnswer}</span></div>`
    )
    .join("") || "<p>No questions yet.</p>";
}

document.getElementById("refreshQuestionsBtn").onclick = () =>
  loadQuestions().catch((e) => setStatus(e.message, true));

document.getElementById("punjabSetupBtn").onclick = async () => {
  const btn = document.getElementById("punjabSetupBtn");
  try {
    btn.disabled = true;
    setStatus("Loading Punjab Board (English, Physics, Chemistry, Biology, Computer)...");
    const res = await fetch(`${API_BASE}/api/questionbank/setup-punjab`, { method: "POST" });
    const json = await res.json().catch(() => ({}));
    if (!res.ok || json.success === false) {
      throw new Error(json.error || `Setup failed (${res.status})`);
    }
    showJson(json.data || json);
    await loadAll();
    const rem = json.data && json.data.removedLegacy;
    const remTxt = rem
      ? ` Cleaned: ${(rem.boards || []).join(", ") || "—"} boards, ${(rem.books || []).join(", ") || "—"} old books.`
      : "";
    setStatus((json.message || "Punjab Board ready") + remTxt);
  } catch (e) {
    setStatus(toAdminMessage(e), true);
    adminAlert(e);
  } finally {
    btn.disabled = false;
  }
};

document.getElementById("importJsonBtn").onclick = async () => {
  const chapterId = document.getElementById("importChapterId").value;
  if (!chapterId) {
    setStatus("Select chapter for import.", true);
    return;
  }
  let payload;
  try {
    payload = JSON.parse(document.getElementById("importJsonText").value.trim());
  } catch {
    setStatus("Invalid JSON. Use { \"questions\": [ ... ] }", true);
    return;
  }
  const questions = payload.questions || payload;
  if (!Array.isArray(questions) || !questions.length) {
    setStatus("JSON must contain a questions array.", true);
    return;
  }
  try {
    setStatus("Importing...");
    const data = await apiFetch("/api/questionbank/admin/import-questions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chapterId: parseInt(chapterId, 10), questions }),
    });
    showJson(data);
    await loadChapters();
    setStatus(`Imported ${data.imported} questions.`);
  } catch (e) {
    setStatus(e.message, true);
  }
};

initSetupClearButtons();
initUnifiedBookUpload();
document.getElementById("chapterBookId")?.addEventListener("change", renderChapterList);
restoreAdminTab();

function bootQuestionBankAdmin() {
  loadAll().catch((e) => {
    const msg =
      typeof toAdminMessage === "function"
        ? toAdminMessage(e)
        : "Unable to load data. Please try again.";
    setStatus(msg, true);
    const alertEl = document.getElementById("setupAlert");
    if (alertEl) {
      alertEl.classList.remove("d-none");
      alertEl.className = "alert alert-warning mb-3";
      alertEl.textContent = msg;
    }
  });
}
