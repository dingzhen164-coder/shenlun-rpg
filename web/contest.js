/* 📊 年度考核：整套模考 / 套卷的成绩记录与走势。
   记录走 /api/boss（成绩按 0–100 分制；贵州卷 150 分这类，填满分后自动折算成百分制）。
   最近两次较低的成绩若高于当前综合评价，政绩直接补上；达到晋升分数线是晋升考核的条件之一（规则见 训练/规则.md）。 */
"use strict";
(() => {
  const pct = (score, full) => Math.round((Number(score) / Number(full)) * 1000) / 10;

  function trend(list) {
    if (list.length < 2) return "";
    const W_ = 520, H = 120, pad = 22, lo = Math.max(0, Math.min(...list.map((b) => b.score)) - 5), hi = Math.min(100, Math.max(...list.map((b) => b.score)) + 5);
    const x = (i) => pad + (i * (W_ - 2 * pad)) / (list.length - 1), y = (v) => H - pad - ((v - lo) / (hi - lo || 1)) * (H - 2 * pad);
    const pts = list.map((b, i) => `${x(i).toFixed(1)},${y(b.score).toFixed(1)}`).join(" ");
    return `<svg class="ct-trend" viewBox="0 0 ${W_} ${H}" role="img" aria-label="成绩走势"><polyline points="${pts}" fill="none" stroke="var(--gold)" stroke-width="2.5" stroke-linejoin="round"/>
      ${list.map((b, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(b.score).toFixed(1)}" r="4" fill="var(--gold)"><title>${esc(b.name)} ${b.score} 分</title></circle>
      <text x="${x(i).toFixed(1)}" y="${(y(b.score) - 9).toFixed(1)}" text-anchor="middle" font-size="11" fill="var(--muted)">${b.score}</text>`).join("")}</svg>`;
  }

  async function render(v) {
    const d = DASH, list = d.boss_all || d.boss || [];
    const last2 = list.slice(-2).map((b) => b.score);
    v.innerHTML = `<div class="card"><h3>${esc(W("boss"))} <small>整套模考的成绩：最近两次的较低分，会拉动${esc(W("score"))}与${esc(W("tribulation"))}条件</small></h3>
      <div class="row ct-form"><input id="ctName" placeholder="卷子名称，如 国考行政执法 2025" style="flex:3"><input id="ctScore" placeholder="得分" style="flex:1">
        <input id="ctFull" placeholder="满分" value="100" style="flex:1"><button class="primary" id="ctGo">记录</button></div>
      <div class="small muted" id="ctHint" style="margin-top:6px">按百分制记录；贵州卷（150 分）填满分 150，会自动折算。</div></div>
      <div class="card"><h3>📈 走势 <small>最近 ${list.length} 次</small></h3>${list.length >= 2 ? trend(list) : '<p class="muted">记两次以上才有走势图。</p>'}
        ${last2.length === 2 ? `<p class="small muted">最近两次：${last2.join(" / ")} 分，较低的是 <b>${Math.min(...last2)}</b>。</p>` : ""}</div>
      <div class="card"><h3>📜 历次成绩</h3>${list.length ? list.slice().reverse().map((b) => `<div class="row"><span class="small faint">${esc(b.d)}</span><b>${esc(b.name)}</b><span class="spacer"></span><b>${b.score} 分</b></div>`).join("") : '<p class="muted">还没有记录。</p>'}</div>`;
    const hint = $("#ctHint"), upd = () => {
      const s = $("#ctScore").value, f = $("#ctFull").value;
      if (s && f && Number(f) > 0) hint.textContent = `折算后：${pct(s, f)} 分（百分制）`;
    };
    $("#ctScore").oninput = upd; $("#ctFull").oninput = upd;
    $("#ctGo").onclick = async () => {
      const s = Number($("#ctScore").value), f = Number($("#ctFull").value);
      if (!(s >= 0) || !(f > 0) || s > f) return toast("得分和满分要填数字，得分不能超过满分");
      const name = ($("#ctName").value.trim() || "模考") + (f !== 100 ? `（${s}/${f}）` : "");
      try { const r = await api("/api/boss", { name, score: pct(s, f) }); handleEvents(r.events); await refresh(); render(); } catch (e) { showError(e); }
    };
  }
  window.CONTEST = { render };
})();
