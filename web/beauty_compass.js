/* 3.2.6 十二经罗盘：把“各模块时辰”画成一个十二瓣的灵力罗盘（玫瑰图）。
 * 十二个扇区＝十二个模块，花瓣长度＝该模块时长（开方缩放，短的也看得见）；外圈刻十二时辰（子丑寅卯…），最勤的模块花瓣带光环；
 * 中心显示总时长与最勤模块；点（或回车）一个花瓣看听课 / 做题 / 复习分钟。不需要任何图片素材。
 * 只是显示方式，数据仍是 app.js 的 boardtime；app.js 的 boardTimeCard 用本模块出图，失败时回到法印球。 */
(() => {
  'use strict';
  const C = 120, R0 = 30, R1 = 84, RL = 98;           // 圆心、花瓣内/外半径、标签半径（viewBox 0 0 240 240）
  const BRANCH = '子丑寅卯辰巳午未申酉戌亥';
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const pt = (r, deg) => { const a = (deg - 90) * Math.PI / 180; return [C + r * Math.cos(a), C + r * Math.sin(a)]; };
  function sector(r0, r1, a0, a1) {
    const [x0, y0] = pt(r1, a0), [x1, y1] = pt(r1, a1), [x2, y2] = pt(r0, a1), [x3, y3] = pt(r0, a0);
    const f = (n) => n.toFixed(2);
    return `M${f(x0)} ${f(y0)}A${r1} ${r1} 0 0 1 ${f(x1)} ${f(y1)}L${f(x2)} ${f(y2)}A${r0} ${r0} 0 0 0 ${f(x3)} ${f(y3)}Z`;
  }
  function html(list, total, top, colors) {
    const n = Math.min(12, list.length) || 1, step = 360 / 12, gap = 2.4, max = Math.max(1, ...list.map((b) => b.total));
    const petals = list.slice(0, 12).map((b, i) => {
      const a0 = i * step + gap / 2, a1 = (i + 1) * step - gap / 2, mid = (a0 + a1) / 2;
      const len = R0 + (R1 - R0) * Math.sqrt(b.total / max) * (b.total ? 1 : 0), share = total ? b.total / total : 0;
      const r1 = b.total ? Math.max(R0 + 6, len) : R0 + 3, [lx, ly] = pt(RL, mid), side = Math.abs(lx - C) < 6 ? 'middle' : lx < C ? 'end' : 'start';
      const mins = Math.round(b.total);
      return `<g class="cp-petal${b.total ? ' on' : ''}${b.total === top && total ? ' top' : ''}" style="--c:${colors[i % colors.length]};--i:${i}" data-cp="${i}" tabindex="0" role="button" aria-label="${esc(b.board)} ${mins} 分钟">
        <path class="cp-slot" d="${sector(R0, R1, a0, a1)}"/><path class="cp-fill" d="${sector(R0, r1, a0, a1)}"/>
        <text class="cp-zhi" x="${pt(R0 + 8, mid)[0].toFixed(1)}" y="${(pt(R0 + 8, mid)[1] + 1.6).toFixed(1)}" text-anchor="middle" font-size="5">${BRANCH[i]}</text>
        <text class="cp-name" x="${lx.toFixed(1)}" y="${(ly - 0.5).toFixed(1)}" text-anchor="${side}" font-size="5.4">${esc(b.board)}</text>
        <text class="cp-time" x="${lx.toFixed(1)}" y="${(ly + 5).toFixed(1)}" text-anchor="${side}" font-size="4.4">${mins} 分${total ? ' · ' + Math.round(share * 100) + '%' : ''}</text></g>`;
    }).join('');
    const best = total ? list.find((b) => b.total === top) : null;
    const ticks = Array.from({ length: 60 }, (_, k) => { const [x0, y0] = pt(R1 + 3, k * 6), [x1, y1] = pt(R1 + (k % 5 ? 4.4 : 6), k * 6); return `M${x0.toFixed(1)} ${y0.toFixed(1)}L${x1.toFixed(1)} ${y1.toFixed(1)}`; }).join('');
    return `<div class="cp-wrap"><svg class="cp-svg" viewBox="-30 -4 300 248" role="img" aria-label="十二经罗盘">
      <g class="cp-rings"><circle cx="${C}" cy="${C}" r="${R1}"/><circle cx="${C}" cy="${C}" r="${(R0 + R1) / 2}"/><circle cx="${C}" cy="${C}" r="${R0}"/><path class="cp-ticks" d="${ticks}"/></g>
      ${petals}
      <g class="cp-center"><text x="${C}" y="${C - 3}" text-anchor="middle" font-size="13" class="cp-total">${Math.round(total)}</text>
        <text x="${C}" y="${C + 5}" text-anchor="middle" font-size="4.2" class="cp-sub">分钟</text>
        <text x="${C}" y="${C + 11.5}" text-anchor="middle" font-size="3.8" class="cp-sub">${best ? '最勤 · ' + esc(best.board) : '尚无记录'}</text></g></svg>
      <div class="cp-detail" data-cp-detail aria-live="polite">点一片花瓣，看这个模块的听课 / 做题 / 复习分钟。</div></div>`;
  }
  function bind(root, list) {
    root.querySelectorAll('[data-cp]').forEach((n) => {
      const go = () => {
        root.querySelectorAll('.cp-petal.sel').forEach((x) => x.classList.remove('sel')); n.classList.add('sel');
        const b = list[Number(n.dataset.cp)], d = root.querySelector('[data-cp-detail]');
        if (b && d) d.innerHTML = `<b>${esc(b.board)}</b>：听课 ${b.lecture} 分 · 做题 ${b.practice} 分 · 复习 ${b.review} 分（共 ${b.total} 分）`;
      };
      n.addEventListener('click', go); n.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    });
  }
  window.BeautyCompass = { html, bind };
})();
