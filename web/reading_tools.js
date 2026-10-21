/* 答题/复盘页字号按钮：复用本机既有chatLayout偏好，默认与旧版相同，不缩放页面。fixed_layout在页头整理后调用。 */
(() => {
 'use strict';
 const lens=sign=>`<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6.5"/><path d="m15 15 6 6M6.5 10h7${sign==='+'?'M10 6.5v7':''}"/></svg>`;
 function mount(root){
  if(!root?.querySelector('.chat'))return;
  const head=root.querySelector('#studyHud .subpage-tools')||root.querySelector('.chat>.review-head');if(!head)return;
  const existing=root.querySelector('.reading-size-tools');if(existing){if(existing.parentElement!==head)head.prepend(existing);return;}
  const bar=document.createElement('span');bar.className='reading-size-tools';bar.setAttribute('role','group');bar.setAttribute('aria-label','答题字号');
  bar.innerHTML=`<button type="button" data-reading-size="-10" aria-label="缩小字号" title="缩小字号">${lens('-')}</button><output aria-live="polite"></output><button type="button" data-reading-size="10" aria-label="放大字号" title="放大字号">${lens('+')}</button>`;
  head.prepend(bar);
  const update=()=>{const fs=chatPrefs().fs;bar.querySelector('output').textContent=fs+'%';bar.querySelector('[data-reading-size="-10"]').disabled=fs<=80;bar.querySelector('[data-reading-size="10"]').disabled=fs>=160;};
  bar.querySelectorAll('button').forEach(button=>button.onclick=()=>{const prefs=chatPrefs();prefs.fs=Math.max(80,Math.min(160,prefs.fs+Number(button.dataset.readingSize)));try{localStorage.setItem('chatLayout',JSON.stringify({...prefs,schema:2}));}catch(_){}applyChatLayout(prefs);update();window.dispatchEvent(new Event('resize'));});
  update();
 }
 window.READING_TOOLS={mount};
})();
