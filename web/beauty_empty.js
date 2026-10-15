/* 3.2.2 空状态：界面里“还没有…/暂无…/空空如也”这类单行提示，自动换成带卷轴小插画的空状态样式（ds-empty）。
 * 只改外观；已有 ds-empty、含子元素、或文字较长的提示不动。 */
(() => {
  'use strict';
  const RE = /^(还没有|还没|暂无|暂时没有|空空如也|尚未|没有记录|这段时间还没有|无记录)/;
  function scan(root) {
    root.querySelectorAll?.('p.muted, div.muted, p.faint, div.faint').forEach((el) => {
      if (el.classList.contains('ds-empty') || el.children.length || el.closest('.ds-empty,.row,button,summary,.bag-grid')) return;
      const t = el.textContent.trim(); if (t.length > 90 || !RE.test(t)) return;
      el.classList.add('ds-empty');
    });
  }
  let q = 0; const later = () => { if (q) return; q = 1; (window.requestAnimationFrame || setTimeout)(() => { q = 0; scan(document.body); }); };
  const start = () => { scan(document.body); new MutationObserver(later).observe(document.body, { childList: true, subtree: true }); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
