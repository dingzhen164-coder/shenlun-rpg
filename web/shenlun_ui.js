/* 申论2.8视觉层：统一导航线图标和页面台头。只装饰已知程序容器，不改用户正文。
 * app.js在换科目/渲染后调用；状态、题库、计时与笔迹仍由原模块管理。 */
(() => {
  const pages={home:['办公室','查看今日安排，积累学时与政绩。'],train:['办理中心','温习知识、领取训练，完成作答与复盘。'],notes:['公务手账','记录阅读批注，整理学习与办理笔记。'],contest:['年度考核','以考核检验积累，以复盘完善表达。'],tianji:['时政简报','阅读政策与实践，积累申论素材。'],skeleton:['档案室','统一管理知识便笺、真题卷宗与采分点。'],log:['政绩录','回顾学习履历，查看作答与成长记录。'],settings:['系统设置','管理备考日程、模型连接与本机外观。']};
  const paths={home:'M3 10 12 3l9 7M5 10v11h14V10M9 21v-7h6v7',train:'M9 3H4v18h16V8M9 3v5h11M9 3h6l5 5M8 12h8M8 16h6',notes:'M4 3h14v18H4zM8 3v18M11 8h4M11 12h4M11 16h3',contest:'M7 3h10v6a5 5 0 0 1-10 0V3M7 5H3v3a4 4 0 0 0 4 4M17 5h4v3a4 4 0 0 1-4 4M12 14v5M8 21h8',tianji:'M3 4h18v16H3zM7 8h10M7 12h6M7 16h10',skeleton:'M3 7h18v14H3zM3 7V3h7l3 4M7 11h10M7 15h6',log:'M5 21V12M12 21V7M19 21V3M3 21h18',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2'};
  function icon(view){return `<svg class="sl-ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[view]||paths.train}"/></svg>`;}
  function chrome(){
    if(!document.body.classList.contains('guantu'))return;
    document.querySelectorAll('#nav a').forEach(a=>{const title=pages[a.dataset.view]?.[0];if(title){a.innerHTML=icon(a.dataset.view)+`<span>${title}</span>`;a.setAttribute('aria-label',title);}});
  }
  function heading(view){
    const [title,description]=pages[view]||pages.home;
    return `<section class="sl-ui-masthead ${view==='skeleton'?'sl-ui-archive':''}"><div class="sl-ui-heading-copy"><div class="sl-ui-eyebrow">公考模拟器 <span>/</span> 申论工作台</div><div class="sl-ui-title-row"><h1>${title}</h1><div class="sl-ui-section-tabs"></div></div><p>${description}</p></div><div class="sl-ui-heading-seal" aria-hidden="true">申<br>论</div><div class="sl-ui-heading-rule" aria-hidden="true"></div></section>`;
  }
  function mount(view){
    const root=document.getElementById('view');
    if(!document.body.classList.contains('guantu')||document.documentElement.classList.contains('in-sl-exam')||document.documentElement.classList.contains('in-chat'))return;
    if(!root.querySelector('.sl-ui-masthead'))root.insertAdjacentHTML('afterbegin',heading(view));
    // 移动原入口节点，保留原事件与状态；手账重绘左栏时重新接入台头。
    const slot=root.querySelector('.sl-ui-section-tabs');
    const selector={train:'.hall-gates',notes:'.nt-side .nt-tabs',skeleton:'.lib-head .lib-tabs'}[view];
    const tabs=selector&&root.querySelector(selector);
    if(tabs){
      const fold=tabs.querySelector('#ntSideMin');if(fold)tabs.closest('.nt-side').prepend(fold);
      slot.replaceChildren(tabs);
      tabs.setAttribute('aria-label',pages[view][0]+'分类');
      tabs.querySelectorAll('[data-hall]').forEach(b=>{b.setAttribute('role','button');b.tabIndex=0;b.setAttribute('aria-pressed',String(b.classList.contains('on')));b.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();b.click();}};});
      tabs.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.classList.contains('on'))));
      const head=root.querySelector('.lib-head');if(head&&!head.querySelector('.lib-tabs'))head.remove();
    }
  }
  window.SL_UI={chrome,heading,mount,icon};
})();
