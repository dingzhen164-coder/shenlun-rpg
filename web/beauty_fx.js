/* 3.2.7 答题反馈特效：选对时迸出光点、连续答对出现“连击 ×N”，选错时轻轻抖一下。
 * 只是外观反馈，不影响判分、经验与记录（程序算分）。靠观察选项 .tj-opt 的 right/wrong 类（点选项后4秒内出现才算），不改答题代码。
 * 减少动画（data-motion=reduced / 系统设置）时不做。 */
(() => {
  'use strict';
  const still = () => document.documentElement.dataset.motion === 'reduced' || matchMedia('(prefers-reduced-motion: reduce)').matches;
  let combo = 0, badge = null, badgeTimer = 0;
  const COLORS = ['#f3d98b', '#8fd6a8', '#fff3c4', '#b7e4c7'];

  function burst(el) {
    const r = el.getBoundingClientRect(); const cx = r.left + Math.min(r.width, 80) / 2 + 18, cy = r.top + r.height / 2;
    for (let i = 0; i < 12; i++) {
      const d = document.createElement('i');
      d.style.cssText = `position:fixed;left:${cx}px;top:${cy}px;width:6px;height:6px;border-radius:50%;pointer-events:none;z-index:90;background:${COLORS[i % COLORS.length]};box-shadow:0 0 6px ${COLORS[i % COLORS.length]}`;
      document.body.appendChild(d);
      const a = Math.random() * 6.28, dist = 30 + Math.random() * 46;
      d.animate([{ transform: 'translate(0,0) scale(1)', opacity: 1 }, { transform: `translate(${Math.cos(a) * dist}px,${Math.sin(a) * dist - 16}px) scale(.2)`, opacity: 0 }], { duration: 650 + Math.random() * 250, easing: 'cubic-bezier(.2,.7,.3,1)' }).onfinish = () => d.remove();
    }
  }
  function shake(el) {
    el.animate([{ transform: 'translateX(0)' }, { transform: 'translateX(-6px)' }, { transform: 'translateX(5px)' }, { transform: 'translateX(-3px)' }, { transform: 'translateX(0)' }], { duration: 300 });
  }
  function showCombo(n) {
    if (!badge) {
      badge = document.createElement('div'); badge.setAttribute('aria-hidden', 'true');
      badge.style.cssText = 'position:fixed;top:18%;left:50%;transform:translateX(-50%);z-index:90;pointer-events:none;font:700 28px/1 var(--display,serif);letter-spacing:.12em;color:#f3d98b;text-shadow:0 2px 0 #3b2a05,0 0 14px #e0bf62;opacity:0';
      document.body.appendChild(badge);
    }
    badge.textContent = `连击 ×${n}`; clearTimeout(badgeTimer);
    badge.animate([{ transform: 'translateX(-50%) scale(.6)', opacity: 0 }, { transform: 'translateX(-50%) scale(1.15)', opacity: 1, offset: .25 }, { transform: 'translateX(-50%) scale(1)', opacity: 1, offset: .8 }, { transform: 'translateX(-50%) scale(1)', opacity: 0 }], { duration: 1400, fill: 'forwards' });
    if (window.BeautyAudio && n >= 3) BeautyAudio.sfx('combo');
  }
  // 作答反馈：用户点选项后 4 秒内，题目被重绘成带 right/wrong 的样子才算“刚作答”（翻看已答题目不触发）
  let armed = 0;
  document.addEventListener('pointerdown', (e) => { if (e.target.closest && e.target.closest('.tj-opt')) armed = Date.now(); }, true);
  function check() {
    if (!armed || Date.now() - armed > 4000) return;
    const root = document.getElementById('view'); if (!root) return;
    const wrong = root.querySelector('.tj-opt.wrong'), right = root.querySelector('.tj-opt.right');
    if (!wrong && !right) return;
    armed = 0;
    document.dispatchEvent(new CustomEvent('beauty:answer', { detail: { right: !wrong } }));
    if (!wrong) { combo++; if (!still()) { burst(right); if (combo >= 3) showCombo(combo); } }
    else { combo = 0; if (!still()) shake(wrong); }
  }
  // 页面转场：顶栏当前页变化后，#view 内容第一次被换掉时淡入上移（通知音效模块放翻页声）
  let pendingView = 0, curView = '';
  function watchNav() {
    const nav = document.getElementById('nav'); if (!nav) return;
    new MutationObserver(() => {
      const a = nav.querySelector('a.active'); const vw = a ? a.dataset.view : '';
      if (vw && vw !== curView) { const first = !curView; curView = vw; if (!first) { pendingView = Date.now(); document.dispatchEvent(new CustomEvent('beauty:view', { detail: { view: vw } })); } }
    }).observe(nav, { attributes: true, attributeFilter: ['class'], subtree: true });
  }
  const start = () => {
    const v = document.getElementById('view'); if (!v) return;
    watchNav();
    new MutationObserver(() => {
      if (pendingView && Date.now() - pendingView < 2500 && !still()) { pendingView = 0; v.animate([{ opacity: 0, transform: 'translateY(10px)' }, { opacity: 1, transform: 'none' }], { duration: 320, easing: 'ease-out' }); }
    }).observe(v, { childList: true });
    new MutationObserver(() => { if (armed) check(); }).observe(v, { attributes: true, attributeFilter: ['class'], subtree: true, childList: true });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  // 奖励飘字：经验类 toast（class xp）出现时，在屏幕中上方飘起“+N”（读 toast 文字里的数字，只做外观）
  function floatReward(text) {
    const d = document.createElement('div'); d.setAttribute('aria-hidden', 'true'); d.textContent = text;
    d.style.cssText = 'position:fixed;left:50%;top:34%;transform:translateX(-50%);z-index:90;pointer-events:none;font:700 30px/1 var(--display,serif);letter-spacing:.08em;color:#f3d98b;text-shadow:0 2px 0 #3b2a05,0 0 12px #e0bf62';
    document.body.appendChild(d);
    d.animate([{ transform: 'translate(-50%,14px) scale(.7)', opacity: 0 }, { transform: 'translate(-50%,0) scale(1.1)', opacity: 1, offset: .2 }, { transform: 'translate(-50%,-46px) scale(1)', opacity: 0 }], { duration: 1500, easing: 'ease-out' }).onfinish = () => d.remove();
  }
  const watchToasts = () => {
    const tt = document.getElementById('toasts'); if (!tt) return;
    new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => {
      if (n.classList && n.classList.contains('xp') && !still()) { const m2 = /\+\s*(\d+)/.exec(n.textContent || ''); if (m2) floatReward('+' + m2[1]); }
    }))).observe(tt, { childList: true });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watchToasts); else watchToasts();
  window.BeautyFx = { burst, shake, showCombo };
})();
