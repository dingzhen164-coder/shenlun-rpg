/* 3.2.5 对话打字机：纪事对话框里的开场白与剧情段落逐字显现。
 * 文字内容与 DOM 文本不变（只是把字包进 span 控制显隐），点一下对话框正文可立即显示全部；
 * 减少动画（data-motion=reduced / 系统设置）时不做。每3个字响一声“type”音（BeautyAudio 有就响）。 */
(() => {
  'use strict';
  const still = () => document.documentElement.dataset.motion === 'reduced' || matchMedia('(prefers-reduced-motion: reduce)').matches;
  let queue = [], running = false, skip = false;

  function prepare(el) {
    if (el.dataset.tw || still()) return;
    if (el.childNodes.length !== 1 || el.firstChild.nodeType !== 3) return;
    const txt = el.firstChild.nodeValue; if (!txt.trim() || txt.length > 900) return;
    el.dataset.tw = '1';
    const frag = document.createDocumentFragment(), spans = [];
    for (const ch of txt) { const s = document.createElement('span'); s.className = 'tw-c'; s.textContent = ch; frag.appendChild(s); spans.push(s); }
    el.textContent = ''; el.appendChild(frag); el.classList.add('tw-on');
    queue.push(spans); if (!running) run();
  }
  async function run() {
    running = true;
    while (queue.length) {
      const spans = queue.shift(); const per = Math.max(14, Math.min(42, 2600 / spans.length));
      for (let i = 0; i < spans.length; i++) {
        if (skip || !spans[i].isConnected) { spans.forEach((s) => s.classList.add('tw-v')); break; }
        spans[i].classList.add('tw-v');
        if (i % 3 === 0 && window.BeautyAudio) BeautyAudio.sfx('type', 0.35);
        await new Promise((r) => setTimeout(r, per));
      }
      spans.forEach((s) => s.classList.add('tw-v'));
    }
    running = false; skip = false;
  }
  function scan(root) {
    (root.querySelectorAll ? root.querySelectorAll('.narrative-lead, .narrative-text p') : []).forEach(prepare);
  }
  document.addEventListener('click', (e) => { if (e.target.closest && e.target.closest('.narrative-paper') && running) skip = true; });
  new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => { if (n.nodeType === 1) { if (n.matches?.('.narrative-lead, .narrative-text p')) prepare(n); else scan(n); } }))).observe(document.documentElement, { childList: true, subtree: true });
})();
