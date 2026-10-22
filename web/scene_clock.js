/* 全场景共用时钟：主页/子页读取同一scene-time偏好，独立于阅读主题。
   保留auto/day/night/theme旧键；每分钟及返回前台更新，只有时段实际变化才通知。
   无服务器请求，不写学习存档。scene_fx复用phase/resolve，BeautyArt监听根属性。 */
(() => {
  'use strict';
  const root=document.documentElement;
  const mode=()=>{try{return localStorage.getItem('scene-time')||'auto';}catch(_){return 'auto';}};
  function phase(d=new Date()){const h=d.getHours()+d.getMinutes()/60;return h>=5.5&&h<8?'dawn':h>=8&&h<17?'day':h>=17&&h<19.5?'dusk':'night';}
  function resolve(){const m=mode(),ph=m==='theme'?(root.dataset.theme==='dark'?'night':'day'):m==='day'||m==='night'?m:phase();return {ph,img:ph==='night'?'night':'day'};}
  function apply(){const r=resolve();if(root.dataset.sceneTime!==r.img)root.dataset.sceneTime=r.img;if(root.dataset.scenePhase!==r.ph)root.dataset.scenePhase=r.ph;return r;}
  function settingsHtml(){return `<label>场景时间<select data-scene-time>${[['auto','自动（跟随时钟）'],['day','一直白天'],['night','一直夜晚'],['theme','跟随亮暗主题']].map(([v,t])=>`<option value="${v}" ${mode()===v?'selected':''}>${t}</option>`).join('')}</select></label>`;}
  document.addEventListener('change',e=>{const t=e.target.closest?.('select[data-scene-time]');if(!t)return;try{localStorage.setItem('scene-time',t.value);}catch(_){}apply();});
  new MutationObserver(()=>{if(mode()==='theme')apply();}).observe(root,{attributes:true,attributeFilter:['data-theme']});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)apply();});
  window.addEventListener('pageshow',apply);window.addEventListener('focus',apply);window.addEventListener('storage',e=>{if(e.key==='scene-time'||e.key===null)apply();});
  window.SCENE_CLOCK={phase,resolve,apply,settingsHtml};apply();setInterval(apply,60000);
})();
