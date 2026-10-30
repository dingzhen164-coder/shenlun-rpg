/* 🧹 清除（藏经阁 · 行测）：把导入的套卷、板块题目里混进来的广告文字清掉。后端见 rpg/ad_clean.py。
   流程：输入广告文字 → 查找（忽略空白，列出所有位置和前后文）→ 勾选要清的 → 清除（先备份，可撤销上一次）；
   “以后导入自动清除”把这段文字记进广告词库，之后导入套卷、板块题时自动清掉。只处理导入的内容，不碰库里原有的真题复盘。 */
(() => {
  let HITS = [], TEXT = "", STATUS = { last: null, words: [] }, SCOPES = { paper: true, bank: true };
  const scopes = () => Object.keys(SCOPES).filter((k) => SCOPES[k]);
  const mark = (h) => `${esc(h.before)}<mark>${esc(h.hit)}</mark>${esc(h.after)}`;
  function hitsHtml() {
    if (!TEXT) return "";
    if (!HITS.length) return `<p class="ac-note">没有找到“${esc(TEXT)}”。已按忽略空白和大小写查找；可以缩短一点再试。</p>`;
    const groups = {};
    HITS.forEach((h) => (groups[h.where] = groups[h.where] || []).push(h));
    return `<div class="ac-summary"><b>找到 ${HITS.length} 处</b>，涉及 ${Object.keys(groups).length} 个位置。<button type="button" class="ghost small" data-ac-all="1">全选</button><button type="button" class="ghost small" data-ac-all="0">全不选</button></div>
      ${Object.entries(groups).map(([where, rows]) => `<section class="ac-group"><h4>${esc(where)} <small>${rows.length}</small></h4>${rows.map((h) => `<label class="ac-hit"><input type="checkbox" data-ac-hit="${esc(h.id)}" checked>
        <span class="ac-q">${esc(h.question || "（文件开头）")}</span><span class="ac-ctx">…${mark(h)}…</span>${h.whole_line ? '<em class="ac-tag">整行</em>' : ""}${h.check ? '<em class="ac-tag ac-warn" title="广告夹在一句话中间，清掉后两边的字会接起来，请核对">请核对</em>' : ""}</label>`).join("")}</section>`).join("")}
      <div class="ac-actions"><button type="button" class="primary" data-ac-clean="1">清除选中的（<span data-ac-count>${HITS.length}</span> 处）</button><span class="faint small">清除前会自动备份，可以撤销上一次清除。</span></div>`;
  }
  function sideHtml() {
    const last = STATUS.last;
    return `<section class="ac-side"><h4>广告词库 <small>导入时自动清除</small></h4>
      ${STATUS.words.length ? `<ul class="ac-words">${STATUS.words.map((w) => `<li><span>${esc(w.text)}</span><button type="button" class="ghost small" data-ac-word-rm="${esc(w.text)}">删除</button></li>`).join("")}</ul>` : '<p class="muted small">词库是空的。查找一段广告文字后，点“以后导入自动清除”，它就会记在这里，之后导入套卷、板块题时自动清掉。</p>'}
      <h4>撤销</h4>${last ? `<p class="small">上一次清除：“${esc(last.text)}”，涉及 ${last.files} 个文件（${esc(last.time)}）。</p><button type="button" class="ghost small" data-ac-undo="1">撤销上一次清除</button>` : '<p class="muted small">还没有清除记录。</p>'}</section>`;
  }
  function body() {
    return `<div class="ac-top"><p class="ac-intro">导入套卷、板块题目时，文字识别分不出广告（如“一手最全公考资源加微信 biguo368”）。在这里输入这段文字，查出所有位置，勾选后一键清除。只处理导入的内容，不碰库里原有的真题复盘。</p>
      <div class="ac-search"><input id="acText" type="text" placeholder="粘贴要清除的广告文字" value="${esc(TEXT)}" maxlength="120"><button type="button" class="primary" id="acFind">查找</button>
        <label><input type="checkbox" data-ac-scope="paper" ${SCOPES.paper ? "checked" : ""}> 套卷与模考复盘</label><label><input type="checkbox" data-ac-scope="bank" ${SCOPES.bank ? "checked" : ""}> 板块题目</label></div></div>
      <div class="ac-main"><div id="acResult">${hitsHtml()}</div>${sideHtml()}</div>`;
  }
  async function refreshStatus() { try { STATUS = await api("/api/adclean/status", {}); } catch (e) { /* 状态读不到不影响查找 */ } }
  async function render() {
    await refreshStatus();
    return `<div class="ac-root">${body()}</div>`;
  }
  function bind(root) {
    const R = root.querySelector(".ac-root"); if (!R) return;
    const repaint = () => { R.innerHTML = body(); bind(root); };
    const find = async () => {
      const text = R.querySelector("#acText").value.trim(); TEXT = text;
      if (!text) { HITS = []; return repaint(); }
      try { const r = await api("/api/adclean/find", { text, scopes: scopes() }); HITS = r.hits || []; }
      catch (e) { HITS = []; repaint(); return showError(e); }
      repaint();
    };
    R.querySelector("#acFind").onclick = find;
    R.querySelector("#acText").onkeydown = (e) => { if (e.key === "Enter") find(); };
    R.querySelectorAll("[data-ac-scope]").forEach((c) => (c.onchange = () => { SCOPES[c.dataset.acScope] = c.checked; }));
    const count = () => { const n = R.querySelectorAll("[data-ac-hit]:checked").length; const el = R.querySelector("[data-ac-count]"); if (el) el.textContent = n; const b = R.querySelector("[data-ac-clean]"); if (b) b.disabled = !n; };
    R.querySelectorAll("[data-ac-hit]").forEach((c) => (c.onchange = count));
    R.querySelectorAll("[data-ac-all]").forEach((b) => (b.onclick = () => { R.querySelectorAll("[data-ac-hit]").forEach((c) => (c.checked = b.dataset.acAll === "1")); count(); }));
    const clean = R.querySelector("[data-ac-clean]");
    if (clean) clean.onclick = async () => {
      const ids = [...R.querySelectorAll("[data-ac-hit]:checked")].map((c) => c.dataset.acHit);
      if (!ids.length) return;
      clean.disabled = true;
      try {
        const r = await api("/api/adclean/clean", { text: TEXT, scopes: scopes(), ids });
        toast(`🧹 已清除 ${r.cleaned} 处（${r.files} 个文件）；可在右侧撤销`);
        const f = await api("/api/adclean/find", { text: TEXT, scopes: scopes() }); HITS = f.hits || [];
        await refreshStatus(); repaint();
      } catch (e) { clean.disabled = false; showError(e); }
    };
    R.querySelector("[data-ac-undo]")?.addEventListener("click", async () => {
      if (!confirm("撤销上一次清除？清除之后你又改过的文件不会被覆盖。")) return;
      try {
        const r = await api("/api/adclean/undo", {});
        toast(`已撤销：恢复 ${r.restored} 个文件${r.skipped.length ? `；${r.skipped.length} 个文件清除后被改过，没有覆盖` : ""}`);
        if (TEXT) { const f = await api("/api/adclean/find", { text: TEXT, scopes: scopes() }); HITS = f.hits || []; }
        await refreshStatus(); repaint();
      } catch (e) { showError(e); }
    });
    R.querySelectorAll("[data-ac-word-rm]").forEach((b) => (b.onclick = async () => {
      try { await api("/api/adclean/words", { act: "remove", text: b.dataset.acWordRm }); await refreshStatus(); repaint(); } catch (e) { showError(e); }
    }));
    // 查找结果下面再给一个“以后导入自动清除”
    const add = document.createElement("button");
    if (TEXT && R.querySelector("#acResult")) {
      add.type = "button"; add.className = "ghost small"; add.textContent = "＋ 以后导入自动清除这段文字";
      add.onclick = async () => { try { const r = await api("/api/adclean/words", { act: "add", text: TEXT }); toast(r.again ? "词库里已经有这段了" : "已记进广告词库：以后导入自动清除"); await refreshStatus(); repaint(); } catch (e) { showError(e); } };
      (R.querySelector(".ac-actions") || R.querySelector("#acResult")).appendChild(add);
    }
  }
  window.AD_CLEAN = { render, bind };
})();
