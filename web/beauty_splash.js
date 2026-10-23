/* 3.2.2 启动画面：页面一打开先显示品牌与流动条，首屏内容渲染好（#view 有内容）后淡出；最多停 6 秒，保证不挡住使用。 */
(() => {
  'use strict';
  const el = document.getElementById('splash'); if (!el) return;
  // 仅公考index声明新图；法考共用脚本但保留自己的品牌与美术。
  const arts=(el.dataset.loadingArt||'').split(',').filter(Boolean);
  if(arts.length){
    let i=0;try{i=Number(sessionStorage.getItem('loading-art-next')||0)%arts.length;sessionStorage.setItem('loading-art-next',String(i+1));}catch(_){}
    if(!Number.isInteger(i)||i<0)i=0;
    el.dataset.art=String(i);
    const art=new Image();art.className='splash-art';art.alt='';art.setAttribute('aria-hidden','true');
    art.onload=()=>el.classList.add('splash-art-ready');art.src=arts[i];el.prepend(art);
  }
  const t0 = Date.now(); let gone = false;
  const sub = el.querySelector('small'); if (sub && window.SUBJECT0) sub.textContent = window.SUBJECT0;
  function out() { if (gone) return; gone = true; observer?.disconnect();el.classList.add('splash-out'); setTimeout(() => el.remove(), 700); }
  function check() { const v = document.getElementById('view'); if (v && v.children.length) setTimeout(out, Math.max(0, 700 - (Date.now() - t0))); }
  const v = document.getElementById('view');
  const observer=v?new MutationObserver(check):null;
  if (v) observer.observe(v, { childList: true });
  setTimeout(out, 6000); check();
})();
