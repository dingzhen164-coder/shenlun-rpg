/* 3.2.6 十二经经络图：把“各模块时辰”画成人体经络图，十二个穴位对应十二个模块，穴位大小/亮度按时长占比。
 * 人体图可换：assets/beauty/dongfu/meridian-body.svg（viewBox 0 0 100 120，放了就用它，缺了用内置剪影）；
 * 穴位位置可换：assets/beauty/dongfu/meridian-nodes.json（[[x,y],…] 共12个，坐标按上面的 100×120）。
 * 只是显示方式，数据仍是 app.js 的 boardtime；app.js 里 boardTimeCard 用本模块出图，失败时回到原来的法印球。 */
(() => {
  'use strict';
  const BASE = 'assets/beauty/dongfu/';
  // 内置穴位（头顶、咽喉、左右肩、胸中、左右肘、丹田、左右膝、左右足；顺序固定，按模块顺序依次点亮）
  let NODES = [[50, 10], [50, 23], [29, 35], [71, 35], [50, 47], [17, 58], [83, 58], [50, 67], [38, 90], [62, 90], [38, 113], [62, 113]];
  let BODY = null;   // 用户提供的人体图（svg 文本）
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  function preload() {
    fetch(BASE + 'meridian-nodes.json').then((r) => (r.ok ? r.json() : null)).then((j) => {
      if (Array.isArray(j) && j.length >= 12 && j.every((p) => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite))) NODES = j;
    }).catch(() => {});
    fetch(BASE + 'meridian-body.svg').then((r) => (r.ok ? r.text() : null)).then((t) => { if (t && /<svg/i.test(t)) BODY = t; }).catch(() => {});
  }
  // 内置剪影：站立的人形（头、颈、躯干、双臂、双腿），线条风格，随主题色
  const DEFAULT_BODY = `<g class="mer-body" fill="none" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="50" cy="12" r="8.5"/><path d="M45 20v6M55 20v6"/>
    <path d="M32 29c6-3 12-4 18-4s12 1 18 4l5 24-6 4-3-12-1 24c1 8 3 18 3 30l-3 22h-9l-3-24-3 24h-9l-3-22c0-12 2-22 3-30l-1-24-3 12-6-4z"/></g>`;
  // 经络线：按穴位顺序用平滑曲线串起来（脊线 + 两臂两腿），看起来像气脉流转
  function lines(P) {
    const pts = (a) => a.map((i) => P[i]).filter(Boolean);
    const path = (a) => { const q = pts(a); return q.length < 2 ? '' : 'M' + q.map((p) => p.join(' ')).join('L'); };
    return [[0, 1, 4, 7, 8, 10], [0, 1, 4, 7, 9, 11], [1, 2, 5], [1, 3, 6], [4, 2], [4, 3]].map((a) => `<path d="${path(a)}"/>`).join('');
  }
  function html(list, total, top, colors, hm) {
    const P = NODES;
    const body = BODY ? `<g class="mer-user">${BODY.replace(/<\?xml[^>]*>/, '').replace(/<svg[^>]*>/i, '').replace(/<\/svg>/i, '')}</g>` : DEFAULT_BODY;
    const dots = list.slice(0, 12).map((b, i) => {
      const mins = Math.round(b.total), [x, y] = P[i] || P[0], share = total ? b.total / total : 0, r = 2.6 + share * 7;
      const left = x < 49 ? true : x > 51 ? false : i % 2 === 1, side = left ? 'end' : 'start', tx = x + (left ? -(r + 2) : r + 2);
      return `<g class="mer-node${b.total ? ' on' : ''}${b.total === top && total ? ' top' : ''}" style="--c:${colors[i % colors.length]}" data-mer="${i}" tabindex="0" role="button" aria-label="${esc(b.board)} ${mins} 分钟">
        <circle class="mer-halo" cx="${x}" cy="${y}" r="${r + 2.4}"/><circle class="mer-dot" cx="${x}" cy="${y}" r="${r}"/>
        <text x="${tx}" y="${y - 0.6}" text-anchor="${side}" class="mer-name" font-size="3.4">${esc(b.board)}</text>
        <text x="${tx}" y="${y + 3.6}" text-anchor="${side}" class="mer-time" font-size="2.8">${mins} 分${total ? ' · ' + Math.round(share * 100) + '%' : ''}</text></g>`;
    }).join('');
    return `<div class="mer-wrap"><svg class="mer-svg" viewBox="-12 0 124 122" role="img" aria-label="十二经经络图">${body}<g class="mer-lines" fill="none" stroke-linecap="round">${lines(P)}</g>${dots}</svg>
      <div class="mer-detail" data-mer-detail aria-live="polite">点一个穴位，看这个模块的听课 / 做题 / 复习分钟。</div></div>`;
  }
  function detail(list, i) {
    const b = list[i]; if (!b) return '';
    return `<b>${esc(b.board)}</b>：听课 ${b.lecture} 分 · 做题 ${b.practice} 分 · 复习 ${b.review} 分（共 ${b.total} 分）`;
  }
  function bind(root, list) {
    root.querySelectorAll('[data-mer]').forEach((n) => {
      const go = () => {
        root.querySelectorAll('.mer-node.sel').forEach((x) => x.classList.remove('sel')); n.classList.add('sel');
        const d = root.querySelector('[data-mer-detail]'); if (d) d.innerHTML = detail(list, Number(n.dataset.mer));
      };
      n.addEventListener('click', go); n.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    });
  }
  preload();
  window.BeautyMeridian = { html, bind, preload };
})();
