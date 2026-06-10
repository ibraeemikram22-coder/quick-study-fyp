let metaCache = null;
let selectedBook = null;

async function fetchBooks(subject) {
  return apiFetch(`/api/questionbank/books?subject=${encodeURIComponent(subject)}`);
}

async function fetchChapters(book, subject) {
  return apiFetch(
    `/api/questionbank/chapters?book=${encodeURIComponent(book)}&subject=${encodeURIComponent(subject)}`
  );
}

async function loadMetadata() {
  metaCache = await apiFetch("/api/questionbank/metadata");
  const classSel = document.getElementById("class");
  const boardSel = document.getElementById("board");
  const examSel = document.getElementById("exam");
  const subjectSel = document.getElementById("subject");

  classSel.innerHTML = '<option value="">Select Class</option>';
  (metaCache.classes || []).forEach((c) => {
    classSel.innerHTML += `<option value="${c.id}">${c.name}</option>`;
  });

  boardSel.innerHTML = '<option value="">Select Board</option>';
  (metaCache.boards || []).forEach((b) => {
    boardSel.innerHTML += `<option value="${b.id}" data-code="${b.code}">${b.name}</option>`;
  });

  examSel.innerHTML = '<option value="">Select Exam</option>';
  (metaCache.examTypes || []).forEach((e) => {
    examSel.innerHTML += `<option value="${e.id}" data-code="${e.code}">${e.name}</option>`;
  });

  subjectSel.innerHTML = '<option value="">Select Subject</option>';
  (metaCache.subjects || []).forEach((s) => {
    subjectSel.innerHTML += `<option value="${s.name}">${s.name}</option>`;
  });
}

document.getElementById("subject").onchange = async function () {
  const subject = this.value;
  if (!subject) return;
  const books = await fetchBooks(subject);
  let html = "";
  books.forEach((b) => {
    html += `<button type="button" class="select-btn" data-book="${b.name}">${b.name}</button>`;
  });
  document.getElementById("bookContainer").innerHTML =
    html || '<p class="text-muted">No books. Add in Admin panel.</p>';
  document.querySelectorAll("#bookContainer .select-btn").forEach((btn) => {
    btn.onclick = () => loadChapters(btn.dataset.book);
  });
};

async function loadChapters(book) {
  selectedBook = book;
  const subject = document.getElementById("subject").value;
  const chapters = await fetchChapters(book, subject);
  let html = "";
  chapters.forEach((c) => {
    html += `<div><input type="checkbox" class="ch" value="${c.title}"> ${c.title} <small class="text-muted">(${c.questionCount} Q)</small></div>`;
  });
  document.getElementById("chapterContainer").innerHTML = html;

  const boardId = document.getElementById("board").value;
  const examId = document.getElementById("exam").value;
  if (boardId && examId) {
    try {
      const pattern = await apiFetch(
        `/api/questionbank/pattern?boardId=${boardId}&examTypeId=${examId}`
      );
      document.getElementById("patternBox").textContent = JSON.stringify(
        {
          MCQs: pattern.mcqCount,
          Short: pattern.shortCount,
          Long: pattern.longCount,
          Marks: pattern.totalMarks,
          Time: pattern.duration,
        },
        null,
        2
      );
    } catch {
      document.getElementById("patternBox").textContent = "Pattern not set in admin.";
    }
  }
}

function selectAll() {
  document.querySelectorAll(".ch").forEach((c) => (c.checked = true));
}

async function generatePaper() {
  const subject = document.getElementById("subject").value;
  const boardId = parseInt(document.getElementById("board").value, 10);
  const examTypeId = parseInt(document.getElementById("exam").value, 10);
  const chapters = [];
  document.querySelectorAll(".ch:checked").forEach((c) => chapters.push(c.value));

  if (!subject || !selectedBook || !chapters.length || !boardId || !examTypeId) {
    alert("Select class, board, exam, subject, book, and at least one chapter.");
    return;
  }

  try {
    const paper = await apiFetch("/api/questionbank/papers/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject,
        book: selectedBook,
        chapters,
        boardId,
        examTypeId,
        difficulty: document.getElementById("difficulty").value,
      }),
    });

    let html = `<h4>${paper.title}</h4><p>Marks: ${paper.marks} | Time: ${paper.duration}</p><hr>`;
    (paper.sections || []).forEach((sec) => {
      html += `<h5>${sec.title}</h5>`;
      (sec.questions || []).forEach((q, i) => {
        html += `<p><strong>Q${i + 1}.</strong> ${q.questionText}</p>`;
        if (q.options && q.options.length) {
          html += "<ul>" + q.options.map((o) => `<li>${o}</li>`).join("") + "</ul>";
        }
      });
      html += "<hr>";
    });

    document.getElementById("outputBox").style.display = "block";
    document.getElementById("output").innerHTML = html;
    window._lastPaper = paper;
  } catch (e) {
    alert(e.message);
  }
}

window.selectAll = selectAll;
window.generatePaper = generatePaper;
window.loadChapters = loadChapters;

loadMetadata().catch(() => {
  document.getElementById("bookContainer").innerHTML =
    "<p class='text-danger'>Backend not running. Start: python app.py in backend folder.</p>";
});
