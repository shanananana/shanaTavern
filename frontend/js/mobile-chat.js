/** 手机端同页对话浮层 — 避免跳转 chat.html 整页重载 */
const MobileChat = {
  sessionId: null,
  charId: null,
  char: null,
  charMap: {},
  sessions: [],
  user: null,
  streaming: false,
  _ready: false,

  init(user) {
    const mobile = typeof isMobileLayout === "function" ? isMobileLayout() : window.matchMedia("(max-width: 768px)").matches;
    if (!mobile) return;
    this.user = user;
    if (!document.getElementById("mobile-chat-overlay")) {
      document.body.insertAdjacentHTML("beforeend", `
        <div id="mobile-chat-overlay" class="mobile-chat-overlay" aria-hidden="true">
          <div class="mobile-chat-panel">
            <div class="chat-mobile-bar mobile-chat-bar">
              <button type="button" class="btn-icon" id="mc-close" aria-label="关闭">←</button>
              <div class="chat-mobile-title" id="mc-title">对话</div>
              <a href="#" class="btn-icon" id="mc-full" aria-label="完整对话页" title="完整页">↗</a>
            </div>
            <div class="chat-messages mobile-chat-messages" id="mc-messages">
              <div class="chat-messages-empty">加载中…</div>
            </div>
            <div class="chat-input-bar mobile-chat-input">
              <textarea id="mc-input" placeholder="输入消息…" rows="1" enterkeyhint="send"></textarea>
              <button class="btn btn-primary" id="mc-send">发送</button>
            </div>
          </div>
        </div>`);
      document.getElementById("mc-close").addEventListener("click", () => this.close());
      document.getElementById("mc-full").addEventListener("click", e => {
        e.preventDefault();
        if (this.charId) {
          try {
            sessionStorage.setItem("tm_chat_prefill", JSON.stringify({ id: this.charId, ...this.char }));
          } catch (_) {}
          location.href = `/chat.html?character_id=${this.charId}`;
        }
      });
      document.getElementById("mc-send").addEventListener("click", () => this.send());
      document.getElementById("mc-input").addEventListener("keydown", e => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this.send(); }
      });
    }
    this._prefetch();
  },

  _prefetch() {
    const sessKey = API._cacheKey("/api/chat/sessions");
    const charsKey = API._cacheKey("/api/characters");
    const sessHit = API._cache.get(sessKey);
    const charsHit = API._cache.get(charsKey);
    const needSess = !sessHit || Date.now() - sessHit.at >= (sessHit.ttlMs || 60000);
    const needChars = !charsHit || Date.now() - charsHit.at >= (charsHit.ttlMs || 300000);
    if (!needSess && !needChars) {
      this.sessions = sessHit.data || [];
      this.charMap = {};
      (charsHit.data || []).forEach(c => { this.charMap[c.id] = c; });
      this._ready = true;
      return;
    }
    Promise.all([
      needSess ? API.cachedGet("/api/chat/sessions", 60000) : Promise.resolve(sessHit.data),
      needChars ? API.cachedGet("/api/characters", 300000) : Promise.resolve(charsHit.data),
    ]).then(([sessions, chars]) => {
      this.sessions = sessions || [];
      this.charMap = {};
      (chars || []).forEach(c => { this.charMap[c.id] = c; });
      this._ready = true;
    }).catch(() => {});
  },

  _label() {
    return this.user?.nickname || this.user?.username || "你";
  },

  _scrollBottom() {
    const el = document.getElementById("mc-messages");
    if (el) el.scrollTop = el.scrollHeight;
  },

  async open(charId, meta) {
    if (!document.getElementById("mobile-chat-overlay")) this.init(this.user);
    this.charId = +charId;
    this.char = { ...(this.charMap[this.charId] || {}), ...(meta || {}), id: this.charId };
    if (!this.char.name) this.char.name = "角色";

    const overlay = document.getElementById("mobile-chat-overlay");
    document.getElementById("mc-title").textContent = this.char.name;
    document.getElementById("mc-messages").innerHTML = `<div class="chat-messages-empty">连接 ${escHtml(this.char.name)}…</div>`;
    document.getElementById("mc-input").value = "";
    overlay.classList.add("open");
    overlay.setAttribute("aria-hidden", "false");
    document.body.classList.add("mobile-chat-open");

    await this._ensureSession();
    await this._loadMessages();
  },

  close() {
    const overlay = document.getElementById("mobile-chat-overlay");
    overlay?.classList.remove("open");
    overlay?.setAttribute("aria-hidden", "true");
    document.body.classList.remove("mobile-chat-open");
    this.streaming = false;
  },

  async _ensureSession() {
    if (!this.sessions.length) {
      this.sessions = await API.cachedGet("/api/chat/sessions", 60000);
    }
    const existing = this.sessions.find(s => s.character_id === this.charId);
    if (existing) {
      this.sessionId = existing.id;
      return;
    }
    const s = await API.post("/api/chat/sessions", { character_id: this.charId });
    this.sessionId = s.id;
    this.sessions.unshift({
      id: s.id,
      character_id: this.charId,
      character_name: this.char.name,
      title: "新对话",
    });
  },

  async _loadMessages() {
    const el = document.getElementById("mc-messages");
    const msgs = await API.get(`/api/chat/sessions/${this.sessionId}/messages`);
    if (!msgs.length) {
      el.innerHTML = `<div class="chat-messages-empty">与 ${escHtml(this.char.name)} 的对话开始了</div>`;
      return;
    }
    el.innerHTML = msgs.map(m => renderChatBubble({
      role: m.role,
      content: m.content,
      char: m.role === "assistant" ? this.char : null,
      userLabel: this._label(),
    })).join("");
    this._scrollBottom();
  },

  _finalizeBubble(bubble, text) {
    bubble?.classList.remove("msg-streaming");
    const wrap = bubble?.querySelector(".msg-content");
    if (wrap) wrap.innerHTML = formatChatContent(text);
  },

  async send() {
    if (this.streaming || !this.sessionId) return;
    const input = document.getElementById("mc-input");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    this.streaming = true;
    document.getElementById("mc-send").disabled = true;

    const el = document.getElementById("mc-messages");
    el.querySelector(".chat-messages-empty")?.remove();
    el.insertAdjacentHTML("beforeend", renderChatBubble({
      role: "user",
      content: text,
      userLabel: this._label(),
    }));

    const wrapper = document.createElement("div");
    wrapper.innerHTML = renderChatBubble({
      role: "assistant",
      content: "",
      char: this.char,
      streaming: true,
    });
    const bubble = wrapper.firstElementChild;
    el.appendChild(bubble);
    const contentEl = bubble.querySelector(".stream-content");
    this._scrollBottom();

    try {
      await API.stream(
        `/api/chat/sessions/${this.sessionId}/send`,
        { content: text },
        token => { contentEl.textContent += token; this._scrollBottom(); },
        () => {
          this._finalizeBubble(bubble, contentEl.textContent);
          this.streaming = false;
          document.getElementById("mc-send").disabled = false;
        },
        err => {
          contentEl.textContent = "错误: " + err;
          this.streaming = false;
          document.getElementById("mc-send").disabled = false;
        }
      );
    } catch (ex) {
      contentEl.textContent = "错误: " + ex.message;
      this.streaming = false;
      document.getElementById("mc-send").disabled = false;
    }
  },
};
