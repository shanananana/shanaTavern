/** Shared chat session state + streaming — load after utils.js, before api.js */
const ChatSessionStore = {
  STORAGE_KEY: "st_chat_sessions",
  SESSIONS_KEY: "st_chat_sessions_list",

  _readMap() {
    try {
      const raw = localStorage.getItem(this.STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  },

  _writeMap(map) {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(map));
    } catch (_) {}
  },

  getSessionId(charId) {
    const map = this._readMap();
    const id = map[String(charId)];
    return id ? +id : null;
  },

  setSessionId(charId, sessionId) {
    const map = this._readMap();
    map[String(charId)] = sessionId;
    this._writeMap(map);
  },

  cacheSessions(sessions) {
    try {
      localStorage.setItem(this.SESSIONS_KEY, JSON.stringify({ sessions, at: Date.now() }));
    } catch (_) {}
  },

  readCachedSessions(maxAgeMs = 60000) {
    try {
      const raw = localStorage.getItem(this.SESSIONS_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed?.sessions || Date.now() - (parsed.at || 0) > maxAgeMs) return null;
      return parsed.sessions;
    } catch {
      return null;
    }
  },

  syncFromApiSessions(sessions) {
    if (!Array.isArray(sessions)) return;
    this.cacheSessions(sessions);
    const map = this._readMap();
    let changed = false;
    for (const s of sessions) {
      const key = String(s.character_id);
      if (!map[key]) {
        map[key] = s.id;
        changed = true;
      }
    }
    if (changed) this._writeMap(map);
  },
};

function finalizeStreamBubble(bubble, text) {
  if (!bubble) return;
  bubble.classList.remove("msg-streaming");
  const contentWrap = bubble.querySelector(".msg-content");
  if (contentWrap) contentWrap.innerHTML = formatChatContent(text);
}

function appendStreamingBubble(containerEl, char) {
  containerEl.querySelector(".chat-messages-empty")?.remove();
  const wrapper = document.createElement("div");
  wrapper.innerHTML = renderChatBubble({
    role: "assistant",
    content: "",
    char,
    streaming: true,
  });
  const bubble = wrapper.firstElementChild;
  containerEl.appendChild(bubble);
  return {
    bubble,
    contentEl: bubble.querySelector(".stream-content"),
  };
}

async function streamChatMessage({
  sessionId,
  body,
  messagesEl,
  char,
  onStart,
  onComplete,
}) {
  const { bubble, contentEl } = appendStreamingBubble(messagesEl, char);
  if (onStart) onStart(bubble, contentEl);

  const scrollBottom = () => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  };

  try {
    await API.stream(
      `/api/chat/sessions/${sessionId}/send`,
      body,
      (token) => {
        contentEl.textContent += token;
        scrollBottom();
      },
      () => {
        finalizeStreamBubble(bubble, contentEl.textContent);
        if (onComplete) onComplete(null, bubble);
      },
      (err) => {
        contentEl.textContent = "错误: " + err;
        if (onComplete) onComplete(err, bubble);
      }
    );
  } catch (ex) {
    contentEl.textContent = "错误: " + ex.message;
    if (onComplete) onComplete(ex, bubble);
  }
}

function bindMobileChatViewport(inputEl) {
  if (!inputEl || !isMobileLayout()) return;
  inputEl.addEventListener("focus", () => {
    requestAnimationFrame(() => {
      inputEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
      setTimeout(() => {
        window.scrollTo(0, 0);
        document.body.classList.add("keyboard-open");
      }, 300);
    });
  });
  inputEl.addEventListener("blur", () => {
    document.body.classList.remove("keyboard-open");
  });
}
