const API = {
  get token() {
    return localStorage.getItem("st_token");
  },
  set token(v) {
    if (v) localStorage.setItem("st_token", v);
    else {
      localStorage.removeItem("st_token");
      try { sessionStorage.removeItem("st_user"); } catch (_) {}
    }
  },

  _cache: new Map(),
  _inflight: new Map(),
  streamTimeoutMs: 180000,

  _cacheKey(path) {
    return `${this.token || "anon"}:${path}`;
  },

  clearCache(prefix = "") {
    if (!prefix) {
      this._cache.clear();
      this._inflight.clear();
      return;
    }
    for (const key of this._cache.keys()) {
      if (key.includes(prefix)) this._cache.delete(key);
    }
    for (const key of this._inflight.keys()) {
      if (key.includes(prefix)) this._inflight.delete(key);
    }
  },

  seedCache(path, data, ttlMs = 120000) {
    this._cache.set(this._cacheKey(path), { data, at: Date.now(), ttlMs });
  },

  cachedGet(path, ttlMs = 60000) {
    const key = this._cacheKey(path);
    const hit = this._cache.get(key);
    const ttl = hit?.ttlMs ?? ttlMs;
    if (hit && Date.now() - hit.at < ttl) {
      return Promise.resolve(hit.data);
    }
    if (this._inflight.has(key)) {
      return this._inflight.get(key);
    }
    const pending = this.get(path).then((data) => {
      this._cache.set(key, { data, at: Date.now(), ttlMs });
      this._inflight.delete(key);
      return data;
    }).catch((err) => {
      this._inflight.delete(key);
      throw err;
    });
    this._inflight.set(key, pending);
    return pending;
  },

  async request(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    const res = await fetch(path, { ...options, headers });
    if (res.status === 401) {
      this.token = null;
      this.clearCache();
      if (!window.location.pathname.includes("login")) {
        window.location.href = "/login.html";
      }
      throw new Error("未登录");
    }
    const text = await res.text();
    let data;
    try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    if (!res.ok) {
      const msg = (data && data.detail) ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : res.statusText;
      throw new Error(msg);
    }
    if (method !== "GET") {
      this.clearCache("/api/");
    }
    return data;
  },

  get(path) { return this.request(path); },
  post(path, body) { return this.request(path, { method: "POST", body: JSON.stringify(body) }); },
  put(path, body) { return this.request(path, { method: "PUT", body: JSON.stringify(body) }); },
  delete(path) { return this.request(path, { method: "DELETE" }); },

  async fetchCharacters(path, ttlMs = 120000, useCache = true) {
    const data = useCache ? await this.cachedGet(path, ttlMs) : await this.get(path);
    return normalizeCharacterPage(data);
  },

  async uploadAvatar(characterId, file) {
    const form = new FormData();
    form.append("file", file);
    const headers = {};
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    const res = await fetch(`/api/characters/${characterId}/avatar`, {
      method: "POST",
      headers,
      body: form,
    });
    if (res.status === 401) {
      this.token = null;
      window.location.href = "/login.html";
      throw new Error("未登录");
    }
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || res.statusText);
    }
    return data;
  },

  async stream(path, body, onToken, onDone, onError, timeoutMs) {
    const limit = timeoutMs ?? this.streamTimeoutMs;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), limit);
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    let res;
    try {
      res = await fetch(path, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (err) {
      clearTimeout(timer);
      if (err.name === "AbortError") {
        onError(`请求超时（${Math.round(limit / 1000)}s），请重试`);
        return;
      }
      throw err;
    }
    if (!res.ok) {
      clearTimeout(timer);
      const err = await res.text();
      throw new Error(err || res.statusText);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let gotDone = false;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === "token") {
              onToken(evt.content);
            } else if (evt.type === "done") {
              gotDone = true;
              onDone(evt.message);
            } else if (evt.type === "error") {
              onError(evt.content);
            }
          } catch (_) { /* skip */ }
        }
      }
    } catch (err) {
      if (err.name === "AbortError") {
        onError(`请求超时（${Math.round(limit / 1000)}s），请重试`);
      } else {
        throw err;
      }
    } finally {
      clearTimeout(timer);
      controller.abort();
    }
    if (!gotDone) onError("模型未返回内容，请确认 LM Studio 已加载模型");
  },
};

const USER_CACHE_KEY = "st_user";
const USER_CACHE_TTL_MS = 300000;

function _readCachedUser() {
  try {
    const raw = sessionStorage.getItem(USER_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.user || !parsed.at) return null;
    if (Date.now() - parsed.at > USER_CACHE_TTL_MS) return null;
    return parsed.user;
  } catch {
    return null;
  }
}

function _writeCachedUser(user) {
  try {
    sessionStorage.setItem(USER_CACHE_KEY, JSON.stringify({ user, at: Date.now() }));
  } catch (_) {}
}

function _refreshUserInBackground() {
  if (!API.token) return;
  API.get("/api/auth/me").then(_writeCachedUser).catch(() => {});
}

async function requireAuth() {
  if (!API.token) { window.location.href = "/login.html"; return null; }
  const cached = _readCachedUser();
  if (cached) {
    _refreshUserInBackground();
    return cached;
  }
  try {
    const user = await API.get("/api/auth/me");
    _writeCachedUser(user);
    return user;
  } catch {
    window.location.href = "/login.html";
    return null;
  }
}

function applyBootstrap(data) {
  if (!data || typeof data !== "object" || !data.user) {
    throw new Error("bootstrap 数据无效");
  }
  _writeCachedUser(data.user);
  if (Array.isArray(data.characters)) {
    const page = {
      items: data.characters,
      total: data.characters.length,
      page: 1,
      page_size: data.characters.length,
      has_more: false,
    };
    API.seedCache("/api/characters", page, 120000);
  }
  if (Array.isArray(data.sessions)) {
    API.seedCache("/api/chat/sessions", data.sessions, 30000);
    ChatSessionStore.syncFromApiSessions(data.sessions);
  }
  window._bootstrap = data;
  return data.user;
}

async function fetchBootstrap() {
  try {
    const data = await API.cachedGet("/api/bootstrap", 60000);
    return applyBootstrap(data);
  } catch (err) {
    if (typeof console !== "undefined" && console.warn) {
      console.warn("bootstrap failed, fallback to auth", err);
    }
    API.clearCache("/api/bootstrap");
    return requireAuth();
  }
}

function showMainError(err) {
  const main = document.getElementById("main-content");
  const msg = err?.message || String(err);
  const html = `<div class="page-header"><h1>加载失败</h1><p class="subtitle">${escHtml(msg)}</p><button class="btn btn-primary" onclick="location.reload()">重试</button></div>`;
  if (main) main.innerHTML = html;
  else {
    const shell = document.getElementById("app-shell");
    if (shell) shell.innerHTML = `<div class="main" id="main-content">${html}</div>`;
  }
}

let _mobileChatLoading = null;

function loadMobileChat() {
  if (typeof MobileChat !== "undefined") return Promise.resolve();
  if (_mobileChatLoading) return _mobileChatLoading;
  _mobileChatLoading = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "/static/js/mobile-chat.js?v=6";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("mobile-chat load failed"));
    document.head.appendChild(script);
  });
  return _mobileChatLoading;
}

function openChat(charId, meta) {
  if (isMobileLayout()) {
    loadMobileChat().then(() => {
      if (!MobileChat.user && window._tmUser) MobileChat.user = window._tmUser;
      MobileChat.open(charId, meta);
    }).catch(() => {
      location.href = `/chat.html?character_id=${charId}`;
    });
    return;
  }
  if (meta) {
    try { sessionStorage.setItem("st_chat_prefill", JSON.stringify({ id: charId, ...meta })); } catch (_) {}
  }
  location.href = `/chat.html?character_id=${charId}`;
}

function renderBottomNav(active, user) {
  const adminLink = user && user.is_admin
    ? `<a href="/admin.html" class="${active === "admin" ? "active" : ""}">管理</a>`
    : "";
  return `
    <nav class="bottom-nav" aria-label="主导航">
      <a href="/index.html" class="${active === "home" ? "active" : ""}"><span>首页</span></a>
      <a href="/discover.html" class="${active === "discover" ? "active" : ""}"><span>发现</span></a>
      <a href="/characters.html" class="${active === "characters" ? "active" : ""}"><span>角色</span></a>
      <a href="/chat.html" class="${active === "chat" ? "active" : ""}"><span>对话</span></a>
      <a href="/settings.html" class="${active === "settings" ? "active" : ""}"><span>我的</span></a>
      ${adminLink}
    </nav>`;
}

function renderSidebar(active, user) {
  const adminLink = user && user.is_admin
    ? `<a href="/admin.html" class="${active === "admin" ? "active" : ""}">管理后台</a>`
    : "";
  return `
    <div class="sidebar">
      <div class="logo">🍺 shanaTavern</div>
      <nav>
        <a href="/index.html" class="${active === "home" ? "active" : ""}">首页</a>
        <a href="/discover.html" class="${active === "discover" ? "active" : ""}">发现</a>
        <a href="/characters.html" class="${active === "characters" ? "active" : ""}">角色</a>
        <a href="/chat.html" class="${active === "chat" ? "active" : ""}">对话</a>
        <a href="/ingredients.html" class="${active === "ingredients" ? "active" : ""}">配料 & 配方</a>
        <a href="/settings.html" class="${active === "settings" ? "active" : ""}">设置</a>
        ${adminLink}
      </nav>
      <div class="user-info">
        ${user ? escHtml(user.nickname || user.username) : ""}
        <br><a href="#" id="logout-btn">退出登录</a>
      </div>
    </div>`;
}

function mountShell(active, opts = {}) {
  if (!API.token) {
    window.location.href = "/login.html";
    return;
  }

  const mobile = isMobileLayout();
  const cachedUser = _readCachedUser();
  if (cachedUser) {
    window._tmUser = cachedUser;
    _paintShell(active, cachedUser, mobile);
    if (!opts.bootstrap) _refreshUserInBackground();
  } else {
    document.body.className = `page-${active}${mobile ? " mobile" : ""}`;
    const shell = document.getElementById("app-shell");
    if (shell) {
      shell.innerHTML = `<div class="main" id="main-content"><div class="page-header"><h1>加载中…</h1></div></div>`;
    }
  }

  const authPromise = opts.bootstrap ? fetchBootstrap() : requireAuth();
  authPromise.then((user) => {
    if (!user) {
      showMainError(new Error("无法获取用户信息，请重新登录"));
      return;
    }
    window._tmUser = user;
    if (!cachedUser || cachedUser.id !== user.id) {
      _paintShell(active, user, mobile);
    } else if (mobile) {
      loadMobileChat().then(() => {
        if (typeof MobileChat !== "undefined") MobileChat.init(user);
      }).catch(() => {});
    }
    if (window.onAppReady) {
      Promise.resolve(window.onAppReady(user)).catch(showMainError);
    }
  }).catch(showMainError);
}

function _paintShell(active, user, mobile) {
  document.body.className = `page-${active}${mobile ? " mobile" : ""}`;
  const shell = document.getElementById("app-shell");
  if (!shell) return;
  shell.innerHTML =
    (mobile ? "" : renderSidebar(active, user))
    + `<div class="main" id="main-content"></div>`
    + (mobile ? renderBottomNav(active, user) : "");
  if (!mobile) {
    document.getElementById("logout-btn")?.addEventListener("click", (e) => {
      e.preventDefault();
      API.token = null;
      window.location.href = "/login.html";
    });
  }
  if (mobile) {
    loadMobileChat().then(() => {
      if (typeof MobileChat !== "undefined") MobileChat.init(user);
    }).catch(() => {});
  }
}
