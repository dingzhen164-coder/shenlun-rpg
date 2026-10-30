/* 📎 摘编（申论 · 档案室）：每日文章「一键精读」里存下来的“万能对策”和“黄金句式”，在这里翻阅（只读，不是复习卡片）。
   数据：训练/时政文章/摘编/<编号>.json（见 rpg/articles.py 的 digest_*）；接口 GET /api/articles/digest、POST /api/articles/digest_remove。
   三种看法：对策按领域、黄金句式按类型、按文章。每篇可“移出摘编”（只删这份摘编，不删文章和精读）。 */
(() => {
  const MODES = [["act", "对策 · 按领域"], ["quote", "黄金句式 · 按类型"], ["art", "按文章"]];
  const QKINDS = [["巧用形象", "巧用形象的"], ["辩证论述", "辩证论述的"], ["标题段首句", "标题 / 段首句"]];
  let MODE = "act", DATA = [];
  const tag = (t) => `<span class="tag">${esc(t)}</span>`;
  const from = (a) => `<span class="faint small dg-from">《${esc(a.title)}》${a.source ? " · " + esc(a.source) : ""}</span>`;
  function body() {
    if (!DATA.length) return `<div class="muted dg-empty">还没有摘编。去 参阅室 打开一篇文章 → 一键精读 → “📎 存入摘编”，第三步的对策和第四步的黄金句式就会收到这里。</div>`;
    if (MODE === "quote") {
      return QKINDS.map(([k, name]) => {
        const rows = DATA.flatMap((a) => (a.quotes || []).filter((q) => q.kind === k).map((q) => ({ a, q })));
        return rows.length ? `<section class="dg-sec"><h3>${name} <small>${rows.length}</small></h3>${rows.map(({ a, q }) => `<blockquote>${esc(q.text)}${q.use ? `<small>${esc(q.use)}</small>` : ""}${from(a)}</blockquote>`).join("")}</section>` : "";
      }).join("") || `<div class="muted dg-empty">摘编里还没有黄金句式。</div>`;
    }
    if (MODE === "art") {
      return DATA.map((a) => `<details class="dg-art" open><summary><b>${esc(a.title)}</b> <span class="faint small">${esc(a.source || "")} ${esc(a.date || "")} · 存于 ${esc(a.saved || "")}</span></summary>
        ${(a.countermeasures || []).length ? `<h5>万能对策</h5>${a.countermeasures.map((x) => `<div class="ar-act">${tag(x.domain)} <span class="ar-act-dir">原文：${esc(x.direction)}</span><div>落地：${esc(x.landing)} ${tag(x.source)}</div></div>`).join("")}` : ""}
        ${(a.quotes || []).length ? `<h5>黄金句式</h5>${a.quotes.map((q) => `<blockquote>${tag(q.kind)} ${esc(q.text)}${q.use ? `<small>${esc(q.use)}</small>` : ""}</blockquote>`).join("")}` : ""}
        <div class="row"><button class="ghost small" data-dg-rm="${esc(a.id)}">移出摘编</button></div></details>`).join("");
    }
    const byDomain = {};
    DATA.forEach((a) => (a.countermeasures || []).forEach((x) => (byDomain[x.domain] = byDomain[x.domain] || []).push({ a, x })));
    const order = ["人才", "科技", "民生", "治理", "经济", "生态", "文化", "其他"].filter((d) => byDomain[d]);
    return order.map((d) => `<section class="dg-sec"><h3>${esc(d)} <small>${byDomain[d].length}</small></h3>${byDomain[d].map(({ a, x }) => `<div class="ar-act"><div class="ar-act-dir">原文：${esc(x.direction)}</div><div>落地：${esc(x.landing)} ${tag(x.source)}</div>${from(a)}</div>`).join("")}</section>`).join("") || `<div class="muted dg-empty">摘编里还没有对策。</div>`;
  }
  async function render() {
    try { DATA = (await api("/api/articles/digest")).items || []; } catch (e) { return `<div class="warn dg-empty">摘编打开失败：${esc(e.message)}</div>`; }
    return `<div class="dg-root"><div class="lib-subtabs dg-modes" role="tablist">${MODES.map(([k, t]) => `<button class="ghost small ${k === MODE ? "on" : ""}" data-dg-mode="${k}" role="tab" aria-selected="${k === MODE}">${t}</button>`).join("")}<span class="spacer"></span><span class="faint small">共 ${DATA.length} 篇摘编 · 只翻阅</span></div><div id="dgBody">${body()}</div></div>`;
  }
  function bind(root) {
    const R = root.querySelector(".dg-root"); if (!R) return;
    const paint = () => { R.querySelector("#dgBody").innerHTML = body(); R.querySelectorAll("[data-dg-mode]").forEach((b) => { const on = b.dataset.dgMode === MODE; b.classList.toggle("on", on); b.setAttribute("aria-selected", String(on)); }); bindRm(); };
    const bindRm = () => R.querySelectorAll("[data-dg-rm]").forEach((b) => (b.onclick = async () => {
      if (!confirm("把这篇移出摘编？文章和精读都不会删。")) return;
      try { await api("/api/articles/digest_remove", { id: b.dataset.dgRm }); DATA = DATA.filter((a) => a.id !== b.dataset.dgRm); paint(); } catch (e) { showError(e); }
    }));
    R.querySelectorAll("[data-dg-mode]").forEach((b) => (b.onclick = () => { MODE = b.dataset.dgMode; paint(); }));
    bindRm();
  }
  window.DIGEST = { render, bind };
})();
