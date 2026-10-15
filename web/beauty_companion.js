/* 3.2.5 同伴站位：在洞府页面左下角站着本科目的引导人物（半身立绘，缓慢呼吸），偶尔冒一句话；点一下打开人物对话（任务大殿）。
 * 只在有半身立绘（profile.portraits.calm）、电脑宽屏、非答题/手写/对话时出现；可在 设置→地点排布 里关掉（localStorage companion=0）。
 * 只是陪伴外观，台词是按时段的通用问候，不涉及成绩与学习判断。 */
(() => {
  'use strict';
  const KEY = 'companion';
  const on = () => { try { return localStorage.getItem(KEY) !== '0'; } catch (e) { return true; } };
  const still = () => document.documentElement.dataset.motion === 'reduced' || matchMedia('(prefers-reduced-motion: reduce)').matches;
  let el = null, img = '', bubbleT = 0, hideT = 0;

  const lines = () => {
    const h = new Date().getHours();
    const t = h < 6 ? ['夜深了，今天做到这里也好。', '别熬太晚，明天再接着来。'] : h < 11 ? ['早。从一小段复习开始，状态会好起来。', '清晨最适合背诵。'] : h < 14 ? ['中午了，吃点东西再继续。', '先做一页再休息。'] : h < 18 ? ['下午容易犯困，起来动一动再学。', '慢一些无妨，重要的是每一步都扎实。'] : ['晚上适合复盘：把今天错的题再看一遍。', '今天辛苦了，收个尾吧。'];
    return t;
  };
  function profile() { const d = window.DASH_REF && window.DASH_REF(); return d?.narrative?.profile || d?.narrative?.guide_profile || null; }
  function build() {
    el = document.createElement('div'); el.id = 'companion'; el.setAttribute('role', 'button'); el.tabIndex = 0; el.hidden = true;
    el.innerHTML = '<div class="comp-bubble" hidden></div><img class="comp-img" alt=""><span class="comp-x" aria-label="收起同伴" title="收起（可在 设置→地点排布 重新打开）">×</span>';
    document.body.appendChild(el);
    const open = () => { if (window.NARRATIVE) NARRATIVE.open(); };
    el.addEventListener('click', (e) => { if (e.target.closest('.comp-x')) { try { localStorage.setItem(KEY, '0'); } catch (err) { /* 只管本次 */ } update(); return; } open(); });
    el.addEventListener('keydown', (e) => { if (e.key === 'Enter') open(); });
  }
  function say(text) {
    const b = el.querySelector('.comp-bubble'); b.textContent = text; b.hidden = false; clearTimeout(hideT);
    hideT = setTimeout(() => { b.hidden = true; }, 6500);
  }
  function update() {
    const p = profile(), portrait = p?.portraits?.calm;
    const busy = document.body.classList.contains('portal-home') || document.querySelector('.tj-opt, #modal:not(.hidden), .narrative-dialog[open]') || document.documentElement.matches('.in-notes,.in-chat,.in-sl-exam');
    const onPage = typeof VIEW !== 'undefined' && VIEW === 'dwelling';   // 只在洞府出现，别的页面不遮挡内容
    const show = onPage && !!portrait && on() && window.innerWidth >= 1100 && !busy && !document.hidden;
    if (!el && show) build();
    if (!el) return;
    if (show && img !== portrait) { img = portrait; el.querySelector('.comp-img').src = portrait; }
    const was = !el.hidden; el.hidden = !show;
    el.classList.toggle('comp-still', still());
    if (show && !was) { clearTimeout(bubbleT); bubbleT = setTimeout(() => { if (!el.hidden) { const l = lines(); say(l[Math.floor(Math.random() * l.length)]); } }, 1800); }
    if (!show) { clearTimeout(bubbleT); const b = el.querySelector('.comp-bubble'); if (b) b.hidden = true; }
  }
  let q = 0; const later = () => { if (q) return; q = 1; setTimeout(() => { q = 0; update(); }, 250); };
  const start = () => {
    new MutationObserver(later).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    window.addEventListener('resize', later); document.addEventListener('visibilitychange', later);
    setInterval(() => { if (el && !el.hidden && Math.random() < 0.5) { const l = lines(); say(l[Math.floor(Math.random() * l.length)]); } }, 70000);
    later();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  // 设置页开关（scene_fx 的设置卡里放一个勾选框）
  document.addEventListener('change', (e) => { if (e.target.matches?.('[data-companion-toggle]')) { try { localStorage.setItem(KEY, e.target.checked ? '1' : '0'); } catch (err) { /* ok */ } update(); } });
  window.BeautyCompanion = { on, update, settingsHtml: () => `<label class="small"><input type="checkbox" data-companion-toggle ${on() ? 'checked' : ''} style="width:auto"> 洞府里显示引导人物站位（宽屏电脑）</label>` };
})();
