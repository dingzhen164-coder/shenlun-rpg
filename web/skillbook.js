/* 藏经阁多老师心法：一板块一本书，书内按老师分文件；全局ZIP按文件名预览分发。
   旧心法归“原有心法”，历史/修改/回滚保留；总诀和长教学说明已删除。
   读取计划按板块+老师缓存，切换文件校验请求代次，不能把迟到正文放到另一位老师名下。
   阅读区用 MDLITE 渲染（逻辑符号、表格、英文小标题换中文）；修改区永远是原文。
   状态留在本模块里：切到别的页面再回来，书架立刻出现，选中的板块、文件和没保存的草稿都还在。 */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const POS = "skillbook-pos";
  let DATA = [], LOADED = false, SHELF = true, PLANS = {}, BOARD = "", FILE = "", CUR = null, MODE = "view", DRAFT = "", HIST = null, PREVIEW = null, NOTE = "", BUSY = false;
  let TEACHER = "",FILE_TICKET=0;
  const name = () => (window.W ? W("skillbook") : "心法");
  const multiTeacher=()=>typeof DASH!=='undefined'&&DASH?.subject==='\u884c\u6d4b';
  const board = () => {const b=DATA.find(b=>b.board===BOARD);if(!b)return null;const row=b.teachers?.find(t=>t.name===TEACHER)||b.teachers?.[0];TEACHER=row?.name||"";return {...b,files:row?.files||b.files,n_files:(row?.files||b.files).length};};
  const plan = () => PLANS[BOARD+'\n'+TEACHER] || null;
  const savePos = () => { try { localStorage.setItem(POS, JSON.stringify({ b: BOARD, f: FILE, teacher:TEACHER })); } catch {} };
  const loadPos = () => { try { return JSON.parse(localStorage.getItem(POS) || "{}"); } catch { return {}; } };
  const num = (n) => Number(n || 0).toLocaleString("en-US");
  const read = (t) => (window.MDLITE ? MDLITE.render(t) : `<pre>${esc(t)}</pre>`);
  const nice = (rel, title) => (window.MDLITE ? MDLITE.friendly(rel, title) : rel);

  async function loadFile(rel) {
    const b = board();
    if (!b || !rel) { CUR = null; return; }
    const ticket=++FILE_TICKET,who=TEACHER;
    FILE = rel; savePos();
    try { const data=await api("/api/skillbook/file", { board: b.board, path: rel });if(ticket===FILE_TICKET&&BOARD===b.board&&TEACHER===who)CUR=data; } catch (e) { if(ticket===FILE_TICKET){CUR = null; NOTE = e.message;} }
  }

  async function loadPlan() {
    const b = board();
    if (!b || !b.n_files || plan()) return;
    const key=BOARD+'\n'+TEACHER;
    try { PLANS[key] = await api("/api/skillbook/plan", { board: b.board, teacher:TEACHER||undefined }); } catch { PLANS[key] = { items: [], total: 0, words: 0, limit: 0, failed: true }; }
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
    if (!pl) return '<div class="skb-meter small muted" role="status">正在计算方法学习与追问时会读到什么……</div>';
    if (pl.failed) return '<div class="skb-meter small muted">读取情况暂时算不出来，不影响查看和修改。</div>';
    const pct = Math.min(100, Math.round((pl.total / pl.limit) * 100));
    const skipped = pl.items.filter((i) => i.kind === "method" && !i.read);
    const refs = pl.items.filter((i) => i.kind === "ref").length;
    return `<div class="skb-meter" role="group" aria-label="方法学习与追问读取情况">
      <div class="small" title="字数按汉字和单词算，不含符号、空格和标记；读取上限按字符算（${num(pl.total)} / ${num(pl.limit)} 字符）"><b>方法学习与追问时会读：</b>${pl.items.filter((i) => i.read).length} 个文件 · 约 <b>${num(pl.words)}</b> 字 · 占读取上限 ${pct}%${refs ? `<br><span class="muted">references / 学习版 里的 ${refs} 个文件只供查阅或阅读，不自动读入</span>` : ""}</div>
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
    if (!b.n_files) return `<div class="skb-banner">这个板块的${esc(name())}还是空的。可以「📥 导入 skill」（别的平台生成的 .skill 压缩包，或 .md 文件），也可以「＋ 新建文件」自己写。导入、修改后，下一次方法学习与追问就按这里的内容讲；每次修改前的样子都留在「🕘 历史」里。</div>`;
    return `<div class="skb-banner skb-tip2">直接修改就行：保存后下一次方法学习与追问就按新内容讲，每次修改前的样子都留在「🕘 历史」里，可以回滚。</div>`;
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
      return `<div class="skb-editor"><div class="small muted">正在修改 <b>${esc(FILE)}</b>（原文，可以看到 Markdown 和公式的写法）· 保存后<b>下一次方法学习与追问</b>就按新内容讲 · Ctrl+S 保存</div>
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
        ${b.teachers?.length?`<label class="skb-teacher-label">心法老师<select data-skb-teacher aria-label="选择心法老师">${b.teachers.map(t=>`<option value="${esc(t.name)}" ${t.name===TEACHER?'selected':''}>${esc(t.name)}</option>`).join('')}</select></label>`:''}
        ${meter(b)}${b.files.length && MODE === "view" ? chips(b) : ""}`;
  }

  function shelf() {
    return `${multiTeacher()?'<div class="skb-import-bar"><button class="primary" data-skb="teachers-import">导入老师 skill</button><span class="small muted">ZIP / MD · 按“老师-板块”分发</span></div>':''}${NOTE?`<p class="skb-note" role="status">${esc(NOTE)}</p>`:''}
      <div class="tome-grid skb-shelf">${DATA.map((x, i) => {
        const seal = x.n_files ? x.n_files + " 篇" : "空";
        return `<div class="tome-slot"><button class="tome skb-tome ${x.n_files ? "" : "none"}" style="--h:${(i * 47 + 20) % 360};--d:${(i * 0.9).toFixed(1)}s" data-skb-board="${esc(x.board)}" aria-label="${esc(x.board)}（${seal}）">
          <span class="tome-cover"><span class="tome-label ${x.board.length > 4 ? "long" : ""}">${vlabel(x.board.slice(0, 6))}</span><span class="tome-seal">${seal}</span></span></button>
          <div class="tome-cap">${esc(x.board)}<br>${x.n_files ? (x.teachers?.length||1) + " 位老师 · "+x.n_files+" 份文档" : "还没有内容"}</div></div>`;
      }).join("")}</div><input type="file" id="skbTeachersPick" accept=".zip,.md,.markdown" hidden>`;
  }

  function html() {
    if (!DATA.length) return '<div class="card"><p class="muted">还没有连接资料库，或这个科目没有板块。</p></div>';
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
    if (root) { root.className = "skb-root " + (SHELF || !board() ? "shelf" : "detail"); root.innerHTML = html(); }
    const t = document.getElementById("skbText");
    if (t) t.oninput = () => { DRAFT = t.value; };
  }

  function paintSide() {                           // 读取情况算好后只刷新左栏和标题，不动正在写的文本框
    const el = document.querySelector("#skbRoot .skb-side"), b = board();
    if (el && b && !SHELF) el.innerHTML = side(b);
  }

  async function importTeachers(file){
    if(!file)return;
    NOTE='正在核对老师与板块……';paint();
    const data=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result));r.onerror=()=>no(Error('无法读取文件'));r.readAsDataURL(file);});
    const body={name:file.name,data},report=await api('/api/skillbook/teachers/import',{...body,preview:true});
    const lines=report.items.map(x=>x.teacher+' → '+x.boards.join('、'));
    if(!confirm(lines.join('\n')+'\n\n新增 '+report.added.length+' 份，更新 '+report.overwritten.length+' 份（旧内容保留历史），相同 '+report.same.length+' 份。'+(report.skipped.length?'\n跳过：'+report.skipped.map(x=>x.join('：')).join('\n'):'')+'\n确认导入？')){NOTE='已取消，未更改心法。';return;}
    const r=await api('/api/skillbook/teachers/import',body);PLANS={};await overview();NOTE='已导入 '+r.items.length+' 份老师文档，分发到 '+(r.added.length+r.overwritten.length+r.same.length)+' 个板块文档位。'+(r.skipped.length?'跳过 '+r.skipped.length+' 份：'+r.skipped.map(x=>x.join('：')).join('；'):'');
  }

  async function doImport(file) {
    const b = board();
    if (!b || !file) return;
    if (b.n_files && !confirm(`导入到「${b.board}」：包里与现有文件同名的会被覆盖（旧内容留在历史里），其余现有文件不动。继续吗？`)) return;
    NOTE = "正在导入……"; paint();
    const data = await new Promise((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve(String(r.result)); r.onerror = () => reject(new Error("读不了这个文件")); r.readAsDataURL(file); });
    const r = await api("/api/skillbook/import", { board: b.board, name: file.name, data });
    TEACHER='原有心法';
    const touched = [...r.added, ...r.overwritten];
    await reload(touched.includes("SKILL.md") ? "SKILL.md" : (touched[0] || FILE));
    const sk = r.skipped || [];
    NOTE = `已导入：新增 ${r.added.length} 个、覆盖 ${r.overwritten.length} 个、内容相同 ${r.same.length} 个${sk.length ? `；跳过 ${sk.length} 个（${sk.slice(0, 3).map((x) => x[0] + "：" + x[1]).join("；")}${sk.length > 3 ? " 等" : ""}）` : ""}。下一次方法学习与追问就按这里的内容讲。`;
  }

  async function act(kind, el) {
    const b = board();
    NOTE = "";
    try {
      if (kind === "shelf") {
        if (MODE === "edit" && DRAFT !== CUR?.text && !confirm("有没保存的修改，确定放弃吗？")) return;
        MODE = "view"; SHELF = true; await overview();
      } else if(kind==='teachers-import'){
        document.getElementById('skbTeachersPick')?.click();return;
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
          NOTE = r.changed ? "已保存，下一次方法学习与追问就按新内容讲。" : "内容没有变化。";
          MODE = "view"; await reload(FILE);
        } finally { BUSY = false; }
      } else if (kind === "history") {
        HIST = (await api("/api/skillbook/history", { board: b.board, path: FILE })).versions; PREVIEW = null; MODE = "hist";
      } else if (kind === "back") { MODE = "view"; }
      else if (kind === "peek") { PREVIEW = (await api("/api/skillbook/history", { board: b.board, path: FILE, id: el.dataset.id })).text; }
      else if (kind === "restore") {
        if (!confirm("回滚到这一版？现在的内容会先存进历史，可以再回来。")) return;
        await api("/api/skillbook/restore", { board: b.board, path: FILE, id: el.dataset.id, base: CUR.rev });
        MODE = "view"; await reload(FILE); NOTE = "已回滚，下一次方法学习与追问就按这一版讲。";
      } else if (kind === "newfile") {
        const n = (prompt("新文件名（.md，可带一层文件夹，如 chapters/02.md；入口文件叫 SKILL.md）", b.n_files ? "新文件.md" : "SKILL.md") || "").trim();
        if (!n) return;
        const rel=TEACHER&&TEACHER!=='原有心法'&&!n.startsWith('老师/')?'老师/'+TEACHER+'/'+n:n;
        await api("/api/skillbook/create", { board: b.board, path: rel, text: "# " + n.replace(/\.md$/i, "").split("/").pop() + "\n\n" });
        await reload(rel); MODE = "edit"; DRAFT = CUR.text;
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
      SHELF = !(MODE === "edit" && board());  // 有没写完的草稿就回到那一页，否则先看书架
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
          BOARD = bt.dataset.skbBoard; MODE = "view"; NOTE = ""; SHELF = false;TEACHER=loadPos().b===BOARD?loadPos().teacher||'':'';
          const fp = loadPos(); await loadFile(board().files.includes(fp.f) && BOARD === fp.b ? fp.f : board().files[0]); paint(); loadPlan().then(paintSide); return;
        }
        const f = e.target.closest("[data-skb-file]");
        if (f) { MODE = "view"; NOTE = ""; await loadFile(f.dataset.skbFile); paint(); return; }
        const a = e.target.closest("[data-skb]");
        if (a && !a.disabled) act(a.dataset.skb, a);
      };
      root.onchange = async (e) => {
        if(e.target.matches('[data-skb-teacher]')){if(MODE==='edit'&&DRAFT!==CUR?.text&&!confirm('放弃未保存的修改并切换老师？')){paintSide();return;}TEACHER=e.target.value;MODE='view';await loadFile(board().files[0]);paint();loadPlan().then(paintSide);return;}
        if(e.target.id==='skbTeachersPick'){const f=e.target.files?.[0];e.target.value='';try{await importTeachers(f);}catch(er){NOTE=er.message||String(er);}paint();return;}
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
