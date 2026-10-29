/* 旧内核兜底：安卓平板 App 用系统自带的 WebView，没更新的话认不得 color-mix()（Chrome 111 才有）和 dvh（Chrome 108 才有）。
 * 认不得的整条样式会被丢掉：磨砂卡片变全透明、全屏答题页高度塌掉……而 iPad / 电脑的浏览器是新的，看着就和安卓不一样。
 * 这里在内核太旧时把样式表读回来改写成旧内核也认得的写法（dvh→vh；color-mix(A p%, 透明)→A 或透明），
 * 内核够新时什么都不做。测试：地址后加 ?legacycss=1 强制走这一路（tests/ui_legacy_css.cjs）。
 * 放在所有 <link rel=stylesheet> 之后、<body> 之前；后来动态加进来的样式表也会处理。 */
(() => {
  'use strict';
  const force = /[?&]legacycss=1\b/.test(location.search);
  let modern = false;
  try { modern = CSS.supports('color', 'color-mix(in srgb, red 50%, transparent)') && CSS.supports('height', '1dvh'); } catch (e) { modern = false; }
  if (modern && !force) return;
  document.documentElement.classList.add('legacy-css');

  // 括号配平地找出所有 color-mix(...)，由内向外换掉
  function splitTop(s) {
    const out = []; let depth = 0, cur = '';
    for (const ch of s) {
      if (ch === '(') depth++; else if (ch === ')') depth--;
      if (ch === ',' && depth === 0) { out.push(cur); cur = ''; } else cur += ch;
    }
    out.push(cur); return out;
  }
  function pick(inner) {
    const parts = splitTop(inner);
    parts.shift();                                              // 去掉 “in srgb”
    const parse = (p) => { const m = p.trim().match(/^(.*?)(?:\s+(\d+(?:\.\d+)?)%)?$/s); return { c: (m[1] || '').trim(), p: m[2] == null ? null : parseFloat(m[2]) }; };
    const a = parse(parts[0] || ''), b = parse(parts[1] || 'transparent');
    const pa = a.p == null ? (b.p == null ? 50 : 100 - b.p) : a.p;
    if (/^transparent$/i.test(b.c)) return pa >= 50 || a.p == null ? a.c : 'transparent';   // 磨砂底板：旧内核上用实底，保证看得清
    return pa >= 50 ? a.c : b.c;
  }
  function fixMix(css) {
    let i;
    while ((i = css.lastIndexOf('color-mix(')) >= 0) {          // 最后一个一定是最内层
      let depth = 0, j = i + 9;
      for (; j < css.length; j++) { if (css[j] === '(') depth++; else if (css[j] === ')' && --depth === 0) break; }
      css = css.slice(0, i) + pick(css.slice(i + 10, j)) + css.slice(j + 1);
    }
    return css;
  }
  const fix = (css) => fixMix(css.replace(/(\d)dvh\b/g, '$1vh'));

  const done = new WeakSet();
  function rewrite(link) {
    if (done.has(link) || !link.href || new URL(link.href, location.href).origin !== location.origin) return;
    done.add(link);
    try {
      const x = new XMLHttpRequest();
      x.open('GET', link.href, false); x.send();                // 同步读：在页面画出来之前换好，避免闪一下
      if (x.status !== 200) return;
      const st = document.createElement('style');
      st.textContent = fix(x.responseText);
      st.dataset.legacyFrom = link.getAttribute('href');
      link.replaceWith(st);
    } catch (e) { /* 读不到就保持原样 */ }
  }
  const all = () => document.querySelectorAll('link[rel="stylesheet"]').forEach(rewrite);
  all();
  new MutationObserver(all).observe(document.documentElement, { childList: true, subtree: true });
})();
