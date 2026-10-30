/* 📅 每日文章（仅申论，嵌在时政简报的第三个标签里；数据见 rpg/articles.py）。
   列表：按来源（杂志 / 网站）、按分类、按状态（未读 / 已读 / 收藏 / 已精读）筛，能搜标题；「立即抓取」后台抓，「粘贴链接」导入单篇，「来源」里开关 / 增删来源。
   阅读：左边原文，右边「🔍 一键精读」（五步拆解：圈核心概念 / 拆行文骨架 / 挖万能对策 / 记黄金句式 / 做题型映射），对策和黄金句式可存入档案室「摘编」。
   计时：开着一篇、2 分钟内动过，算学习时间（跟着时政简报的心跳走）。 */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = {
    get(k, d) { try { return localStorage.getItem("articles." + k) || d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("articles." + k, v); } catch (e) { /* 只管这一次 */ } },
  };
  let ROOT = null, DATA = null, POLL = null;
  let F = { src: store.get("src", ""), cat: store.get("cat", ""), st: store.get("st", ""), q: "" };
  let CUR = null, JDING = false, SRC_OPEN = false, CRAWL_OPEN = false, lastAct = 0, readerVer = 0;
  let FETCH = { count: Number(store.get("count", "10")), range: store.get("range", "7d"), categories: [], sources: null };
  try { FETCH.categories = JSON.parse(store.get("fetchCats", "[]")); FETCH.sources = JSON.parse(store.get("fetchSources", "null")); } catch (_) {}
  const act = () => (lastAct = Date.now());
  ["click", "scroll", "keydown", "touchstart"].forEach((e) => addEventListener(e, () => { if (CUR) act(); }, { passive: true, capture: true }));

  async function load() { DATA = await api("/api/articles"); }
  async function mount(el) {
    if(!CUR)window.STUDY_LAMP?.reader(null);
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
        <div id="arFetchBox" ${CRAWL_OPEN ? "" : "hidden"}>${fetchHtml()}</div>
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
  function fetchHtml() {
    const names = FETCH.sources === null ? DATA.sources.filter((s) => s.on).map((s) => s.name) : FETCH.sources;
    return `<section class="ar-fetch"><h3>抓取设置</h3><div class="row"><label>合计抓取 <input id="arFetchCount" type="number" min="1" max="100" value="${esc(FETCH.count)}"> 篇</label>
      ${[5,10,15,30].map((n) => `<button class="ghost small" data-count="${n}">${n}篇</button>`).join("")}
      <label>发布时间 <select id="arFetchRange">${[["7d","近七日"],["1m","近一个月"],["6m","近半年"]].map(([v,n]) => `<option value="${v}" ${v === FETCH.range ? "selected" : ""}>${n}</option>`).join("")}</select></label></div>
      <fieldset><legend>文章分类（可多选，不选表示全部）</legend><div class="ar-fetch-options">${DATA.categories.map((c) => `<label><input type="checkbox" data-fetch-cat="${esc(c)}" ${FETCH.categories.includes(c) ? "checked" : ""}>${esc(c)}</label>`).join("")}</div></fieldset>
      <fieldset><legend>抓取来源</legend><div class="ar-fetch-options">${DATA.sources.map((s) => `<label><input type="checkbox" data-fetch-src="${esc(s.name)}" ${names.includes(s.name) ? "checked" : ""}>${esc(s.name)}</label>`).join("")}</div></fieldset>
      <div class="row"><span class="muted small">按发布日期筛选、优先较新文章；重复文章不计入数量。历史内容取决于网站提供的列表，不足时显示实际篇数。</span><span class="spacer"></span><button class="primary" id="arFetchStart" ${DATA.job?.running ? "disabled" : ""}>开始抓取</button></div></section>`;
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
    R.querySelector("#arCrawl").onclick = () => { CRAWL_OPEN = !CRAWL_OPEN; R.querySelector("#arFetchBox").hidden = !CRAWL_OPEN; };
    R.querySelector("#arFetchCount").onchange = (e) => { FETCH.count = Number(e.target.value); store.set("count", FETCH.count); };
    R.querySelector("#arFetchRange").onchange = (e) => { FETCH.range = e.target.value; store.set("range", FETCH.range); };
    R.querySelectorAll("[data-fetch-cat]").forEach((b) => (b.onchange = () => {
      FETCH.categories = [...R.querySelectorAll("[data-fetch-cat]:checked")].map((x) => x.dataset.fetchCat); store.set("fetchCats", JSON.stringify(FETCH.categories));
    }));
    R.querySelectorAll("[data-fetch-src]").forEach((b) => (b.onchange = () => {
      FETCH.sources = [...R.querySelectorAll("[data-fetch-src]:checked")].map((x) => x.dataset.fetchSrc); store.set("fetchSources", JSON.stringify(FETCH.sources));
    }));
    R.querySelectorAll("[data-count]").forEach((b) => (b.onclick = () => { FETCH.count = Number(b.dataset.count); store.set("count", FETCH.count); R.querySelector("#arFetchCount").value = FETCH.count; }));
    R.querySelector("#arFetchStart").onclick = async () => {
      FETCH.count = Number(R.querySelector("#arFetchCount").value);
      FETCH.sources = [...R.querySelectorAll("[data-fetch-src]:checked")].map((x) => x.dataset.fetchSrc);
      if (!Number.isInteger(FETCH.count) || FETCH.count < 1 || FETCH.count > 100) return toast("请填写1–100的整数篇数");
      if (!FETCH.sources.length) return toast("请至少选择一个来源");
      store.set("count", FETCH.count); store.set("fetchSources", JSON.stringify(FETCH.sources));
      try { const r = await api("/api/articles/crawl", FETCH); if (!r.started) toast("上一次抓取还在进行"); CRAWL_OPEN = false; await load(); list(); poll(); } catch (e) { showError(e); }
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
    if (!(await NOTES.leaveArticle())) return;
    try { CUR = await api("/api/articles/get", { id }); act(); reader(); window.scrollTo(0, 0); } catch (e) { showError(e); }
  }
  async function close() { if (!(await NOTES.leaveArticle())) return false; readerVer++; CUR = null; window.STUDY_LAMP?.reader(null); JDING = false; if (ROOT && ROOT.isConnected) await mount(ROOT); return true; }
  // 一键精读：按“五步拆解心法”分步显示（第六步“模拟输出”由自己做，不在这里）。旧版精读（无 version）照常显示，点“重新精读”换新版。
  const JD_INTRO = "让 AI 按五步拆解心法精读这篇：①圈核心概念 ②拆行文骨架 ③挖万能对策 ④记黄金句式 ⑤做题型映射。词语、原文方向、金句保证是原文里真有的。结果会存下来，不重复花钱。";
  function jdHtml(jd) {
    if (!jd) return `<div class="muted small">${JD_INTRO}</div>
      <button class="primary" id="arJd" ${JDING ? "disabled" : ""}>${JDING ? "精读中…" : "🔍 一键精读"}</button>`;
    if (jd.version === 2) return jdHtmlV2(jd);
    const li = (a) => `<ul>${a.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
    return `<div class="ar-jd-box"><p class="small warn">这是旧版精读。点最下面“重新精读”换成五步拆解（会再花一次 AI 费用）。</p><div class="ar-theme">${esc(jd.theme)}</div>
      <h4>核心观点</h4>${li(jd.points || [])}
      ${(jd.structure || []).length ? `<h4>论证脉络</h4><ol>${jd.structure.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>` : ""}
      ${(jd.quotes || []).length ? `<h4>金句</h4>${jd.quotes.map((q) => `<blockquote>${esc(q.text)}<small>${esc(q.use)}</small></blockquote>`).join("")}` : ""}
      ${(jd.materials || []).length ? `<h4>可用素材</h4>${jd.materials.map((m) => `<div class="ar-mat"><span class="tag">${esc(m.kind)}</span> ${esc(m.text)}</div>`).join("")}` : ""}
      ${(jd.tixing || []).length ? `<h4>适合练的题型</h4><div>${jd.tixing.map((t) => `<span class="tag">${esc(t)}</span>`).join(" ")}</div>` : ""}
      ${jd.writing ? `<h4>运用思路</h4><p>${esc(jd.writing)}</p>` : ""}
      <div class="row ar-jd-foot"><button class="ghost small" id="arRe">重新精读</button><span class="faint small">${esc(jd.time || "")}</span></div></div>`;
  }
  function jdHtmlV2(jd) {
    const s1 = jd.step1 || {}, s2 = jd.step2 || {}, s3 = jd.step3 || {}, s4 = jd.step4 || {}, s5 = jd.step5 || {};
    const tag = (t) => `<span class="tag">${esc(t)}</span>`;
    const words = (rows, note) => rows.map((x) => `<li><b>${esc(x.term)}</b>${x[note] ? `<span class="muted small"> · ${esc(x[note])}</span>` : ""}</li>`).join("");
    const group = (title, rows, note) => rows.length ? `<h5>${title}</h5><ul class="ar-terms">${words(rows, note)}</ul>` : "";
    const step = (no, name, body, open = true) => `<details class="ar-step" ${open ? "open" : ""}><summary>第${no}步 · ${name}</summary>${body || '<p class="muted small">这一步没有提炼出可靠的内容。</p>'}</details>`;
    const byDomain = {};
    (s3.items || []).forEach((x) => (byDomain[x.domain] = byDomain[x.domain] || []).push(x));
    const quoteKinds = { "巧用形象": "巧用形象的", "辩证论述": "辩证论述的", "标题段首句": "标题 / 段首句" };
    const p1 = group("老词新用", s1.old_words || [], "note") + group("动词结构", s1.verbs || [], "note") + group("新提法", s1.new_terms || [], "definition");
    const p2 = `<p><b>总论点</b>（提出问题）：${esc(s2.thesis || "")}</p>`
      + ((s2.parts || []).length ? `<h5>分论点</h5><ol class="ar-parts">${s2.parts.map((x) => `<li>${tag(x.kind)} ${esc(x.point)}</li>`).join("")}</ol>` : "")
      + ((s2.paragraphs || []).length ? `<h5>每段大意</h5><ul class="ar-paras">${s2.paragraphs.map((x) => `<li><span class="faint small">第${x.no}段</span> ${tag(x.type)} ${esc(x.summary)}</li>`).join("")}</ul>` : "");
    const p3 = Object.keys(byDomain).map((d) => `<h5>${esc(d)}</h5>${byDomain[d].map((x) => `<div class="ar-act"><div class="ar-act-dir">原文：${esc(x.direction)}</div><div>落地：${esc(x.landing)} ${tag(x.source)}</div></div>`).join("")}`).join("");
    const p4 = Object.keys(quoteKinds).map((k) => { const rows = (s4.quotes || []).filter((q) => q.kind === k); return rows.length ? `<h5>${quoteKinds[k]}</h5>${rows.map((q) => `<blockquote>${esc(q.text)}${q.use ? `<small>${esc(q.use)}</small>` : ""}</blockquote>`).join("")}` : ""; }).join("");
    const p5 = ((s5.yuyan || []).length ? `<h5>言语理解</h5><ul>${s5.yuyan.map((x) => `<li>${tag(x.type)} ${esc(x.question)}</li>`).join("")}</ul>` : "")
      + ((s5.shenlun || []).length ? `<h5>申论</h5><ul>${s5.shenlun.map((x) => `<li>${tag(x.type)} ${esc(x.question)}</li>`).join("")}</ul>` : "");
    const saved = !!(CUR && CUR.digest);
    return `<div class="ar-jd-box ar-jd2">${step(1, "圈核心概念", p1)}${step(2, "拆行文骨架", p2)}${step(3, "挖万能对策", p3)}${step(4, "记黄金句式", p4)}${step(5, "做题型映射", p5)}
      <div class="row ar-jd-foot"><button class="small" id="arDigest" title="把第三步的对策和第四步的黄金句式存到 档案室 › 摘编，只翻阅，不生成复习卡片">${saved ? "✓ 已存入摘编（再点覆盖）" : "📎 存入摘编"}</button>${saved ? '<button class="ghost small" id="arDigestGo">去档案室看</button>' : ""}
        <button class="ghost small" id="arRe">重新精读</button><span class="faint small">${esc(jd.time || "")}</span></div></div>`;
  }
  async function reader() {
    if (!(await NOTES.leaveArticle())) return;
    const a = CUR, version = ++readerVer;
    if(a&&VIEW==='tianji'&&ROOT?.isConnected)window.STUDY_LAMP?.reader({key:'article:'+a.id,board:''});
    if (!a || !ROOT?.isConnected) return;
    ROOT.innerHTML = `<div class="ar-read">
      <div class="card ar-rhead"><button class="ghost" id="arBack">← 返回文章列表</button><span class="spacer"></span>
        <select id="arCat">${DATA.categories.map((c) => `<option ${c === a.category ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>
        <button class="ghost small" id="arStar">${a.star ? "★ 已收藏" : "☆ 收藏"}</button>
        ${a.url ? `<a class="ghost small btn" href="${esc(a.url)}" target="_blank" rel="noopener">🌐 原网页</a>` : ""}
        <button class="ghost small" id="arSideToggle" title="展开 / 收起右侧精读栏">🔍 精读栏</button>
        <button class="ghost small" id="arLedger">📓 公务手账</button><button class="ghost small" id="arDel">🗑</button></div>
      <div class="ar-cols ar-annotate ${store.get("side", "open") === "closed" ? "ar-side-closed" : ""}"><article id="arBook"><div class="card">正在打开文章批注本…</div></article>
        <aside class="card ar-side" id="arSide">${jdHtml(a.jd)}</aside></div></div>`;
    bindReader();
    const el = ROOT.querySelector("#arBook");
    try { await NOTES.mountArticle(el, a.id); }
    catch (e) { if (version === readerVer && el.isConnected) el.innerHTML = `<div class="card ar-art"><p class="warn">批注本未打开：${esc(e.message)}。返回列表重试；已保存的笔迹仍在公务手账。</p><h2>${esc(a.title)}</h2>${a.paras.map((p) => `<p>${esc(p)}</p>`).join("")}</div>`; }
  }
  function bindReader() {
    const R = ROOT, a = CUR;
    R.querySelector("#arBack").onclick = close;
    R.querySelector("#arLedger").onclick = () => go("notes");
    R.querySelector("#arSideToggle").onclick = () => { const cols = R.querySelector(".ar-cols"); const closed = cols.classList.toggle("ar-side-closed"); store.set("side", closed ? "closed" : "open"); dispatchEvent(new Event("resize")); };
    R.querySelector("#arStar").onclick = async () => { a.star = !a.star; await api("/api/articles/mark", { id: a.id, star: a.star }); reader(); };
    R.querySelector("#arCat").onchange = async (e) => { try { await api("/api/articles/category", { id: a.id, category: e.target.value }); a.category = e.target.value; } catch (x) { showError(x); } };
    R.querySelector("#arDel").onclick = async () => { if (!confirm("删掉这篇文章（连精读一起）？公务手账里的批注本和已存入的摘编会保留。")) return; try { if (!(await NOTES.leaveArticle())) return; await api("/api/articles/delete", { id: a.id }); CUR = null; mount(ROOT); } catch (e) { showError(e); } };
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
    const c = R.querySelector("#arDigest");
    if (c) c.onclick = async () => {
      try { const r = await api("/api/articles/digest_save", { id: a.id }); a.digest = true; toast(`📎 已存入摘编：${r.countermeasures} 条对策、${r.quotes} 句黄金句式（档案室 › 摘编）`); R.querySelector("#arSide").innerHTML = jdHtml(a.jd); bindSide(); } catch (e) { showError(e); }
    };
    const go2 = R.querySelector("#arDigestGo"); if (go2) go2.onclick = () => { LIB.tab = "digest"; go("skeleton"); };
  }

  const active = () => !!(CUR && VIEW === "tianji" && document.visibilityState === "visible" && Date.now() - lastAct < 120000);
  window.ARTICLES = { mount, close, isOpen: () => !!CUR, active };
})();
