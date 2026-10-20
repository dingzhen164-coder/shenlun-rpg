/* 平板应用外壳：只阻止浏览器的整页缩放；保留单指滚动、笔迹和组件自己的手势事件。
   在页面骨架加载时注册，Safari普通标签页与添加到主屏幕使用相同规则。 */
(() => {
  'use strict';
  const touch = matchMedia('(pointer: coarse)').matches || navigator.maxTouchPoints > 1;
  if (!touch) return;
  document.documentElement.classList.add('tablet-shell');
  const prevent = e => { if (e.cancelable) e.preventDefault(); };
  // iPad Safari会忽略viewport中的user-scalable=no，因此不靠它限制页面缩放。
  for (const type of ['gesturestart', 'gesturechange', 'gestureend']) {
    document.addEventListener(type, prevent, {capture:true, passive:false});
  }
  for (const type of ['touchstart', 'touchmove']) {
    document.addEventListener(type, e => { if (e.touches.length > 1) prevent(e); }, {capture:true, passive:false});
  }
})();
