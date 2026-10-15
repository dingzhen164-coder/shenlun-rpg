/* 3.2.x 动态感：把鼠标位置（电脑）或设备倾斜（平板）变成 -1…1 的两个变量 --mx / --my 写在 <html> 上，
 * 地图全景、云雾、人物立绘按它们做视差与“看向光标”的轻微位移（CSS 里用 translate/rotate 属性，不与原动画冲突）。
 * 缓动跟随，静止后自动停止计算；减少动画、页面隐藏时归零。只改外观。 */
(() => {
  'use strict';
  const root = document.documentElement;
  const reduced = () => root.dataset.motion === 'reduced' || matchMedia('(prefers-reduced-motion: reduce)').matches;
  let tx = 0, ty = 0, x = 0, y = 0, raf = 0;
  function set(nx, ny) { tx = Math.max(-1, Math.min(1, nx)); ty = Math.max(-1, Math.min(1, ny)); if (!raf) raf = requestAnimationFrame(tick); }
  function tick() {
    raf = 0;
    if (reduced() || document.hidden) { tx = ty = 0; }
    x += (tx - x) * 0.08; y += (ty - y) * 0.08;
    root.style.setProperty('--mx', x.toFixed(3)); root.style.setProperty('--my', y.toFixed(3));
    if (Math.abs(tx - x) > 0.002 || Math.abs(ty - y) > 0.002) raf = requestAnimationFrame(tick);
  }
  window.addEventListener('pointermove', (e) => { if (e.pointerType === 'mouse') set((e.clientX / innerWidth - 0.5) * 2, (e.clientY / innerHeight - 0.5) * 2); }, { passive: true });
  window.addEventListener('deviceorientation', (e) => {
    if (e.gamma == null || e.beta == null) return;
    const portrait = innerHeight > innerWidth, g = portrait ? e.gamma : e.beta, b = portrait ? e.beta - 40 : -e.gamma;
    set(g / 25, b / 25);
  }, { passive: true });
  document.addEventListener('visibilitychange', () => { if (document.hidden) set(0, 0); });
})();
