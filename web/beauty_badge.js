/* 3.2.x 境界徽章：按大境界（0 凡人 … 7 真仙；申论为 8 段职级）画一枚徽章，颜色从铜、银、金到翠、蓝、紫、赤、辉金递进，
 * 形状从圆到盾到六边形，高阶带羽翼与桂叶，下方小星表示小境界。纯 SVG，不需要素材。
 * 用法：BeautyBadge.svg({tier, sub, label, size}) 返回 SVG 字符串；BeautyBadge.inline(realmInfo)（洞府用，realmInfo＝dashboard.realm）；
 * BeautyBadge.tierOf(境界名或职级名) 在只有名字时推断档位（大典画面用）。徽章只是外观，不影响成绩。 */
(() => {
  'use strict';
  const PAL = [['#d8a36a', '#7a4f2a'], ['#e6edf2', '#7f8c97'], ['#f1d06b', '#a07a18'], ['#7fe0c4', '#1f7d69'], ['#8cc4f4', '#2b62a3'], ['#c8a8f6', '#6440b0'], ['#f79a80', '#b03a2c'], ['#fff5c4', '#d9a02e']];
  const NAMES = ['凡人', '炼气', '筑基', '金丹', '元婴', '化神', '大乘', '真仙'];
  const RANKS = ['科员', '副科', '正科', '副处', '正处', '副厅', '正厅', '副部', '正部', '副国', '正国'];
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  function tierOf(name) {
    const n = String(name || ''), a = NAMES.findIndex((x) => n.startsWith(x)); if (a >= 0) return a;
    const r = RANKS.findIndex((x) => n.includes(x)); return r >= 0 ? Math.min(7, Math.floor(r * 7 / (RANKS.length - 1))) : 0;
  }
  let uid = 0;
  function svg({ tier = 0, sub = 0, label = '', size = 56 }) {
    const t = Math.max(0, Math.min(7, tier | 0)), [hi, lo] = PAL[t], id = 'bb' + (++uid);
    const shape = t === 0 ? '<circle cx="50" cy="52" r="42"/>' : t <= 2 ? '<path d="M50 6 L88 18 V52 C88 76 70 92 50 102 C30 92 12 76 12 52 V18 Z"/>' : '<path d="M50 5 L90 27 V73 L50 98 L10 73 V27 Z"/>';
    const wings = t >= 5 ? `<g fill="url(#${id}g)" opacity=".9"><path d="M10 44 C-6 36 -10 54 -2 68 C6 60 12 60 16 60Z"/><path d="M90 44 C106 36 110 54 102 68 C94 60 88 60 84 60Z"/></g>` : '';
    const laurel = t >= 3 ? `<g fill="none" stroke="${hi}" stroke-width="1.6" opacity=".75"><path d="M22 80 C10 62 12 40 24 28"/><path d="M78 80 C90 62 88 40 76 28"/></g>` : '';
    const crown = t >= 6 ? `<path d="M36 12 L42 2 L50 10 L58 2 L64 12 Z" fill="${hi}" stroke="${lo}" stroke-width="1"/>` : '';
    const rays = t === 7 ? `<g stroke="${hi}" stroke-width="1.6" opacity=".6">${Array.from({ length: 12 }, (_, i) => { const a = i * Math.PI / 6; return `<path d="M${(50 + 50 * Math.cos(a)).toFixed(1)} ${(52 + 50 * Math.sin(a)).toFixed(1)}L${(50 + 58 * Math.cos(a)).toFixed(1)} ${(52 + 58 * Math.sin(a)).toFixed(1)}"/>`; }).join('')}</g>` : '';
    const np = Math.max(0, Math.min(3, (sub | 0) + 1)), pips = Array.from({ length: np }, (_, i) => { const px = 50 + (i - (np - 1) / 2) * 11; return `<path d="M${px.toFixed(1)} 86 l2.2 4.6 5 .6 -3.7 3.4 1 5 -4.5 -2.5 -4.5 2.5 1 -5 -3.7 -3.4 5 -.6z" fill="${hi}" stroke="${lo}" stroke-width=".5" transform="translate(-2.5 0)"/>`; }).join('');
    const ch = esc([...String(label)][0] || '');
    return `<svg class="bb bb-t${t}" width="${size}" height="${Math.round(size * 1.1)}" viewBox="-12 -4 124 118" role="img" aria-label="境界徽章 ${esc(label)}">
      <defs><linearGradient id="${id}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${hi}"/><stop offset="1" stop-color="${lo}"/></linearGradient>
        <linearGradient id="${id}s" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>
      ${rays}${wings}${laurel}
      <g fill="url(#${id}g)" stroke="${lo}" stroke-width="2.4" stroke-linejoin="round">${shape}</g>
      <g fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="1.2" transform="translate(50 52) scale(.86) translate(-50 -52)">${shape}</g>
      <g fill="url(#${id}s)" opacity=".7">${shape}</g>${crown}
      <text x="50" y="${t === 0 ? 67 : 69}" text-anchor="middle" font-size="44" font-weight="700" class="bb-ch" fill="${lo}" stroke="#fff" stroke-opacity=".5" stroke-width=".8" paint-order="stroke">${ch}</text>${pips ? `<g transform="translate(0 -14)">${pips}</g>` : ''}</svg>`;
  }
  const inline = (R) => R ? `<span class="bb-inline">${svg({ tier: R.big ?? tierOf(R.big_name || R.name), sub: R.sub ?? 0, label: R.big_name || R.name || '', size: 52 })}</span>` : '';
  window.BeautyBadge = { svg, inline, tierOf };
})();
