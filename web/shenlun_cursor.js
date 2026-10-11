/* 申论公文批示鼠标：钢笔指针、短墨迹、朱红「阅」章。app.js换科/设置时调用。
 * 仅本机localStorage保存开关，不写用户库；事件旁观，不拦截点击、触摸和手写。 */
(() => {
  const key='sl-office-cursor',fine=matchMedia('(any-pointer: fine)'),reduce=matchMedia('(prefers-reduced-motion: reduce)');
  let enabled=true,last=null,layer=null;
  try{enabled=localStorage.getItem(key)!=='0';}catch{}
  function clear(){last=null;if(layer)layer.replaceChildren();}
  function sync(){document.body.classList.toggle('sl-office-cursor',enabled&&fine.matches&&document.body.classList.contains('guantu'));clear();}
  function allowed(e){return e.pointerType==='mouse'&&document.body.classList.contains('sl-office-cursor')&&!reduce.matches&&!e.target.closest('input,textarea,select,[contenteditable],canvas,.nt-pages,.sl-material-sheet,.sl-writing-overlay');}
  function add(cls,x,y){
    if(!layer){layer=document.createElement('div');layer.className='sl-cursor-effects';layer.setAttribute('aria-hidden','true');document.body.append(layer);}
    while(layer.children.length>=20)layer.firstElementChild.remove();
    const n=document.createElement('span');n.className=cls;n.style.left=x+'px';n.style.top=y+'px';layer.append(n);setTimeout(()=>n.remove(),650);return n;
  }
  addEventListener('pointermove',e=>{
    if(!allowed(e)){last=null;return;}
    const now=performance.now(),p={x:e.clientX,y:e.clientY,t:now};
    if(last&&now-last.t<28)return;
    if(last){const dx=p.x-last.x,dy=p.y-last.y,d=Math.hypot(dx,dy);if(d>3&&d<90){const n=add('sl-cursor-ink',last.x,last.y);n.style.width=Math.min(d,24)+'px';n.style.transform='rotate('+Math.atan2(dy,dx)+'rad)';}}
    last=p;
  },{passive:true});
  addEventListener('pointerdown',e=>{last=null;if(!allowed(e)||e.button!==0||e.target.closest(':disabled,[aria-disabled="true"]'))return;add('sl-cursor-stamp',e.clientX,e.clientY).textContent='阅';},{passive:true});
  addEventListener('blur',clear);addEventListener('pagehide',clear);document.addEventListener('pointerleave',clear);
  fine.addEventListener?.('change',sync);reduce.addEventListener?.('change',clear);
  function settingsHtml(){return `<div class="card"><h3>公文批示 · 鼠标外观</h3><label class="row"><input type="checkbox" id="slCursorToggle" style="width:auto" ${enabled?'checked':''}>钢笔指针、墨迹与朱红阅章</label><p class="small muted">仅鼠标操作生效，手写、勾画和文字输入保持原样。减少动画模式只保留指针；开关仅记在本机。</p></div>`;}
  function bind(){const b=document.getElementById('slCursorToggle');if(b)b.onchange=()=>{enabled=b.checked;try{localStorage.setItem(key,enabled?'1':'0');}catch{}sync();};}
  window.SL_CURSOR={sync,settingsHtml,bind};
})();
