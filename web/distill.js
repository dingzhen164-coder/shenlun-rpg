/* 藏经阁·心法·蒸馏（3.5）：把课程逐字稿 / 习题册解题过程 / 自己的话，蒸馏成一套能学、能迭代的心法（数据来自 /api/distill/*，见 rpg/distill.py）。
   四个分页：素材（贴逐字稿 → 切分 → 拆卡）· 卡片 · 版本（汇总成 v1.0，之后「更新」吸收新卡）· 检验（用题库的题测做对率、诊断错题）。
   每个需要 AI 的步骤有三个选择：▶ 用软件里的 AI / 📋 复制提示词（去 GPT、Gemini、DeepSeek 等别的平台做）/ 📥 把结果粘回来导入，三条路最后走同一个校验。
   生成的内容都先变成「待审建议」（在页面上方），你勾选采纳后才写进心法文件，并自动存成版本。
   界面状态留在本模块里：切换板块、分页再回来还在原处；由 skillbook.js 在蒸馏页签里 mount。 */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (n) => Number(n || 0).toLocaleString("en-US");
  const TYPES = ["框架", "考点", "例题", "闲聊"];
  const SIZES = { "保守（6000 字一包）": 6000, "常规（12000 字一包）": 12000, "大（30000 字一包）": 30000 };
  let EL = null, BOARD = "", ST = null, HOOKS = {}, BUSY = "";
  const UI = { pastes: {}, sub: "mat", open: {}, packs: {}, size: 12000, card: null, cmp: null, result: null, texts: {}, n: 20, form: { kind: "转写", whole: "", title: "", text: "" } };
  let STEPS = {};

  const call = (path, body) => api("/api/distill/" + path, Object.assign({ board: BOARD }, body || {}));
  const note = (m) => HOOKS.note && HOOKS.note(m);
  const md = (t) => (window.MDLITE ? MDLITE.render(t) : `<pre>${esc(t)}</pre>`);

  async function load() {
    try { ST = await call("state"); } catch (e) { ST = null; note(e.message); }
    render();
  }

  // ---------------------------------------------------------------- 通用：AI 步骤的三个选择
  function stepBox(key, step, params, opt = {}) {
    STEPS[key] = { step, params, opt };
    const pk = UI.packs[key];
    const parts = pk ? pk.parts.map((p, i) => `<div class="dst-pack-part"><div class="small"><b>${esc(p.title)}</b> · ${num(p.chars)} 字 ${i === 0 ? `<span class="muted">${esc(pk.how)}</span>` : ""}</div>
        <textarea class="dst-pack" readonly rows="3" data-dst-sel>${esc(p.text)}</textarea>
        <div class="dst-row"><button class="small" data-dst="copy" data-key="${esc(key)}" data-i="${i}">📋 复制这一包</button>
        <button class="ghost small" data-dst="import" data-key="${esc(key)}" data-i="${i}">📥 导入下面粘贴的回复</button></div>
        <textarea class="dst-paste" rows="3" data-paste="${esc(key)}:${i}" placeholder="把别的平台回复的内容整段粘贴到这里">${esc(UI.pastes[key + ":" + i] || "")}</textarea></div>`).join("") : "";
    return `<div class="dst-step"><div class="dst-row">
        <button class="primary small" data-dst="ai" data-key="${esc(key)}" ${ST.ai || opt.noAi ? "" : "disabled"} ${BUSY ? "disabled" : ""} title="${ST.ai ? "调用你设置里的 AI（会先告诉你要调用几次）" : "需要先在设置里填 AI 的 API key"}">▶ ${esc(opt.label || "用软件里的 AI")}</button>
        <button class="ghost small" data-dst="pack" data-key="${esc(key)}" ${BUSY ? "disabled" : ""} title="生成一段提示词，复制到 GPT / Gemini / DeepSeek 等平台，省软件里的额度">📋 复制提示词，去别的平台做</button>
        ${BUSY === key ? '<span class="small muted" role="status">处理中，请稍等……</span>' : ""}</div>${parts}</div>`;
  }

  async function runStep(key, mode, extra) {
    const s = STEPS[key];
    if (!s) return;
    const body = Object.assign({ step: s.step, params: s.params, mode, size: UI.size }, extra || {});
    try {
      if (mode === "ai") {
        const est = await call("step", Object.assign({}, body, { mode: "estimate" }));
        if (!confirm(`这一步要调用 ${est.calls} 次 AI，大约读 ${num(est.chars)} 字（花你自己的 API 额度）。继续吗？`)) return;
        BUSY = key; render(); note("AI 正在处理，请稍等……");
      }
      const r = await call("step", body);
      if (mode === "pack") { UI.packs[key] = r; BUSY = ""; render(); return; }
      BUSY = ""; delete UI.packs[key];
      Object.keys(UI.pastes).filter((x) => x.startsWith(key + ":")).forEach((x) => delete UI.pastes[x]);
      await load();
      note(r.message || "完成");
      if (HOOKS.refresh) HOOKS.refresh({ open: !!(r.proposal || (r.results || []).some((x) => x.proposal)) });
    } catch (e) { BUSY = ""; note(e.message || String(e)); render(); }
  }

  // ---------------------------------------------------------------- 素材
  function addForm() {
    const f = UI.form, short = f.kind !== "转写";
    return `<details class="dst-add" ${UI.addOpen || !ST.materials.length ? "open" : ""}><summary class="small"><b>＋ 添加素材</b>（课程逐字稿、习题册的解题过程、或你自己写的解法）</summary>
      <div class="dst-row"><label class="small">种类 <select data-dst-f="kind"><option ${f.kind === "转写" ? "selected" : ""}>转写</option><option ${f.kind === "习题册" ? "selected" : ""}>习题册</option><option ${f.kind === "自述" ? "selected" : ""}>自述</option></select></label>
        <label class="small">名称 <input data-dst-f="title" value="${esc(f.title)}" placeholder="如 328 强化课"></label>
        ${short ? `<label class="small">整份当作 <select data-dst-f="whole"><option value="" ${f.whole === "" ? "selected" : ""}>让 AI 自动切分</option><option value="例题" ${f.whole === "例题" ? "selected" : ""}>一道例题的讲解</option><option value="考点" ${f.whole === "考点" ? "selected" : ""}>一个考点的总结</option></select></label>` : ""}</div>
      <textarea class="dst-text" rows="7" data-dst-f="text" placeholder="把逐字稿整段粘贴到这里（口语废话、语音识别的错字都不用删）。你自己写的解法也一样。">${esc(f.text)}</textarea>
      <div class="dst-row"><button class="primary small" data-dst="mat-add">添加</button><span class="small muted">素材只存在你本机的 训练/技能 文件夹里；你自己的话会作为卡片的主表述，排在老师原话前面。</span></div></details>`;
  }

  function segRows(m) {
    const t = UI.texts;
    return m.segments.map((sg) => `<div class="dst-seg ${sg.type === "闲聊" ? "dim" : ""}">
        <label title="采用这个片段"><input type="checkbox" data-dst-seg="inc" data-m="${m.id}" data-s="${sg.id}" ${sg.include ? "checked" : ""}></label>
        <select data-dst-seg="type" data-m="${m.id}" data-s="${sg.id}">${TYPES.map((x) => `<option ${x === sg.type ? "selected" : ""}>${x}</option>`).join("")}</select>
        <input data-dst-seg="title" data-m="${m.id}" data-s="${sg.id}" value="${esc(sg.title)}" aria-label="片段标题">
        <small class="muted">${num(sg.chars)}字</small>
        ${sg.card ? '<span class="tag ok">已拆卡</span>' : sg.type === "闲聊" || !sg.include ? "" : '<span class="tag draft">未拆卡</span>'}
        <button class="ghost small" data-dst="seg-text" data-m="${m.id}" data-s="${sg.id}">${t[m.id + sg.id] ? "收起" : "看全文"}</button>
        <button class="ghost small" data-dst="seg-merge" data-m="${m.id}" data-s="${sg.id}" title="和后面一个片段合并（一道题被切成两段时用）">⤓ 合并下一个</button>
        <div class="dst-prev small muted">${esc(sg.preview)}…${esc(sg.tail)}</div>${t[m.id + sg.id] ? `<pre class="dst-full">${esc(t[m.id + sg.id])}</pre>` : ""}</div>`).join("");
  }

  function matHtml() {
    const mats = ST.materials.map((m) => {
      const open = UI.open[m.id] !== false;
      const todo = m.segments.filter((s) => s.include && s.type !== "闲聊" && !s.card).map((s) => s.id);
      const body = !open ? "" : `${m.chunks_done < m.n_chunks && !m.segments.length ? `<p class="small">第一步：把整份稿子切成片段（框架 / 考点 / 例题 / 闲聊）。${m.n_chunks > 1 ? `稿子较长，会分 ${m.n_chunks} 块处理。` : ""}</p>${stepBox("seg:" + m.id, "segment", { material: m.id }, { label: "用软件里的 AI 切分" })}` : ""}
        ${m.segments.length ? `<div class="small muted">切出 ${m.segments.length} 个片段。下面可以改类型、改标题、取消采用、合并相邻片段；先点「看全文」确认切得对不对。</div><div class="dst-segs">${segRows(m)}</div>
          ${m.skipped.length ? `<details class="small"><summary>已略过 ${m.skipped.length} 段没被任何片段盖住的文字（点开检查有没有误删）</summary>${m.skipped.map((x) => `<div class="dst-skip">${esc(x.preview)}…（${num(x.chars)} 字）</div>`).join("")}</details>` : ""}
          <p class="small" style="margin-top:8px">${todo.length ? `第二步：把 ${todo.length} 个采用的片段拆成卡（${["考点", "例题", "框架"].map((k) => k + " " + m.segments.filter((s) => todo.includes(s.id) && s.type === k).length).join(" · ")}）。` : "采用的片段都已经拆成卡了。想重拆某个片段，先到「卡片」里删掉对应的卡。"}</p>
          ${todo.length ? stepBox("card:" + m.id, "card", { material: m.id, segments: todo }, { label: "用软件里的 AI 拆卡" }) : ""}` : ""}`;
      return `<div class="dst-mat"><div class="dst-mat-h"><b>${esc(m.title)}</b> <span class="tag">${esc(m.kind)}</span> <small class="muted">${num(m.chars)} 字 · ${m.segments.length} 个片段 · ${m.created}</small>
        <span class="dst-grow"></span><button class="ghost small" data-dst="mat-open" data-m="${m.id}">${open ? "收起" : "展开"}</button><button class="ghost small" data-dst="mat-del" data-m="${m.id}">🗑 删除素材</button></div>${body}</div>`;
    }).join("");
    return `<p class="small muted">思路：老师（或你自己）讲了怎么做题，先把原话贴进来；软件把它切成片段、拆成卡；卡片汇总成心法（版本 v1.0），以后再加素材，就在上一版的基础上更新。
      <label class="small">分包大小 <select data-dst-size>${Object.entries(SIZES).map(([k, v]) => `<option value="${v}" ${v === UI.size ? "selected" : ""}>${k}</option>`).join("")}</select></label>
      <span class="muted">（去别的平台做时，一次粘贴的字数上限）</span></p>${addForm()}${mats || '<p class="muted">还没有素材。先添加一份逐字稿。</p>'}`;
  }

  // ---------------------------------------------------------------- 卡片
  function cardsHtml() {
    const groups = [["总纲", "总纲（体系清单、优先级）"], ["考点", "考点卡"], ["例题", "例题卡"]];
    const rows = (kind) => ST.cards.filter((c) => c.kind === kind).map((c) => `<div class="dst-card ${UI.card?.id === c.id ? "on" : ""}">
        <button class="dst-card-h" data-dst="card-open" data-id="${c.id}"><b>${esc(c.title)}</b>
          ${c.status ? `<span class="tag ${c.status === "已印证" ? "ok" : "draft"}">${c.status}</span>` : ""}${c.new ? '<span class="tag skb-pend">新</span>' : ""}${c.edited ? '<span class="tag">手改</span>' : ""}
          ${c.complete === false ? '<span class="tag draft" title="转写里没有完整的题干和选项">题目不完整</span>' : ""}${c.unsure ? `<span class="tag draft">待核对 ${c.unsure}</span>` : ""}
          <small class="muted">${esc(c.sources.join("；"))}${c.status ? ` · 证据 ${c.n_evidence} 处` : ""}</small></button>
        ${UI.card?.id === c.id ? cardDetail() : ""}</div>`).join("");
    return groups.map(([k, label]) => `<h4 class="dst-h">${label} <small class="muted">${ST.cards.filter((c) => c.kind === k).length} 张</small></h4>${rows(k) || '<p class="small muted">还没有。</p>'}`).join("") +
      `<p class="small muted">卡片是源头：蒸馏版的文件都是从卡片生成的。点开一张卡可以看它写成文件后的样子，也可以改（改完在「版本」里更新）。</p>`;
  }

  function cardDetail() {
    const c = UI.card;
    if (!c.loaded) return '<div class="small muted">载入中……</div>';
    return `<div class="dst-card-b"><div class="dst-md md">${md(c.preview)}</div>
      <details class="small"><summary>✎ 修改这张卡（JSON，高级）</summary><textarea class="dst-json" rows="12" data-dst-json spellcheck="false">${esc(JSON.stringify(c.card.data, null, 1))}</textarea>
        <div class="dst-row"><button class="primary small" data-dst="card-save" data-id="${c.id}">保存修改</button><span class="small muted">保存时会校验格式，不对会指出哪里</span></div></details>
      <div class="dst-row"><button class="ghost small" data-dst="card-del" data-id="${c.id}">🗑 删除这张卡</button></div></div>`;
  }

  // ---------------------------------------------------------------- 版本
  function verHtml() {
    const cur = ST.versions[0], n = ST.n_new;
    const head = cur ? `<div class="dst-cur"><b>当前版本 v${esc(cur.version)}</b> · 基于 ${cur.n_cards} 张卡 · ${n ? `<span class="tag skb-pend">有 ${n} 张新卡 / 改过的卡还没并入</span>` : "<span class='tag ok'>卡片都已并入</span>"}</div>`
      : `<div class="dst-cur"><b>还没有蒸馏版</b> · 现有 ${ST.cards.length} 张卡${ST.cards.length ? "，可以汇总生成 v1.0" : "：先去「素材」把逐字稿切分、拆成卡"}</div>`;
    const build = ST.cards.length ? `<div class="dst-row"><button class="primary" data-dst="build" ${!cur || n ? "" : "disabled"} title="把卡片汇总成蒸馏版文件（不花 AI 额度），先变成待审建议，你勾选采纳后存成新版本">🔨 ${cur ? `更新到 v${esc(nextVer(cur.version))}` : "汇总生成 v1.0"}</button>
      <span class="small muted">汇总是程序按模板做的，不调用 AI；采纳后自动存成版本，可对比、可回到旧版本。</span></div>
      <details class="small"><summary>✨ （可选）让 AI 写一份「总流程」${ST.flow_draft ? "（已有草稿，下次汇总会用它）" : ""}</summary><p class="muted">不写的话，总流程会由程序根据考点卡自动列一份草稿。</p>${stepBox("flow", "flow", {}, { label: "用软件里的 AI 写总流程" })}</details>` : "";
    const sw = cur ? `<label class="small dst-sw"><input type="checkbox" data-dst-only ${ST.only_distilled ? "checked" : ""}> 讲题只读蒸馏版${ST.has_skill_md ? "（不读原 skill 的文件）" : ""} <span class="muted">${ST.has_skill_md ? "关掉后，原 skill 的文件也会一起读" : "你没有复制过原 skill，这个开关暂时没有影响"}</span></label>` : "";
    const rows = ST.versions.map((v, i) => `<div class="dst-ver"><div><b>v${esc(v.version)}</b> <small class="muted">${esc(v.created)} · ${v.n_cards} 张卡${v.test ? ` · 检验 <b>${v.test.correct}/${v.test.n}</b>` : ""}</small>
        <div class="small">${esc(v.note)}</div>${(v.changelog || []).length ? `<ul class="small muted">${v.changelog.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}</div>
        <div class="dst-vbtn">${ST.versions[i + 1] ? `<button class="ghost small" data-dst="cmp" data-a="${esc(ST.versions[i + 1].version)}" data-b="${esc(v.version)}">和上一版对比</button>` : ""}
        ${i ? `<button class="ghost small" data-dst="cmp" data-a="${esc(v.version)}" data-b="当前">和现在对比</button><button class="small" data-dst="restore" data-v="${esc(v.version)}">回到这一版</button>` : `<button class="ghost small" data-dst="cmp" data-a="${esc(v.version)}" data-b="当前">和现在对比</button>`}</div></div>`).join("");
    const cmp = UI.cmp ? `<div class="dst-cmp"><b>v${esc(UI.cmp.a)} → ${UI.cmp.b === "当前" ? "现在" : "v" + esc(UI.cmp.b)}</b>
        ${UI.cmp.added.length ? `<div class="small">新增：${UI.cmp.added.map(esc).join("、")}</div>` : ""}${UI.cmp.removed.length ? `<div class="small">删除：${UI.cmp.removed.map(esc).join("、")}</div>` : ""}
        ${UI.cmp.changed.map((c) => `<details class="small"><summary>${esc(c.path)}</summary><pre class="dst-diff">${esc(c.diff)}</pre></details>`).join("")}
        ${!UI.cmp.added.length && !UI.cmp.removed.length && !UI.cmp.changed.length ? '<div class="small muted">没有差别。</div>' : ""}<button class="ghost small" data-dst="cmp-close">关闭对比</button></div>` : "";
    return head + build + sw + `<h4 class="dst-h">版本记录</h4>${rows || '<p class="small muted">还没有版本。</p>'}${cmp}
      ${cur ? '<div class="dst-row"><button class="ghost small" data-dst="save-ver">💾 把现在的状态存为新版本</button><span class="small muted">包括你手改过的内容；手改本身不会自动涨版本号</span></div>' : ""}`;
  }
  const nextVer = (v) => { const [a, b] = String(v).split(".").map(Number); return `${a}.${(b || 0) + 1}`; };

  // ---------------------------------------------------------------- 检验
  function resultHtml() {
    const r = UI.result;
    if (!r) return "";
    const wrong = r.items.filter((x) => !x.ok).length;
    return `<div class="dst-cmp"><b>v${esc(r.version)} 的检验：${r.correct} / ${r.n} 题做对</b>（${Math.round((r.correct / r.n) * 100)}%）
      ${r.items.map((x, i) => `<details class="small ${x.ok ? "" : "dst-bad"}"><summary>${x.ok ? "✅" : "❌"} 第 ${i + 1} 题 · 心法选 ${esc(x.my)} · 正确 ${esc(x.answer)}</summary><div>${esc(x.stem)}</div>
        <div class="muted">${Object.entries(x.options).map(([k, v]) => k + ". " + esc(v)).join("　")}</div><div>心法的理由：${esc(x.why || "（没写）")}</div></details>`).join("")}
      ${wrong ? `<p class="small">让 AI 看看错在哪，起草对心法的补充（生成待审建议，不会直接改）：</p>${stepBox("diag:" + r.id, "diagnose", { run: r.id }, { label: "用软件里的 AI 诊断错题" })}` : '<p class="small muted">这次全对，不需要诊断。</p>'}
      <button class="ghost small" data-dst="res-close">关闭</button></div>`;
  }

  function testHtml() {
    if (!ST.versions.length) return '<p class="muted">还没有蒸馏版。先在「版本」里汇总并采纳 v1.0，才能检验。</p>';
    const open = ST.runs_open.map((r) => `<div class="dst-mat"><b>进行中的检验</b> · v${esc(r.version)} · ${r.n} 道题，已答 ${r.answered}
        <p class="small muted">做对率由程序对照答案算，AI 看不到答案。去别的平台做的话，每一包导入一批题的回复。</p>${stepBox("test:" + r.id, "test", { run: r.id }, { label: "用软件里的 AI 做完剩下的题" })}</div>`).join("");
    const hist = ST.tests.map((t) => `<div class="dst-ver"><div><b>v${esc(t.version)}</b> <small class="muted">${esc(t.date)}</small> · ${t.correct} / ${t.n} 做对（${Math.round((t.correct / t.n) * 100)}%）</div>
        <div class="dst-vbtn"><button class="ghost small" data-dst="res-open" data-id="${t.id}">看结果 / 诊断错题</button></div></div>`).join("");
    return `<p class="small muted">从你的题库里抽题（只用题干、选项和答案，不看题库的解析；例题卡里用过的题不抽），让 AI 只靠这份心法做题，程序判对错，得到做对率。测试集固定，不同版本可以直接比较。</p>
      <div class="dst-row"><label class="small">题数 <input type="number" min="5" max="60" value="${UI.n}" data-dst-n style="width:70px"></label>
        <button class="primary small" data-dst="test-start">开始一次检验（v${esc(ST.versions[0].version)}）</button>
        <button class="ghost small" data-dst="test-reseed" title="重新抽一批题当测试集（以后的检验都用新这一批，和以前的做对率不再可比）">换一批测试题</button></div>
      ${open}${resultHtml()}<h4 class="dst-h">检验记录</h4>${hist || '<p class="small muted">还没有检验过。</p>'}`;
  }

  // ---------------------------------------------------------------- 渲染与事件
  function render() {
    if (!EL) return;
    STEPS = {};
    if (!ST) { EL.innerHTML = '<p class="muted">载入中……</p>'; return; }
    const subs = [["mat", "📄 素材", ST.materials.length], ["cards", "🗂 卡片", ST.cards.length], ["ver", "🏷 版本", ST.versions[0] ? "v" + ST.versions[0].version : ""], ["test", "🎯 检验", ST.tests.length]];
    const body = UI.sub === "mat" ? matHtml() : UI.sub === "cards" ? cardsHtml() : UI.sub === "ver" ? verHtml() : testHtml();
    const keep = EL.querySelector(".dst-body")?.scrollTop || 0;
    EL.innerHTML = `<div class="dst-subs" role="tablist">${subs.map(([k, t, c]) => `<button role="tab" class="dst-sub ${UI.sub === k ? "on" : ""}" data-dst-sub="${k}">${t}${c !== "" && c !== 0 ? ` <small>${c}</small>` : ""}</button>`).join("")}</div><div class="dst-body">${body}</div>`;
    const b = EL.querySelector(".dst-body");
    if (b) b.scrollTop = keep;
  }

  async function onClick(e) {
    const sm = e.target.closest(".dst-add summary");
    if (sm) { UI.addOpen = !sm.parentElement.open; return; }                    // 点标题会切换展开：先记下来，重新渲染时不会收起
    const sub = e.target.closest("[data-dst-sub]");
    if (sub) { UI.sub = sub.dataset.dstSub; render(); return; }
    const t = e.target.closest("[data-dst]");
    if (!t || t.disabled) return;
    const k = t.dataset.dst, d = t.dataset;
    try {
      if (k === "ai" || k === "pack") return runStep(d.key, k);
      if (k === "copy") {
        const ta = EL.querySelectorAll(`[data-dst="copy"][data-key="${d.key}"]`);
        const text = UI.packs[d.key].parts[Number(d.i)].text;
        try { await navigator.clipboard.writeText(text); note("已复制，去别的平台粘贴发送，再把它的回复整段粘回来。"); }
        catch { const box = t.closest(".dst-pack-part").querySelector(".dst-pack"); box.select(); document.execCommand("copy"); note("已复制（如果没成功，请手动选中上面的文字复制）。"); }
        return;
      }
      if (k === "import") {
        const text = EL.querySelector(`[data-paste="${d.key}:${d.i}"]`)?.value || "";
        return runStep(d.key, "import", { text, params: UI.packs[d.key].parts[Number(d.i)].params });
      }
      if (k === "mat-add") {
        const f = UI.form;
        const r = await call("material/add", { kind: f.kind, title: f.title, text: f.text, whole_type: f.kind === "转写" ? "" : f.whole });
        UI.form = { kind: f.kind, whole: f.whole, title: "", text: "" }; UI.addOpen = false; note(`已添加素材「${r.title}」。`); await load(); return;
      }
      if (k === "mat-open") { UI.open[d.m] = UI.open[d.m] === false; render(); return; }
      if (k === "mat-del") { if (!confirm("删除这份素材？（已经拆出的卡片不会删）")) return; await call("material/delete", { id: d.m }); await load(); return; }
      if (k === "seg-text") {
        const key = d.m + d.s;
        if (UI.texts[key]) delete UI.texts[key];
        else { const m = ST.materials.find((x) => x.id === d.m), sg = m.segments.find((x) => x.id === d.s); UI.texts[key] = (await call("material/text", { id: d.m, start: sg.start, end: sg.end })).text; }
        render(); return;
      }
      if (k === "seg-merge") { await call("segment", { material: d.m, segment: d.s, action: "merge" }); UI.texts = {}; await load(); return; }
      if (k === "card-open") {
        if (UI.card?.id === d.id) { UI.card = null; render(); return; }
        UI.card = { id: d.id }; render();
        const r = await call("card", { id: d.id, action: "get" });
        UI.card = { id: d.id, loaded: true, card: r.card, preview: r.preview }; render(); return;
      }
      if (k === "card-save") {
        let data; try { data = JSON.parse(EL.querySelector("[data-dst-json]").value); } catch (err) { note("JSON 格式不对：" + err.message); return; }
        await call("card", { id: d.id, action: "save", data }); note("已保存这张卡。要让蒸馏版文件也更新，去「版本」点更新。"); UI.card = null; await load(); return;
      }
      if (k === "card-del") { if (!confirm("删除这张卡？（蒸馏版里已有的文件不会自动删除）")) return; await call("card", { id: d.id, action: "delete" }); UI.card = null; await load(); return; }
      if (k === "build") {
        const r = await call("build");
        note(`已生成待审建议「${r.proposal.summary}」：在页面上方勾选要采纳的文件，点「采纳勾选的」，会自动存成新版本。`); if (HOOKS.refresh) await HOOKS.refresh({ open: true }); return;
      }
      if (k === "cmp") { UI.cmp = await call("version", { action: "compare", a: d.a, b: d.b }); render(); return; }
      if (k === "cmp-close") { UI.cmp = null; render(); return; }
      if (k === "restore") {
        if (!confirm(`回到 v${d.v}？现在的蒸馏版文件会换成那一版的样子，被换掉的内容先存进各文件的历史，可以找回。`)) return;
        await call("version", { action: "restore", version: d.v }); note(`已回到 v${d.v}（卡片没有变，想重新吸收新卡就再点「更新」）。`); await load(); if (HOOKS.refresh) HOOKS.refresh(); return;
      }
      if (k === "save-ver") { const r = await call("version", { action: "save" }); note(`已存为 v${r.version}。`); await load(); return; }
      if (k === "test-start" || k === "test-reseed") {
        const r = await call("test", { action: "start", n: UI.n, reseed: k === "test-reseed" });
        note(`已抽好 ${r.n} 道题（${r.batches} 批），接下来做题。`); await load(); return;
      }
      if (k === "res-open") { UI.result = await call("test", { action: "result", id: d.id }); render(); return; }
      if (k === "res-close") { UI.result = null; render(); return; }
    } catch (err) { BUSY = ""; note(err.message || String(err)); render(); }
  }

  async function onChange(e) {
    const t = e.target;
    try {
      if (t.dataset.dstF) { UI.form[t.dataset.dstF] = t.value; if (t.dataset.dstF === "kind") render(); return; }
      if (t.dataset.dstSize !== undefined) { UI.size = Number(t.value); UI.packs = {}; render(); return; }
      if (t.dataset.dstN !== undefined) { UI.n = Math.max(5, Math.min(60, Number(t.value) || 20)); return; }
      if (t.dataset.dstOnly !== undefined) { await call("version", { action: "setting", only_distilled: t.checked }); ST.only_distilled = t.checked; note(t.checked ? "讲题只读蒸馏版。" : "讲题会同时读原 skill 的文件。"); if (HOOKS.refresh) HOOKS.refresh(); return; }
      const sg = t.dataset.dstSeg;
      if (sg) {
        const patch = sg === "inc" ? { include: t.checked } : sg === "type" ? { type: t.value } : { title: t.value };
        await call("segment", { material: t.dataset.m, segment: t.dataset.s, patch }); await load();
      }
    } catch (err) { note(err.message || String(err)); load(); }
  }

  window.DISTILL = {
    enabled: () => typeof isSL === "function" && !isSL(),      // 只在行测里用（申论的静态文字会把“行测”换成“申论”，所以不直接比较科目名）
    mount(el, board, hooks) {
      if (board !== BOARD) { UI.card = null; UI.cmp = null; UI.result = null; UI.packs = {}; UI.texts = {}; ST = null; }
      EL = el; BOARD = board; HOOKS = hooks || {};
      el.onclick = onClick; el.onchange = onChange;
      el.oninput = (e) => { const t = e.target; if (t.dataset.dstF === "text") UI.form.text = t.value; if (t.dataset.dstF === "title") UI.form.title = t.value; if (t.dataset.paste) UI.pastes[t.dataset.paste] = t.value; };
      render();
      if (!ST) load();                                  // 已经有数据就直接用（切页签再回来不重复请求）；采纳建议后会 invalidate
    },
    invalidate() { ST = null; },
  };
})();
