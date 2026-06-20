/** Map technical API / AI errors to short user-facing messages. */
function toUserMessage(err) {
  const msg = String(err?.message || err || "").trim();
  const m = msg.toLowerCase();

  if (!msg) return "Something went wrong. Please try again.";

  if (/quota|429|rate limit|resource exhausted|daily limit/.test(m)) {
    return "The AI service is busy right now. Please try again in a few minutes.";
  }
  if (/503|502|504|unavailable|high demand|server busy|temporarily/.test(m) || m.includes("gemini")) {
    return "The AI service is temporarily unavailable. Please try again shortly.";
  }
  if (/timeout|timed out|abort/.test(m)) {
    return "This took too long. Try again with fewer chapters or a shorter exam type.";
  }
  if (/failed to fetch|network|cannot reach|backend offline|econnrefused/.test(m)) {
    return "Cannot connect to the server. Please make sure the application is running.";
  }
  if (/api key|401|403|permission denied/.test(m)) {
    return "This feature is temporarily unavailable. Please try again later.";
  }
  if (/watermark|corrupt|text could not/.test(m)) {
    return "This book file could not be read. Try an official textbook PDF.";
  }
  if (/database|mysql|sql|traceback|\.env|backend\//i.test(msg)) {
    return "Something went wrong. Please try again.";
  }
  if (msg.length > 100 || /detail:|error \(\d+\)|generatecontent/i.test(m)) {
    return "Something went wrong. Please try again later.";
  }
  return msg;
}

function toAdminMessage(err) {
  const msg = String(err?.message || err || "").trim();
  const m = msg.toLowerCase();
  if (/quota|429|503|gemini|unavailable|busy/.test(m)) {
    return "AI service is busy. Please wait a few minutes and try again.";
  }
  if (/watermark|corrupt/.test(m)) {
    return "PDF quality issue — use an official watermark-free textbook PDF.";
  }
  if (/failed to fetch|network|offline/.test(m)) {
    return "Cannot reach the backend. Run START_PROJECT.bat.";
  }
  if (msg.length > 160) {
    return toUserMessage(err);
  }
  return msg || "Action failed.";
}
