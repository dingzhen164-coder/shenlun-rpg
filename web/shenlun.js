/* ✍ 实操：申论题库、作答、采分点批改（后端 rpg/shenlun.py，接口 /api/shenlun/*）。
   两处用到：
   - 办理殿「实操」厅（HALL = shizhan）：题库列表 → 作答 → 批改结果；
   - 档案室「📑 题库 · 采分点」：导入真题解析文档、让 AI 起草采分点、审定定稿。
   在作答页写答案会计入“做题”学时：敲键盘时通知后端（节流），后端核对 2 分钟内有操作才算。 */
"use strict";
(() => {
  const S = { page: "list", qid: "", q: null, result: null, busy: false, lastKey: 0, lastPing: 0, stat: "", qs: null };
  const HIT = { full: ["落实", "ok"], half: ["部分落实", "half"], none: ["未落实", "none"] };
  const post = (url, body) => api(url, body || {});
  const rerender = () => (VIEW === "train" ? renderTrain() : render());

  // ---------------------------------------------------------------- 办理殿 · 实操
  function hallStat() { return S.stat || "作答批改"; }

  async function hallHtml() {
    return S.page === "answer" ? answerHtml() : listHtml();
  }

  async function legacyListHtml() {
    let d;
    try { d = await api("/api/shenlun/questions"); } catch (e) { return `<div class="card muted">${esc(e.message)}</div>`; }
    S.qs = d.questions;
    const scored = (d.recent || []).filter((x) => !x.draft);
    S.stat = d.questions.length ? `${d.questions.length} 道题${scored.length ? " · 最近 " + Math.round(scored[0].rate * 100) + "%" : ""}` : "题库还是空的";
    const head = `<div class="card sl-head"><div class="row"><h3 style="margin:0">✍ 实操 <small>写完交卷，领导按采分点逐条批阅，分数由程序计算</small></h3><span class="spacer"></span>
      <button class="ghost small" id="slToLib">📑 题库 · 导入</button></div></div>`;
    if (!d.questions.length) {
      return head + `<div class="card sl-empty"><div class="sl-empty-ico">📄</div><b>题库还是空的</b>
        <p class="muted">先把真题解析文档（PDF 或文本）导入：到「${esc(NAV("skeleton"))} · 题库 · 采分点」，选文件，让 AI 起草采分点，审定后就能在这里作答了。</p>
        <button class="primary" id="slToLib2">去导入</button></div>`;
    }
    const cards = d.questions.map((q) => `<div class="card sl-q" data-slq="${esc(q.qid)}">
      <div class="row"><span class="tag cur">${esc(q.type || "未分类")}</span>${q.status === "已定稿" ? '<span class="tag ok">已定稿</span>' : '<span class="tag lock">草稿</span>'}
        <span class="small muted">${esc(q.qid)} · ${q.total} 分${q.words ? " · " + q.words + " 字" : ""} · ${q.points} 个采分点</span></div>
      <p class="sl-stem">${esc((q.stem || "（未录入题干）").split("\n")[0])}</p>
      <div class="row"><span class="spacer"></span><button class="primary small">${q.status === "已定稿" ? "作答" : "试批"}</button></div></div>`).join("");
    const recent = (d.recent || []).length ? `<div class="card"><h3>📜 最近批改</h3>${d.recent.map((x) => `<div class="sl-rec"><span class="small faint">${esc(x.d)}</span>
      <b>${esc(x.qid)}</b><span class="small muted">${esc(x.board || "")}</span><span class="spacer"></span>
      ${x.draft ? '<span class="tag lock">试批</span>' : ""}<span class="sl-rate"><i style="width:${Math.round(x.rate * 100)}%"></i></span><b>${x.score}/${x.full}</b>
      ${(x.lost || []).map((c) => `<span class="tag bad">${esc(c)}</span>`).join("")}</div>`).join("")}</div>` : "";
    return head + `<div class="sl-grid">${cards}</div>` + recent;
  }

  async function answerHtml() {
    if (!S.q || S.q.qid !== S.qid) {
      try { S.q = await post("/api/shenlun/question", { qid: S.qid }); }
      catch (e) { S.page = "list"; return `<div class="card muted">${esc(e.message)}</div>` + (await listHtml()); }
    }
    if (S.q.complete_bank) return fullAnswerHtml();
    const q = S.q, draft = q.status !== "已定稿";
    return `<div class="sl-ans-grid">
      <div class="sl-left">
        <div class="card"><div class="row"><button class="ghost small" id="slBack">← 回题库</button><span class="spacer"></span>
          <span class="tag cur">${esc(q.type || "未分类")}</span><span class="small muted">${esc(q.qid)} · ${q.total} 分${q.words ? " · 不超过 " + q.words + " 字" : ""}</span>${draft ? '<span class="tag lock">草稿 · 试批</span>' : ""}</div>
          <p class="sl-stem big">${esc(q.stem || "（未录入题干）").replace(/\n/g, "<br>")}</p></div>
        ${draft ? `<div class="warn small">采分点还是草稿：可以试批，但不计入政绩和${esc(W("root"))}。到「${esc(NAV("skeleton"))} · 题库」审定后才计分。</div>` : ""}
        <div class="card"><textarea id="slAns" class="sl-ta" placeholder="在这里作答……" spellcheck="false"></textarea>
          <div class="row" style="margin-top:8px"><span class="small muted" id="slCnt">0 字${q.words ? " / " + q.words : ""}</span><span class="spacer"></span>
          <button class="primary" id="slSubmit">交卷批改</button></div></div></div>
      <div class="sl-right" id="slRes">${S.result ? resultHtml(S.result) : '<div class="card sl-empty"><div class="sl-empty-ico">🖊</div><b>等你交卷</b><p class="muted">批改结果会出现在这里</p></div>'}</div></div>`;
  }

  function resultHtml(r) {
    if (r.standard_hash) return comprehensiveHtml(r);
    const pct = Math.round(r.rate * 100);
    const rows = r.points.map((p) => {
      const [lab, cls] = HIT[p.hit];
      return `<div class="sl-pt ${cls}"><div class="row"><b>${p.bonus ? "加分 · " : ""}${esc(p.name)}</b><span class="tag sl-${cls}">${lab}</span><span class="spacer"></span><b>${p.earned} / ${p.score}</b></div>
        ${p.reason ? `<div class="small muted">${esc(p.reason)}</div>` : ""}${p.evidence ? `<blockquote class="sl-ev">${esc(p.evidence)}</blockquote>` : ""}
        ${p.flag ? `<div class="small bad">${esc(p.flag)}</div>` : ""}</div>`;
    }).join("");
    const ded = r.deductions.map((d) => `<div class="sl-pt none"><div class="row"><b>${esc(d.reason)}</b><span class="spacer"></span><b>-${d.points}</b></div></div>`).join("");
    const lost = r.lost.length ? `<div class="row" style="margin-top:8px;flex-wrap:wrap">${r.lost.map((x) => `<span class="tag bad" title="${esc(x.note)}">${esc(x.code)} ${esc(x.name)}</span>`).join("")}</div>` : "";
    return `<div class="card sl-score ${r.draft ? "trial" : ""}"><div class="sl-ring" style="--p:${pct}"><div><b>${r.total}</b><small>/ ${r.full}</small></div></div>
        <div><div class="rune">${r.draft ? "试批 · 不计入政绩" : "本次得分"}</div><div class="sl-pct">得分率 ${pct}% · ${r.words} 字</div>${lost}</div></div>
      ${r.summary ? `<div class="card sl-pishi"><div class="npc">${tutorFace()}<div><b>${esc(DASH?.persona?.tutor || "")}</b> <small class="muted">批示</small>
        <div class="sl-quote">${esc(r.summary)}</div></div></div></div>` : ""}
      <div class="card"><h3>采分点 <small>${r.points.filter((p) => !p.bonus).length} 个</small></h3>${rows}${ded}</div>
      <div class="small muted">复盘已保存到 ${esc(r.review_file)}</div>`;
  }

  function bindHall(root) {
    bindBank(root);
    const lib = () => { LIB.tab = "bank"; go("skeleton"); };
    const l1 = root.querySelector("#slToLib"), l2 = root.querySelector("#slToLib2");
    if (l1) l1.onclick = lib;
    if (l2) l2.onclick = lib;
    root.querySelectorAll("[data-slq]").forEach((c) => (c.onclick = () => { open(c.dataset.slq); }));
    const back = root.querySelector("#slBack");
    if (back) back.onclick = async () => { if (!(await leaveAnswer())) return; S.page = "list"; S.result = null; rerender(); };
    const ta = root.querySelector("#slAns");
    if (ta && S.q.complete_bank) { bindFullAnswer(root, ta); return; }
    if (ta) {
      ta.value = S.draftText && S.draftFor === S.qid ? S.draftText : "";
      const count = () => {
        const n = ta.value.replace(/\s/g, "").length, c = root.querySelector("#slCnt");
        c.textContent = n + " 字" + (S.q.words ? " / " + S.q.words : "");
        c.classList.toggle("bad", !!S.q.words && n > S.q.words * 1.1);
      };
      ta.oninput = () => {
        S.lastKey = Date.now(); S.draftText = ta.value; S.draftFor = S.qid; count();
        if (Date.now() - S.lastPing > 15000) { S.lastPing = Date.now(); post("/api/shenlun/active").catch(() => {}); }
      };
      count();
      root.querySelector("#slSubmit").onclick = () => submit(root, ta);
    }
  }

  async function open(qid) {
    if (!(await leaveAnswer())) return;
    S.draftText = ""; S.draftFor = ""; S.q = null; S.result = null; S.qid = qid;
    if (qid.startsWith("slq-")) {
      try {
        S.q = await post("/api/shenlun/question", { qid });
        const d = await post("/api/shenlun/answer", { qid });
        S.draftText = d.text; S.draftFor = qid; B.revision = d.revision; B.seconds = d.seconds;
        B.history = (await post("/api/shenlun/history", { qid })).history; B.dirty = false; B.seq = 0;
        const local = localDraft(qid);
        B.recovery = local && local.text !== d.text ? local : null;
        if (B.recovery && local.revision === d.revision) { S.draftText = local.text; B.dirty = true; }
      } catch (e) { showError(e); return; }
    }
    HALL = "shizhan"; S.page = "answer";
    VIEW === "train" ? renderTrain() : go("train");
  }

  async function submit(root, ta) {
    if (!ta.value.trim()) return toast("先写点什么再交卷");
    if (S.busy) return;
    S.busy = true;
    const btn = root.querySelector("#slSubmit"); btn.disabled = true; btn.textContent = "阅卷中……";
    root.querySelector("#slRes").innerHTML = '<div class="card thinking">领导正在逐条批阅</div>';
    try {
      const r = await post("/api/shenlun/grade", { qid: S.qid, answer: ta.value });
      S.result = r; S.draftText = "";
      root.querySelector("#slRes").innerHTML = resultHtml(r);
      handleEvents(r.events);
      await refresh();
    } catch (e) {
      root.querySelector("#slRes").innerHTML = `<div class="card"><b>批改没成功</b><p class="muted">${esc(e.message)}</p><p class="small muted">这次不计分、不进记录，重试即可。</p></div>`;
    }
    S.busy = false; btn.disabled = false; btn.textContent = "交卷批改";
  }

  function active() {
    return VIEW === "train" && HALL === "shizhan" && S.page === "answer" && document.visibilityState === "visible" && Date.now() - S.lastKey < 120000;
  }
  function board() { return S.q ? S.q.type : ""; }

  // ---------------------------------------------------------------- 档案室 · 题库 · 采分点
  async function libHtml() {
    let d;
    try { d = await api("/api/shenlun/questions"); } catch (e) { return `<div class="card muted">${esc(e.message)}</div>`; }
    const imp = `<div class="card"><h3>📥 导入真题解析文档 <small>PDF（要带文字，不是扫描图）、.txt、.md</small></h3>
      <p class="small muted">选一份机构出的真题解析：程序会识别每道题的题干、分值、字数和“得分要点清单”，再让 AI 把要点表整理成采分点<b>草稿</b>。已存在的采分点不会被覆盖；起草完到下面审定。</p>
      <div class="row"><input id="slPrefix" placeholder="题目编号前缀，如 国考2026-副省 → 生成 国考2026-副省-01、-02…" style="flex:2"><input id="slFile" type="file" accept=".pdf,.txt,.md" style="flex:1"></div>
      <div id="slMsg" class="small muted" style="margin-top:6px"></div><div id="slStep2"></div></div>`;
    const list = d.questions.length ? `<div class="card"><h3>📑 题库 <small>${d.questions.length} 题 · 采分点文件在 训练/采分点/，可以在 Obsidian 里直接改</small></h3>
      ${d.questions.map((q) => `<div class="sl-lib-row"><div class="row"><span class="tag cur">${esc(q.type || "未分类")}</span>
        ${q.status === "已定稿" ? '<span class="tag ok">已定稿</span>' : '<span class="tag lock">草稿</span>'}<b>${esc(q.qid)}</b>
        <span class="small muted">${q.total} 分 · ${q.points} 个采分点${q.words ? " · " + q.words + " 字" : ""}</span><span class="spacer"></span>
        ${q.status !== "已定稿" ? `<button class="small" data-slfin="${esc(q.qid)}" ${q.errors.length ? 'title="' + esc(q.errors.join("；")) + '"' : ""}>审定并定稿</button>` : ""}
        <button class="primary small" data-slopen="${esc(q.qid)}">作答</button></div>
        ${q.status !== "已定稿" && q.errors.length ? `<div class="small bad">还不能定稿：${esc(q.errors.join("；"))}</div>` : ""}
        <div class="small muted sl-stem-line">${esc((q.stem || "").split("\n")[0])}</div></div>`).join("")}</div>`
      : `<div class="card muted">题库还是空的，先导入一份解析文档。</div>`;
    return `<div class="sl-lib">${await bankHtml(true)}<details class="card"><summary>旧版解析文档与采分点</summary>${imp}${list}</details></div>`;
  }

  function bindLib(root) {
    bindBank(root);
    root.querySelectorAll("[data-slopen]").forEach((b) => (b.onclick = () => open(b.dataset.slopen)));
    root.querySelectorAll("[data-slfin]").forEach((b) => (b.onclick = async () => {
      try { await post("/api/shenlun/finalize", { qid: b.dataset.slfin }); toast("已定稿"); render(); } catch (e) { showError(e); }
    }));
    const fileEl = root.querySelector("#slFile"), msg = root.querySelector("#slMsg");
    if (!fileEl) return;
    const b64 = (f) => new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(",")[1]); r.onerror = no; r.readAsDataURL(f); });
    fileEl.onchange = async () => {
      const f = fileEl.files[0]; if (!f) return;
      const pre = root.querySelector("#slPrefix");
      if (!pre.value.trim()) pre.value = f.name.replace(/\.[^.]+$/, "").slice(0, 24);
      msg.className = "small muted"; msg.textContent = "上传并识别中……"; root.querySelector("#slStep2").innerHTML = "";
      try {
        const j = await post("/api/shenlun/import", { name: f.name, data: await b64(f) });
        msg.textContent = `识别到 ${j.questions.length} 道题`;
        showQuestions(root, j, pre);
      } catch (e) {
        msg.className = "small bad"; msg.textContent = e.message;
        if (/pymupdf/.test(e.message)) {
          msg.insertAdjacentHTML("afterend", '<div style="margin-top:8px"><button class="small" id="slInst">安装 PDF 读取组件（只需一次，需要联网）</button></div>');
          root.querySelector("#slInst").onclick = async (ev) => {
            const b = ev.currentTarget; b.disabled = true; b.textContent = "安装中，请稍候……";
            try { await post("/api/shenlun/install_pdf"); toast("安装完成，请重新选择文件"); b.remove(); fileEl.value = ""; msg.className = "small muted"; msg.textContent = "安装完成，请重新选择文件"; }
            catch (e2) { b.textContent = "安装失败：" + e2.message; }
          };
        }
      }
    };
  }

  function showQuestions(root, j, pre) {
    const box = root.querySelector("#slStep2");
    box.innerHTML = `<ul class="sl-rec-list">${j.questions.map((q) => `<li id="slq${q.no}"><div class="row"><b>第 ${q.no} 题</b><span class="tag cur">${esc(q.type || "题型未识别")}</span>
        <span class="small muted">${q.score || "?"} 分 · ${q.words || "?"} 字 · 要点表 ${q.table_lines} 行 · 参考答案 ${q.answers} 份</span></div>
        <div class="small muted">${esc(q.stem)}</div><div class="small" id="slr${q.no}"></div></li>`).join("")}</ul>
      <div class="row" style="margin-top:8px"><button class="primary" id="slGo">让 AI 起草采分点</button><span class="small muted">已存在的采分点不会被覆盖</span></div>`;
    root.querySelector("#slGo").onclick = async (ev) => {
      const btn = ev.currentTarget; btn.disabled = true; let n = 0;
      for (const q of j.questions) {
        const out = root.querySelector("#slr" + q.no); out.className = "small muted"; out.textContent = "AI 起草中……";
        try {
          const d = await post("/api/shenlun/draft", { file: j.file, prefix: pre.value.trim(), no: q.no });
          out.className = "small " + (d.skipped ? "muted" : "ok");
          out.textContent = d.skipped ? "已存在，跳过" : `✓ 已生成 ${d.points} 个采分点` + (d.warnings && d.warnings.length ? "；需处理：" + d.warnings.join("；") : "");
          if (!d.skipped) n++;
        } catch (e) { out.className = "small bad"; out.textContent = "失败：" + e.message; }
      }
      btn.disabled = false; toast(`完成：新生成 ${n} 题，到下面题库里审定`);
      setTimeout(render, 1200);
    };
  }

  // 完整真题：题干材料与作答分开，参考资料只在批改后展示。
  const B = { papers: [], region: '', year: '', type: '', search: '', page: 0, dirty: false, seq: 0, revision: 0, seconds: 0, saving: null, timer: null, history: [], recovery: null };
  const localDraft = qid => { try { return JSON.parse(localStorage.getItem('sl.draft.' + qid) || 'null'); } catch (_) { return null; } };
  const keepDraft = () => { try { localStorage.setItem('sl.draft.' + S.qid, JSON.stringify({ text: S.draftText, revision: B.revision, updated: Date.now() })); } catch (_) {} };
  const uid = () => [...crypto.getRandomValues(new Uint8Array(16))].map(x => x.toString(16).padStart(2, '0')).join('');
  async function listHtml() {
    const full = await bankHtml(false);
    const legacy = await legacyListHtml();
    return full + `<details class="card"><summary>旧版采分点练习</summary>${legacy}</details>`;
  }
  async function bankHtml(importing) {
    const d = await api('/api/shenlun/papers'); B.papers = d.papers;
    const controls = `<div class="card sl-bank-head"><div class="row"><h3>📑 完整真题 <small>录入 → 作答 → 证据批改 → 修改复练</small></h3><span class="spacer"></span>${importing ? '' : '<button class="ghost small" id="slBankImport">录入真题</button>'}</div>
      <p class="small muted">按题干和给定资料独立作答，交卷前隐藏参考答案。批改建议分供训练使用，评分标准同题固定。</p>
      <button class="primary" id="slSourceStart">⬇ 下载并录入公开申论题库</button> <button class="ghost small" id="slBankRefresh">刷新题库</button>
      <div class="small muted" id="slSourceStatus">首次下载约330MB，保存到电脑的申论库；重复录入保留已有题目。</div>
      ${importing ? `<details class="sl-bank-input"><summary>导入自己的题目包（JSON）</summary><p class="small muted">可导入整套或多套；包含title、materials和questions。材料原文、参考答案只存本地。</p><input type="file" id="slPackage" accept=".json"><button class="ghost small" id="slTemplate">下载格式模板</button><div id="slImportMessage" class="small muted"></div></details>
      <details class="sl-bank-input"><summary>手动录入一道题</summary><div class="sl-manual-grid">
      <label>试卷标题<input id="slManualTitle" placeholder="如2026国考行政执法"></label><label>地区<input id="slManualRegion" placeholder="国考 / 贵州"></label>
      <label>题型<select id="slManualType">${['归纳概括','综合分析','提出对策','贯彻执行','大作文'].map(x=>`<option>${x}</option>`).join('')}</select></label>
      <label>满分<input id="slManualScore" type="number" min="1" max="150" value="20"></label><label>字数上限<input id="slManualWords" type="number" min="0" max="5000" value="300"></label></div>
      <label>题干及要求<textarea id="slManualStem" rows="3" placeholder="粘贴完整题干及作答要求"></textarea></label>
      <label>对应给定资料<textarea id="slManualMaterial" rows="7" placeholder="粘贴本题需要的完整材料，保留材料编号"></textarea></label>
      <label>参考答案（可空）<textarea id="slManualReference" rows="3"></textarea></label><button id="slManualSave" class="primary">录入并保存</button><div id="slManualMessage" class="small muted"></div></details>` : ''}</div>`;
    return controls + '<div id="slPaperList">' + paperListHtml() + '</div>';
  }
  function paperListHtml() {
    const regions = [...new Set(B.papers.map(p=>p.region))].sort(), years = [...new Set(B.papers.map(p=>p.year))].sort().reverse();
    const select = (id, values, value, label) => `<select id="${id}" aria-label="${label}"><option value="">${label}</option>${values.map(x=>`<option ${x===value?'selected':''}>${esc(x)}</option>`).join('')}</select>`;
    const filtered = B.papers.filter(p=>(!B.region||p.region===B.region)&&(!B.year||p.year===B.year)&&(!B.search||p.title.includes(B.search))).map(p=>({...p,questions:p.questions.filter(q=>!B.type||q.type===B.type)})).filter(p=>p.questions.length);
    const count = Math.ceil(filtered.length/12); B.page = Math.min(B.page, Math.max(0,count-1));
    const filter = `<div class="card row sl-bank-filters">${select('slFilterRegion',regions,B.region,'全部地区')}${select('slFilterYear',years,B.year,'全部年份')}${select('slFilterType',['归纳概括','综合分析','提出对策','贯彻执行','大作文'],B.type,'全部题型')}<input id="slFilterSearch" placeholder="搜索试卷" value="${esc(B.search)}"><span class="small muted">${filtered.length}套 · ${filtered.reduce((n,p)=>n+p.questions.length,0)}题</span></div>`;
    if (!filtered.length) return filter + '<div class="card sl-empty">还没有匹配的完整真题。可下载公开题库，或在档案室录入自己的题目。</div>';
    return filter + filtered.slice(B.page*12,B.page*12+12).map(p=>`<details class="card sl-paper"><summary><b>${esc(p.title)}</b><span class="tag">${esc(p.region)}</span><span class="small muted">${p.questions.length}题 · ${esc(p.edition)}</span></summary><p class="small muted">${esc(p.source)} · 材料${p.materials}则</p>${p.questions.map(q=>`<div class="sl-paper-q"><span class="tag cur">第${q.no}题 · ${esc(q.type)}</span><span class="small muted">${q.total||'分值待补'}分${q.words?' · '+q.words+'字':''}</span>${q.complete?'':'<span class="tag bad">资料待补全</span>'}<p>${esc(q.stem)}</p><button class="primary small" data-slq="${esc(q.qid)}">作答</button></div>`).join('')}</details>`).join('') + `<div class="card row"><button id="slPaperPrev" ${B.page?'':'disabled'}>← 上一页</button><span>第${B.page+1}/${count}页</span><button id="slPaperNext" ${B.page<count-1?'':'disabled'}>下一页 →</button></div>`;
  }
  function bindBank(root) {
    const $ = s=>root.querySelector(s);
    const redraw = () => { const box=$('#slPaperList'); if(box) { box.innerHTML=paperListHtml(); bindBank(root); } };
    for (const [id,key] of [['#slFilterRegion','region'],['#slFilterYear','year'],['#slFilterType','type']]) { const el=$(id); if(el)el.onchange=()=>{B[key]=el.value;B.page=0;redraw();}; }
    const search=$('#slFilterSearch'); if(search)search.onchange=()=>{B.search=search.value.trim();B.page=0;redraw();};
    root.querySelectorAll('[data-slq]').forEach(el=>el.onclick=()=>open(el.dataset.slq));
    const prev=$('#slPaperPrev'),next=$('#slPaperNext'); if(prev)prev.onclick=()=>{B.page--;redraw();};if(next)next.onclick=()=>{B.page++;redraw();};
    const imp=$('#slBankImport');if(imp)imp.onclick=()=>{LIB.tab='bank';go('skeleton');};
    const refreshBtn=$('#slBankRefresh');if(refreshBtn)refreshBtn.onclick=rerender;
    const status=$('#slSourceStatus'),start=$('#slSourceStart');
    async function progress() {
      if(!status?.isConnected)return;
      try {const d=await post('/api/shenlun/bank_source'); status.textContent=d.message+(d.running?' · '+d.progress+'%':'');start.disabled=d.running;
        if(d.running)setTimeout(progress,1500);
      } catch(e) {status.textContent=e.message;}
    }
    if(start) {start.onclick=async()=>{start.disabled=true;try{await post('/api/shenlun/bank_source',{start:true});progress();}catch(e){showError(e);start.disabled=false;}};progress();}
    const file=$('#slPackage');if(file)file.onchange=async()=>{const f=file.files[0];if(!f)return;const msg=$('#slImportMessage');try{if(f.size>32*1024*1024)throw Error('题目包最大32MB');const papers=JSON.parse(await f.text());const d=await post('/api/shenlun/bank_import',{papers});msg.textContent=`新增${d.added}套，已有${d.skipped}套保留`;toast(msg.textContent);rerender();}catch(e){msg.textContent=e.message;}};
    const template=$('#slTemplate');if(template)template.onclick=()=>{const data={title:'自编示例卷（请替换为你的试卷）',region:'自编',year:'2026',sourceName:'用户提供',materials:[{id:'1',label:'材料1',text:'在这里粘贴完整材料原文'}],questions:[{type:'贯彻执行',text:'在这里粘贴题干和要求',score:20,limit:400,material_ids:['1'],references:[]}]};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='申论题目包模板.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    const manual=$('#slManualSave');if(manual)manual.onclick=async()=>{const msg=$('#slManualMessage');try{const material=$('#slManualMaterial').value.trim();if(!material)throw Error('请填写对应完整材料');const ref=$('#slManualReference').value.trim();const papers={title:$('#slManualTitle').value.trim(),region:$('#slManualRegion').value.trim(),sourceName:'用户录入',materials:[{text:material,label:'对应给定资料'}],questions:[{text:$('#slManualStem').value.trim(),type:$('#slManualType').value,score:Number($('#slManualScore').value),limit:Number($('#slManualWords').value),references:ref?[{organization:'用户提供',answer:ref}]:[]}]};const d=await post('/api/shenlun/bank_import',{papers});msg.textContent=`新增${d.added}套，已有${d.skipped}套保留`;toast(msg.textContent);rerender();}catch(e){msg.textContent=e.message;}};
  }
  // 来源段落优先；无段落时仅做阅读分隔，不冒充原文段落、不改材料内容。
  function materialHtml(text) {
    let paras=String(text||'').split(/\r\n?|\n/).map(x=>x.trim()).filter(Boolean);
    const reading=paras.length===1 && [...paras[0]].length>300;
    if(reading){
      const sentences=paras[0].match(/[^。！？]*[。！？]+[”’」』]*|[^。！？]+$/g)||paras;
      paras=[];let current='';
      for(const sentence of sentences){current+=sentence;if([...current].length>=200){paras.push(current);current='';}}
      if(current)paras.push(current);
    }
    return `${reading?'<p class="small muted sl-paragraph-note">来源未标注段落，以下按句群分隔阅读；不代表原文段落。</p>':''}<div class="sl-material-text">${paras.map(x=>`<p>${esc(x)}</p>`).join('')}</div>`;
  }
  function fullAnswerHtml() {
    const q=S.q;
    return `<div class="card"><div class="row"><button class="ghost small" id="slBack">← 回题库</button><span class="tag cur">${esc(q.type)}</span><b>${esc(q.paper_title)} · 第${q.no}题</b><span class="spacer"></span><span>${q.total||'待补分值'}分${q.words?' · '+q.words+'字':''}</span></div><p class="sl-stem big">${esc(q.stem).replace(/\[materialid\](\d+)\[\/materialid\]/g,'〔原库材料ID：$1〕').replace(/\n/g,'<br>')}</p>${q.stem.includes('[materialid]')?'<p class="small warn">来源库的材料ID不是下方材料序号；下方保留整卷资料，请先按题干内容核对本题对应材料。</p>':''}${q.requirement?`<p>${esc(q.requirement)}</p>`:''}<div class="small muted">${esc(q.edition)} · ${esc(q.source)}</div></div>
      ${q.complete?'':'<div class="warn">本题缺少材料或分值，可以先保存作答；请在本地训练/题库/申论真题中核对并补全材料、分值后，再刷新题库进行批改。</div>'}
      <div class="sl-full-grid"><section class="card sl-materials"><h3>给定资料 <small>交卷前不显示参考答案</small></h3>${q.materials.map(m=>`<article><h4>${esc(m.label)}</h4>${materialHtml(m.text)}</article>`).join('')||'<p class="muted">尚未录入材料</p>'}</section>
      <section class="card sl-writing"><div class="row"><h3>我的作答</h3><span class="spacer"></span><span class="small muted" id="slSaveStatus">已保存 · 有效编辑${Math.floor(B.seconds/60)}分钟</span><button class="ghost small" id="slDraftSave">保存</button></div>
      ${B.recovery?'<button class="ghost small" id="slRecover">恢复本机未保存文字</button>':''}<textarea id="slAns" class="sl-ta" spellcheck="false" placeholder="输入答案，或粘贴你已经写好的报告……"></textarea>
      <div class="row"><span class="small muted" id="slCnt"></span><span class="spacer"></span><button class="primary" id="slSubmit" ${q.complete?'':'disabled'}>交卷 · 综合批改</button></div>
      <p class="small muted">材料、题干和本次答案会发给设置中的AI。先建立材料评分标准，再按含义判断；失败不计分，草稿保留。</p>
      ${B.history.length?`<details><summary>历史作答与批改（${B.history.length}稿）</summary>${B.history.map((x,i)=>`<button class="ghost small" data-slhistory="${i}">第${i+1}稿 · ${x.result.total}/${x.result.full}</button>`).join('')}</details>`:''}</section></div>
      <section id="slRes">${S.result?comprehensiveHtml(S.result):'<div class="card muted">交卷后显示材料证据、原句点评、专项检查与修改建议。</div>'}</section>`;
  }
  function comprehensiveHtml(r) {
    const points=r.points.map(x=>`<div class="sl-pt ${x.hit}"><div class="row"><b>${esc(x.name)}</b><span class="tag">${HIT[x.hit][0]}</span><span class="spacer"></span><span>${x.earned}/${x.score}</span></div><p class="sl-point-action">${x.hit==='full'?'核心含义已覆盖，保持。':esc(x.suggestion||x.reason||'补充该核心含义。')}</p><details class="sl-point-detail"><summary>查看材料与作答证据</summary><p class="small"><b>材料依据：</b>${esc(x.material_quote)}</p><blockquote class="sl-ev"><b>你的原句：</b>${esc(x.evidence||'未体现')}</blockquote><p class="small">${esc(x.reason)}</p></details></div>`).join('');
    return `<div class="card sl-pishi"><div class="row"><h3>领导批示 · 综合批改</h3><span class="spacer"></span><b class="sl-review-total">${r.total}/${r.full}</b></div><p>${esc(r.summary)}</p><div class="row">${r.parts.map(x=>`<span class="tag">${esc(x.name)} ${x.earned}/${x.full}</span>`).join('')}<span class="small muted">${r.words}字 · ${esc(r.method)}</span></div><p class="small muted">${esc(r.scoring_note)}${r.word_warning?' · '+esc(r.word_warning):''}</p></div>
      ${r.comparison?`<div class="card sl-comparison"><h3>修改稿对比</h3><p>上一稿${r.comparison.previous}分 → 本稿${r.total}分（${r.comparison.change>=0?'+':''}${r.comparison.change}）</p><p>改善：${esc(r.comparison.improved.join('、')||'暂无新增命中')}</p><p>退步：${esc(r.comparison.regressed.join('、')||'暂无')}</p></div>`:''}
      <div class="card"><h3>题干任务拆解</h3><p>${esc(r.task)}</p></div>
      ${points?`<div class="card"><h3>材料与作答逐点对照</h3>${points}</div>`:''}
      <div class="sl-review-grid"><div class="card"><h3>结构与表达</h3>${r.dimensions.map(x=>`<div class="sl-pt"><b>${esc(x.name)} · ${x.level}/4档</b><p>${esc(x.reason)}</p><details><summary class="small">查看原句</summary><blockquote class="sl-ev">${esc(x.quote||'尚未体现')}</blockquote></details><p class="small">下一步：${esc(x.improvement||'保持')}</p></div>`).join('')}</div><div class="card"><h3>题型专项检查</h3>${r.checks.map(x=>`<p><b>${esc(x.name)} · ${esc(x.status)}</b><br>${esc(x.reason)}</p>`).join('')||'<p class="muted">本题未返回额外专项检查</p>'}<h3>原句修改建议</h3>${r.revisions.length?`<p class="small ${r.revision_verified?'muted':'warn'}">${r.revision_verified?`将以下修改同时替换原句后共${r.revision_words}字${r.word_limit?' / 上限'+r.word_limit+'字':''}，已由程序核验。`:'历史建议未核验整篇字数，请重新批改后采用。'}</p>`:''}${r.revisions.map(x=>`<div class="sl-pt"><blockquote class="sl-ev">${esc(x.quote)}</blockquote><p><b>建议：</b>${esc(x.rewrite)}</p><p class="small muted">${esc(x.reason)}</p></div>`).join('')||'<p class="muted">优先按采分点缺口修改</p>'}</div></div>
      <details class="card"><summary>交卷后参考资料</summary>${r.references.map(x=>`<h4>${esc(x.source)}</h4><p>${esc(x.answer).replace(/\n/g,'<br>')}</p>`).join('')}${r.analysis?`<h4>来源库解析（非官方细则）</h4><p>${esc(r.analysis).replace(/\n/g,'<br>')}</p>`:''}${!r.references.length&&!r.analysis?'<p>该题未提供参考答案或解析。</p>':''}</details><p class="small muted">复盘已保存：${esc(r.review_file)}</p>`;
  }
  function saveLabel(value) {const el=document.getElementById('slSaveStatus');if(el)el.textContent=value;}
  async function flushDraft() {
    clearTimeout(B.timer);
    if(B.saving)return B.saving;
    B.saving=(async()=>{
      while(B.dirty&&S.q?.complete_bank){
        const qid=S.qid,text=S.draftText,seq=B.seq,revision=B.revision;
        saveLabel('正在保存……');
        try{const d=await post('/api/shenlun/answer',{save:true,qid,text,revision});B.revision=d.revision;B.seconds=d.seconds;
          if(B.seq===seq){B.dirty=false;try{localStorage.removeItem('sl.draft.'+qid);}catch(_){}}else keepDraft();
          saveLabel('已保存 · 有效编辑'+Math.floor(B.seconds/60)+'分钟');
        }catch(e){saveLabel('保存失败，点击“保存”重试');toast(e.message);return false;}
      }return true;
    })();
    try{return await B.saving;}finally{B.saving=null;}
  }
  async function leaveAnswer(){if(S.busy){toast('正在批改，请等本次批改完成');return false;}return flushDraft();}
  function bindFullAnswer(root,ta) {
    ta.value=S.draftText||'';
    const count=()=>{const n=[...ta.value.replace(/\s/g,'')].length;root.querySelector('#slCnt').textContent=n+'字'+(S.q.words?' / '+S.q.words:'');};
    ta.oninput=()=>{S.lastKey=Date.now();S.draftText=ta.value;B.dirty=true;B.seq++;keepDraft();count();saveLabel('未保存');clearTimeout(B.timer);B.timer=setTimeout(flushDraft,800);if(Date.now()-S.lastPing>15000){S.lastPing=Date.now();post('/api/shenlun/active').catch(()=>{});}};count();
    root.querySelector('#slDraftSave').onclick=flushDraft;
    const recover=root.querySelector('#slRecover');if(recover)recover.onclick=()=>{ta.value=B.recovery.text;ta.oninput();recover.remove();};
    root.querySelectorAll('[data-slhistory]').forEach(b=>b.onclick=()=>{S.result=B.history[Number(b.dataset.slhistory)].result;root.querySelector('#slRes').innerHTML=comprehensiveHtml(S.result);});
    root.querySelector('#slSubmit').onclick=async()=>{if(S.busy||!ta.value.trim())return;S.busy=true;const btn=root.querySelector('#slSubmit');btn.disabled=true;ta.disabled=true;
      try{if(!(await flushDraft()))throw Error('答案尚未保存，请先重试保存');btn.textContent='建立标准并阅卷中……';root.querySelector('#slRes').innerHTML='<div class="card thinking">领导正在核对题干、材料与作答证据……</div>';
        const r=await post('/api/shenlun/comprehensive',{qid:S.qid,answer:S.draftText,revision:B.revision,submission_id:(B.pending?.text===S.draftText&&B.pending.qid===S.qid?B.pending.id:(B.pending={text:S.draftText,qid:S.qid,id:uid()}).id)});B.pending=null;S.result=r;root.querySelector('#slRes').innerHTML=comprehensiveHtml(r);B.history=(await post('/api/shenlun/history',{qid:S.qid})).history;handleEvents(r.events);await refresh();
      }catch(e){root.querySelector('#slRes').innerHTML=`<div class="card warn">${esc(e.message)}。答案草稿仍保留；若网络断开，重试会核对本次交卷记录。</div>`;}
      S.busy=false;btn.disabled=false;ta.disabled=false;btn.textContent='交卷 · 综合批改';};
    if(B.dirty)B.timer=setTimeout(flushDraft,800);
  }
  addEventListener('beforeunload',e=>{if(B.dirty){keepDraft();e.preventDefault();e.returnValue='';}});
  window.SHENLUN = { hallStat, hallHtml, bindHall, libHtml, bindLib, active, board, flush: leaveAnswer };
})();
