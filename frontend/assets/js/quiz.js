const inputText = document.getElementById("inputText");
const outputBox = document.getElementById("outputBox");
const mcqLimit = document.getElementById("mcqLimit");
const importBtn = document.getElementById("importBtn");
const fileInput = document.getElementById("fileInput");
const generateBtn = document.getElementById("generateBtn");

let quizQuestions = [];
let currentIndex = 0;
let score = 0;

/* ========= FILE IMPORT ========= */
importBtn.onclick = () => fileInput.click();

fileInput.onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const fileName = file.name.toLowerCase();

  // ===== TXT FILE =====
  if (fileName.endsWith(".txt")) {
    const text = await file.text();
    inputText.value = text;
  }

  // ===== PDF FILE =====
  else if (fileName.endsWith(".pdf")) {
    const reader = new FileReader();

    reader.onload = async function () {
      const typedarray = new Uint8Array(this.result);
      const pdf = await pdfjsLib.getDocument(typedarray).promise;

      let fullText = "";

      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const content = await page.getTextContent();

        content.items.forEach(item => {
          fullText += item.str + " ";
        });
      }

      inputText.value = fullText;
    };

    reader.readAsArrayBuffer(file);
  }

  // ===== DOCX FILE =====
  else if (fileName.endsWith(".docx")) {
    const reader = new FileReader();

    reader.onload = async function () {
      const result = await mammoth.extractRawText({
        arrayBuffer: reader.result
      });

      inputText.value = result.value;
    };

    reader.readAsArrayBuffer(file);
  }

  else {
    alert("❌ Unsupported file type");
  }
};

/* ========= GENERATE QUIZ ========= */
generateBtn.onclick = () => {
  if (!requireModuleAccess("quiz", "Quiz Generator")) return;
  if (!inputText.value.trim()) {
    alert("Please add text first");
    return;
  }

  startQuiz();
};

/* ========= CALL BACKEND ========= */
function startQuiz() {
  outputBox.innerHTML = "⏳ Generating quiz... Please wait";

  fetch(`${API_BASE}/quiz/generate`, moduleHistoryFetchOpts({
    text: inputText.value,
    limit: parseInt(mcqLimit.value)
  }))
    .then(res => res.json())
    .then(data => {
      quizQuestions = data.questions || [];

      if (quizQuestions.length === 0) {
        outputBox.innerHTML = "❌ No questions generated";
        return;
      }

      recordModuleUse("quiz");
      currentIndex = 0;
      score = 0;
      showQuestion();
      refreshQuizHistory();
    })
    .catch(err => {
      console.error(err);
      outputBox.innerHTML = "❌ Backend error (Flask not running)";
    });
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/"/g, "&quot;");
}

/* ========= SHOW QUESTION ========= */
function showQuestion() {
  const q = quizQuestions[currentIndex];
  const labels = ["A", "B", "C", "D"];

  const optionsHTML = q.options
    .map(
      (opt, idx) => `
    <button type="button" class="btn btn-outline-primary option-btn"
      data-idx="${idx}" onclick="checkAnswer(${idx}, this)">
      <strong>${labels[idx]})</strong> ${escapeHtml(opt)}
    </button>`
    )
    .join("");

  outputBox.innerHTML = `
    <div class="quiz-card quiz-wrapper output-box quiz-mode">
      <div class="quiz-progress">Question ${currentIndex + 1} of ${quizQuestions.length}</div>
      <div class="quiz-question">${escapeHtml(q.question)}</div>
      <div class="quiz-options">${optionsHTML}</div>
      <div id="result" class="fw-bold" style="min-height:1.5rem"></div>
      <button type="button" id="nextBtn" class="btn btn-success mt-1 d-none" onclick="nextQuestion()">
        Next Question →
      </button>
    </div>
  `;
}

function checkAnswer(optionIndex, btn) {
  const q = quizQuestions[currentIndex];
  const selected = q.options[optionIndex];
  const correct = q.answer;
  const resultDiv = document.getElementById("result");

  const allBtns = document.querySelectorAll(".option-btn");

  // disable all buttons
  allBtns.forEach(b => {
    b.disabled = true;
    b.classList.remove("btn-outline-primary");
  });

  if (selected.trim().toLowerCase() === correct.trim().toLowerCase()) {
    btn.classList.add("btn-success");
    resultDiv.innerHTML = `✅ Correct — <span class="text-success">${escapeHtml(correct)}</span>`;
    resultDiv.style.color = "green";
    score++;
  } else {
    btn.classList.add("btn-danger");

    allBtns.forEach(b => {
      const idx = parseInt(b.dataset.idx, 10);
      if (q.options[idx].trim().toLowerCase() === correct.trim().toLowerCase()) {
        b.classList.add("btn-success");
      }
    });

    resultDiv.innerHTML = `❌ Wrong — correct answer: <strong>${escapeHtml(correct)}</strong>`;
    resultDiv.style.color = "#c0392b";
  }

  document.getElementById("nextBtn").classList.remove("d-none");
}
/* ========= NEXT QUESTION ========= */
function nextQuestion() {
  currentIndex++;

  if (currentIndex < quizQuestions.length) {
    showQuestion();
  } else {
    outputBox.innerHTML = `
      <div class="quiz-card text-center">
        <h3>🎉 Quiz Completed</h3>
        <p>Your Score: <strong>${score} / ${quizQuestions.length}</strong></p>
      </div>
    `;
  }
}

function loadQuizFromHistory(row) {
  const qs = (row.result || {}).questions || [];
  if (qs.length) {
    quizQuestions = qs;
    currentIndex = 0;
    score = 0;
    showQuestion();
  }
}

function refreshQuizHistory() {}

bootHistoryFromUrl((id) => `/api/records/${id}`, loadQuizFromHistory);