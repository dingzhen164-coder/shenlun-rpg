/* 美术文件夹（rpg/art.py）的前端部分：服务器在 index.html 里注入 window.ART_FILES（库里 训练/外观/美术/ 有哪些覆盖文件及修改时间）。
 * 1) 子地图背景：当前页（洞府、修炼、试炼塔…）若有 beauty/page/<页>-day|night.webp 或 <页>.webp，就把它当作这一页背后的背景（亮色用 -day，暗色用 -night，都没有用不带后缀的），
 *    没有就用程序默认的淡透全景；覆盖图本身给得更清晰，遮罩调淡。
 * 2) BeautyArt.has / url：给别的脚本判断某个资源是否被覆盖（申论首页夜景用）。
 * 首页全景、人物立绘、音乐、音效不需要前端处理：它们请求的原路径会被服务器直接换成美术文件夹里的文件。 */
(() => {
  'use strict';
  const F = new Map((Array.isArray(window.ART_FILES) ? window.ART_FILES : []).map((x) => [x[0], x[1]]));
  const has = (r) => F.has(r), url = (r) => 'assets/' + r + '?v=' + F.get(r);
  // 洞府页签名 → key（与 rpg/art.py 的 DWELLING_TABS 对应）
  const TAB_KEY = { '修为与突破': 'growth', '仕途与晋升': 'growth', '成长与晋升': 'growth', '十二经': 'shier', '修行记录': 'records', '学习记录': 'records', '储物袋': 'bag', '修行日志': 'diary', '学时与出勤': 'daily', '时辰与日课': 'daily' };
  const REGION_KEY = { '万象峰': 'chang', '辨言峰': 'yan', '明理峰': 'li', '演数峰': 'shu', '观星峰': 'zi', '归纳概括': 'guina', '综合分析': 'zonghe', '提出对策': 'duice', '贯彻执行': 'guanche', '大作文': 'dazuowen',
    '民法': 'minfa', '刑法': 'xingfa', '民诉': 'minsu', '刑诉': 'xingsu', '行政法': 'xingzheng', '商经知': 'shangjing', '三国法': 'sanguo', '理论法': 'lilun' };
  const regionName = () => { try { return window.STUDY_REGIONS ? STUDY_REGIONS.title() : ''; } catch (e) { return ''; } };
  const tabLabel = () => { const t = document.querySelector('.fx-tab[aria-selected="true"]'); return t ? t.textContent.trim() : ''; };
  let view = '';
  function apply() {
    const b = document.body; if (!b) return;
    const dark = document.documentElement.dataset.theme === 'dark', dn = dark ? 'night' : 'day', want = [];
    if (view && view !== 'home') {
      const tk = view === 'dwelling' ? TAB_KEY[tabLabel()] : '';              // 洞府每个页签可单独配背景，没有就回退洞府整体背景
      if (tk) want.push(`beauty/page/dwelling-${tk}-${dn}.webp`, `beauty/page/dwelling-${tk}.webp`);
      const rk = view === 'train' ? REGION_KEY[regionName()] : '';          // 修炼页选中某个分区（五峰等）时可单独配背景
      if (rk) want.push(`beauty/page/train-${rk}-${dn}.webp`, `beauty/page/train-${rk}.webp`);
      want.push(`beauty/page/${view}-${dn}.webp`, `beauty/page/${view}.webp`);
    }
    const hit = want.find(has);
    if (hit) { b.style.setProperty('--ds-page-art', `url("${url(hit)}")`); b.classList.add('has-page-art'); }
    else { b.style.removeProperty('--ds-page-art'); b.classList.remove('has-page-art'); }
  }
  function readView() {                                                       // 当前页取 app.js 的 VIEW（试炼塔 bank 等不在顶栏里，不能靠顶栏判断）
    let v = ''; try { v = typeof VIEW !== 'undefined' ? VIEW : ''; } catch (e) { v = ''; }
    if (v !== view) { view = v; apply(); }
  }
  const start = () => {
    const nav = document.getElementById('nav');
    if (nav) new MutationObserver(readView).observe(nav, { attributes: true, attributeFilter: ['class'], subtree: true });
    new MutationObserver(apply).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    readView();
    const v = document.getElementById('view'); let q = 0;                    // 洞府切页签时更新背景
    if (v) new MutationObserver(() => { if (!q) { q = 1; setTimeout(() => { q = 0; readView(); apply(); }, 60); } }).observe(v, { attributes: true, attributeFilter: ['aria-selected'], subtree: true, childList: true });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  window.BeautyArt = { has, url, files: () => Array.from(F.keys()) };
})();
