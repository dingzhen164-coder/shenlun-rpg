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
  // 三考期各用独立的镂空器物：星盘定向、卷轴积学、玉笔启新。
  function atlasIcon(index){
    const forms=[
      `<g class="wx-atlas-orbit"><circle cx="72" cy="65" r="42"/><ellipse cx="72" cy="65" rx="25" ry="48" transform="rotate(35 72 65)"/><path d="M23 65h98M72 15v100"/></g><path class="wx-atlas-solid" d="M46 91q15-6 26 1 12-7 26-1v25q-16-5-26 1-12-6-26-1Z"/><path d="M72 93v24M51 98l15 1m-15 7 15 1m12-8 14-1m-14 10 14-1"/><path class="wx-atlas-glint" d="m72 32 4 20 19 13-19 4-4 21-5-21-20-4 20-13Z"/>`,
      `<g class="wx-atlas-orbit"><path d="M29 29q40-15 84 0M23 109q51 18 98-2"/><circle cx="111" cy="29" r="3"/></g><path class="wx-atlas-solid" d="M38 36h65v70H38z"/><path d="M38 35q-11-10-13 0v69q0 10 13 2m65-70q12-9 13 1v67q-2 11-13 2M45 45h49M45 52h38M48 61v29m9-29v33m9-33v24m9-24v31m9-31v27m9-27v35"/><path class="wx-atlas-glint" d="m93 16 3 8 8 3-8 3-3 8-3-8-8-3 8-3Z"/>`,
      `<g class="wx-atlas-orbit"><ellipse cx="70" cy="74" rx="48" ry="35" transform="rotate(-30 70 74)"/><path d="M29 104q35 17 87-30"/></g><path class="wx-atlas-solid" d="m78 25 14 8-40 70-14 8 3-17Z"/><path d="m73 35 14 8M47 84l14 8m-21 6 11 6M38 111l-5 13M94 101q10-38 30-52-1 32-30 52m-1 3 23-31"/><path class="wx-atlas-glint" d="m109 18 2 7 8 2-8 3-2 7-3-7-7-3 7-2Z"/>`
    ];
    return `<svg class="wx-atlas-instrument" viewBox="0 0 144 144" aria-hidden="true"><g>${forms[index%3]}</g></svg>`;
  }
  window.WANXIANG_ART={icon,atlasIcon};
})();
