let cache = { boards: [], subjects: [], books: [], chapters: [] };

function setStatus(msg, isError = false) {
  const el = document.getElementById("adminStatus");
  el.textContent = msg;
  el.className = "status-bar " + (isError ? "error" : "ok");
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

  document.getElementById("boardList").innerHTML = cache.boards
    .map((b) => `<li>${b.name} <code>${b.code}</code></li>`)
    .join("");
  document.getElementById("classList").innerHTML = (classes || [])
    .map((c) => `<li>${c.name}${c.boardName ? " — " + c.boardName : ""}</li>`)
    .join("");
  document.getElementById("examList").innerHTML = (cache.examTypes || [])
    .map((e) => `<li>${e.name} <code>${e.code}</code></li>`)
    .join("");
  document.getElementById("subjectList").innerHTML = cache.subjects
    .map((s) => `<li>${s.name}</li>`)
    .join("");
  document.getElementById("bookList").innerHTML = books
    .map((b) => `<li>${b.name} — ${b.subjectName}</li>`)
    .join("");
  document.getElementById("patternList").innerHTML = (cache.patterns || [])
    .map(
      (p) =>
        `<li>${p.boardCode}/${p.examCode}: MCQ ${p.mcqCount}, Short ${p.shortCount}, Long ${p.longCount}</li>`
    )
    .join("");

  await loadChapters();
  setStatus("Connected to backend. Data loaded.");
}

async function loadChapters() {
  const chapters = await apiFetch("/api/questionbank/admin/chapters");
  cache.chapters = chapters;
  fillSelect("genChapterId", chapters, "id", (c) => `${c.title} (${c.questionCount} Q)`);
  fillSelect("viewChapterId", chapters, "id", (c) => c.title);
  fillSelect("importChapterId", chapters, "id", (c) => c.title);
  document.getElementById("chapterList").innerHTML = chapters
    .map(
      (c) =>
        `<li><strong>${c.title}</strong> — ${c.questionCount} questions<br><span class="text-muted">${c.contentPreview || "no content"}</span></li>`
    )
    .join("");
}

document.querySelectorAll("#adminTabs .nav-link").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll("#adminTabs .nav-link").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const tab = btn.dataset.tab;
    document.querySelectorAll(".tab-panel").forEach((p) => {
      p.classList.toggle("d-none", p.dataset.panel !== tab);
    });
  };
});

document.getElementById("addBoardBtn").onclick = async () => {
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

document.getElementById("seedSampleBtn").onclick = async () => {
  try {
    setStatus("Loading sample data...");
    const data = await apiFetch("/api/questionbank/seed", { method: "POST" });
    showJson(data);
    await loadAll();
    setStatus(data.message || "Sample data ready.");
  } catch (e) {
    setStatus(e.message, true);
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

loadAll().catch((e) => setStatus(e.message + " — Is backend running on port 3000?", true));
