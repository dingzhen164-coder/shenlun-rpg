/* 3.2.2 启动画面：页面一打开先显示品牌与流动条，首屏内容渲染好（#view 有内容）后淡出；最多停 6 秒，保证不挡住使用。 */
(() => {
  'use strict';
  const el = document.getElementById('splash'); if (!el) return;
  const t0 = Date.now(); let gone = false;
  const sub = el.querySelector('small'); if (sub && window.SUBJECT0) sub.textContent = window.SUBJECT0;
  function out() { if (gone) return; gone = true; el.classList.add('splash-out'); setTimeout(() => el.remove(), 700); }
  function check() { const v = document.getElementById('view'); if (v && v.children.length) setTimeout(out, Math.max(0, 700 - (Date.now() - t0))); }
  const v = document.getElementById('view');
  if (v) new MutationObserver(check).observe(v, { childList: true });
  setTimeout(out, 6000); check();
})();
