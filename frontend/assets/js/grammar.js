/* ==========================================
frontend/assets/js/grammar.js
========================================== */

document.addEventListener("DOMContentLoaded", () => {

    const input = document.getElementById("grammar-input");
    const output = document.getElementById("output-box");
    const percent = document.getElementById("grammar-percentage");
    const explanationBox = document.getElementById("explanation-box");

    const checkBtn = document.getElementById("check-btn");
    const copyBtn = document.getElementById("copy-btn");
    const highlightBtn = document.getElementById("highlight-btn");
    const notesCheckbox = document.getElementById("convert-notes");

    let originalText = "";
    let correctedText = "";
    let errorsList = [];
    let highlighted = false;

    /* ================= CHECK ================= */
    checkBtn.addEventListener("click", async () => {
        if (!requireModuleAccess("grammar", "Grammar Check")) return;

        let text = input.value.trim();

        if (!text) {
            alert("Enter text first");
            return;
        }

        output.innerText = "Checking...";
        explanationBox.innerHTML = "";

        const res = await fetch(`${API_BASE}/grammar/check`, moduleHistoryFetchOpts({ text }));

        const data = await res.json().catch(() => ({}));

        if (!res.ok || data.error) {
            const msg = typeof handleAiModuleError === "function"
                ? handleAiModuleError(new Error(data.error || "Grammar check failed."), data)
                : (typeof toUserMessage === "function" ? toUserMessage(data.error || "Grammar check failed.") : (data.error || "Grammar check failed."));
            output.innerText = msg;
            percent.innerText = "Errors: —";
            explanationBox.innerHTML = "";
            return;
        }

        originalText = text;
        correctedText = data.corrected || "";
        errorsList = data.errors || [];

        if (notesCheckbox.checked) {
            correctedText = correctedText
                .split(".")
                .map(line => "• " + line.trim())
                .join("\n");
        }

        output.innerText = correctedText;
        percent.innerText = "Errors: " + data.error_count;

        /* Explanation */
        data.errors.forEach(err => {

            explanationBox.innerHTML += `
                <div class="explain-card">
                     <b>${err.message}</b><br>
                     Replace With: ${err.suggestions[0] || "N/A"}<br>
                     Why: ${err.explanation}
                </div>
            `;
        });

        highlighted = false;
        recordModuleUse("grammar");
        refreshGrammarHistory();
    });

    function refreshGrammarHistory() {}

    bootHistoryFromUrl((id) => `/api/records/${id}`, (row) => {
        const r = row.result || {};
        if (r.corrected) {
            input.value = r.original || "";
            output.innerText = r.corrected;
            percent.innerText = "Errors: " + (r.error_count || 0);
        }
    });

    /* ================= COPY ================= */
    copyBtn.addEventListener("click", () => {

        navigator.clipboard.writeText(correctedText);
        alert("Copied!");
    });

    /* ================= SHOW MISTAKES ================= */
    highlightBtn.addEventListener("click", () => {

        if (!originalText) return;

        if (!highlighted) {

            let html = originalText;

            errorsList.forEach(err => {

                let wrong = originalText.substr(err.offset, err.length);

                html = html.replace(
                    wrong,
                    `<mark style="background:yellow;color:red">${wrong}</mark>`
                );
            });

            output.innerHTML = html;
            highlighted = true;

        } else {
            output.innerText = correctedText;
            highlighted = false;
        }
    });

});