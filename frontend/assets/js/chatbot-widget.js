(function initChatbotWidget() {
  const box = document.getElementById("chatbot-box");
  const icon = document.getElementById("chatbot-icon");
  const closeBtn = document.getElementById("chatbot-close");
  const messages = document.getElementById("cbMessages");
  const topics = document.getElementById("cbTopics");
  const searchInput = document.getElementById("cbSearch");
  const categoryBar = document.getElementById("cbCategories");
  const quickBar = document.getElementById("cbQuick");

  if (!box || !messages || !window.FAQ_TOPICS) return;

  let activeCategory = "all";
  let welcomed = false;

  function addMsg(text, who) {
    const el = document.createElement("div");
    el.className = "cb-msg " + who;
    const bubble = document.createElement("div");
    bubble.className = "cb-msg-bubble";
    bubble.textContent = text;
    el.appendChild(bubble);
    if (who === "bot") {
      const av = document.createElement("span");
      av.className = "cb-msg-avatar";
      av.innerHTML = '<i class="fas fa-robot"></i>';
      el.prepend(av);
    }
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  function showTyping() {
    const el = document.createElement("div");
    el.className = "cb-msg bot cb-typing";
    el.innerHTML =
      '<span class="cb-msg-avatar"><i class="fas fa-robot"></i></span>' +
      '<div class="cb-msg-bubble"><span class="cb-dots"><span></span><span></span><span></span></span></div>';
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  function showAnswer(faq) {
    addMsg(faq.question, "user");
    const typing = showTyping();
    setTimeout(() => {
      typing.remove();
      addMsg(faq.answer, "bot");
    }, 400);
  }

  function showSearchReply(query) {
    const matched = typeof matchSearchQuery === "function" ? matchSearchQuery(query) : null;
    addMsg(query, "user");
    const typing = showTyping();
    setTimeout(() => {
      typing.remove();
      if (matched) addMsg(matched.answer, "bot");
      else addMsg(getIrrelevantReply(), "bot");
    }, 400);
  }

  function renderTopics(list) {
    if (!topics) return;
    topics.innerHTML = "";
    const items = list.length ? list : FAQ_TOPICS;
    items.forEach((faq) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cb-topic-btn";
      const cat = FAQ_CATEGORIES.find((c) => c.id === faq.category);
      btn.innerHTML =
        (cat ? `<span class="cb-topic-tag">${cat.label}</span>` : "") +
        `<span class="cb-topic-text">${faq.question}</span>`;
      btn.addEventListener("click", () => showAnswer(faq));
      topics.appendChild(btn);
    });
    if (!items.length) {
      topics.innerHTML =
        '<p class="cb-no-results">No matching topics. Try: login, quiz, paper — or pick Hello below.</p>';
    }
  }

  function filterTopics() {
    const q = (searchInput?.value || "").trim().toLowerCase();
    let list = getFaqsByCategory(activeCategory);
    if (q) {
      list = list.filter(
        (f) =>
          f.question.toLowerCase().includes(q) ||
          f.answer.toLowerCase().includes(q) ||
          (f.keywords || []).some((k) => k.toLowerCase().includes(q))
      );
    }
    renderTopics(list);
  }

  if (quickBar) {
    ["hello", "thanks", "login", "trial"].forEach((id) => {
      const faq = FAQ_TOPICS.find((f) => f.id === id);
      if (!faq) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cb-quick-btn";
      btn.textContent = faq.question.replace(/[!?]/g, "");
      btn.addEventListener("click", () => showAnswer(faq));
      quickBar.appendChild(btn);
    });
  }

  if (categoryBar && window.FAQ_CATEGORIES) {
    FAQ_CATEGORIES.forEach((cat) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cb-cat-btn" + (cat.id === activeCategory ? " active" : "");
      btn.innerHTML = `<i class="fas ${cat.icon}"></i> ${cat.label}`;
      btn.addEventListener("click", () => {
        activeCategory = cat.id;
        categoryBar.querySelectorAll(".cb-cat-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        filterTopics();
      });
      categoryBar.appendChild(btn);
    });
  }

  searchInput?.addEventListener("input", filterTopics);
  searchInput?.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    const q = searchInput.value.trim();
    if (!q) return;
    showSearchReply(q);
    searchInput.value = "";
    activeCategory = "all";
    categoryBar?.querySelectorAll(".cb-cat-btn").forEach((b, i) => {
      b.classList.toggle("active", i === 0);
    });
    renderTopics(FAQ_TOPICS);
  });

  renderTopics(FAQ_TOPICS);

  icon?.addEventListener("click", () => {
    const open = box.classList.toggle("active");
    if (open && !welcomed) {
      welcomed = true;
      addMsg(
        "Hi! Select a question below for help with login, papers, AI tools, and common issues.",
        "bot"
      );
    }
  });
  closeBtn?.addEventListener("click", () => box.classList.remove("active"));
})();
