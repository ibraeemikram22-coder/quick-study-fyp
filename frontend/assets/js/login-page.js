const loginEmail = document.getElementById("loginEmail");
const loginPassword = document.getElementById("loginPassword");
const signupName = document.getElementById("signupName");
const signupEmail = document.getElementById("signupEmail");
const signupPassword = document.getElementById("signupPassword");
const signupRole = document.getElementById("signupRole");
const authMsg = document.getElementById("authMsg");

function showMsg(text, isError) {
  if (!authMsg) return;
  authMsg.textContent = text;
  authMsg.style.color = isError ? "#c0392b" : "#1e8449";
}

function redirectAfterLogin(user) {
  const params = new URLSearchParams(window.location.search);
  const to = params.get("redirect");
  if (to) {
    window.location.href = to;
    return;
  }
  routeByRole(user.role);
}

function routeByRole(role) {
  if (role === "admin") {
    window.location.href = "admin/dashboard.html";
  } else if (role === "teacher") {
    window.location.href = "module/questionbank/teacher.html";
  } else if (role === "student") {
    window.location.href = "module/questionbank/student.html";
  } else {
    window.location.href = "index.html";
  }
}

async function handleLogin() {
  try {
    const data = await apiAuth("/api/auth/login", {
      email: loginEmail.value.trim(),
      password: loginPassword.value,
    });
    saveUser(data.user);
    showMsg("Login successful. Redirecting...");
    setTimeout(() => redirectAfterLogin(data.user), 400);
  } catch (e) {
    showMsg(e.message, true);
  }
}

async function handleSignup() {
  try {
    await apiAuth("/api/auth/signup", {
      name: signupName.value.trim(),
      email: signupEmail.value.trim(),
      password: signupPassword.value,
      role: signupRole.value,
    });
    showMsg("Account created. You can login now (optional — dashboards work without login for now).");
    toggle();
  } catch (e) {
    showMsg(e.message, true);
  }
}

const container = document.getElementById("container");

function toggle() {
  container.classList.toggle("active");
  const title = document.getElementById("panelTitle");
  const text = document.getElementById("panelText");
  const btn = document.querySelector(".switch-btn");
  if (container.classList.contains("active")) {
    title.innerText = "Welcome Back!";
    text.innerText = "Already have an account? Login now";
    btn.innerText = "Login";
  } else {
    title.innerText = "New here?";
    text.innerText = "Create account to continue";
    btn.innerText = "Sign Up";
  }
}

function googleLogin() {
  alert("Coming soon. For now use email/password, or open dashboards without login.");
}

window.toggle = toggle;
window.handleLogin = handleLogin;
window.handleSignup = handleSignup;
window.googleLogin = googleLogin;

(function initLoginPage() {
  showMsg(
    "Login is optional right now. Student & Teacher dashboards open directly from the menu.",
    false
  );
})();
