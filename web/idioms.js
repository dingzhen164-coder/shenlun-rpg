/* 藏经阁·词录（成语 / 实词）：以“一组易混词”为单位，读 训练/成语实词录/ 下用户维护的区别汇总文档（后端 rpg/wordbook.py）。
   左边分组目录（可搜），右边组页：判别轴横幅 → 表格（词、回答的问题、一句话区别、出处与例句；字义默认折叠）→ 易混提示 → 真题出处。
   “同步到卡片”把每组做成一张组卡，在辨言峰（逻辑填空 › 成语组 / 实词组）温习。类名统一 wb- 前缀。 */
(function () {
  let DATA = null;
  const POS_KEY = "wb-pos-v1";
  const S = (() => { try { return Object.assign({ kind: "成语", id: "", q: "" }, JSON.parse(localStorage.getItem(POS_KEY) || "{}")); } catch (_) { return { kind: "成语", id: "", q: "" }; } })();
  const save = () => { try { localStorage.setItem(POS_KEY, JSON.stringify({ kind: S.kind, id: S.id })); } catch (_) {} };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const TAGS = { 推断: "推断", 待核: "待核", 二手: "二手", 常识: "常识" };

  // 行内：加粗、<br>、〔标签〕、[文字](链接) 只显示文字。先转义，再还原这几种写法。
  function inline(raw) {
    let s = esc(raw);
    s = s.replace(/\[([^\]]+)\]\((?:[^)]+)\)/g, "$1");
    s = s.replace(/\*\*([^*]+?)\*\*/g, "<b>$1</b>");
    s = s.replace(/&lt;br\s*\/?&gt;/gi, "<br>");
    s = s.replace(/〔(推断|待核|二手|常识)〕/g, (_, t) => `<span class="wb-tag wb-tag-${t === "待核" ? "warn" : "info"}">${TAGS[t]}</span>`);
    return s;
  }
  // 出处格：<br> 之后以 生僻字 / 熟词僻义 / 类似 开头的字义折起来
  function cell(raw, isSource) {
    if (!isSource) return inline(raw);
    const parts = String(raw || "").split(/<br\s*\/?>/i), main = [], words = [];
    for (const p of parts) (/^\s*\*\*(生僻字|熟词僻义|类似)/.test(p) ? words : main).push(p);
    return inline(main.join("<br>")) + (words.length ? `<details class="wb-chars"><summary>字义</summary><div>${inline(words.join("<br>"))}</div></details>` : "");
  }
  function para(md) { return md.split(/\n+/).map((l) => `<p>${inline(l)}</p>`).join(""); }

  function table(b, gr) {
    const src = b.head.findIndex((h) => /出处|例句/.test(h));
    const head = `<tr>${b.head.map((h, i) => `<th class="${i === b.word_col ? "wb-wcol" : ""}">${inline(h)}</th>`).join("")}</tr>`;
    const rows = b.rows.map((r) => `<tr>${b.head.map((_, i) => {
      const v = r[i] || "";
      if (i === b.word_col) {
        const w = v.replace(/\*\*/g, "").trim(), more = (DATA.where[w] || []).filter((x) => x.id !== gr.id);
        return `<th scope="row" class="wb-word">${inline(v)}${more.length ? `<span class="wb-also">${more.map((x) => `<button type="button" class="wb-link" data-wbgo="${esc(x.id)}">也在${esc(x.label)}</button>`).join("")}</span>` : ""}</th>`;
      }
      return `<td class="${i === b.diff_col ? "wb-diff" : ""}">${cell(v, i === src)}</td>`;
    }).join("")}</tr>`).join("");
    return `<div class="wb-table-wrap"><table class="wb-table"><thead>${head}</thead><tbody>${rows}</tbody></table></div>`;
  }

  function groupView(gr) {
    if (!gr) return `<div class="wb-empty muted">左边选一组。</div>`;
    const blocks = gr.blocks.map((b) => b.type === "table" ? table(b, gr)
      : b.type === "axis" ? `<div class="wb-axis">${para(b.md)}</div>`
      : b.type === "tip" ? `<div class="wb-tip">${para(b.md)}</div>`
      : `<div class="wb-para">${para(b.md)}</div>`).join("");
    const src = gr.words.filter((w) => DATA.sources[w]).map((w) => `<div class="wb-src"><b>${esc(w)}</b>${DATA.sources[w].map((s) =>
      `<button type="button" class="ghost small wb-jump" data-wbkey="${esc(s.key)}" data-wbq="${esc(s.id)}" data-wbboard="${esc(s.board)}" title="${esc(s.paper || "")}">↗ ${esc(s.id)}</button>`).join("")}</div>`).join("");
    return `<article class="wb-group" aria-labelledby="wbTitle">
      <header class="wb-ghead"><span class="wb-no">${esc(gr.label)}</span><h3 id="wbTitle">${esc(gr.words.join("、") || gr.heading)}</h3><p class="small muted">${esc(gr.heading)}</p></header>
      ${blocks}
      ${src ? `<details class="wb-srcs"><summary>真题出处（${gr.words.filter((w) => DATA.sources[w]).length} 个词在题库里考过）</summary>${src}</details>` : ""}
    </article>`;
  }

  function html() {
    const d = DATA, q = S.q.trim();
    const list = q ? d.groups.filter((g) => g.name.includes(q) || g.heading.includes(q)) : d.groups;
    if (!d.groups.some((g) => g.id === S.id)) S.id = (d.groups[0] || {}).id || "";
    const cur = d.groups.find((g) => g.id === S.id);
    const tabs = `<div class="wb-kinds" role="tablist" aria-label="成语或实词">${d.kinds.map((k) => `<button type="button" role="tab" aria-selected="${k === d.kind}" class="${k === d.kind ? "on" : ""}" data-wbkind="${esc(k)}">${esc(k)}</button>`).join("")}</div>`;
    const bar = `<div class="wb-bar">${tabs}
      <input id="wbQ" type="search" placeholder="搜${esc(d.kind)}或组名" value="${esc(S.q)}" aria-label="搜索">
      <button type="button" class="primary small" id="wbSync" ${d.exists ? "" : "disabled"} title="每组一张组卡，放进辨言峰（${esc(d.deck)}）；改了文档再点一次就更新，温习进度保留">🃏 同步到卡片${d.synced ? `（已有 ${d.synced} 张）` : ""}</button></div>`;
    const warn = d.problems.length ? `<div class="wb-warn" role="alert"><b>文档里有几处没读懂：</b>${d.problems.map((p) => `<div>${esc(p)}</div>`).join("")}</div>` : "";
    if (!d.exists) {
      return bar + `<div class="wb-empty"><h3>还没有${esc(d.kind)}文档</h3><p>在本地新建 <b>${esc(d.file)}</b>，照 <b>${esc(d.template)}</b> 的格式按组写：<code>## 1. 组名</code>、加粗的“最深区别”、一张带“${esc(d.kind)}”列和“一句话区别”列的表格。保存后回到这里就能看到。</p></div>`;
    }
    const side = `<nav class="wb-side" aria-label="分组目录">${list.map((g) => `<button type="button" class="wb-gbtn ${g.id === S.id ? "on" : ""}" data-wbgo="${esc(g.id)}" aria-current="${g.id === S.id}"><span class="wb-gno">${esc(g.label)}</span><span class="wb-gwords">${esc(g.words.join("、"))}</span></button>`).join("") || `<p class="small muted">没有搜到。</p>`}</nav>`;
    const intro = d.intro ? `<details class="wb-intro"><summary>说明</summary>${para(d.intro.replace(/^>\s?/gm, ""))}</details>` : "";
    return bar + warn + `<div class="wb-body">${side}<div class="wb-main">${intro}${groupView(cur)}<p class="small wb-file">内容来自 ${esc(d.file)}（本地修改后重新打开即可）· 共 ${d.groups.length} 个小组</p></div></div>`;
  }

  async function load() { DATA = await api("/api/wordbook", { kind: S.kind }); }
  async function render() { await load(); return html(); }

  function bind() {
    const box = document.querySelector("#view .id-root");
    if (!box) return;
    box.querySelectorAll("[data-wbkind]").forEach((b) => (b.onclick = async () => { S.kind = b.dataset.wbkind; S.id = ""; save(); await load(); rerender(); }));
    box.querySelectorAll("[data-wbgo]").forEach((b) => (b.onclick = () => { S.id = b.dataset.wbgo; save(); rerender(); box.querySelector(".wb-main")?.scrollTo?.({ top: 0 }); }));
    const q = box.querySelector("#wbQ");
    if (q) q.oninput = () => { S.q = q.value; const pos = q.selectionStart; rerender(); const n = document.querySelector("#wbQ"); if (n) { n.focus(); n.setSelectionRange(pos, pos); } };
    const sync = box.querySelector("#wbSync");
    if (sync) sync.onclick = async () => {
      sync.disabled = true; sync.textContent = "同步中…";
      try {
        DATA = await api("/api/wordbook/cards", { kind: S.kind });
        const r = DATA.result;
        toast(`已同步 ${r.cards} 张组卡（新 ${r.new}、保留进度 ${r.kept}${r.removed ? `、删去 ${r.removed}` : ""}），在辨言峰「${r.deck.replace("::", " › ")}」温习`);
        rerender();
      } catch (e) { showError(e); sync.disabled = false; sync.textContent = "🃏 同步到卡片"; }
    };
    // 真题跳转：切到经卷，搜这道题的编号并直接展开
    box.querySelectorAll(".wb-jump").forEach((b) => (b.onclick = () => {
      LIB.tab = "yujian";
      Object.assign(LIB.yj, { q: b.dataset.wbq, board: b.dataset.wbboard, topic: "", status: "", page: 0, openKey: b.dataset.wbkey, from: "idioms" });
      window.scrollTo(0, 0);
      window.render();
    }));
  }
  function rerender() {
    const box = document.querySelector("#view .id-root");
    if (!box || !DATA) return;
    box.innerHTML = html();
    bind();
  }
  window.IDIOMS = { render, bind };
})();
