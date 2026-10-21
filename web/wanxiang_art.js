/* 万象峰六枚器物动态图标：统一插画底图+独立SVG流光/书页/珠算/星轨。
   study_regions.js调用icon(kind)；无需GIF解码或外部库，离开页面/减少动态时暂停。 */
(() => {
  'use strict';
  const motifs={
    politics:`<g class="wx-solar"><circle cx="60" cy="68" r="15"/><path d="M60 46v5m0 34v5M38 68h5m34 0h5M44 52l4 4m24 24 4 4M44 84l4-4m24-24 4-4"/></g><path class="wx-script" d="M61 91q25-15 54-8M65 103q23-11 48-6M71 116q18-8 39-5"/><path class="wx-ribbon" d="M141 26q-21 17 0 36t-5 35"/>`,
    common:`<g class="wx-armillary"><ellipse cx="98" cy="90" rx="72" ry="29" transform="rotate(-28 98 90)"/><ellipse cx="98" cy="90" rx="27" ry="75" transform="rotate(30 98 90)"/></g><path class="wx-stream" d="M105 69q-12 23-4 36t-13 30"/><g class="wx-starfield"><circle cx="42" cy="58" r="2"/><circle cx="151" cy="63" r="1.5"/><circle cx="134" cy="135" r="2"/></g>`,
    geo:`<g class="wx-latitudes"><ellipse cx="97" cy="90" rx="58" ry="20" transform="rotate(18 97 90)"/><ellipse cx="97" cy="90" rx="25" ry="61" transform="rotate(18 97 90)"/></g><path class="wx-current" d="M63 72q16-14 30 0t24 0M58 101q18-13 34 0t32 0"/><circle class="wx-cartography" cx="97" cy="90" r="68"/>`,
    history:`<g class="wx-page wx-page-one"><path d="M89 132Q74 103 46 101L44 79q28-2 45 36Z"/></g><g class="wx-page wx-page-two"><path d="M91 130q21-28 48-22l7-27q-30-5-54 29Z"/></g><path class="wx-script" d="M48 102q19-2 32 9M104 109q12-9 26-8"/><circle class="wx-book-light" cx="92" cy="114" r="28"/>`,
    economy:`<g class="wx-abacus"><circle class="wx-bead wx-bead-one" cx="59" cy="83" r="4"/><circle class="wx-bead wx-bead-two" cx="86" cy="72" r="4"/><circle class="wx-bead wx-bead-three" cx="113" cy="62" r="4"/></g><g class="wx-coins"><circle cx="117" cy="147" r="20"/><path d="m107 142 11-4 5 10-11 4Z"/></g><path class="wx-ledger" d="M43 126q42-9 79-41"/>`,
    science:`<g class="wx-gyroscope"><ellipse cx="96" cy="84" rx="66" ry="25" transform="rotate(-20 96 84)"/><ellipse cx="96" cy="84" rx="26" ry="64" transform="rotate(35 96 84)"/></g><circle class="wx-core" cx="96" cy="84" r="25"/><g class="wx-science-star"><circle cx="96" cy="21" r="3"/><circle cx="157" cy="105" r="2"/></g>`
  };
  function icon(kind){
    const key=Object.prototype.hasOwnProperty.call(motifs,kind)?kind:'common';
    return `<span class="wx-sigil wx-sigil--${key}" aria-hidden="true"><span class="wx-illumination"></span><span class="wx-object"></span><svg class="wx-instrument-motion" viewBox="0 0 192 192">${motifs[key]}</svg><span class="wx-dust wx-dust-one"></span><span class="wx-dust wx-dust-two"></span><span class="wx-dust wx-dust-three"></span></span>`;
  }
  document.addEventListener('visibilitychange',()=>document.documentElement.classList.toggle('wx-motion-paused',document.hidden));
  window.WANXIANG_ART={icon};
})();
