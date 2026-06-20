/**
 * Quick Study Builder — Help assistant (predefined topics + keyword matching).
 */
const FAQ_CATEGORIES = [
  { id: "all", label: "All", icon: "fa-list" },
  { id: "account", label: "Login", icon: "fa-user" },
  { id: "student", label: "Student", icon: "fa-user-graduate" },
  { id: "teacher", label: "Teacher", icon: "fa-chalkboard-teacher" },
  { id: "tools", label: "AI Tools", icon: "fa-wand-magic-sparkles" },
  { id: "help", label: "Help", icon: "fa-life-ring" },
];

const FAQ_TOPICS = [
  {
    id: "about",
    category: "help",
    question: "What is Quick Study Builder?",
    keywords: ["what is", "about", "quick study", "fyp", "website"],
    answer:
      "Quick Study Builder is an AI-powered learning platform for Punjab Board students and teachers.\n\n• Students: practice papers, quizzes, notes, grammar, and more\n• Teachers: generate board-style exam papers from the question bank\n• All tools share one login once you sign in",
  },
  {
    id: "login",
    category: "account",
    question: "How do I log in or sign up?",
    keywords: ["login", "sign in", "sign up", "register", "account", "email", "password"],
    answer:
      "Click Login / Signup in the header.\n\n• Student Portal — for student dashboard and learning tools\n• Teacher Portal — for teacher dashboard and paper generation\n• Sign in once — your session works across all modules (SSO)",
  },
  {
    id: "sso",
    category: "account",
    question: "Do I need to log in on every module?",
    keywords: ["sso", "single sign", "every module", "again", "session", "one login"],
    answer:
      "No. After you sign in from any module or dashboard, you stay logged in across the entire website until you sign out or the session expires (7 days).\n\nPremium modules give 3 free uses each before login is required. Once signed in, all modules unlock without asking again.",
  },
  {
    id: "trial",
    category: "account",
    question: "What is the free trial limit?",
    keywords: ["free", "trial", "3", "limit", "uses", "premium"],
    answer:
      "Each premium AI tool allows 3 free uses without an account:\n\n• Quiz Generator\n• Summarized Notes\n• Grammar Check\n• AI Humanizer\n• Video Transcript\n\nAfter 3 uses, sign in with your email to continue. Student and Teacher dashboards do not use this trial — they require login directly.",
  },
  {
    id: "student-teacher-diff",
    category: "account",
    question: "What is the difference between Student and Teacher?",
    keywords: ["difference", "student teacher", "student vs", "which account"],
    answer:
      "Student and Teacher are separate account types:\n\n• Student — access Student Dashboard, practice papers, timed tests, and all AI modules\n• Teacher — access Teacher Dashboard, Punjab Board paper builder, and all AI modules\n\nYou cannot open Teacher Dashboard with a Student account (and vice versa). AI modules work with both account types after login.",
  },
  {
    id: "logout",
    category: "account",
    question: "How do I sign out?",
    keywords: ["logout", "log out", "sign out", "clear session"],
    answer:
      "Click Logout in the header, or Sign out on a module banner / dashboard bar.\n\nThis ends your global session. You will need to sign in again when accessing premium modules or dashboards.\n\nTo fully reset the browser, open clear-session.html or run CLEAR_SESSION.bat.",
  },
  {
    id: "student-dashboard",
    category: "student",
    question: "Where is the Student Dashboard?",
    keywords: ["student dashboard", "student portal", "generate paper student"],
    answer:
      "Header → Login (Student) or open module/questionbank/student.html after signing in.\n\nFrom the dashboard you can:\n• Upload notes or PDF to generate a practice paper\n• Take a timed online test\n• Download papers as Word documents\n• View saved papers in History",
  },
  {
    id: "student-paper",
    category: "student",
    question: "How does student paper generation work?",
    keywords: ["student paper", "practice paper", "timed test", "upload notes", "word download"],
    answer:
      "Student Dashboard → choose Practice paper or Timed test.\n\n1. Upload PDF, DOCX, or paste notes\n2. Select question types and counts\n3. Click Generate\n4. Download Word, print, or attempt the timed test online\n\nYour paper is also saved in History for later.",
  },
  {
    id: "teacher",
    category: "teacher",
    question: "How do I generate a teacher exam paper?",
    keywords: ["teacher paper", "exam paper", "punjab board", "mukabbir", "generate paper teacher"],
    answer:
      "Open Teacher Dashboard (sign in with Teacher account).\n\n1. Select class (11th or 12th)\n2. Select subject and book\n3. Choose exam type (Weekly, Monthly, Preboard, etc.)\n4. Select chapters for syllabus coverage\n5. Set MCQ / short / long question counts\n6. Click Generate Paper\n7. Print or download as Word (board format available)",
  },
  {
    id: "teacher-books",
    category: "teacher",
    question: "Where do teacher paper questions come from?",
    keywords: ["question bank", "chapters", "textbook", "punjab books"],
    answer:
      "Questions are pulled from the Question Bank — chapter content uploaded by Admin.\n\nTeachers select chapters when building a paper. The system mixes MCQs, short questions, and long questions according to Punjab Board style.\n\nIf a subject has no chapters yet, ask your administrator to upload the book PDF in Question Bank Admin.",
  },
  {
    id: "quiz",
    category: "tools",
    question: "How do I use the Quiz Generator?",
    keywords: ["quiz", "mcq", "generate quiz", "questions from notes"],
    answer:
      "Home → Features → Quiz Generator.\n\nPaste text or upload a file. The AI creates multiple-choice questions from your content.\n\n3 free generations without login, then sign in for unlimited use. Works for both students and teachers.",
  },
  {
    id: "notes",
    category: "tools",
    question: "How do I summarize notes?",
    keywords: ["summarizer", "summarize", "notes", "summary", "short notes"],
    answer:
      "Home → Features → Summarized Notes.\n\nUpload a PDF, DOCX, or paste text. The AI produces concise study notes.\n\nLarge PDFs may take a few minutes. Keep the backend running (START_PROJECT.bat).",
  },
  {
    id: "grammar",
    category: "tools",
    question: "How does Grammar Check work?",
    keywords: ["grammar", "spell", "mistakes", "correct english"],
    answer:
      "Home → Features → Grammar Check.\n\nPaste your text and run the check. The tool highlights grammar issues and suggests corrections — useful for essays and assignments.",
  },
  {
    id: "humanizer",
    category: "tools",
    question: "What is the AI Humanizer?",
    keywords: ["humanizer", "humanize", "ai text", "rewrite"],
    answer:
      "Home → Features → AI Humanizer.\n\nPaste AI-generated or formal text to rewrite it in a more natural, human-readable style. Sign in after the free trial for unlimited access.",
  },
  {
    id: "transcript",
    category: "tools",
    question: "How do I get a video transcript?",
    keywords: ["transcript", "video", "youtube", "subtitle", "caption"],
    answer:
      "Home → Features → Video Transcript.\n\nPaste a YouTube link or upload audio/video. The system generates a text transcript you can copy or download.\n\nRequires the backend with transcript dependencies installed.",
  },
  {
    id: "hello",
    category: "help",
    question: "Hello!",
    keywords: ["hi", "hello", "hey", "salam", "assalam", "good morning", "good evening", "how are you"],
    answer:
      "Hello! Welcome to Quick Study Builder.\n\nI'm here to help with this website — login, student & teacher papers, AI tools, and common issues.\n\nPlease pick a question from the list below.",
  },
  {
    id: "thanks",
    category: "help",
    question: "Thank you!",
    keywords: ["thanks", "thank you", "shukriya", "thx", "ok thanks"],
    answer: "You're welcome! If you need anything else, choose another topic below.",
  },
  {
    id: "history",
    category: "tools",
    question: "Where are my saved papers and results?",
    keywords: ["history", "saved", "previous", "past papers"],
    answer:
      "Open Saved / History from the Student or Teacher dashboard, or go to module/history/saved.html.\n\nYou can filter by module (question bank, quiz, etc.) and reopen previous work.",
  },
  {
    id: "server",
    category: "help",
    question: "Backend or server not working?",
    keywords: ["server", "backend", "not working", "connection", "offline", "start project"],
    answer:
      "1. Double-click START_PROJECT.bat in the project folder\n2. Keep the \"QSB Backend\" window open\n3. Frontend opens at http://localhost:5500\n4. Backend health: http://localhost:3000/api/health\n\nIf login fails, confirm Python is installed and the backend window shows no errors.",
  },
  {
    id: "paper-slow",
    category: "help",
    question: "Paper or AI generation is slow or fails?",
    keywords: ["slow", "timeout", "failed", "generating", "stuck", "error paper"],
    answer:
      "Try these steps:\n\n• Keep the backend window open\n• Select fewer chapters or smaller content first\n• Check your Gemini API key in backend/.env\n• For large PDFs, wait up to several minutes\n• Refresh the page and sign in again if the session expired",
  },
  {
    id: "contact",
    category: "help",
    question: "How do I contact support?",
    keywords: ["contact", "support", "help email", "message admin"],
    answer:
      "Use the Contact Us page from the header or footer.\n\nFill in your name, email, and message. The administrator receives your request and can reply by email.",
  },
  {
    id: "profile",
    category: "account",
    question: "How do I edit my profile?",
    keywords: ["profile", "name", "photo", "avatar", "edit account"],
    answer:
      "Click your profile icon in the header (when logged in as a student).\n\nYou can update your display name and profile photo. Email cannot be changed.\n\nTeachers are redirected to the Teacher Dashboard instead of the profile page.",
  },
];

function findFaq(topicIdOrQuestion) {
  const key = (topicIdOrQuestion || "").trim().toLowerCase();
  if (!key) return null;

  const byId = FAQ_TOPICS.find((f) => f.id === key);
  if (byId) return byId;

  const byQuestion = FAQ_TOPICS.find(
    (f) => f.question.toLowerCase() === key || f.question.toLowerCase().includes(key)
  );
  if (byQuestion) return byQuestion;

  return null;
}

function getFaqsByCategory(categoryId) {
  if (!categoryId || categoryId === "all") return FAQ_TOPICS;
  return FAQ_TOPICS.filter((f) => f.category === categoryId);
}

/** Match casual search text (hello, thanks, or a real topic). */
function matchSearchQuery(text) {
  const raw = (text || "").trim();
  if (!raw) return null;
  const key = raw.toLowerCase().replace(/[!?.]+$/g, "").trim();

  const byId = FAQ_TOPICS.find((f) => f.id === key);
  if (byId) return byId;

  const byQuestion = FAQ_TOPICS.find((f) => f.question.toLowerCase().replace(/[!?.]+$/g, "") === key);
  if (byQuestion) return byQuestion;

  for (const faq of FAQ_TOPICS) {
    for (const kw of faq.keywords || []) {
      const k = kw.toLowerCase();
      if (key === k || key.startsWith(k + " ") || key.endsWith(" " + k)) return faq;
    }
  }

  let best = null;
  let bestScore = 0;
  for (const faq of FAQ_TOPICS) {
    let score = 0;
    if (faq.question.toLowerCase().includes(key)) score += 12;
    for (const kw of faq.keywords || []) {
      if (key.includes(kw.toLowerCase())) score += Math.min(kw.length, 10);
    }
    if (score > bestScore) {
      bestScore = score;
      best = faq;
    }
  }
  if (best && bestScore >= 6) return best;
  return null;
}

function getIrrelevantReply() {
  return (
    "I can only help with Quick Study Builder.\n\n" +
    "Please select a topic below — for example login, free trial, student paper, teacher paper, quiz, or server issues."
  );
}

function getFaqAnswer(topicIdOrQuestion) {
  const faq = findFaq(topicIdOrQuestion);
  return faq ? faq.answer : null;
}

function getAssistantReply(userText) {
  const matched = matchSearchQuery(userText);
  if (matched) return matched.answer;
  return getIrrelevantReply();
}

window.FAQ_CATEGORIES = FAQ_CATEGORIES;
window.FAQ_TOPICS = FAQ_TOPICS;
window.getFaqAnswer = getFaqAnswer;
window.getAssistantReply = getAssistantReply;
window.findFaq = findFaq;
window.getFaqsByCategory = getFaqsByCategory;
window.matchSearchQuery = matchSearchQuery;
window.getIrrelevantReply = getIrrelevantReply;
