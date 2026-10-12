/* 场景首页与地点排布：app.js提供config={id,title,image,places:[{id,label,x,y,view}]}和go回调。
   localStorage scene-layout:<id>={desktop:{地点:{x,y}},narrow:{地点:{x,y}}}，百分比位置。
   只记本机外观，设置中拖动/方向键/坐标微调后显式保存，不写训练数据或改变奖励。 */
(() => {
  'use strict';
  let config, navigate, edit, drag;
  const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clamp = n => Math.round(Math.max(5,Math.min(95,n))*10)/10;
  function normalize(source, places) {
    const result={desktop:{},narrow:{}};
    for(const profile of ['desktop','narrow'])places.forEach((p,i)=>{
      const fallback=profile==='desktop'?{x:p.x,y:p.y}:{x:28+(i%2)*44,y:18+Math.floor(i/2)*(64/Math.max(1,Math.ceil(places.length/2)-1))};
      const v=source?.[profile]?.[p.id];
      result[profile][p.id]={x:typeof v?.x==='number'&&Number.isFinite(v.x)?clamp(v.x):fallback.x,
                            y:typeof v?.y==='number'&&Number.isFinite(v.y)?clamp(v.y):fallback.y};
    });return result;
  }
  function load() {let d;try{const raw=localStorage.getItem('scene-layout:'+config.id);if(raw&&raw.length<20000)d=JSON.parse(raw);}catch(e){}return normalize(d,config.places);}
  const profile = () => window.innerWidth/window.innerHeight>=1.15?'desktop':'narrow';
  function configure(c, go) {if(config?.id!==c.id){edit=null;cancelDrag();}config=c;navigate=go;}
  function stageHtml(layout, device, editing=false) {
    return `<div class="portal-stage ${editing?'portal-stage-editor':''}" data-profile="${device}" data-portal-stage="${editing?'edit':'home'}"><img class="portal-landscape" src="${esc(config.image)}" alt="${esc(config.title)}全景">${config.places.map(p=>{
      const pos=layout[device][p.id];return `<button class="portal-place" style="--px:${pos.x}%;--py:${pos.y}%" ${editing?`data-portal-point="${esc(p.id)}" aria-pressed="${p.id===edit.selected}"`:`data-portal-go="${esc(p.id)}"`}><span aria-hidden="true">◆</span><b>${esc(p.label)}</b></button>`;
    }).join('')}</div>`;
  }
  function homeHtml() {return `<section class="portal-world portal-${esc(config.id)}" aria-label="${esc(config.title)}"><div class="portal-caption"><small>${esc(config.subtitle||'')}</small><h1>${esc(config.title)}</h1><p>点击地点进入 · 位置可在设置中调整</p>${config.extraHtml?.()||''}</div>${stageHtml(load(),profile())}</section>`;}
  function settingsHtml() {
    edit={layout:load(),device:profile(),selected:config.places[0].id};
    return `<section class="card portal-settings"><h3>地点排布 <small>拖动地点，适配这台设备的界面</small></h3><div class="portal-editor-tools"><label>布局<select data-portal-device><option value="desktop" ${edit.device==='desktop'?'selected':''}>电脑 / 横屏</option><option value="narrow" ${edit.device==='narrow'?'selected':''}>平板 / 竖屏</option></select></label><label>地点<select data-portal-selected>${config.places.map(p=>`<option value="${esc(p.id)}">${esc(p.label)}</option>`).join('')}</select></label><label>横向位置 %<input data-portal-x type="number" min="5" max="95" step="0.1"></label><label>纵向位置 %<input data-portal-y type="number" min="5" max="95" step="0.1"></label></div><div data-portal-preview>${stageHtml(edit.layout,edit.device,true)}</div><p class="small muted">鼠标或笔拖动地点；选中后也可用方向键移动（Shift加快）。两套布局独立保存，只影响本机界面。</p><div class="row"><button data-portal-save class="primary">保存排布</button><button data-portal-reset>恢复当前布局默认位置</button><button data-portal-reload>撤销未保存调整</button><span data-portal-status role="status"></span></div></section>`;
  }
  function status(s) {const el=document.querySelector('[data-portal-status]');if(el)el.textContent=s;}
  function syncEditor() {
    if(!edit)return;
    const xy=edit.layout[edit.device][edit.selected];
    const x=document.querySelector('[data-portal-x]'),y=document.querySelector('[data-portal-y]'),select=document.querySelector('[data-portal-selected]');
    if(x)x.value=xy.x;if(y)y.value=xy.y;if(select)select.value=edit.selected;
    document.querySelectorAll('[data-portal-point]').forEach(b=>{const p=edit.layout[edit.device][b.dataset.portalPoint];b.style.setProperty('--px',p.x+'%');b.style.setProperty('--py',p.y+'%');b.setAttribute('aria-pressed',String(b.dataset.portalPoint===edit.selected));});
  }
  function redrawEditor() {const slot=document.querySelector('[data-portal-preview]');if(slot)slot.innerHTML=stageHtml(edit.layout,edit.device,true);syncEditor();}
  function cancelDrag() {if(drag){if(edit)edit.layout[edit.device][drag.id]=drag.before;drag=null;syncEditor();}}
  function mount(view) {
    cancelDrag();document.body.classList.toggle('portal-home',view==='home');
    const bar=document.querySelector('.topbar'),r=bar?.getBoundingClientRect();
    const sidebar=r&&r.height>window.innerHeight*.7&&r.width<300;
    document.documentElement.style.setProperty('--portal-top',sidebar?'0px':Math.max(0,r?.bottom||0)+'px');
    if(view==='settings')syncEditor();
  }
  document.addEventListener('click',e=>{
    const place=e.target.closest('[data-portal-go]');if(place&&config){const p=config.places.find(p=>p.id===place.dataset.portalGo);if(p)navigate(p);return;}
    if(!edit||!document.querySelector('[data-portal-preview]'))return;
    const point=e.target.closest('[data-portal-point]');if(point){edit.selected=point.dataset.portalPoint;syncEditor();return;}
    if(e.target.closest('[data-portal-save]')){try{localStorage.setItem('scene-layout:'+config.id,JSON.stringify(edit.layout));status('排布已保存');}catch(err){status('保存失败，请检查浏览器存储权限；调整仍保留在当前页面。');}}
    if(e.target.closest('[data-portal-reset]')){cancelDrag();edit.layout[edit.device]=normalize(null,config.places)[edit.device];redrawEditor();status('已恢复默认位置，点击保存生效');}
    if(e.target.closest('[data-portal-reload]')){cancelDrag();edit.layout=load();redrawEditor();status('已撤销未保存调整');}
  });
  document.addEventListener('change',e=>{
    if(!edit)return;
    if(e.target.matches('[data-portal-device]')){cancelDrag();edit.device=e.target.value==='narrow'?'narrow':'desktop';redrawEditor();}
    if(e.target.matches('[data-portal-selected]')){edit.selected=e.target.value;syncEditor();}
    if(e.target.matches('[data-portal-x],[data-portal-y]')){const n=e.target.valueAsNumber;if(Number.isFinite(n)){edit.layout[edit.device][edit.selected][e.target.matches('[data-portal-x]')?'x':'y']=clamp(n);syncEditor();status('尚未保存');}}
  });
  document.addEventListener('pointerdown',e=>{
    const point=e.target.closest('[data-portal-point]');if(!point||!edit||e.button!==0)return;
    edit.selected=point.dataset.portalPoint;syncEditor();
    drag={id:edit.selected,pointer:e.pointerId,before:{...edit.layout[edit.device][edit.selected]},rect:point.closest('[data-portal-stage]').getBoundingClientRect()};point.setPointerCapture(e.pointerId);e.preventDefault();
  });
  document.addEventListener('pointermove',e=>{
    if(!drag||e.pointerId!==drag.pointer)return;
    const r=drag.rect;if(r.width>0&&r.height>0){edit.layout[edit.device][drag.id]={x:clamp((e.clientX-r.left)/r.width*100),y:clamp((e.clientY-r.top)/r.height*100)};syncEditor();status('尚未保存');}
  });
  document.addEventListener('pointerup',e=>{if(drag&&e.pointerId===drag.pointer)drag=null;});
  document.addEventListener('pointercancel',cancelDrag);
  document.addEventListener('keydown',e=>{
    const point=e.target.closest('[data-portal-point]');if(!point||!edit)return;
    const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];if(!delta)return;
    e.preventDefault();edit.selected=point.dataset.portalPoint;const p=edit.layout[edit.device][edit.selected],step=e.shiftKey?5:1;p.x=clamp(p.x+delta[0]*step);p.y=clamp(p.y+delta[1]*step);syncEditor();status('尚未保存');
  });
  window.addEventListener('resize',()=>{cancelDrag();if(document.body.classList.contains('portal-home')){const root=document.getElementById('view');if(root)root.innerHTML=homeHtml();mount('home');}});
  window.SCENE_PORTAL={configure,homeHtml,settingsHtml,mount,normalize,profile};
})();
