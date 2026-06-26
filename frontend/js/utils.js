/** Shared DOM / formatting helpers — load before api.js */
function escHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function parseApiTime(iso) {
  if (!iso) return null;
  if (typeof iso !== "string") return new Date(iso);
  const s = iso.trim();
  if (!s) return null;
  if (/[zZ]$/.test(s) || /[+-]\d{2}:\d{2}$/.test(s)) return new Date(s);
  return new Date(`${s}Z`);
}

function formatDateTime(iso) {
  const d = parseApiTime(iso);
  if (!d || Number.isNaN(d.getTime())) return iso || "";
  return d.toLocaleString("zh-CN", { hour12: false });
}

function formatChatContent(text) {
  if (!text) return "";
  const safe = escHtml(text.trim());
  return safe
    .split(/\n{2,}/)
    .map((block) => {
      let line = block.replace(/\*([^*\n]+)\*/g, '<em class="msg-action">$1</em>');
      line = line.replace(/「([^」]+)」/g, '<span class="msg-quote">「$1」</span>');
      line = line.replace(/\n/g, "<br>");
      return `<p class="msg-para">${line}</p>`;
    })
    .join("");
}

function avatarSrcset(url) {
  if (!url) return "";
  const safe = escHtml(url);
  return `${safe} 128w, ${safe} 256w`;
}

function avatarImg(url, name, cls = "avatar", priority = false) {
  const letter = escHtml((name || "?").charAt(0));
  if (url) {
    const load = priority ? "eager" : "lazy";
    const pri = priority ? ' fetchpriority="high"' : "";
    return `<img class="${cls}" src="${escHtml(url)}" srcset="${avatarSrcset(url)}" sizes="(max-width: 768px) 64px, 128px" alt="${letter}" loading="${load}" decoding="async"${pri}>`;
  }
  return `<div class="${cls} avatar-fallback">${letter}</div>`;
}

function renderChatBubble({ role, content, char, userLabel, streaming = false }) {
  const isUser = role === "user";
  const label = isUser ? (userLabel || "你") : (char?.name || "角色");
  const body = streaming
    ? `<span class="stream-content"></span><span class="stream-cursor" aria-hidden="true"></span>`
    : formatChatContent(content);
  const avatar = !isUser && char
    ? avatarImg(char.avatar_url, char.name, "avatar avatar-sm msg-avatar")
    : "";
  const streamClass = streaming ? " msg-streaming" : "";
  return `<div class="msg ${role}${streamClass}">
    ${avatar}
    <div class="msg-body">
      <div class="role-label">${escHtml(label)}</div>
      <div class="msg-content">${body}</div>
    </div>
  </div>`;
}

function cutenessScore(tags) {
  const parts = new Set((tags || "").split(",").map(t => t.trim()).filter(Boolean));
  let score = 0;
  if (parts.has("可爱")) score += 1000;
  for (const [i, tag] of ["软萌", "兽耳", "女仆", "元气", "治愈", "校园", "偶像", "甜点", "傲娇", "俏皮", "慵懒"].entries()) {
    if (parts.has(tag)) score += 50 - i;
  }
  for (const tag of ["御姐", "冷淡", "严肃", "霸道总裁", "痞气", "佣兵", "剑客"]) {
    if (parts.has(tag)) score -= 80;
  }
  if (parts.has("男性")) score -= 200;
  return score;
}

function sortByCuteness(list) {
  if (!Array.isArray(list)) return [];
  return [...list].sort((a, b) => cutenessScore(b.tags) - cutenessScore(a.tags) || a.id - b.id);
}

function normalizeCharacterPage(data) {
  if (Array.isArray(data)) {
    return { items: data, total: data.length, page: 1, page_size: data.length, has_more: false };
  }
  if (data && Array.isArray(data.items)) return data;
  return { items: [], total: 0, page: 1, page_size: 0, has_more: false };
}

function characterItems(data) {
  return normalizeCharacterPage(data).items;
}

function isMobileLayout() {
  return window.matchMedia("(max-width: 768px)").matches;
}
