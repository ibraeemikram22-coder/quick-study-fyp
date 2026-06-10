// ================= FLOW CONTROL =================

const classSelect = document.getElementById("classSelect");
const boardSelect = document.getElementById("boardSelect");
const examType = document.getElementById("examType");
const subjectSelect = document.getElementById("subjectSelect");

// STEP FLOW
classSelect.addEventListener("change", () => {
    if (classSelect.value) boardSelect.disabled = false;
});

boardSelect.addEventListener("change", () => {
    if (boardSelect.value) examType.disabled = false;
    loadPattern(boardSelect.value);
});

examType.addEventListener("change", () => {
    if (examType.value) subjectSelect.disabled = false;
});

subjectSelect.addEventListener("change", () => {
    updateBook();
    loadChapters(subjectSelect.value);
});

// ================= BOOK =================

function updateBook() {
    const cls = classSelect.value;
    const sub = subjectSelect.value;

    document.getElementById("bookBox").innerText =
        `${sub || ""} ${cls || ""} PTB Book`;
}

// ================= CHAPTERS =================

const chapterData = {
    Physics: ["Chapter 1", "Chapter 2", "Chapter 3", "Chapter 4"],
    Chemistry: ["Chapter 1", "Chapter 2", "Chapter 3"],
    Math: ["Chapter 1", "Chapter 2"],
    English: ["Lesson 1", "Lesson 2"],
    Urdu: ["Nazm 1", "Nazm 2"]
};

function loadChapters(subject) {

    const list = document.getElementById("chapterList");
    list.innerHTML = "";

    if (!chapterData[subject]) return;

    chapterData[subject].forEach((ch, i) => {

        list.innerHTML += `
        <div class="form-check">
            <input type="checkbox" class="form-check-input chapter" value="${ch}">
            <label class="form-check-label">${ch}</label>
        </div>`;
    });
}

// ================= PATTERN =================

const patterns = {
    "Gujranwala Board": {
        MCQs: 20,
        "Short Questions": 8,
        "Long Questions": 3
    },
    "FBISE": {
        MCQs: 17,
        "Short Questions": 10,
        "Long Questions": 5
    }
};

function loadPattern(board) {

    const box = document.getElementById("patternBox");
    box.innerHTML = "";

    if (!patterns[board]) return;

    for (let key in patterns[board]) {
        box.innerHTML += `
        <div class="d-flex justify-content-between border-bottom py-2">
            <strong>${key}</strong>
            <span>${patterns[board][key]}</span>
        </div>`;
    }
}

// ================= GENERATE PAPER =================

document.getElementById("generateBtn").addEventListener("click", () => {

    const subject = subjectSelect.value;

    const chapters = document.querySelectorAll(".chapter:checked");

    let output = `<h4>${subject} Paper</h4><hr>`;

    if (chapters.length === 0) {
        output += "<p>No chapters selected</p>";
    } else {
        chapters.forEach((ch, i) => {
            output += `<p>${i + 1}. Question from ${ch.value}</p>`;
        });
    }

    document.getElementById("output").innerHTML = output;
    document.getElementById("outputSection").style.display = "block";
});