/* 藏经阁·心法（skill）：每个板块一份可随时修改的解题方法，初始是空的（数据来自 /api/skillbook，见 rpg/skillbook.py）。
   先是一排会浮动的古籍书架（一个板块一本，最前面还有一本「心法总诀」），点开才进入全屏的阅读/修改页；“解惑会读到什么”的计算较慢，打开板块时才算并缓存。
   没有“原版 / 我的版本”：直接改就是了，每次修改前的样子都留在历史里，可以回滚；别的平台生成的 .skill / .zip / .md 可以直接导入进来。
   心法总诀：随程序发布的四份文件（蒸馏第一步、第二步、配置空白模板、使用流程），只读，可复制、可下载，拿到别的平台用。
   阅读区用 MDLITE 渲染（逻辑符号、表格、英文小标题换中文）；修改区永远是原文。
   状态留在本模块里：切到别的页面再回来，书架立刻出现，选中的板块、文件和没保存的草稿都还在。 */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const POS = "skillbook-pos";
  let DATA = [], LOADED = false, SHELF = true, PLANS = {}, BOARD = "", FILE = "", CUR = null, MODE = "view", DRAFT = "", HIST = null, PREVIEW = null, NOTE = "", BUSY = false;
  let ZJ = false, ZJFILES = [], ZJFILE = "", ZJTEXT = "";
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

  async function loadPlan() {
    const b = board();
    if (!b || !b.n_files || PLANS[b.board]) return;
    try { PLANS[b.board] = await api("/api/skillbook/plan", { board: b.board }); } catch { PLANS[b.board] = { items: [], total: 0, words: 0, limit: 0, failed: true }; }
  }

  async function overview() {
    DATA = (await api("/api/skillbook")).boards; LOADED = true;
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
    paint(); loadPlan().then(paintSide);          // 先出内容，读取情况算好了再补上
  }

  function meter(b) {
    if (!b.n_files) return "";
    const pl = plan();
    if (!pl) return '<div class="skb-meter small muted" role="status">正在计算解惑时会读到什么……</div>';
    if (pl.failed) return '<div class="skb-meter small muted">读取情况暂时算不出来，不影响查看和修改。</div>';
    const pct = Math.min(100, Math.round((pl.total / pl.limit) * 100));
    const skipped = pl.items.filter((i) => i.kind === "method" && !i.read);
    const refs = pl.items.filter((i) => i.kind === "ref").length;
    return `<div class="skb-meter" role="group" aria-label="解惑读取情况">
      <div class="small" title="字数按汉字和单词算，不含符号、空格和标记；读取上限按字符算（${num(pl.total)} / ${num(pl.limit)} 字符）"><b>解惑时会读：</b>${pl.items.filter((i) => i.read).length} 个文件 · 约 <b>${num(pl.words)}</b> 字 · 占读取上限 ${pct}%${refs ? `<br><span class="muted">references / 学习版 里的 ${refs} 个文件只供查阅或阅读，不自动读入</span>` : ""}</div>
      <div class="skb-bar"><i style="width:${pct}%"></i></div>
      ${skipped.length ? `<div class="skb-warn small">⚠ ${skipped.length} 个文件超出上限没有读入：${skipped.map((i) => esc(i.rel) + "（" + num(i.words) + " 字）").join("、")}。请精简、拆分，或把它们放进 references/ 文件夹（只供查阅，不自动读入）。</div>` : ""}</div>`;
  }

  function chips(b) {
    const info = Object.fromEntries((plan()?.items || []).map((i) => [i.rel, i]));
    return `<div class="skb-files" role="tablist">${b.files.map((f) => {
      const i = info[f];
      return `<button role="tab" class="skb-chip ${f === FILE ? "on" : ""}" data-skb-file="${esc(f)}" aria-selected="${f === FILE}" title="${esc(f)}"><span>${esc(nice(f, i?.title))}</span>${i ? `<small>${num(i.words)}字${i.kind === "ref" ? " · 仅查阅" : i.read ? "" : " · 未读入"}</small>` : ""}</button>`;
    }).join("")}</div>`;
  }

  function banner(b) {
    if (!b.n_files) return `<div class="skb-banner">这个板块的${esc(name())}还是空的。可以「📥 导入 skill」（别的平台生成的 .skill 压缩包，或 .md 文件），也可以「＋ 新建文件」自己写。导入、修改后，下一次解惑就按这里的内容讲；每次修改前的样子都留在「🕘 历史」里。</div>`;
    return `<div class="skb-banner skb-tip2">直接修改就行：保存后下一次解惑就按新内容讲，每次修改前的样子都留在「🕘 历史」里，可以回滚。</div>`;
  }

  function toolbar(b) {
    const imp = `<button class="ghost small" data-skb="import" title="选择别的平台生成的 .skill / .zip（压缩包）或 .md 文件；同名文件会被覆盖，旧内容留在历史里">📥 导入 skill</button>`;
    if (!b.n_files) return `<button class="primary small" data-skb="import">📥 导入 skill</button><button class="ghost small" data-skb="newfile">＋ 新建文件</button>`;
    return `<button class="primary small" data-skb="edit" ${CUR ? "" : "disabled"}>✎ 修改</button>
      <button class="ghost small" data-skb="history" ${CUR ? "" : "disabled"}>🕘 历史</button><button class="ghost small" data-skb="newfile">＋ 新建文件</button>
      <button class="ghost small" data-skb="rename" ${CUR && FILE !== "SKILL.md" ? "" : "disabled"}>改名</button><button class="ghost small" data-skb="delete" ${CUR ? "" : "disabled"}>🗑 删除</button>${imp}`;
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
      return `<div class="skb-hist"><div class="small muted">「${esc(FILE)}」的历史版本（每次保存、导入覆盖、改名、删除前都会留一份；回滚前的内容也会留）</div>
        ${rows || '<p class="muted small">还没有历史：这个文件还没改过。</p>'}${PREVIEW != null ? `<div class="skb-preview md"><div class="small muted">预览：</div>${read(PREVIEW)}</div>` : ""}
        <div class="skb-acts"><button class="ghost" data-skb="back">返回</button></div></div>`;
    }
    if (!b.n_files) return '<p class="muted">（空板块）</p>';
    return CUR ? `<div class="skb-read md">${read(CUR.text) || '<p class="muted">（空文件）</p>'}</div>` : '<p class="muted">选一个文件看看。</p>';
  }

  function side(b) {
    return `<button class="ghost small" data-skb="shelf">← 回书架</button>
        <div class="skb-who"><b>${esc(b.board)}</b></div>
        ${meter(b)}${b.files.length && MODE === "view" ? chips(b) : ""}`;
  }

  function shelf() {
    return `<p class="lib-tip skb-tip small">每本古籍是一个板块的${esc(name())}，一开始都是空的：点开可看、可改、可导入别的平台生成的 skill，保存后下一次解惑就按新内容讲。</p>
      <button class="skb-zj-card" data-skb="zj"><b>📜 ${esc(name())}总诀</b><span class="small muted">蒸馏第一步、第二步、第三步（学习版）、配置空白模板、使用流程——拿到 GPT / Gemini / DeepSeek 等平台生成 skill 或学习版，再导入下面的板块</span></button>
      <div class="tome-grid skb-shelf">${DATA.map((x, i) => {
        const seal = x.n_files ? x.n_files + " 篇" : "空";
        return `<div class="tome-slot"><button class="tome skb-tome ${x.n_files ? "" : "none"}" style="--h:${(i * 47 + 20) % 360};--d:${(i * 0.9).toFixed(1)}s" data-skb-board="${esc(x.board)}" aria-label="${esc(x.board)}（${seal}）">
          <span class="tome-cover"><span class="tome-label ${x.board.length > 4 ? "long" : ""}">${vlabel(x.board.slice(0, 6))}</span><span class="tome-seal">${seal}</span></span></button>
          <div class="tome-cap">${esc(x.board)}<br>${x.n_files ? x.n_files + " 个文件" : "还没有内容"}</div></div>`;
      }).join("")}</div>`;
  }

  function zjHtml() {
    return `<aside class="skb-side card" aria-label="总诀文件"><button class="ghost small" data-skb="shelf">← 回书架</button>
        <div class="skb-who"><b>📜 ${esc(name())}总诀</b></div>
        <p class="small muted">五份可以直接复制到别的 AI 平台使用的说明。用法：配置（填一份）→ 第一步（每份逐字稿一次）→ 第二步（攒够再跑，得到做题用的 .skill）→ 第三步（可选，生成学习版）→ 回来导入到板块。</p>
        <div class="skb-files" role="tablist">${ZJFILES.map((f) => `<button role="tab" class="skb-chip ${f.file === ZJFILE ? "on" : ""}" data-skb-zj="${esc(f.file)}" aria-selected="${f.file === ZJFILE}"><span>${esc(f.title)}</span></button>`).join("")}</div></aside>
      <section class="skb-main card"><div class="skb-head"><h3>${esc(ZJFILES.find((f) => f.file === ZJFILE)?.title || "")} <small class="muted">${esc(ZJFILES.find((f) => f.file === ZJFILE)?.desc || "")}</small></h3>
        <div class="skb-tools"><button class="primary small" data-skb="zj-copy">📋 复制全文</button><a class="ghost small skb-dl" href="/zongjue-file?f=${encodeURIComponent(ZJFILE)}" download="${esc(ZJFILE)}">⬇ 下载 .md</a></div></div>
        ${NOTE ? `<div class="skb-note" role="status">${esc(NOTE)}</div>` : ""}
        <div class="skb-body"><pre class="skb-zj-text" id="skbZj">${esc(ZJTEXT)}</pre></div></section>`;
  }

  function html() {
    if (!DATA.length) return '<div class="card"><p class="muted">还没有连接资料库，或这个科目没有板块。</p></div>';
    if (ZJ) return zjHtml();
    const b = board();
    if (SHELF || !b) return shelf();
    return `<aside class="skb-side card" aria-label="文件">${side(b)}</aside>
      <section class="skb-main card"><div class="skb-head"><h3>${esc(b.board)} · ${esc(name())}${MODE === "view" && FILE ? ` <small class="muted">${esc(nice(FILE, plan()?.items.find((i) => i.rel === FILE)?.title))}</small>` : ""}</h3><div class="skb-tools">${MODE === "view" ? toolbar(b) : ""}</div></div>
        ${NOTE ? `<div class="skb-note" role="status">${esc(NOTE)}</div>` : ""}${MODE === "view" ? banner(b) : ""}
        <div class="skb-body">${body(b)}</div></section>
      <input type="file" id="skbPick" accept=".skill,.zip,.md,.txt,.markdown" hidden>`;
  }

  function paint() {
    const root = document.getElementById("skbRoot");
    if (root) { root.className = "skb-root " + (SHELF && !ZJ || !board() && !ZJ ? "shelf" : "detail"); root.innerHTML = html(); }
    const t = document.getElementById("skbText");
    if (t) t.oninput = () => { DRAFT = t.value; };
  }

  function paintSide() {                           // 读取情况算好后只刷新左栏和标题，不动正在写的文本框
    const el = document.querySelector("#skbRoot .skb-side"), b = board();
    if (el && b && !SHELF && !ZJ) el.innerHTML = side(b);
  }

  async function openZj(file) {
    if (!ZJFILES.length) ZJFILES = (await api("/api/skillbook/zongjue", {})).files;
    ZJFILE = file || ZJFILE || ZJFILES[0].file;
    ZJTEXT = (await api("/api/skillbook/zongjue", { file: ZJFILE })).text;
  }

  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch {}
    const ta = document.createElement("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0"; document.body.appendChild(ta); ta.select();
    let ok = false; try { ok = document.execCommand("copy"); } catch {}
    ta.remove(); return ok;
  }

  async function doImport(file) {
    const b = board();
    if (!b || !file) return;
    if (b.n_files && !confirm(`导入到「${b.board}」：包里与现有文件同名的会被覆盖（旧内容留在历史里），其余现有文件不动。继续吗？`)) return;
    NOTE = "正在导入……"; paint();
    const data = await new Promise((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve(String(r.result)); r.onerror = () => reject(new Error("读不了这个文件")); r.readAsDataURL(file); });
    const r = await api("/api/skillbook/import", { board: b.board, name: file.name, data });
    const touched = [...r.added, ...r.overwritten];
    await reload(touched.includes("SKILL.md") ? "SKILL.md" : (touched[0] || FILE));
    const sk = r.skipped || [];
    NOTE = `已导入：新增 ${r.added.length} 个、覆盖 ${r.overwritten.length} 个、内容相同 ${r.same.length} 个${sk.length ? `；跳过 ${sk.length} 个（${sk.slice(0, 3).map((x) => x[0] + "：" + x[1]).join("；")}${sk.length > 3 ? " 等" : ""}）` : ""}。下一次解惑就按这里的内容讲。`;
  }

  async function act(kind, el) {
    const b = board();
    NOTE = "";
    try {
      if (kind === "shelf") {
        if (MODE === "edit" && DRAFT !== CUR?.text && !confirm("有没保存的修改，确定放弃吗？")) return;
        MODE = "view"; SHELF = true; ZJ = false; await overview();
      } else if (kind === "zj") {
        await openZj(); ZJ = true; SHELF = false;
      } else if (kind === "zj-copy") {
        NOTE = (await copyText(ZJTEXT)) ? "已复制全文，可以粘贴到别的 AI 平台。" : "复制失败，请手动全选文字复制。";
      } else if (kind === "import") {
        document.getElementById("skbPick")?.click(); return;
      } else if (kind === "edit") {
        MODE = "edit"; DRAFT = CUR.text;
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
        const n = (prompt("新文件名（.md，可带一层文件夹，如 chapters/02.md；入口文件叫 SKILL.md）", b.n_files ? "新文件.md" : "SKILL.md") || "").trim();
        if (!n) return;
        await api("/api/skillbook/create", { board: b.board, path: n, text: "# " + n.replace(/\.md$/i, "").split("/").pop() + "\n\n" });
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
      SHELF = !(MODE === "edit" && board()) && !ZJ;  // 有没写完的草稿就回到那一页，否则先看书架
      if (LOADED) {                                   // 再次进入：用缓存立刻出，后台悄悄刷新
        overview().then(() => { if (SHELF) paint(); }).catch(() => {});
      } else {
        try { await overview(); } catch (e) { return `<div class="card"><p class="muted">读取失败：${esc(e.message)}</p></div>`; }
      }
      if (!SHELF && !ZJ) loadPlan().then(paintSide);
      return `<div class="skb-root ${SHELF && !ZJ ? "shelf" : "detail"}" id="skbRoot">${html()}</div>`;
    },
    bind(view) {
      const root = view?.querySelector("#skbRoot");
      if (!root) return;
      paint();
      root.onclick = async (e) => {
        const bt = e.target.closest("[data-skb-board]");
        if (bt) {
          if (MODE === "edit" && BOARD === bt.dataset.skbBoard) { SHELF = false; paint(); return; }
          BOARD = bt.dataset.skbBoard; MODE = "view"; NOTE = ""; SHELF = false; ZJ = false;
          const fp = loadPos(); await loadFile(board().files.includes(fp.f) && BOARD === fp.b ? fp.f : board().files[0]); paint(); loadPlan().then(paintSide); return;
        }
        const z = e.target.closest("[data-skb-zj]");
        if (z) { NOTE = ""; await openZj(z.dataset.skbZj); paint(); return; }
        const f = e.target.closest("[data-skb-file]");
        if (f) { MODE = "view"; NOTE = ""; await loadFile(f.dataset.skbFile); paint(); return; }
        const a = e.target.closest("[data-skb]");
        if (a && !a.disabled) act(a.dataset.skb, a);
      };
      root.onchange = async (e) => {
        if (e.target.id !== "skbPick") return;
        const file = e.target.files?.[0]; e.target.value = "";
        try { await doImport(file); } catch (er) { NOTE = er.message || String(er); }
        paint();
      };
      root.onkeydown = (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && MODE === "edit") { e.preventDefault(); act("save"); }
      };
    },
  };
})();
