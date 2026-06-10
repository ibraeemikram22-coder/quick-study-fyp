async function loadContactEmail() {
  const el = document.getElementById("displayContactEmail");
  if (!el) return;
  try {
    const info = await apiFetch("/api/contact/info");
    const email = info.contactEmail || "quickstudybuilder@gmail.com";
    el.innerHTML = `<a href="mailto:${email}">${email}</a>`;
  } catch {
    el.textContent = "quickstudybuilder@gmail.com";
  }
}

async function sendToBackend(payload) {
  return apiFetch("/api/contact/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function setupContactForm() {
  const form = document.querySelector(".contact-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = form.querySelector('[name="name"]')?.value.trim();
    const email = form.querySelector('[name="email"]')?.value.trim();
    const message = form.querySelector('[name="message"]')?.value.trim();
    const btn = form.querySelector('[type="submit"]');

    if (!name || !email || !message) {
      alert("Please fill all fields.");
      return;
    }

    if (btn) {
      btn.disabled = true;
      btn.value = "Sending...";
    }

    try {
      const res = await sendToBackend({
        name,
        email,
        subject: "contact",
        message,
      });
      alert(res.message || "Message sent successfully!");
      form.reset();
    } catch (err) {
      alert(err.message || "Could not send. Is backend running? (python app.py)");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.value = "Send Message";
      }
    }
  });
}

window.openFeedback = function openFeedback() {
  document.getElementById("feedbackPopup").style.display = "flex";
};

window.closeFeedback = function closeFeedback() {
  document.getElementById("feedbackPopup").style.display = "none";
};

window.submitFeedback = async function submitFeedback() {
  const rating = document.getElementById("rating").value;
  const text = document.getElementById("fbText").value.trim();
  const nameEl = document.getElementById("fbName");
  const emailEl = document.getElementById("fbEmail");
  const name = nameEl ? nameEl.value.trim() : "Feedback user";
  const email = emailEl ? emailEl.value.trim() : "";

  if (!text) {
    alert("Please write feedback first!");
    return;
  }

  try {
    const res = await sendToBackend({
      name: name || "Feedback user",
      email,
      subject: "feedback",
      rating: parseInt(rating, 10),
      message: text,
    });
    alert(res.message || "Thank you for your feedback!");
    document.getElementById("fbText").value = "";
    closeFeedback();
  } catch (err) {
    alert(err.message || "Could not send feedback. Start backend: python app.py");
  }
};

setupContactForm();
loadContactEmail();
