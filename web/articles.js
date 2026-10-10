/* 📅 每日文章（仅申论，嵌在时政简报的第三个标签里；数据见 rpg/articles.py）。
   列表：按来源（杂志 / 网站）、按分类、按状态（未读 / 已读 / 收藏 / 已精读）筛，能搜标题；「立即抓取」后台抓，「粘贴链接」导入单篇，「来源」里开关 / 增删来源。
   阅读：左边原文，右边「🔍 一键精读」（观点 / 论证脉络 / 金句 / 素材 / 适用题型 / 运用思路），金句和素材可一键刻成玉简。
   计时：开着一篇、2 分钟内动过，算学习时间（跟着时政简报的心跳走）。 */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = {
    get(k, d) { try { return localStorage.getItem("articles." + k) || d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("articles." + k, v); } catch (e) { /* 只管这一次 */ } },
  };
  let ROOT = null, DATA = null, POLL = null;
  let F = { src: store.get("src", ""), cat: store.get("cat", ""), st: store.get("st", ""), q: "" };
  let CUR = null, JDING = false, SRC_OPEN = false, lastAct = 0;
  const act = () => (lastAct = Date.now());
  ["click", "scroll", "keydown", "touchstart"].forEach((e) => addEventListener(e, () => { if (CUR) act(); }, { passive: true, capture: true }));

  async function load() { DATA = await api("/api/articles"); }
  async function mount(el) {
    ROOT = el;
    if (CUR) return reader();
    try { await load(); } catch (e) { showError(e); DATA = { items: [], sources: [], categories: [], job: {} }; }
    list();
    if (DATA.job && DATA.job.running) poll();
  }
  function poll() {
    clearInterval(POLL);
    POLL = setInterval(async () => {
      if (!ROOT || !ROOT.isConnected || CUR) { clearInterval(POLL); return; }
      try { await load(); } catch (e) { clearInterval(POLL); return; }
      list();
      if (!DATA.job.running) clearInterval(POLL);
    }, 1500);
  }

  function filtered() {
    const q = F.q.trim().toLowerCase();
    return DATA.items.filter((a) => (!F.src || a.source === F.src) && (!F.cat || a.category === F.cat) &&
      (!F.st || (F.st === "unread" ? !a.read : F.st === "read" ? a.read : F.st === "star" ? a.star : a.jd)) &&
      (!q || (a.title + a.source + a.lead).toLowerCase().includes(q)));
  }
  const chips = (key, opts, cur) => opts.map(([v, n, c]) => `<a class="ar-chip ${cur === v ? "on" : ""}" data-f="${key}" data-v="${esc(v)}">${esc(n)}${c != null ? `<small>${c}</small>` : ""}</a>`).join("");

  function list() {
    const I = DATA.items, shown = filtered();
    const srcNames = [...new Set(I.map((a) => a.source))];
    const cats = DATA.categories.filter((c) => I.some((a) => a.category === c));
    const job = DATA.job || {};
    const today = new Date().toISOString().slice(0, 10);
    const stat = `共 ${I.length} 篇 · 今日 ${I.filter((a) => a.date === today).length} · 未读 ${I.filter((a) => !a.read).length} · 已精读 ${I.filter((a) => a.jd).length}`;
    ROOT.innerHTML = `<div class="ar-wrap">
      <div class="card ar-bar">
        <div class="row"><b>📅 每日文章</b><span class="muted small">${stat}</span><span class="spacer"></span>
          <input id="arQ" type="search" placeholder="搜标题 / 来源…" value="${esc(F.q)}">
          <button class="ghost small" id="arUrl">🔗 粘贴链接</button>
          <button class="ghost small" id="arSrc">⚙ 来源</button>
          <button class="primary" id="arCrawl" ${job.running ? "disabled" : ""}>${job.running ? `抓取中 ${job.done}/${job.total}…` : "⬇ 立即抓取"}</button></div>
        ${job.log && job.log.length ? `<div class="ar-log small">${job.log.map((x) => `<div>${esc(x)}</div>`).join("")}</div>` : ""}
        <div class="ar-chips"><span class="faint small">来源</span>${chips("src", [["", "全部", I.length], ...srcNames.map((n) => [n, n, I.filter((a) => a.source === n).length])], F.src)}</div>
        <div class="ar-chips"><span class="faint small">分类</span>${chips("cat", [["", "全部", null], ...cats.map((c) => [c, c, I.filter((a) => a.category === c).length])], F.cat)}</div>
        <div class="ar-chips"><span class="faint small">状态</span>${chips("st", [["", "全部"], ["unread", "未读"], ["read", "已读"], ["star", "★ 收藏"], ["jd", "已精读"]], F.st)}</div>
        <div id="arSrcBox" ${SRC_OPEN ? "" : "hidden"}>${srcHtml()}</div></div>
      ${shown.length ? `<div class="ar-list">${shown.map(card).join("")}</div>` :
        `<div class="card ar-empty"><div class="ar-empty-ico">📅</div><h3>${I.length ? "没有符合筛选的文章" : "还没有文章"}</h3>
          <p class="muted">${I.length ? "换个来源 / 分类 / 状态试试。" : "点右上「⬇ 立即抓取」，从打开的来源里抓最新的评论和理论文章，存在你的库里（训练/时政文章）。<br>也可以「🔗 粘贴链接」导入某一篇。"}</p></div>`}
    </div>`;
    bindList();
  }
  function card(a) {
    return `<a class="card ar-item ${a.read ? "read" : ""}" data-open="${esc(a.id)}">
      <div class="ar-item-t">${a.star ? "★ " : ""}${esc(a.title)}</div>
      <div class="ar-item-m"><span class="tag">${esc(a.source)}</span><span class="tag">${esc(a.category)}</span><span class="faint small">${esc(a.date)} · ${a.chars} 字</span>
        ${a.read ? `<span class="faint small">✓ 已读</span>` : `<span class="ar-new small">未读</span>`}${a.jd ? `<span class="ar-jd small">精读</span>` : ""}</div>
      <div class="ar-item-l muted small">${esc(a.lead)}</div></a>`;
  }
  function srcHtml() {
    const S = DATA.sources;
    return `<div class="ar-src"><div class="muted small">打开 / 关闭抓取的来源。标「未实测」的是默认关闭的，开了抓不到就关掉；也可以加自己的来源（填列表页网址，程序自动找文章链接）。</div>
      ${S.map((s) => `<div class="ar-src-row"><label><input type="checkbox" data-tog="${esc(s.name)}" ${s.on ? "checked" : ""}> <b>${esc(s.name)}</b>${s.untested ? ` <span class="tag">未实测</span>` : ""}</label>
        <span class="faint small">${esc(s.url)}</span>${s.builtin ? "" : `<button class="ghost small" data-rm="${esc(s.name)}">删</button>`}</div>`).join("")}
      <div class="ar-src-add row"><input id="arSN" placeholder="来源名称" style="width:140px"><input id="arSU" placeholder="列表页网址 http://…" style="flex:1;min-width:200px">
        <select id="arSC"><option value="">分类自动判断</option>${DATA.categories.map((c) => `<option>${esc(c)}</option>`).join("")}</select>
        <button class="small" id="arSAdd">＋ 添加</button></div></div>`;
  }
  function bindList() {
    const R = ROOT;
    R.querySelectorAll("[data-f]").forEach((a) => (a.onclick = () => { F[a.dataset.f] = a.dataset.v; store.set(a.dataset.f, a.dataset.v); list(); }));
    const q = R.querySelector("#arQ");
    q.oninput = () => { F.q = q.value; const pos = q.selectionStart; list(); const n = ROOT.querySelector("#arQ"); n.focus(); n.setSelectionRange(pos, pos); };
    R.querySelectorAll("[data-open]").forEach((a) => (a.onclick = () => open(a.dataset.open)));
    R.querySelector("#arCrawl").onclick = async () => {
      try { const r = await api("/api/articles/crawl", {}); if (!r.started) toast("上一次抓取还在进行"); await load(); list(); poll(); } catch (e) { showError(e); }
    };
    R.querySelector("#arUrl").onclick = async () => {
      const url = prompt("粘贴文章链接（http 开头）：");
      if (!url) return;
      try { const r = await api("/api/articles/import_url", { url }); toast(r.new ? `✅ 已导入《${esc(r.title)}》` : "这篇已经在库里了"); await load(); list(); if (r.id) open(r.id); } catch (e) { showError(e); }
    };
    R.querySelector("#arSrc").onclick = () => { SRC_OPEN = !SRC_OPEN; R.querySelector("#arSrcBox").hidden = !SRC_OPEN; };
    R.querySelectorAll("[data-tog]").forEach((c) => (c.onchange = async () => { try { await api("/api/articles/source", { act: "toggle", name: c.dataset.tog, on: c.checked }); await load(); list(); } catch (e) { showError(e); } }));
    R.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = async () => { if (!confirm("删掉来源“" + b.dataset.rm + "”？（已抓的文章不删）")) return; try { await api("/api/articles/source", { act: "remove", name: b.dataset.rm }); await load(); list(); } catch (e) { showError(e); } }));
    const add = R.querySelector("#arSAdd");
    if (add) add.onclick = async () => {
      try { await api("/api/articles/source", { act: "add", name: R.querySelector("#arSN").value, url: R.querySelector("#arSU").value, category: R.querySelector("#arSC").value }); await load(); list(); }
      catch (e) { showError(e); }
    };
  }

  // ---------------------------------------------------------------- 阅读 + 精读
  async function open(id) {
    try { CUR = await api("/api/articles/get", { id }); act(); reader(); window.scrollTo(0, 0); } catch (e) { showError(e); }
  }
  function close() { CUR = null; JDING = false; if (ROOT && ROOT.isConnected) mount(ROOT); }
  function jdHtml(jd) {
    if (!jd) return `<div class="muted small">让 AI 把这篇文章提炼成：主旨、观点、论证脉络、可背的金句、可用素材、适合练的题型。金句保证是原文里真有的句子。结果会存下来，不重复花钱。</div>
      <button class="primary" id="arJd" ${JDING ? "disabled" : ""}>${JDING ? "精读中…" : "🔍 一键精读"}</button>`;
    const li = (a) => `<ul>${a.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
    return `<div class="ar-jd-box"><div class="ar-theme">${esc(jd.theme)}</div>
      <h4>核心观点</h4>${li(jd.points)}
      ${jd.structure.length ? `<h4>论证脉络</h4><ol>${jd.structure.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>` : ""}
      ${jd.quotes.length ? `<h4>金句</h4>${jd.quotes.map((q) => `<blockquote>${esc(q.text)}<small>${esc(q.use)}</small></blockquote>`).join("")}` : ""}
      ${jd.materials.length ? `<h4>可用素材</h4>${jd.materials.map((m) => `<div class="ar-mat"><span class="tag">${esc(m.kind)}</span> ${esc(m.text)}</div>`).join("")}` : ""}
      ${jd.tixing.length ? `<h4>适合练的题型</h4><div>${jd.tixing.map((t) => `<span class="tag">${esc(t)}</span>`).join(" ")}</div>` : ""}
      ${jd.writing ? `<h4>运用思路</h4><p>${esc(jd.writing)}</p>` : ""}
      <div class="row ar-jd-foot"><button class="small" id="arCard" ${jd.carded ? "disabled" : ""}>${jd.carded ? "✓ 已刻成玉简" : "🧧 金句 / 素材刻成玉简"}</button>
        <button class="ghost small" id="arRe">重新精读</button><span class="faint small">${esc(jd.time || "")}</span></div></div>`;
  }
  function reader() {
    const a = CUR;
    ROOT.innerHTML = `<div class="ar-read">
      <div class="card ar-rhead"><button class="ghost" id="arBack">← 返回文章列表</button><span class="spacer"></span>
        <select id="arCat">${DATA.categories.map((c) => `<option ${c === a.category ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>
        <button class="ghost small" id="arStar">${a.star ? "★ 已收藏" : "☆ 收藏"}</button>
        ${a.url ? `<a class="ghost small btn" href="${esc(a.url)}" target="_blank" rel="noopener">🌐 原网页</a>` : ""}
        <button class="ghost small" id="arDel">🗑</button></div>
      <div class="ar-cols"><article class="card ar-art"><h2>${esc(a.title)}</h2>
        <div class="ar-item-m"><span class="tag">${esc(a.source)}</span><span class="faint small">${esc(a.date)}</span></div>
        ${a.paras.map((p) => `<p>${esc(p)}</p>`).join("")}</article>
        <aside class="card ar-side" id="arSide">${jdHtml(a.jd)}</aside></div></div>`;
    bindReader();
  }
  function bindReader() {
    const R = ROOT, a = CUR;
    R.querySelector("#arBack").onclick = close;
    R.querySelector("#arStar").onclick = async () => { a.star = !a.star; await api("/api/articles/mark", { id: a.id, star: a.star }); reader(); };
    R.querySelector("#arCat").onchange = async (e) => { try { await api("/api/articles/category", { id: a.id, category: e.target.value }); a.category = e.target.value; } catch (x) { showError(x); } };
    R.querySelector("#arDel").onclick = async () => { if (!confirm("删掉这篇文章（连精读一起）？")) return; try { await api("/api/articles/delete", { id: a.id }); CUR = null; mount(ROOT); } catch (e) { showError(e); } };
    bindSide();
  }
  function bindSide() {
    const R = ROOT, a = CUR;
    const run = async (force) => {
      JDING = true; act(); R.querySelector("#arSide").innerHTML = jdHtml(null);
      try { const r = await api("/api/articles/jd", { id: a.id, force: !!force }); a.jd = r.jd; } catch (e) { showError(e); }
      JDING = false; if (CUR === a) { R.querySelector("#arSide").innerHTML = jdHtml(a.jd); bindSide(); }
    };
    const b = R.querySelector("#arJd"); if (b) b.onclick = () => run(false);
    const re = R.querySelector("#arRe"); if (re) re.onclick = () => { if (confirm("重新精读会再花一次 AI 费用，确定？")) run(true); };
    const c = R.querySelector("#arCard");
    if (c) c.onclick = async () => {
      try { const r = await api("/api/articles/cards", { id: a.id }); a.jd.carded = true; toast(`🧧 刻了 ${r.added || 0} 枚玉简（${esc(r.deck || "")}）`); R.querySelector("#arSide").innerHTML = jdHtml(a.jd); bindSide(); } catch (e) { showError(e); }
    };
  }

  const active = () => !!(CUR && VIEW === "tianji" && document.visibilityState === "visible" && Date.now() - lastAct < 120000);
  window.ARTICLES = { mount, close, isOpen: () => !!CUR, active };
})();
