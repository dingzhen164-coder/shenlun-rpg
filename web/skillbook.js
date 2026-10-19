/* 藏经阁·心法（skill）：每个板块的解题方法，可随时在这里看、改（数据来自 /api/skillbook，见 rpg/skillbook.py）。
   先是一排会浮动的古籍书架（一个板块一本），点开才进入全屏的阅读/修改页；“解惑会读到什么”的计算较慢，打开板块时才算并缓存。
   没有“我的版本”：直接改就是了，第一次保存时程序自动把库里原来的 skill 复制到 训练/技能/<板块>/，之后每次修改前的样子都留在历史里。
   阅读区用 MDLITE 渲染（逻辑符号、表格、英文小标题换中文）；修改区永远是原文。
   状态留在本模块里：切到别的页面再回来，书架立刻出现，选中的板块、文件和没保存的草稿都还在。 */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const POS = "skillbook-pos";
  let DATA = [], LOADED = false, SHELF = true, PLANS = {}, BOARD = "", FILE = "", CUR = null, MODE = "view", DRAFT = "", HIST = null, PREVIEW = null, NOTE = "", BUSY = false;
  let PROPS = [], AI = false, TAB = "files", PROPS_OPEN = false;
  const name = () => (window.W ? W("skillbook") : "心法");
  const board = () => DATA.find((b) => b.board === BOARD) || null;
  const plan = () => PLANS[BOARD] || null;
  const savePos = () => { try { localStorage.setItem(POS, JSON.stringify({ b: BOARD, f: FILE })); } catch {} };
  const loadPos = () => { try { return JSON.parse(localStorage.getItem(POS) || "{}"); } catch { return {}; } };
  const num = (n) => Number(n || 0).toLocaleString("en-US");
  const read = (t) => (window.MDLITE ? MDLITE.render(t) : `<pre>${esc(t)}</pre>`);
  const nice = (rel, title) => (window.MDLITE ? MDLITE.friendly(rel, title) : rel);

  async function loadFile(rel) {
    const b = board();
    if (!b || !rel) { CUR = null; return; }
    FILE = rel; savePos();
    try { CUR = await api("/api/skillbook/file", { board: b.board, path: rel }); } catch (e) { CUR = null; NOTE = e.message; }
  }

  async function loadProps() {
    const b = board();
    PROPS = [];
    if (!b) return;
    try { PROPS = (await api("/api/skillbook/proposals", { board: b.board })).proposals; } catch { PROPS = []; }
  }

  async function loadPlan() {
    const b = board();
    if (!b || b.mode === "none" || PLANS[b.board]) return;
    try { PLANS[b.board] = await api("/api/skillbook/plan", { board: b.board }); } catch { PLANS[b.board] = { items: [], total: 0, words: 0, limit: 0, mode: b.mode, failed: true }; }
  }

  async function overview() {
    const v = await api("/api/skillbook");
    DATA = v.boards; AI = !!v.ai; LOADED = true;
  }

  async function reload(keepFile) {
    PLANS = {};
    await overview();
    const p = loadPos();
    if (!board()) BOARD = DATA.some((b) => b.board === p.b) ? p.b : (DATA[0]?.board || "");
    const b = board();
    if (b) {
      const pick = keepFile && b.files.includes(keepFile) ? keepFile : (b.files.includes(p.f) && !keepFile ? p.f : b.files[0]);
      await loadFile(pick);
    } else CUR = null;
    await loadProps();
    paint(); loadPlan().then(paintSide);          // 先出内容，读取情况算好了再补上
  }

  function meter(b) {
    if (b.mode === "none") return "";
    const pl = plan();
    if (!pl) return '<div class="skb-meter small muted" role="status">正在计算解惑时会读到什么……</div>';
    if (pl.failed) return '<div class="skb-meter small muted">读取情况暂时算不出来，不影响查看和修改。</div>';
    const pct = Math.min(100, Math.round((pl.total / pl.limit) * 100));
    const skipped = pl.items.filter((i) => !i.read);
    const mats = pl.items.filter((i) => i.kind === "material" && i.read).length;
    return `<div class="skb-meter" role="group" aria-label="解惑读取情况">
      <div class="small" title="字数按汉字和单词算，不含符号、空格和标记；读取上限按字符算（${num(pl.total)} / ${num(pl.limit)} 字符）"><b>解惑时会读：</b>${pl.items.filter((i) => i.read).length} 个文件${mats ? `（含 ${mats} 份引用的资料）` : ""} · 约 <b>${num(pl.words)}</b> 字 · 占读取上限 ${pct}%</div>
      <div class="skb-bar"><i style="width:${pct}%"></i></div>
      ${skipped.length ? `<div class="skb-warn small">⚠ ${skipped.length} 个文件超出上限没有读入：${skipped.map((i) => esc(i.rel) + "（" + num(i.words) + " 字）").join("、")}。请精简或拆分。</div>` : ""}</div>`;
  }

  function chips(b) {
    const info = Object.fromEntries((plan()?.items || []).filter((i) => i.kind === "method").map((i) => [i.rel, i]));
    return `<div class="skb-files" role="tablist">${b.files.map((f) => {
      const i = info[f];
      return `<button role="tab" class="skb-chip ${f === FILE ? "on" : ""}" data-skb-file="${esc(f)}" aria-selected="${f === FILE}" title="${esc(f)}"><span>${esc(nice(f, i?.title))}</span>${i ? `<small>${num(i.words)}字${i.read ? "" : " · 未读入"}</small>` : ""}</button>`;
    }).join("")}</div>`;
  }

  function banner(b) {
    if (b.mode === "none") return `<div class="skb-banner">这个板块还没有${esc(name())}。${b.source ? `（规则里写的 skill「${esc(b.source)}」在库里没找到。）` : ""}可以新建一份标准模板，再随时修改。</div>`;
    return `<div class="skb-banner skb-tip2">直接修改就行：保存后下一次解惑就按新内容讲，每次修改前的样子都留在「🕘 历史」里，可以回滚。</div>`;
  }

  function toolbar(b) {
    const learn = b.mode !== "none" ? `<button class="ghost small" data-skb="organize" ${AI ? "" : "disabled"} title="${AI ? "让 AI 把这份心法改写成你能学的“学习版”：怎么用、识别信号、方法卡、陷阱、示范、速查（调用 AI，生成待审建议，不改现有文件）" : "需要先在设置里填 AI 的 API key"}">✨ 生成学习版</button>` : "";
    if (b.mode === "none") return `<button class="primary small" data-skb="template">＋ 新建标准模板</button>`;
    return `<button class="primary small" data-skb="edit" ${CUR ? "" : "disabled"}>✎ 修改</button>
      <button class="ghost small" data-skb="history" ${CUR ? "" : "disabled"}>🕘 历史</button><button class="ghost small" data-skb="newfile">＋ 新建文件</button>
      <button class="ghost small" data-skb="rename" ${CUR && FILE !== "SKILL.md" ? "" : "disabled"}>改名</button><button class="ghost small" data-skb="delete" ${CUR ? "" : "disabled"}>🗑 删除</button>${learn}`;
  }

  // 修改前后对比（按行）：只给“整个文件替换”的建议用，文件不大，简单的最长公共子序列就够
  function lineDiff(a, b) {
    const x = String(a).split("\n"), y = String(b).split("\n");
    if (x.length * y.length > 160000) return `<div class="skb-add">${esc(b)}</div>`;
    const L = Array.from({ length: x.length + 1 }, () => new Array(y.length + 1).fill(0));
    for (let i = x.length - 1; i >= 0; i--) for (let j = y.length - 1; j >= 0; j--) L[i][j] = x[i] === y[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    const out = []; let i = 0, j = 0;
    while (i < x.length && j < y.length) {
      if (x[i] === y[j]) { out.push(`<div class="skb-same">${esc(x[i])}</div>`); i++; j++; }
      else if (L[i + 1][j] >= L[i][j + 1]) out.push(`<div class="skb-del">− ${esc(x[i++])}</div>`);
      else out.push(`<div class="skb-add">+ ${esc(y[j++])}</div>`);
    }
    while (i < x.length) out.push(`<div class="skb-del">− ${esc(x[i++])}</div>`);
    while (j < y.length) out.push(`<div class="skb-add">+ ${esc(y[j++])}</div>`);
    return out.join("");
  }

  function proposals() {
    if (!PROPS.length) return "";
    return `<div class="skb-props" role="region" aria-label="待审建议">${PROPS.map((p) => `<div class="skb-prop" data-pid="${esc(p.id)}">
      <div class="skb-prop-h"><b>📝 ${esc(p.summary || "建议")}</b><span class="small faint">${esc(p.created)}${p.source?.label ? " · " + esc(p.source.label) : ""}</span></div>
      ${(p.meta?.changelog || []).length ? `<div class="small muted">${p.meta.changelog.map(esc).join("；")}</div>` : ""}
      ${p.edits.length > 6 ? `<div class="skb-bulk small"><button class="ghost small" data-skb="pick-all" data-pid="${esc(p.id)}">全选</button><button class="ghost small" data-skb="pick-none" data-pid="${esc(p.id)}">全不选</button></div>` : ""}
      ${p.edits.map((e, i) => `<label class="skb-edit ${e.done ? "done" : ""}"><input type="checkbox" data-skb-pick="${esc(p.id)}" value="${i}" ${e.done || e.flag ? "" : "checked"} ${e.done ? "disabled" : ""}>
        <span><b>${esc(e.path)}</b> <small>${e.action === "new" ? "新建（已有同名不覆盖）" : e.action === "replace" ? "整个文件更新" : "追加到末尾"}${e.done ? " · 已采纳" : ""}</small>
        ${e.flag ? `<span class="small skb-warn">⚠ ${esc(e.flag)}</span>` : ""}${e.reason ? `<span class="small muted">${esc(e.reason)}</span>` : ""}
        <details><summary class="small">${e.action === "replace" ? "看修改前后" : "看内容"}</summary>${e.action === "replace" ? `<div class="skb-diff skb-lines">${lineDiff(e.before, e.text)}</div>` : `<div class="skb-diff md">${read(e.text)}</div>`}</details></span></label>`).join("")}
      <div class="skb-acts"><button class="primary small" data-skb="accept" data-pid="${esc(p.id)}">采纳勾选的</button><button class="ghost small" data-skb="dismiss" data-pid="${esc(p.id)}">忽略这条</button>
        <span class="small faint">采纳前不会改任何文件；采纳后写进变更记录，随时可以回滚${["distill", "update", "diagnose"].includes(p.kind) ? "，并自动存成新版本" : ""}</span></div></div>`).join("")}</div>`;
  }

  function body(b) {
    if (!b) return '<div class="muted">还没有板块。</div>';
    if (MODE === "edit" && CUR) {
      return `<div class="skb-editor"><div class="small muted">正在修改 <b>${esc(FILE)}</b>（原文，可以看到 Markdown 和公式的写法）· 保存后<b>下一次解惑</b>就按新内容讲 · Ctrl+S 保存</div>
        <textarea id="skbText" spellcheck="false" aria-label="修改 ${esc(FILE)}">${esc(DRAFT)}</textarea>
        <div class="skb-acts"><button class="primary" data-skb="save" ${BUSY ? "disabled" : ""}>保存</button><button class="ghost" data-skb="cancel">取消</button>
        <span class="small faint">${num(DRAFT.length)} 字符</span></div></div>`;
    }
    if (MODE === "hist" && CUR) {
      const rows = (HIST || []).map((v) => `<div class="skb-ver"><span>${esc(v.at)} · ${num(v.chars)} 字符</span><span>
        <button class="ghost small" data-skb="peek" data-id="${esc(v.id)}">查看</button><button class="small" data-skb="restore" data-id="${esc(v.id)}">回滚到这版</button></span></div>`).join("");
      return `<div class="skb-hist"><div class="small muted">「${esc(FILE)}」的历史版本（每次保存、改名、删除前都会留一份；回滚前的内容也会留）</div>
        ${rows || '<p class="muted small">还没有历史：这个文件还没改过。</p>'}${PREVIEW != null ? `<div class="skb-preview md"><div class="small muted">预览：</div>${read(PREVIEW)}</div>` : ""}
        <div class="skb-acts"><button class="ghost" data-skb="back">返回</button></div></div>`;
    }
    return CUR ? `<div class="skb-read md">${read(CUR.text) || '<p class="muted">（空文件）</p>'}</div>` : '<p class="muted">选一个文件看看。</p>';
  }

  function side(b) {
    return `<button class="ghost small" data-skb="shelf">← 回书架</button>
        <div class="skb-who"><b>${esc(b.board)}</b>${b.pending ? `<span class="tag skb-pend" title="有待审建议">📝${b.pending}</span>` : ""}</div>
        ${meter(b)}${b.files.length && MODE === "view" ? chips(b) : ""}`;
  }

  function shelf() {
    return `<p class="lib-tip skb-tip small">每本古籍是一个板块的${esc(name())}：点开可看、可改，保存后下一次解惑就按新内容讲。</p>
      <div class="tome-grid skb-shelf">${DATA.map((x, i) => {
        const seal = x.mode === "none" ? "未接入" : x.n_files + " 篇";
        return `<div class="tome-slot"><button class="tome skb-tome ${x.mode === "none" ? "none" : ""}" style="--h:${(i * 47 + 20) % 360};--d:${(i * 0.9).toFixed(1)}s" data-skb-board="${esc(x.board)}" aria-label="${esc(x.board)}（${seal}）">
          <span class="tome-cover"><span class="tome-label ${x.board.length > 4 ? "long" : ""}">${vlabel(x.board.slice(0, 6))}</span><span class="tome-seal">${seal}</span></span>${x.pending ? `<span class="skb-pend-badge" title="有待审建议">📝${x.pending}</span>` : ""}</button>
          <div class="tome-cap">${esc(x.board)}<br>${x.n_files ? x.n_files + " 个文件" : "还没有内容"}</div></div>`;
      }).join("")}</div>`;
  }

  function html() {
    if (!DATA.length) return '<div class="card"><p class="muted">还没有连接资料库，或这个科目没有板块。</p></div>';
    const b = board();
    if (SHELF || !b) return shelf();
    const dist = window.DISTILL?.enabled() ? `<div class="skb-tabs" role="tablist"><button role="tab" class="${TAB === "files" ? "on" : ""}" data-skb-tab="files">📖 心法文件</button><button role="tab" class="${TAB === "distill" ? "on" : ""}" data-skb-tab="distill">🎓 蒸馏</button></div>` : "";
    const inDist = dist && TAB === "distill";
    return `<aside class="skb-side card" aria-label="文件">${side(b)}</aside>
      <section class="skb-main card"><div class="skb-head"><h3>${esc(b.board)} · ${esc(name())}${!inDist && MODE === "view" && FILE ? ` <small class="muted">${esc(nice(FILE, plan()?.items.find((i) => i.rel === FILE)?.title))}</small>` : ""}</h3>${dist}<div class="skb-tools">${!inDist && MODE === "view" ? toolbar(b) : ""}</div></div>
        ${NOTE ? `<div class="skb-note" role="status">${esc(NOTE)}</div>` : ""}${!inDist && MODE === "view" ? banner(b) : ""}${inDist ? (PROPS.length ? `<details class="skb-propbar" ${PROPS_OPEN ? "open" : ""}><summary><b>📝 ${PROPS.length} 条待审建议</b>（蒸馏 / 更新生成的内容在这里勾选采纳）</summary>${proposals()}</details>` : "") : MODE === "view" ? proposals() : ""}
        <div class="skb-body">${inDist ? '<div class="dst-root" id="dstRoot"></div>' : body(b)}</div></section>`;
  }

  function paint() {
    const root = document.getElementById("skbRoot");
    if (root) { root.className = "skb-root " + (SHELF || !board() ? "shelf" : "detail"); root.innerHTML = html(); }
    const t = document.getElementById("skbText");
    if (t) t.oninput = () => { DRAFT = t.value; };
    const dst = document.getElementById("dstRoot");
    if (dst && window.DISTILL) DISTILL.mount(dst, BOARD, { note: (m) => { NOTE = m; const n = document.querySelector("#skbRoot .skb-note"); if (n) n.textContent = m; else paint(); }, refresh: async (o) => { if (o?.open) PROPS_OPEN = true; await reload(FILE); } });
  }

  function paintSide() {                           // 读取情况算好后只刷新左栏和标题，不动正在写的文本框
    const el = document.querySelector("#skbRoot .skb-side"), b = board();
    if (el && b && !SHELF) el.innerHTML = side(b);
  }

  async function act(kind, el) {
    const b = board();
    NOTE = "";
    try {
      if (kind === "shelf") {
        if (MODE === "edit" && DRAFT !== CUR?.text && !confirm("有没保存的修改，确定放弃吗？")) return;
        MODE = "view"; SHELF = true; await overview();
      } else if (kind === "edit") {
        MODE = "edit"; DRAFT = CUR.text;
      } else if (kind === "template") {
        await api("/api/skillbook/create", { board: b.board, how: "template" }); await reload(); NOTE = "已新建标准模板，点「✎ 修改」开始写。";
      } else if (kind === "cancel") {
        if (DRAFT !== CUR.text && !confirm("有没保存的修改，确定放弃吗？")) return;
        MODE = "view"; await reload(FILE);      // 取消后重新读一遍，看到的永远是最新内容（别处改过也能看到）
      } else if (kind === "save") {
        BUSY = true; paint();
        try {
          const r = await api("/api/skillbook/save", { board: b.board, path: FILE, text: DRAFT, base: CUR.rev });
          NOTE = r.changed ? "已保存，下一次解惑就按新内容讲。" : "内容没有变化。";
          MODE = "view"; await reload(FILE);
        } finally { BUSY = false; }
      } else if (kind === "organize") {
        if (!confirm("让 AI 读这份心法，改写成你能学的“学习版”（怎么用、识别信号、方法卡、陷阱、示范、速查）。要调用多次 AI，可能要几分钟；示范会用你题库里的真题。结果只是待审建议，采纳前不改任何文件。继续吗？")) return;
        NOTE = "AI 正在生成学习版，请稍等几分钟……"; paint();
        await api("/api/skillbook/organize", { board: b.board }); await loadProps(); await reload(FILE);
        NOTE = "已生成学习版的待审建议，勾选要采纳的文件。";
      } else if (kind === "accept") {
        const pid = el.dataset.pid, picks = [...document.querySelectorAll(`[data-skb-pick="${pid}"]:checked`)].map((x) => Number(x.value));
        const r = await api("/api/skillbook/accept", { board: b.board, id: pid, picks });
        await reload(r.applied[0] || FILE);
        NOTE = (r.applied.length ? `已采纳：${r.applied.length > 4 ? r.applied.length + " 个文件" : r.applied.join("、")}，下一次解惑就按新内容讲。` : "没有写入任何文件。") + (r.version ? ` 已存成版本 v${r.version}。` : "") + (r.skipped.length ? " 跳过：" + r.skipped.join("；") : "");
        if (window.DISTILL) DISTILL.invalidate();
      } else if (kind === "pick-all" || kind === "pick-none") {
        document.querySelectorAll(`[data-skb-pick="${el.dataset.pid}"]:not(:disabled)`).forEach((x) => { x.checked = kind === "pick-all"; });
        return;
      } else if (kind === "dismiss") {
        if (!confirm("忽略这条建议？")) return;
        await api("/api/skillbook/dismiss", { board: b.board, id: el.dataset.pid }); await loadProps(); NOTE = "已忽略。";
      } else if (kind === "history") {
        HIST = (await api("/api/skillbook/history", { board: b.board, path: FILE })).versions; PREVIEW = null; MODE = "hist";
      } else if (kind === "back") { MODE = "view"; }
      else if (kind === "peek") { PREVIEW = (await api("/api/skillbook/history", { board: b.board, path: FILE, id: el.dataset.id })).text; }
      else if (kind === "restore") {
        if (!confirm("回滚到这一版？现在的内容会先存进历史，可以再回来。")) return;
        await api("/api/skillbook/restore", { board: b.board, path: FILE, id: el.dataset.id, base: CUR.rev });
        MODE = "view"; await reload(FILE); NOTE = "已回滚，下一次解惑就按这一版讲。";
      } else if (kind === "newfile") {
        const n = (prompt("新文件名（.md，可带一层文件夹，如 chapters/02.md）", "新文件.md") || "").trim();
        if (!n) return;
        await api("/api/skillbook/create", { board: b.board, how: "file", path: n, text: "# " + n.replace(/\.md$/i, "").split("/").pop() + "\n\n" });
        await reload(n); MODE = "edit"; DRAFT = CUR.text;
      } else if (kind === "rename") {
        const n = (prompt("新的文件名", FILE) || "").trim();
        if (!n || n === FILE) return;
        const r = await api("/api/skillbook/rename", { board: b.board, path: FILE, new_path: n, base: CUR.rev });
        await reload(r.path); NOTE = "已改名，原内容留在历史里。";
      } else if (kind === "delete") {
        if (!confirm(`删除「${FILE}」？内容会先存进历史，可以找回。`)) return;
        await api("/api/skillbook/delete", { board: b.board, path: FILE, base: CUR.rev });
        await reload(); NOTE = "已删除，内容留在历史里。";
      }
    } catch (e) { NOTE = e.message || String(e); }
    paint();
  }

  window.SKILLBOOK = {
    async render() {
      SHELF = !(MODE === "edit" && board());         // 有没写完的草稿就回到那一页，否则先看书架
      if (LOADED) {                                   // 再次进入：用缓存立刻出，后台悄悄刷新
        overview().then(() => { if (SHELF) paint(); }).catch(() => {});
      } else {
        try { await overview(); } catch (e) { return `<div class="card"><p class="muted">读取失败：${esc(e.message)}</p></div>`; }
      }
      if (!SHELF) loadPlan().then(paintSide);
      return `<div class="skb-root ${SHELF ? "shelf" : "detail"}" id="skbRoot">${html()}</div>`;
    },
    bind(view) {
      const root = view?.querySelector("#skbRoot");
      if (!root) return;
      paint();
      root.onclick = async (e) => {
        const bt = e.target.closest("[data-skb-board]");
        if (bt) {
          if (MODE === "edit" && BOARD === bt.dataset.skbBoard) { SHELF = false; paint(); return; }
          BOARD = bt.dataset.skbBoard; MODE = "view"; NOTE = ""; SHELF = false;
          const fp = loadPos(); await loadFile(board().files.includes(fp.f) && BOARD === fp.b ? fp.f : board().files[0]); await loadProps(); paint(); loadPlan().then(paintSide); return;
        }
        const tab = e.target.closest("[data-skb-tab]");
        if (tab) { TAB = tab.dataset.skbTab; NOTE = ""; paint(); return; }
        const f = e.target.closest("[data-skb-file]");
        if (f) { MODE = "view"; NOTE = ""; TAB = "files"; await loadFile(f.dataset.skbFile); paint(); return; }
        const a = e.target.closest("[data-skb]");
        if (a && !a.disabled) act(a.dataset.skb, a);
      };
      root.addEventListener("toggle", (e) => { if (e.target.classList?.contains("skb-propbar")) PROPS_OPEN = e.target.open; }, true);
      root.onkeydown = (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && MODE === "edit") { e.preventDefault(); act("save"); }
      };
    },
  };
})();
