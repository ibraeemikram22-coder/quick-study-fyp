const PROFILE_TOOLS = {
  student: [
    { href: "module/quiz/quiz.html", icon: "fa-question-circle", label: "AI Quiz Generator" },
    { href: "module/summarizer/summarizer-notes.html", icon: "fa-file-lines", label: "Summarized Notes" },
    { href: "module/grammer/grammar.html", icon: "fa-spell-check", label: "Grammar Check" },
    { href: "module/humanizer/humanize.html", icon: "fa-user-check", label: "AI Humanizer" },
    { href: "module/transcript/videotranscript.html", icon: "fa-closed-captioning", label: "Video Transcript" },
    { href: "module/questionbank/student.html", icon: "fa-file-alt", label: "Generate Paper" },
  ],
  teacher: [
    { href: "module/questionbank/teacher.html", icon: "fa-chalkboard-teacher", label: "Teacher Dashboard" },
    { href: "module/quiz/quiz.html", icon: "fa-question-circle", label: "AI Quiz Generator" },
    { href: "module/summarizer/summarizer-notes.html", icon: "fa-file-lines", label: "Summarized Notes" },
    { href: "module/grammer/grammar.html", icon: "fa-spell-check", label: "Grammar Check" },
    { href: "module/humanizer/humanize.html", icon: "fa-user-check", label: "AI Humanizer" },
    { href: "module/transcript/videotranscript.html", icon: "fa-closed-captioning", label: "Video Transcript" },
  ],
};

function roleLabel(role) {
  if (role === "teacher") return "Teacher";
  return "Student";
}

function paintAvatarBox(el, user) {
  if (!el || !user) return;
  const avatar = getUserAvatar(user.id);
  if (avatar) {
    el.innerHTML = `<img src="${avatar}" alt="Profile photo">`;
  } else {
    el.innerHTML = `<span class="user-avatar-initial">${userInitial(user)}</span>`;
  }
}

function refreshProfileUI(user) {
  paintAvatarBox(document.getElementById("profileAvatarBox"), user);
  document.getElementById("profileNameDisplay").textContent = user.name || "User";
  document.getElementById("profileEmail").textContent = user.email || "";
  document.getElementById("editName").value = user.name || "";
  document.getElementById("editEmail").value = user.email || "";

  const badge = document.getElementById("profileRole");
  if (badge) badge.style.display = "none";

  if (typeof updateAuthNav === "function") updateAuthNav(document);
}

function showSaveMsg(text, ok) {
  const el = document.getElementById("profileSaveMsg");
  if (!el) return;
  el.textContent = text;
  el.style.color = ok ? "#1e8449" : "#c0392b";
}

async function saveProfileName(user) {
  const name = document.getElementById("editName")?.value.trim() || "";
  if (name.length < 2) {
    showSaveMsg("Name must be at least 2 characters.", false);
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/api/auth/profile`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id": String(user.id),
      },
      body: JSON.stringify({ userId: user.id, name }),
    });
    const data = await res.json();
    if (!res.ok || data.success === false) {
      throw new Error(data.error || "Could not save profile.");
    }
    const updated = data.user;
    saveUser(updated);
    refreshProfileUI(updated);
    showSaveMsg("Profile saved successfully.", true);
  } catch (e) {
    showSaveMsg(e.message || "Could not save. Is backend running?", false);
  }
}

function handleAvatarFile(file, user) {
  if (!file || !file.type.startsWith("image/")) {
    showSaveMsg("Please choose an image file (JPG, PNG).", false);
    return;
  }
  if (file.size > 800000) {
    showSaveMsg("Image too large. Use a photo under 800 KB.", false);
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    setUserAvatar(user.id, reader.result);
    refreshProfileUI(user);
    showSaveMsg("Photo updated.", true);
  };
  reader.readAsDataURL(file);
}

function initProfilePage() {
  const user = getUser();
  if (!user) {
    if (typeof AuthPortal !== "undefined") {
      AuthPortal.show({
        mode: "fullscreen",
        context: "module",
        redirect: "profile.html",
        startSignup: true,
        reloadOnSuccess: true,
      });
    } else {
      window.location.href = "login.html?redirect=profile.html&signup=1";
    }
    return;
  }
  if (user.role === "admin") {
    window.location.href = "admin/dashboard.html";
    return;
  }
  if (user.role === "teacher") {
    window.location.href = "module/questionbank/teacher.html";
    return;
  }

  refreshProfileUI(user);

  const role = user.role === "teacher" ? "teacher" : "student";
  const links = PROFILE_TOOLS[role] || PROFILE_TOOLS.student;
  document.getElementById("profileLinks").innerHTML = links
    .map(
      (item) => `
    <a class="profile-link-card" href="${item.href}" target="_blank" rel="noopener">
      <i class="fas ${item.icon}"></i>
      <span>${item.label}</span>
    </a>`
    )
    .join("");

  document.getElementById("saveProfileBtn").onclick = () => saveProfileName(getUser());
  document.getElementById("profileLogout").onclick = () => logoutUser();

  document.getElementById("avatarInput").onchange = (e) => {
    const file = e.target.files?.[0];
    if (file) handleAvatarFile(file, getUser());
    e.target.value = "";
  };

  document.getElementById("removePhotoBtn").onclick = () => {
    setUserAvatar(getUser().id, "");
    refreshProfileUI(getUser());
    showSaveMsg("Photo removed.", true);
  };
}

initProfilePage();
