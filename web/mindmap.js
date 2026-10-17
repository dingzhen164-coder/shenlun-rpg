/* 3.1.0知识导图：修炼分区只读导图/分级文档/双栏，资料库负责编辑、导入与整理。
   本地训练/灵脉图/<板块>/<名字>.md可外部编辑，重新载入同步阅读；保存带文档指纹，防止覆盖外部修改。
   使用已有离线simple-mind-map（MIT），按需加载；计时交给app.js原心跳，编辑不计复习。 */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const VER = "0.14.0-fix.3";
  const HUES = [40, 200, 150, 280, 10, 320, 180, 95, 220, 260, 30, 170];
  const LAYOUTS = [["logicalStructure", "逻辑结构（向右）"], ["mindMap", "思维导图（两边）"], ["organizationStructure", "组织结构（向下）"],
    ["catalogOrganization", "目录组织"], ["timeline", "时间轴"], ["fishbone", "鱼骨图"]];
  let LIST = null, CUR = null, mm = null, saveT = null, dirty = false, libP = null;
  let saveP = null;
  let opening = false, openSeq = 0, editing = false, lastRead = 0, viewMode = "map";

  function loadLib() {
    if (window.simpleMindMap) return Promise.resolve();
    if (libP) return libP;
    libP = new Promise((ok, bad) => {
      const css = document.createElement("link");
      css.rel = "stylesheet"; css.href = `vendor/mindmap/simpleMindMap.esm.min.css?v=${VER}`;
      document.head.appendChild(css);
      const s = document.createElement("script");
      s.src = `vendor/mindmap/simpleMindMap.umd.min.js?v=${VER}`;
      s.onload = () => ok(); s.onerror = () => { libP = null; bad(new Error("思维导图编辑器没加载出来，刷新再试")); };
      document.head.appendChild(s);
    });
    return libP;
  }
  // 富文本插件（节点文字放在 foreignObject 里）在有的内核上量错高度，字只显示半截：去掉它，节点文字用普通 SVG 文字
  const M = () => {
    const Mind = window.simpleMindMap.default || window.simpleMindMap;
    // 本界面用拖动/缩放，没有自定义滚动条；无需启动其后台尺寸测量插件。
    // 该插件销毁时未取消延迟rbox任务，快速退出后会测量已移除的SVG。
    for (let i=(Mind.pluginList||[]).length-1;i>=0;i--)
      if (["richText","scrollbar"].includes(Mind.pluginList[i].instanceName)) Mind.pluginList.splice(i,1);
    return Mind;
  };
  // 以前（或别处）存的富文本节点 "<p>增长</p>" → 纯文字
  function plain(node) {
    if (!node || !node.data) return node;
    if (node.data.richText || /<[a-z][^>]*>/i.test(node.data.text || "")) {
      const d = document.createElement("div");
      d.innerHTML = String(node.data.text || "").replace(/<\/p>\s*<p[^>]*>/gi, "\n").replace(/<br\s*\/?>/gi, "\n");
      node.data.text = d.textContent.trim();
      delete node.data.richText;
    }
    (node.children || []).forEach(plain);
    return node;
  }

  // ---------------------------------------------------------------- 修炼殿：灵脉阵盘
  function disk(i) {
    // 中间一颗主节点，五条灵脉向外生长，末端的小节点一闪一闪
    const rays = [0, 72, 144, 216, 288].map((a, k) => {
      const r = (a + i * 17) * Math.PI / 180, x = 50 + Math.cos(r) * 33, y = 50 + Math.sin(r) * 33;
      const mx = 50 + Math.cos(r + 0.5) * 18, my = 50 + Math.sin(r + 0.5) * 18;
      return `<path class="ln-vein" d="M50 50 Q${mx.toFixed(1)} ${my.toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)}" style="--k:${k}"/>
        <circle class="ln-dot" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.2" style="--k:${k}"/>`;
    }).join("");
    return `<svg viewBox="0 0 100 100" class="ln-svg"><circle cx="50" cy="50" r="46" class="ln-ring"/><circle cx="50" cy="50" r="38" class="ln-ring2"/>
      ${rays}<circle cx="50" cy="50" r="7" class="ln-core"/></svg>`;
  }
  async function hubHtml(boards, manage = false) {
    try { LIST = await api("/api/mindmap"); } catch (e) { return `<div class="card"><p class="muted">${esc(e.message)}</p></div>`; }
    let shown=boards?boards.map(board=>LIST.boards.find(b=>b.board===board)||{board,maps:[]}).filter(b=>!['言语理解','成语实词','判断推理'].includes(b.board)||b.maps.length):LIST.boards;
    if (!manage) shown=shown.filter(b=>b.maps.length);
    if (!manage && !shown.length) return "";
    return `<div class="card ln-hall" data-ln-manage="${manage}"><div class="row"><h3 style="margin:0">🌿 灵脉图</h3>
        <span class="small muted">${manage ? "绘制、导入与整理知识导图；Markdown可在本地文档中编辑" : "只读复习 · 导图 / 分级文档 / 双栏对照"}</span></div>
      <div class="ln-grid">${shown.map((b, i) => {
        const n = b.maps.reduce((a, m) => a + m.nodes, 0);
        return `<div class="ln-slot" data-ln="${esc(b.board)}"><div class="ln-disk ${b.maps.length ? "lit" : ""}" style="--h:${HUES[i % HUES.length]};--d:${(i % 6) * 0.7}s">${disk(i)}</div>
          <div class="ln-name">${esc(b.board)}</div><div class="ln-cap">${b.maps.length ? `${b.maps.length} 幅 · ${n} 节` : "未绘"}</div></div>`;
      }).join("")}</div></div>`;
  }
  function bindHub(root = document) {
    root.querySelectorAll("[data-ln]").forEach((el) => (el.onclick = () => openBoard(el.dataset.ln, el.closest("[data-ln-manage]")?.dataset.lnManage === "true")));
  }
  async function openBoard(board, manage = false) {
    const b = (LIST?.boards || []).find((x) => x.board === board);
    const maps = b ? b.maps : [];
    if (maps.length > 1) return pickMap(board, maps, manage);
    open(board, maps[0]?.name || board, manage);
  }
  function pickMap(board, maps, manage) {
    const m = $("#modal");
    m.innerHTML = `<div class="modal-box"><h3>🌿 ${esc(board)} · 灵脉图</h3>
      <div class="ln-pick">${maps.map((x) => `<button data-pk="${esc(x.name)}"><b>${esc(x.name)}</b><small>${x.nodes} 节 · ${esc(x.updated)}</small></button>`).join("")}</div>
      <div class="row">${manage ? '<button class="ghost" id="lnPNew">＋ 新画一幅</button>' : ''}<span class="spacer"></span><button class="ghost" id="lnPX">关</button></div></div>`;
    m.classList.remove("hidden");
    m.querySelectorAll("[data-pk]").forEach((x) => (x.onclick = () => { m.classList.add("hidden"); open(board, x.dataset.pk, manage); }));
    $("#lnPX").onclick = () => m.classList.add("hidden");
    const add = $("#lnPNew"); if (add) add.onclick = async () => { m.classList.add("hidden"); newMap(board); };
  }
  async function newMap(board, data, name) {
    name = name || prompt(`新画一幅「${board}」的灵脉图，名字：`, board);
    if (!name) return;
    try { const r = await api("/api/mindmap/create", { board, name, data }); open(board, r.name, true); } catch (e) { showError(e); }
  }

  // ---------------------------------------------------------------- 编辑器
  function stage() {
    let s = document.getElementById("yjStage");
    if (!s) { s = document.createElement("div"); s.id = "yjStage"; s.className = "yj-stage ln-stage"; document.body.appendChild(s); }
    document.documentElement.classList.add("yj-on");
    return s;
  }
  async function open(board, name, manage = false) {
    if (CUR) { if(!(await flush()))return; await finishReading(); try { mm?.destroy(); } catch (_) {} mm=null; CUR=null; }
    const seq=++openSeq; opening=true; editing=manage; viewMode="map";
    const s = stage();
    s.innerHTML = `<div class="yj-top"><button class="ghost" id="lnBack">${typeof VIEW !== "undefined" && VIEW === "skeleton" ? "← 返回资料库" : "← 返回分区"}</button><b class="yj-top-title">🌿 灵脉图 · ${esc(board)}</b></div><div class="yj-wait">展开灵脉…</div>`;
    document.getElementById("lnBack").onclick = close;
    let d;
    try { [d] = await Promise.all([api("/api/mindmap/get", { board, name, readonly: !manage }), loadLib()]); } catch (e) { if(seq===openSeq){showError(e);return close();}return; }
    if(seq!==openSeq||!s.isConnected){if(d.reading_token)api("/api/mindmap/stop",{token:d.reading_token}).catch(()=>{});return;}
    opening=false;
    CUR = { board, name: d.name, document_revision: d.document_revision, reading_token: d.reading_token, document_path: d.document_path };
    lastRead = Date.now();
    const data = d.data || {};
    s.innerHTML = `<div class="yj-top"><button class="ghost" id="lnBack">${typeof VIEW !== "undefined" && VIEW === "skeleton" ? "← 返回资料库" : "← 返回分区"}</button>
        <b class="yj-top-title">🌿 ${esc(board)} · ${manage ? `<a id="lnName" title="改名">${esc(d.name)}</a>` : esc(d.name)}</b><span class="spacer"></span><span class="small faint" id="lnSaved"></span></div>
      ${manage ? `<div class="ln-tools">
        <button data-c="child" title="给选中的节点加子节点（Tab）">＋ 子节点</button><button data-c="sib" title="加同级节点（Enter）">＋ 同级</button>
        <button data-c="del" title="删除选中的节点（Delete）">✕ 删除</button><span class="ln-sep"></span>
        <button data-c="undo" title="撤销（Ctrl+Z）">↶</button><button data-c="redo" title="重做（Ctrl+Y）">↷</button><span class="ln-sep"></span>
        <select id="lnLayout" title="布局">${LAYOUTS.map(([k, v]) => `<option value="${k}" ${k === (data.layout || "logicalStructure") ? "selected" : ""}>${v}</option>`).join("")}</select>
        <button data-c="fit" title="整幅放进屏幕">⤢ 适应</button><button data-c="in" title="放大">＋</button><button data-c="out" title="缩小">－</button><span class="ln-sep"></span>
        <button data-c="import" title="导入 .xmind / Markdown / .json，导成新的一幅">📥 导入</button>
        <select id="lnExport" title="导出到 训练/灵脉图/导出/"><option value="">📤 导出…</option><option value="xmind">XMind（.xmind）</option><option value="png">图片（.png）</option>
          <option value="md">Markdown（.md）</option><option value="json">JSON</option></select>
        <span class="spacer"></span><button class="ghost" data-c="new">＋ 新一幅</button><button class="ghost danger" data-c="trash" title="删掉这一幅">🗑</button>
        <input type="file" id="lnFile" accept=".xmind,.md,.markdown,.txt,.json,.smm" hidden></div>` : `<div class="ln-reading-tabs" role="group" aria-label="阅读方式">
        <button data-ln-mode="map" aria-pressed="true">灵脉图</button><button data-ln-mode="document" aria-pressed="false">分级文档</button><button data-ln-mode="split" aria-pressed="false">双栏对照</button><span class="spacer"></span><button id="lnReload">↻ 重新载入</button>
        ${d.document_path ? `<button id="lnDocument" title="${esc(d.document_path)}">本地文档</button>` : ''}</div>`}
      <div class="ln-reading-body" data-mode="map"><div class="ln-canvas" id="lnCanvas"></div><article class="ln-document" id="lnMarkdown" hidden>${outline(plain(JSON.parse(JSON.stringify(data.root || {data:{text:board}}))))}</article></div>
      ${manage ? '<div class="ln-tip small faint">点节点选中 · 双击改字 · 拖动节点换位置 · 改了自动保存</div>' : ''}`;
    document.getElementById("lnBack").onclick = close;
    const Mind = M(), palette=getComputedStyle(document.body), color=k=>palette.getPropertyValue(k).trim();
    try {
      mm = new Mind({
        el: document.getElementById("lnCanvas"),
        readonly: !manage,
        // 等完整节点绘制后适应画布，不能用固定100ms猜测慢浏览器的渲染完成时间。
        fit: false,   // 库自带的绘制后适应在画布已关闭/隐藏时会抛错，改成下面带保护的版本
        data: plain(data.root || { data: { text: board }, children: [] }),
        layout: data.layout || "logicalStructure",
        theme: data.theme?.template || "default",
        themeConfig: Object.assign({ backgroundColor: color('--panel'), lineColor: color('--accent'), generalizationLineColor: color('--accent'),
          root: { fillColor: color('--accent'), color: color('--panel'), borderColor: color('--accent'), fontSize: 18 },
          second: { fillColor: color('--panel2'), color: color('--text'), borderColor: color('--line'), fontSize: 15 },
          general: { fillColor: color('--panel'), color: color('--text'), borderColor: color('--line') } }, data.theme?.config || {}),
        viewData: data.view || null,
        mousewheelAction: "zoom", mousewheelZoomActionReverse: true,
      });
      try { mm.rainbowLines && mm.rainbowLines.updateRainLinesConfig({ open: true }); } catch (_) {}
      if (!manage || !data.view) { const inst = mm, cv = document.getElementById('lnCanvas'); let fitted = false;
        inst.on('node_tree_render_end', () => { if (fitted) return; fitted = true;
          try { if (mm === inst && cv.isConnected && cv.offsetWidth && cv.offsetHeight) inst.view.fit(); } catch (_) {} }); }
    } catch (e) { showError(e); return; }
    if (!manage) {
      s.querySelectorAll('[data-ln-mode]').forEach(b=>b.onclick=()=>setViewMode(b.dataset.lnMode));
      document.getElementById('lnReload').onclick=async()=>{const mode=viewMode;await open(board, CUR.name, false);setViewMode(mode);};
      const doc=document.getElementById('lnDocument');if(doc)doc.onclick=()=>localDocument();
      updateStudyDot();return;
    }
    mm.on("data_change", queueSave);
    mm.on("view_data_change", queueSave);
    const cmd = {
      child: () => mm.execCommand("INSERT_CHILD_NODE", true, mm.renderer.activeNodeList.length ? [] : [mm.renderer.root]),
      sib: () => mm.renderer.activeNodeList.length ? mm.execCommand("INSERT_NODE") : toast("先点一下要在哪个节点旁边加"),
      del: () => mm.renderer.activeNodeList.length ? mm.execCommand("REMOVE_NODE") : toast("先点一下要删的节点"),
      undo: () => mm.execCommand("BACK"), redo: () => mm.execCommand("FORWARD"),
      fit: () => mm.view.fit(), in: () => mm.view.enlarge(), out: () => mm.view.narrow(),
      import: () => document.getElementById("lnFile").click(),
      new: () => newMap(board),
      trash: async () => {
        if (!confirm(`删掉「${CUR.name}」这一幅灵脉图？（删了不能恢复）`)) return;
        try { await api("/api/mindmap/delete", CUR); dirty = false; close(); } catch (e) { showError(e); }
      },
    };
    s.querySelectorAll("[data-c]").forEach((b) => (b.onclick = () => cmd[b.dataset.c]()));
    document.getElementById("lnLayout").onchange = (e) => mm.setLayout(e.target.value);
    document.getElementById("lnExport").onchange = (e) => { const v = e.target.value; e.target.value = ""; if (v) exportAs(v); };
    document.getElementById("lnFile").onchange = (e) => { const f = e.target.files[0]; e.target.value = ""; if (f) importFile(f); };
    document.getElementById("lnName").onclick = async () => {
      const n = prompt("改成：", CUR.name);
      if (!n || n === CUR.name) return;
      if(!(await flush()))return;
      try { const r = await api("/api/mindmap/rename", { board, name: CUR.name, new: n }); CUR.name = r.name; document.getElementById("lnName").textContent = r.name; } catch (e) { showError(e); }
    };
  }
  function queueSave() {
    if (!editing) return;
    dirty = true;
    const el = document.getElementById("lnSaved"); if (el) el.textContent = "…";
    clearTimeout(saveT); saveT = setTimeout(flush, 1200);
  }
  async function flush() {
    clearTimeout(saveT);
    if(saveP){const ok=await saveP;return ok&&dirty?flush():ok;}
    if (!dirty || !mm || !CUR) return true;
    const current=CUR,data=mm.getData(true);dirty=false;
    saveP=(async()=>{
      try {
        const saved=await api('/api/mindmap/save',{board:current.board,name:current.name,data,document_revision:current.document_revision});
        current.document_revision=saved.document_revision;current.document_path=saved.document_path;
        const el=document.getElementById('lnSaved');if(el&&CUR===current)el.textContent='已保存';
        return true;
      }catch(e){if(CUR===current)dirty=true;showError(e);return false;}
    })();
    const ok=await saveP;saveP=null;return ok&&dirty?flush():ok;
  }
  async function close() {
    ++openSeq; opening=false;
    if(!(await flush()))return false;
    const closing=CUR; await finishReading();
    if(CUR!==closing)return;
    try { if (mm) mm.destroy(); } catch (_) {}
    mm = null; CUR = null; editing=false; dirty=false;
    const s = document.getElementById("yjStage");
    if (s) s.remove();
    document.documentElement.classList.remove("yj-on");
    if (typeof VIEW !== "undefined" && VIEW === "train") renderTrain();
    else if (typeof VIEW !== "undefined" && VIEW === "skeleton") window.render();
    updateStudyDot();
    return true;
  }
  async function importFile(f) {
    const Mind = M();
    const ext = f.name.split(".").pop().toLowerCase();
    let root;
    try {
      if (ext === "xmind") root = await Mind.xmind.parseXmindFile(f);
      else {
        const text = await f.text();
        if (ext === "json" || ext === "smm") { const o = JSON.parse(text); root = o.root || o; }
        else root = Mind.markdown.transformMarkdownTo(text);
      }
      plain(root);
      if (!root || !root.data) throw new Error("没认出内容（XMind 要 .xmind 文件；Markdown 用 # 标题或 - 列表分层）");
    } catch (e) { return showError(e); }
    if(!(await flush()))return;
    newMap(CUR.board, { root, layout: "logicalStructure" }, f.name.replace(/\.[^.]+$/, ""));
  }
  async function exportAs(ext) {
    if(!(await flush()))return;
    let data;
    try { data = await mm.export(ext, false, CUR.name); } catch (e) { return showError(e); }
    try {
      const r = await api("/api/mindmap/export", { board: CUR.board, name: CUR.name, ext, data });
      const local = ["127.0.0.1", "localhost", "[::1]"].includes(location.hostname);
      const el = document.createElement("div");
      el.className = "toast nt-pdf-toast";
      el.innerHTML = `📤 导出好了：${esc(r.name)}<div class="small muted">${esc(r.path)}</div>
        <div class="row">${local ? '<button class="small primary" data-o="open">打开</button>' : `<a class="small" href="${esc(r.url)}" download="${esc(r.name)}" target="_blank" rel="noopener">⬇ 下载到这台设备</a>`}
          <span class="spacer"></span><button class="small ghost" data-o="x">关</button></div>`;
      document.getElementById("toasts").appendChild(el);
      const tm = setTimeout(() => el.remove(), 20000);
      el.querySelector('[data-o="x"]').onclick = () => { clearTimeout(tm); el.remove(); };
      const o = el.querySelector('[data-o="open"]');
      if (o) o.onclick = async () => { try { await api("/api/notes/open", { path: r.path }); } catch (e) { showError(e); } };
    } catch (e) { showError(e); }
  }
  addEventListener("beforeunload", () => { if (dirty && mm && CUR) navigator.sendBeacon?.("/api/mindmap/save", new Blob([JSON.stringify({ board: CUR.board, name: CUR.name, data: mm.getData(true), document_revision: CUR.document_revision })], { type: "application/json" })); });

  // 只读文档用文本节点生成层级，用户HTML不进入页面；双栏只移动视图，不触发保存。
  function outline(root) {
    const children=n=>(n.children||[]).length?`<ul>${n.children.map(c=>`<li><span>${esc(c.data?.text||'')}</span>${children(c)}</li>`).join('')}</ul>`:'';
    return `<h1>${esc(root.data?.text||'')}</h1>${children(root)}`;
  }
  function setViewMode(mode) {
    viewMode=mode;const body=document.querySelector('.ln-reading-body');if(!body)return;
    body.dataset.mode=mode;document.getElementById('lnCanvas').hidden=mode==='document';document.getElementById('lnMarkdown').hidden=mode==='map';
    document.querySelectorAll('[data-ln-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.lnMode===mode)));
    if(mode!=='document')requestAnimationFrame(()=>{try{mm.resize();mm.view.fit();}catch(_){}});
  }
  async function localDocument() {
    if(!CUR?.document_path)return;
    if(['127.0.0.1','localhost','[::1]'].includes(location.hostname)) {
      try{await api('/api/mindmap/local',{board:CUR.board,name:CUR.name});}catch(e){showError(e);}
    } else toast('在电脑资料库中编辑：'+esc(CUR.document_path)+'；保存后点重新载入');
  }
  async function finishReading() {
    const token=CUR?.reading_token;if(!token)return;
    CUR.reading_token='';updateStudyDot();
    await window.finishMindmapReading?.(token);
    await api('/api/mindmap/stop',{token}).catch(()=>{});
  }
  ['pointerdown','pointermove','keydown','wheel','touchstart','scroll'].forEach(ev=>addEventListener(ev,()=>{if(CUR&&!editing)lastRead=Date.now();},{passive:true,capture:true}));
  const active=()=>!!CUR?.reading_token&&!editing&&document.visibilityState==='visible'&&Date.now()-lastRead<120000;
  window.MINDMAP = { hubHtml, bindHub, open, close, active, token:()=>CUR?.reading_token||'', board:()=>CUR?.board||'', isOpen: () => opening || !!CUR };

})();
