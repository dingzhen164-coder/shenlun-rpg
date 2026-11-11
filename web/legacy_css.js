/* 旧内核兜底：安卓平板 App 用系统自带的 WebView，没更新的话认不得 color-mix()（Chrome 111 才有）和 dvh（Chrome 108 才有）。
 * 认不得的整条样式会被丢掉：磨砂卡片变全透明、全屏答题页高度塌掉……而 iPad / 电脑的浏览器是新的，看着就和安卓不一样。
 * 这里在内核太旧时把样式表读回来改写成旧内核也认得的写法，内核够新时什么都不做。测试：地址后加 ?legacycss=1 强制走这一路
 * （tests/ui_legacy_css.cjs、tests/ui_legacy_glass.cjs）。放在所有 <link rel=stylesheet> 之后、<body> 之前；后来动态加进来的样式表也会处理。
 *
 * 改写规则（2026-11-11 重做：原来半透明一律换成“实底或全透明”，镂空后的淡底框在安卓上整块消失）：
 *   dvh → vh；
 *   每个颜色变量 --x: <颜色> 旁边补一个 --lc-x: r,g,b（--x: var(--y) 就补 --lc-x: var(--lc-y)），跟着原来的主题/作用域一起变；
 *   color-mix(in srgb, var(--x) 32%, transparent) → rgba(var(--lc-x, 当时的r,g,b), .32)，透明度照原样；
 *   透明度本身是变量（设置里的透明度滑块）：color-mix(…, var(--x) var(--interface-panel-alpha,32%), transparent) → rgba(var(--lc-x…), var(--interface-panel-alpha,32%))；
 *   两个具体颜色相混 → 直接算出混合色；认不出的（currentColor、两个变量相混）照旧取占比大的那个颜色。
 *   JS 直接写在 <html style> 上的颜色变量（时政地图 iframe 抄父页配色）由 MutationObserver 补上对应的 --lc-x。
 *   :has()（Chrome 105 才有）：内核不认时，把 “A:has(B)” 换成 “A.lch3” 这样的类，页面变化时由脚本给“含有 B 的 A”挂上这个类。
 *   参阅室阅读页的定高、题头隐藏等都靠它（2026-11-11：安卓上大标题卡不隐藏、两栏不定高一起滑，就是这个原因）。测试加 &nohas=1 强制走这一路。 */
(() => {
  'use strict';
  let force = /[?&]legacycss=1\b/.test(location.search);
  try { force = force || (parent !== window && /[?&]legacycss=1\b/.test(parent.location.search)); } catch (e) { /* 跨域 iframe 不管 */ }   // 测试：时政地图 iframe 跟着父页强制
  let modern = false;
  try { modern = CSS.supports('color', 'color-mix(in srgb, red 50%, transparent)') && CSS.supports('height', '1dvh'); } catch (e) { modern = false; }
  let hasOk = true;
  try { hasOk = CSS.supports('selector(:has(a))'); } catch (e) { hasOk = false; }
  try { if (/[?&]nohas=1\b/.test(location.search) || (parent !== window && /[?&]nohas=1\b/.test(parent.location.search))) hasOk = false; } catch (e) { /* 跨域 iframe */ }
  if (modern && !force) return;
  const root = document.documentElement;
  root.classList.add('legacy-css');

  // 颜色探针：让浏览器自己把任意颜色写法（#hex、rgb()、颜色名、var(--x)）算成 rgb 数字
  const probe = document.createElement('i');
  probe.setAttribute('aria-hidden', 'true');
  probe.style.display = 'none';
  root.appendChild(probe);
  const known = new Map();                                                // 具体颜色只算一次（平板上样式声明成百上千条）
  function rgbOf(value) {
    const fixed = !/var\(/i.test(value);
    if (fixed && known.has(value)) return known.get(value);
    const out = measure(value);
    if (fixed) known.set(value, out);
    return out;
  }
  function measure(value) {
    probe.style.color = '';
    probe.style.color = value;
    if (!probe.style.color) return null;
    const m = getComputedStyle(probe).color.match(/rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+)(%?))?/);
    if (!m) return null;
    const a = m[4] == null ? 1 : m[5] ? parseFloat(m[4]) / 100 : parseFloat(m[4]);
    return { r: +m[1], g: +m[2], b: +m[3], a, t: `${Math.round(m[1])},${Math.round(m[2])},${Math.round(m[3])}` };
  }
  const num = (x) => String(Math.round(x * 1000) / 1000);

  // 按最外层的逗号 / 空白切开（括号里的不切）
  function splitTop(s, sep) {
    const out = []; let depth = 0, cur = '';
    for (const ch of s) {
      if (ch === '(') depth++; else if (ch === ')') depth--;
      if (depth === 0 && (sep === ',' ? ch === ',' : /\s/.test(ch))) { if (sep === ',' || cur) out.push(cur); cur = ''; } else cur += ch;
    }
    if (sep === ',' || cur) out.push(cur);
    return out;
  }

  const COLOR_VARS = new Set();         // 样式表里声明成颜色（或指向别的变量）的 --x：这些会有 --lc-x
  const VAR = /^var\(\s*(--[\w-]+)\s*(?:,\s*([\s\S]+))?\)$/;
  const DECL = /(^|[;{\s])(--[\w-]+)\s*:\s*([^;{}]+?)\s*(?=[;}])/g;
  const literal = (v) => !/var\(|color-mix\(/i.test(v) && !/^(transparent|currentcolor|inherit|initial|unset)$/i.test(v) && CSS.supports('color', v);
  function collect(css) {
    css.replace(DECL, (m, pre, name, value) => {
      if (name.startsWith('--lc-')) return m;
      const v = value.replace(/\s*!important$/i, '');
      if (VAR.test(v) || literal(v)) COLOR_VARS.add(name);
      return m;
    });
  }
  // --x: 颜色 → 补 --lc-x: r,g,b；--x: var(--y) → 补 --lc-x: var(--lc-y, 当时的 r,g,b)
  function addTriplets(css) {
    return css.replace(DECL, (m, pre, name, value) => {
      if (name.startsWith('--lc-') || !COLOR_VARS.has(name)) return m;
      const imp = /!important$/i.test(value) ? ' !important' : '', v = value.replace(/\s*!important$/i, '');
      const ref = v.match(VAR);
      if (ref) {
        if (ref[1] === name) return m;                                     // --line: var(--line) 这种自指的不补，避免循环
        const fb = ref[2] && literal(ref[2].trim()) ? rgbOf(ref[2].trim()) : null;
        return `${m};--lc-${name.slice(2)}:var(--lc-${ref[1].slice(2)}${fb && fb.a === 1 ? ',' + fb.t : ''})${imp}`;
      }
      const c = rgbOf(v);
      return c && c.a === 1 ? `${m};--lc-${name.slice(2)}:${c.t}${imp}` : m;
    });
  }

  // 一个颜色乘上透明度（alpha：0–1 的数字，或 var(--interface-panel-alpha,32%) 这样的百分比表达式）
  function fade(color, alpha) {
    const c = color.trim();
    const ref = c.match(VAR);
    if (ref) {
      const now = rgbOf(c);                                               // 兜底值：此刻根元素上的颜色
      // 样式表里没声明、此刻也取不到（如元素 style 里临时写的 --c）：认不出，照旧
      if (COLOR_VARS.has(ref[1]) || now) {
        COLOR_VARS.add(ref[1]);                                           // 之后 JS 写到 <html style> 上也能补 --lc-x
        return `rgba(var(--lc-${ref[1].slice(2)}${now && now.a === 1 ? ',' + now.t : ''}),${typeof alpha === 'number' ? num(alpha) : alpha})`;
      }
    }
    const nested = c.match(/^rgba\((var\(--lc-[^)]*\)),([\d.]+)\)$/);    // 里层 color-mix 改写出来的
    if (nested && typeof alpha === 'number') return `rgba(${nested[1]},${num(+nested[2] * alpha)})`;
    if (!/var\(/i.test(c)) {
      const lit = rgbOf(c);
      if (lit) return typeof alpha === 'number' ? `rgba(${lit.t},${num(lit.a * alpha)})` : `rgba(${lit.t},${alpha})`;
    }
    return null;
  }
  const isTransparent = (c) => /^transparent$/i.test(c.trim());
  function pick(inner) {
    const parts = splitTop(inner, ',');
    parts.shift();                                                        // 去掉 “in srgb”
    const parse = (p) => { const t = splitTop((p || '').trim(), ' '); return { c: t[0] || '', p: t.slice(1).join(' ') }; };
    const a = parse(parts[0]), b = parse(parts[1] || 'transparent');
    const pct = (x) => { const m = /^(\d+(?:\.\d+)?)%$/.exec(x.p); return m ? parseFloat(m[1]) : null; };
    let pa = pct(a), pb = pct(b);
    if (pa == null && pb == null && !a.p && !b.p) { pa = 50; pb = 50; }
    else if (pa == null && pb != null && !a.p) pa = 100 - pb;
    else if (pb == null && pa != null && !b.p) pb = 100 - pa;
    // 和透明相混：颜色 × 透明度
    if (isTransparent(b.c) || isTransparent(a.c)) {
      const side = isTransparent(b.c) ? a : b, share = isTransparent(b.c) ? pa : pb;
      const alpha = share != null ? share / 100 : side.p || 0.5;
      const out = fade(side.c, alpha);
      if (out) return out;
      return (share == null || share >= 50) ? side.c : 'transparent';   // 认不出：照旧
    }
    // 两个具体颜色：直接算出混合色
    if (pa != null && pb != null && !/var\(/i.test(a.c + b.c)) {
      const x = rgbOf(a.c), y = rgbOf(b.c);
      if (x && y) {
        const k = pa / (pa + pb), mix = (u, v) => Math.round(u * k + v * (1 - k));
        return `rgba(${mix(x.r, y.r)},${mix(x.g, y.g)},${mix(x.b, y.b)},${num(x.a * k + y.a * (1 - k))})`;
      }
    }
    return (pa == null ? 50 : pa) >= 50 ? a.c : b.c;                      // 两个变量相混：取占比大的那个
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
  // ---- :has() 替身 ----
  const HAS = [];                                                         // [{cls, anchor, inner}]
  function hasRule(prelude) {
    return splitTop(prelude, ',').map((sel) => {
      let guard = 0;
      while (sel.includes(':has(') && guard++ < 4) {
        const at = sel.indexOf(':has(');
        let depth = 0, j = at + 4;
        for (; j < sel.length; j++) { if (sel[j] === '(') depth++; else if (sel[j] === ')' && --depth === 0) break; }
        const inner = sel.slice(at + 5, j).trim();
        if (/^[+~]/.test(inner)) return null;                             // 兄弟关系的 :has 不做，整条照旧丢掉
        const anchor = sel.slice(0, at).replace(/:has\((?:[^()]|\([^()]*\))*\)/g, '').trim() || '*';
        const cls = 'lch' + HAS.length;
        HAS.push({ cls, anchor: /[\s>+~]$/.test(anchor) ? anchor + '*' : anchor, inner: /^>/.test(inner) ? ':scope ' + inner : inner });
        sel = sel.slice(0, at) + '.' + cls + sel.slice(j + 1);
      }
      return sel;
    }).filter((x) => x != null).join(',');
  }
  function fixHas(css) {
    if (hasOk || !css.includes(':has(')) return css;
    return css.replace(/([^{};]+)\{/g, (m, prelude) => (prelude.trim().startsWith('@') || !prelude.includes(':has(')) ? m : (hasRule(prelude) || ':not(*)') + '{');
  }
  let hasQueued = false;
  function syncHas() {
    hasQueued = false;
    for (const h of HAS) {
      let want = [];
      try { want = [...document.querySelectorAll(h.anchor)].filter((el) => el.querySelector(h.inner)); } catch (e) { continue; }
      document.querySelectorAll('.' + h.cls).forEach((el) => { if (!want.includes(el)) el.classList.remove(h.cls); });
      want.forEach((el) => { if (!el.classList.contains(h.cls)) el.classList.add(h.cls); });
    }
  }
  const queueHas = () => { if (HAS.length && !hasQueued) { hasQueued = true; setTimeout(syncHas, 50); } };   // 页面一阵变化合并成一次，平板上不每帧都查

  const fix = (css) => addTriplets(fixMix(fixHas(css.replace(/(\d)dvh\b/g, '$1vh'))));

  const done = new WeakSet();
  function read(link) {
    if (done.has(link) || !link.href || new URL(link.href, location.href).origin !== location.origin) return null;
    done.add(link);
    try {
      const x = new XMLHttpRequest();
      x.open('GET', link.href, false); x.send();                // 同步读：在页面画出来之前换好，避免闪一下
      return x.status === 200 ? x.responseText : null;
    } catch (e) { return null; }                                // 读不到就保持原样
  }
  function swap(link, css) {
    const st = document.createElement('style');
    st.textContent = fix(css);
    st.dataset.legacyFrom = link.getAttribute('href');
    link.replaceWith(st);
  }
  // 先把所有样式表读完、记下哪些变量是颜色，再统一改写（变量常在前一个文件里声明、后一个文件里用）
  function all() {
    const got = [];
    document.querySelectorAll('link[rel="stylesheet"]').forEach((link) => { const css = read(link); if (css != null) got.push([link, css]); });
    got.forEach(([, css]) => collect(css));
    got.forEach(([link, css]) => swap(link, css));
  }
  // JS 写在 <html style> 上的颜色变量：补上 --lc-x
  function inlineVars() {
    const s = root.style;
    for (let i = 0; i < s.length; i++) {
      const name = s[i];
      if (!name.startsWith('--') || name.startsWith('--lc-') || !COLOR_VARS.has(name)) continue;
      const c = rgbOf(s.getPropertyValue(name).trim());
      const key = '--lc-' + name.slice(2);
      if (c && c.a === 1 && s.getPropertyValue(key) !== c.t) s.setProperty(key, c.t);
    }
  }
  all();
  inlineVars();
  if (!hasOk) {
    root.classList.add('legacy-has');
    new MutationObserver(queueHas).observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'id'] });   // 自己挂的类再触发一次，查完没有变化就停
    document.addEventListener('DOMContentLoaded', queueHas);
    queueHas();
  }
  new MutationObserver(all).observe(root, { childList: true, subtree: true });
  new MutationObserver(inlineVars).observe(root, { attributes: true, attributeFilter: ['style'] });
  window.LEGACY_CSS = { fix, colorVars: () => [...COLOR_VARS], has: () => HAS.map((h) => ({ ...h })), syncHas };          // 测试用
})();
