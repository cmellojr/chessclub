/**
 * chessclub Cookie Helper — popup.js
 *
 * Reads ACCESS_TOKEN and PHPSESSID from chess.com cookies and exposes
 * them for copy-pasting into `chessclub auth setup`.
 *
 * ⚠️  TEMPORARY — remove this extension once OAuth 2.0 is active.
 */

const CHESS_URL = "https://www.chess.com";

/** Fetch a single cookie value, or null if absent. */
function getCookie(name) {
  return new Promise((resolve) => {
    chrome.cookies.get({ url: CHESS_URL, name }, (cookie) => {
      resolve(cookie ? cookie.value : null);
    });
  });
}

/** Copy text to clipboard and show brief feedback on the button. */
function copyWithFeedback(button, text) {
  navigator.clipboard.writeText(text).then(() => {
    const original = button.textContent;
    button.textContent = "Copied!";
    button.disabled = true;
    setTimeout(() => {
      button.textContent = original;
      button.disabled = false;
    }, 1500);
  });
}

/** Toggle masked / revealed state of a value field. */
function toggleReveal(fieldId, eyeBtn) {
  const el = document.getElementById(fieldId);
  const masked = el.dataset.masked === "true";
  if (masked) {
    el.textContent = el.dataset.value;
    eyeBtn.textContent = "Hide";
    el.dataset.masked = "false";
  } else {
    el.textContent = maskValue(el.dataset.value);
    eyeBtn.textContent = "Show";
    el.dataset.masked = "true";
  }
}

/** Return a masked representation of a value (first 6 chars + asterisks). */
function maskValue(value) {
  if (!value || value.length <= 6) return "••••••";
  return value.slice(0, 6) + "•".repeat(Math.min(value.length - 6, 20));
}

async function init() {
  const [token, sessid] = await Promise.all([
    getCookie("ACCESS_TOKEN"),
    getCookie("PHPSESSID"),
  ]);

  const statusEl = document.getElementById("status");

  if (!token && !sessid) {
    statusEl.textContent =
      "No cookies found. Make sure you are logged in at chess.com.";
    statusEl.className = "status error";
    document.getElementById("content").style.display = "none";
    return;
  }

  statusEl.style.display = "none";

  // Populate ACCESS_TOKEN field
  const tokenEl = document.getElementById("token-value");
  tokenEl.dataset.value = token ?? "";
  tokenEl.dataset.masked = "true";
  tokenEl.textContent = token ? maskValue(token) : "— not found —";

  // Populate PHPSESSID field
  const sessEl = document.getElementById("sessid-value");
  sessEl.dataset.value = sessid ?? "";
  sessEl.dataset.masked = "true";
  sessEl.textContent = sessid ? maskValue(sessid) : "— not found —";

  // Copy individual buttons
  document.getElementById("copy-token").addEventListener("click", (e) => {
    copyWithFeedback(e.target, token ?? "");
  });
  document.getElementById("copy-sessid").addEventListener("click", (e) => {
    copyWithFeedback(e.target, sessid ?? "");
  });

  // Toggle reveal buttons
  document.getElementById("eye-token").addEventListener("click", (e) => {
    toggleReveal("token-value", e.target);
  });
  document.getElementById("eye-sessid").addEventListener("click", (e) => {
    toggleReveal("sessid-value", e.target);
  });

  // Copy both
  document.getElementById("copy-both").addEventListener("click", (e) => {
    const text = `ACCESS_TOKEN: ${token ?? ""}\nPHPSESSID: ${sessid ?? ""}`;
    copyWithFeedback(e.target, text);
  });
}

document.addEventListener("DOMContentLoaded", init);
