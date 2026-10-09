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

  async function listHtml() {
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
    const lib = () => { LIB.tab = "bank"; go("skeleton"); };
    const l1 = root.querySelector("#slToLib"), l2 = root.querySelector("#slToLib2");
    if (l1) l1.onclick = lib;
    if (l2) l2.onclick = lib;
    root.querySelectorAll("[data-slq]").forEach((c) => (c.onclick = () => { open(c.dataset.slq); }));
    const back = root.querySelector("#slBack");
    if (back) back.onclick = () => { S.page = "list"; S.result = null; rerender(); };
    const ta = root.querySelector("#slAns");
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

  function open(qid) {
    HALL = "shizhan"; S.page = "answer"; S.qid = qid; S.q = null; S.result = null; S.draftText = ""; S.draftFor = "";
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
    return `<div class="sl-lib">${imp}${list}</div>`;
  }

  function bindLib(root) {
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

  window.SHENLUN = { hallStat, hallHtml, bindHall, libHtml, bindLib, active, board };
})();
