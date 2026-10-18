/* 藏经阁·心法（skill）：每个板块的解题方法，可随时在这里看、改（数据来自 /api/skillbook，见 rpg/skillbook.py）。
   “我的版本”存在 训练/技能/<板块>/，保存即生效，下一次解惑就按新内容讲；库里原来的 skill 始终只读。
   状态留在本模块里：切到别的页面再回来，选中的板块、文件和没保存的草稿都还在。 */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const POS = "skillbook-pos";
  let DATA = [], BOARD = "", FILE = "", CUR = null, MODE = "view", DRAFT = "", HIST = null, PREVIEW = null, NOTE = "", BUSY = false;
  const name = () => (window.W ? W("skillbook") : "心法");
  const board = () => DATA.find((b) => b.board === BOARD) || null;
  const savePos = () => { try { localStorage.setItem(POS, JSON.stringify({ b: BOARD, f: FILE })); } catch {} };
  const loadPos = () => { try { return JSON.parse(localStorage.getItem(POS) || "{}"); } catch { return {}; } };
  const num = (n) => Number(n || 0).toLocaleString("en-US");
  const tag = (b) => (b.mode === "mine" ? '<span class="tag skb-mine">我的版本</span>' : b.mode === "source" ? '<span class="tag">原 skill</span>' : '<span class="tag draft">未接入</span>');

  async function loadFile(rel) {
    const b = board();
    if (!b || !rel) { CUR = null; return; }
    FILE = rel; savePos();
    try { CUR = await api("/api/skillbook/file", { board: b.board, path: rel }); } catch (e) { CUR = null; NOTE = e.message; }
  }

  async function reload(keepFile) {
    DATA = (await api("/api/skillbook")).boards;
    const p = loadPos();
    if (!board()) BOARD = DATA.some((b) => b.board === p.b) ? p.b : (DATA[0]?.board || "");
    const b = board();
    if (b) {
      const pick = keepFile && b.files.includes(keepFile) ? keepFile : (b.files.includes(p.f) && !keepFile ? p.f : b.files[0]);
      await loadFile(pick);
    } else CUR = null;
  }

  function md(text) {
    return String(text).split("\n").map((l) => {
      const t = esc(l);
      if (/^#{1}\s/.test(l)) return `<h3>${t.replace(/^#\s*/, "")}</h3>`;
      if (/^#{2}\s/.test(l)) return `<h4>${t.replace(/^##\s*/, "")}</h4>`;
      if (/^#{3,}\s/.test(l)) return `<h5>${t.replace(/^#+\s*/, "")}</h5>`;
      if (/^\s*[-*]\s/.test(l)) return `<div class="skb-li">${t.replace(/^\s*[-*]\s/, "")}</div>`;
      return l.trim() ? `<p>${t}</p>` : "";
    }).join("");
  }

  function meter(b) {
    if (b.mode === "none") return "";
    const pct = Math.min(100, Math.round((b.total / b.limit) * 100));
    const skipped = b.items.filter((i) => !i.read);
    const mats = b.items.filter((i) => i.kind === "material" && i.read).length;
    return `<div class="skb-meter" role="group" aria-label="解惑读取情况">
      <div class="small"><b>解惑时会读：</b>${b.items.filter((i) => i.read).length} 个文件（含 ${mats} 份 skill 引用的资料）· <b>${num(b.total)} / ${num(b.limit)}</b> 字</div>
      <div class="skb-bar"><i style="width:${pct}%"></i></div>
      ${skipped.length ? `<div class="skb-warn small">⚠ ${skipped.length} 个文件超出上限没有读入：${skipped.map((i) => esc(i.rel) + "（" + num(i.chars) + " 字）").join("、")}。请精简或拆分。</div>` : ""}</div>`;
  }

  function chips(b) {
    const info = Object.fromEntries(b.items.filter((i) => i.kind === "method").map((i) => [i.rel, i]));
    return `<div class="skb-files" role="tablist">${b.files.map((f) => {
      const i = info[f];
      return `<button role="tab" class="skb-chip ${f === FILE ? "on" : ""}" data-skb-file="${esc(f)}" aria-selected="${f === FILE}">${esc(f)}${i ? `<small>${num(i.chars)}字${i.read ? "" : " · 未读入"}</small>` : ""}</button>`;
    }).join("")}</div>`;
  }

  function banner(b) {
    if (b.mode === "source") return `<div class="skb-banner">这是你库里<b>原来的 skill</b>（只读）。点「✎ 修改」会先复制成<b>我的版本</b>再改，原文件不会动。</div>`;
    if (b.mode === "none") return `<div class="skb-banner">这个板块还没有${esc(name())}。${b.source ? `（规则里写的 skill「${esc(b.source)}」在库里没找到。）` : ""}可以新建一份标准模板，再随时修改。</div>`;
    return "";
  }

  function toolbar(b) {
    if (b.mode === "none") return `<button class="primary small" data-skb="template">＋ 新建标准模板</button>`;
    const mine = b.mode === "mine";
    return `<button class="primary small" data-skb="edit" ${CUR ? "" : "disabled"}>✎ 修改</button>
      ${mine ? `<button class="ghost small" data-skb="history" ${CUR ? "" : "disabled"}>🕘 历史</button><button class="ghost small" data-skb="newfile">＋ 新建文件</button>
      <button class="ghost small" data-skb="rename" ${CUR && FILE !== "SKILL.md" ? "" : "disabled"}>改名</button><button class="ghost small" data-skb="delete" ${CUR ? "" : "disabled"}>🗑 删除</button>`
        : `<button class="ghost small" data-skb="copy" title="只复制成我的版本，不进入修改">复制成我的版本</button>`}`;
  }

  function body(b) {
    if (!b) return '<div class="muted">还没有板块。</div>';
    if (MODE === "edit" && CUR) {
      return `<div class="skb-editor"><div class="small muted">正在修改 <b>${esc(FILE)}</b> · 保存后<b>下一次解惑</b>就按新内容讲 · Ctrl+S 保存</div>
        <textarea id="skbText" spellcheck="false" aria-label="修改 ${esc(FILE)}">${esc(DRAFT)}</textarea>
        <div class="skb-acts"><button class="primary" data-skb="save" ${BUSY ? "disabled" : ""}>保存</button><button class="ghost" data-skb="cancel">取消</button>
        <span class="small faint">${num(DRAFT.length)} 字</span></div></div>`;
    }
    if (MODE === "hist" && CUR) {
      const rows = (HIST || []).map((v) => `<div class="skb-ver"><span>${esc(v.at)} · ${num(v.chars)} 字</span><span>
        <button class="ghost small" data-skb="peek" data-id="${esc(v.id)}">查看</button><button class="small" data-skb="restore" data-id="${esc(v.id)}">回滚到这版</button></span></div>`).join("");
      return `<div class="skb-hist"><div class="small muted">「${esc(FILE)}」的历史版本（每次保存、改名、删除前都会留一份；回滚前的内容也会留）</div>
        ${rows || '<p class="muted small">还没有历史。</p>'}${PREVIEW != null ? `<div class="skb-preview"><div class="small muted">预览：</div>${md(PREVIEW)}</div>` : ""}
        <div class="skb-acts"><button class="ghost" data-skb="back">返回</button></div></div>`;
    }
    return CUR ? `<div class="skb-read">${md(CUR.text) || '<p class="muted">（空文件）</p>'}</div>` : '<p class="muted">选一个文件看看。</p>';
  }

  function html() {
    if (!DATA.length) return '<div class="card"><p class="muted">还没有连接资料库，或这个科目没有板块。</p></div>';
    const b = board();
    return `<aside class="skb-side card" aria-label="板块">${DATA.map((x) => `<button class="skb-board ${x.board === BOARD ? "on" : ""}" data-skb-board="${esc(x.board)}">
        <span>${esc(x.board)}</span>${tag(x)}${x.items.some((i) => !i.read) ? '<span class="skb-dot" title="有文件超出上限没读入">⚠</span>' : ""}</button>`).join("")}</aside>
      <section class="skb-main card"><div class="skb-head"><h3>${esc(b.board)} · ${esc(name())}</h3><div class="skb-tools">${MODE === "view" ? toolbar(b) : ""}</div></div>
        ${NOTE ? `<div class="skb-note" role="status">${esc(NOTE)}</div>` : ""}${banner(b)}${meter(b)}${b.files.length && MODE === "view" ? chips(b) : ""}
        <div class="skb-body">${body(b)}</div></section>`;
  }

  function paint() {
    const root = document.getElementById("skbRoot");
    if (root) root.innerHTML = html();
    const t = document.getElementById("skbText");
    if (t) t.oninput = () => { DRAFT = t.value; };
  }

  async function act(kind, el) {
    const b = board();
    NOTE = "";
    try {
      if (kind === "edit") {
        if (b.mode === "source") {
          if (!confirm("先把原 skill 复制成「我的版本」（原文件不会改动），然后进入修改。继续吗？")) return;
          await api("/api/skillbook/create", { board: b.board, how: "copy" });
          await reload(FILE);
        }
        MODE = "edit"; DRAFT = CUR.text;
      } else if (kind === "copy") {
        await api("/api/skillbook/create", { board: b.board, how: "copy" }); await reload(FILE); NOTE = "已复制成我的版本，原 skill 没有改动。";
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
      try { await reload(FILE); } catch (e) { return `<div class="card"><p class="muted">读取失败：${esc(e.message)}</p></div>`; }
      return `<div class="skb-root" id="skbRoot">${html()}</div>`;
    },
    bind(view) {
      const root = view?.querySelector("#skbRoot");
      if (!root) return;
      paint();
      root.onclick = async (e) => {
        const bt = e.target.closest("[data-skb-board]");
        if (bt) {
          if (MODE === "edit" && DRAFT !== CUR?.text && !confirm("有没保存的修改，确定放弃吗？")) return;
          BOARD = bt.dataset.skbBoard; MODE = "view"; NOTE = ""; await loadFile(board().files.includes(loadPos().f) && BOARD === loadPos().b ? loadPos().f : board().files[0]); paint(); return;
        }
        const f = e.target.closest("[data-skb-file]");
        if (f) { MODE = "view"; NOTE = ""; await loadFile(f.dataset.skbFile); paint(); return; }
        const a = e.target.closest("[data-skb]");
        if (a && !a.disabled) act(a.dataset.skb, a);
      };
      root.onkeydown = (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && MODE === "edit") { e.preventDefault(); act("save"); }
      };
    },
  };
})();
