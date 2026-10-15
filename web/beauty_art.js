/* 美术文件夹（rpg/art.py）的前端部分：服务器在 index.html 里注入 window.ART_FILES（库里 训练/外观/美术/ 有哪些覆盖文件及修改时间）。
 * 1) 子地图背景：当前页（洞府、修炼、试炼塔…）若有 beauty/page/<页>-day|night.webp 或 <页>.webp，就把它当作这一页背后的背景（亮色用 -day，暗色用 -night，都没有用不带后缀的），
 *    没有就用程序默认的淡透全景；覆盖图本身给得更清晰，遮罩调淡。
 * 2) BeautyArt.has / url：给别的脚本判断某个资源是否被覆盖（申论首页夜景用）。
 * 首页全景、人物立绘、音乐、音效不需要前端处理：它们请求的原路径会被服务器直接换成美术文件夹里的文件。 */
(() => {
  'use strict';
  const F = new Map((Array.isArray(window.ART_FILES) ? window.ART_FILES : []).map((x) => [x[0], x[1]]));
  const has = (r) => F.has(r), url = (r) => 'assets/' + r + '?v=' + F.get(r);
  let view = '';
  function apply() {
    const b = document.body; if (!b) return;
    const dark = document.documentElement.dataset.theme === 'dark', want = view && view !== 'home' ? [`beauty/page/${view}-${dark ? 'night' : 'day'}.webp`, `beauty/page/${view}.webp`] : [];
    const hit = want.find(has);
    if (hit) { b.style.setProperty('--ds-page-art', `url("${url(hit)}")`); b.classList.add('has-page-art'); }
    else { b.style.removeProperty('--ds-page-art'); b.classList.remove('has-page-art'); }
  }
  function readView() {
    const a = document.querySelector('#nav a.active'); const v = a ? a.dataset.view : '';
    if (v !== view) { view = v; apply(); }
  }
  const start = () => {
    const nav = document.getElementById('nav');
    if (nav) new MutationObserver(readView).observe(nav, { attributes: true, attributeFilter: ['class'], subtree: true });
    new MutationObserver(apply).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    readView();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  window.BeautyArt = { has, url, files: () => Array.from(F.keys()) };
})();
