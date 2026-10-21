/* 场景首页与地点排布：app.js提供config={id,title,image,places:[{id,label,x,y,view}]}和go回调。
   localStorage scene-layout:<id>={desktop:{地点:{x,y}},narrow:{地点:{x,y}},names:{地点:名称}}；位置以地图可用区百分比表示，名称横竖屏共用。
   只记本机外观，设置中拖动/方向键/坐标微调后显式保存，不写训练数据或改变奖励。 */
(() => {
  'use strict';
  let config, navigate, edit, drag, previewResize;
  const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clamp = n => Math.round(Math.max(5,Math.min(95,n))*10)/10;
  function normalize(source, places) {
    const result={desktop:{},narrow:{},names:{}};
    places.forEach(p=>{const value=source?.names?.[p.id];if(typeof value==='string'){const name=value.replace(/[\x00-\x1f\x7f]/g,'').trim().slice(0,24);if(name)result.names[p.id]=name;}});
    for(const profile of ['desktop','narrow'])places.forEach((p,i)=>{
      const fallback=profile==='desktop'?{x:p.x,y:p.y}:(typeof p.nx==='number'?{x:p.nx,y:p.ny}:{x:28+(i%2)*44,y:18+Math.floor(i/2)*(64/Math.max(1,Math.ceil(places.length/2)-1))});   // 竖屏只显示全景中间一条：地点可自带nx/ny竖屏默认位置
      // 内置地点可用0%靠近地图上缘；保存其他地点时也应保留这些未动过的默认值。
      const v=source?.[profile]?.[p.id];
      result[profile][p.id]={x:typeof v?.x==='number'&&Number.isFinite(v.x)?(v.x===fallback.x?fallback.x:clamp(v.x)):fallback.x,
                            y:typeof v?.y==='number'&&Number.isFinite(v.y)?(v.y===fallback.y?fallback.y:clamp(v.y)):fallback.y};
    });return result;
  }
  // 名牌竖排：每个字一行（不用writing-mode，各平台字体都稳）；名字太长（>8字）或含英文数字时仍横排
  const signHtml=n=>{const cs=[...n];return cs.length>5||/[\x00-\x7f]/.test(n)?`<b class="ds-sign">${esc(n)}</b>`:`<b class="ds-sign portal-sign-v">${cs.map(c=>`<i>${esc(c)}</i>`).join('')}</b>`;};
  const PLACE_ICON = {train:'🗻','peak-chang':'🌿','peak-yan':'📖','peak-li':'🧠','peak-shu':'🎲','peak-zi':'🌙',skeleton:'📚',bank:'🗼',contest:'⚔',dwelling:'🏠',notes:'📝',tianji:'🔮',journal:'📜',log:'📊'};   // 地点牌上的小图标（emoji会被beauty_icons换成统一线条图标）
  const placeName = (p, layout=load()) => layout.names[p.id] || p.label;
  function title(view) {return view==='home'?config?.title:config?.viewTitles?.[view]||config?.places.find(p=>p.view===view)&&placeName(config.places.find(p=>p.view===view));}
  const layoutKey = () => 'scene-layout:' + config.id + ':saved'; // 稳定键不随版本/美术文件名变动
  function localLayout(){
    for(const key of [...new Set([layoutKey(),'scene-layout:'+(config.layoutId||config.id),'scene-layout:'+config.id])]){
      try{const raw=localStorage.getItem(key);if(raw&&raw.length<20000){const value=JSON.parse(raw);if(value&&typeof value==='object'&&(value.desktop||value.narrow)){if(key!==layoutKey())localStorage.setItem(layoutKey(),raw);return value;}}}catch(_){}
    }
    return null;
  }
  function load() {return normalize(localLayout()||config.savedLayout,config.places);}
  async function backup(layout,seed=false){
    if(typeof fetch!=='function')return false;
    const map=config.id,c=config;
    try{const r=await fetch('/api/scene-layout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({map,layout,seed})}).then(r=>r.json());if(r.error)throw Error(r.error);if(config===c)config.savedLayout=r.layout;return true;}catch(_){return false;}
  }
  const profile = () => window.innerWidth/window.innerHeight>=1.15?'desktop':'narrow';
  function configure(c, go) {if(config?.id!==c.id){edit=null;cancelDrag();}config=c;navigate=go;const local=localLayout();if(local&&!c.savedLayout)backup(normalize(local,c.places),true);}
  function motionOff() {
    let saved;try{saved=localStorage.getItem('xrpg-motion');}catch(e){}
    return saved==='reduced'||!!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches||!!window.navigator?.connection?.saveData;
  }
  function syncMotion() {
    if(document.documentElement.dataset)document.documentElement.dataset.motion=motionOff()?'reduced':document.hidden?'paused':'full';
  }
  // 3.4白天/夜晚两张全景：亮色主题显示白天、暗色主题显示夜晚（纯CSS切换，不显示的那张懒加载）；单图场景保持原样。
  function landscapeHtml() {
    const alt = esc(config.title) + '全景';
    const fill=`<div class="portal-landscape-fill" aria-hidden="true" style="--portal-fill-day:url(&quot;${esc(config.images?.day||config.image)}&quot;);--portal-fill-night:url(&quot;${esc(config.images?.night||config.image)}&quot;)"></div>`;
    if (!config.images) return fill+`<img class="portal-landscape" src="${esc(config.image)}" alt="${alt}">`;
    return fill+`<img class="portal-landscape portal-day" src="${esc(config.images.day)}" alt="${alt}"><img class="portal-landscape portal-night" src="${esc(config.images.night)}" alt="" aria-hidden="true" loading="lazy">`;
  }
  function geometry(device) {
    const current=device===profile(),width=current?window.innerWidth:device==='desktop'?1280:800,height=current?window.innerHeight:device==='desktop'?860:1280;
    const hud=typeof getComputedStyle==='function'?parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--study-hud-height'))||142:142;
    return {width,height,top:hud+44,span:Math.max(1,height-hud-100)};
  }
  function stageHtml(layout, device, editing=false) {
    const geo=geometry(device);
    const stage=`<div class="portal-stage ${editing?'portal-stage-editor':''}" data-profile="${device}" data-portal-stage="${editing?'edit':'home'}" data-map-height="${geo.height}" data-map-top="${geo.top}" data-map-span="${geo.span}" data-world-stage="${editing?0:config.progress?.stage||0}">${editing?'':'<div class="portal-atmosphere" aria-hidden="true"><i class="portal-cloud"></i><i class="portal-glow"></i></div>'}${landscapeHtml()}${config.places.map(p=>{
      const pos=layout[device][p.id];return `<button class="portal-place" style="--px:${pos.x}%;--py:${pos.y}%;--portal-y:${pos.y/100}" ${editing?`data-portal-point="${esc(p.id)}" aria-pressed="${p.id===edit.selected}"`:`data-portal-go="${esc(p.id)}"`}><span class="portal-ic" aria-hidden="true">${PLACE_ICON[p.id]||'◆'}</span>${signHtml(placeName(p,layout))}</button>`;
    }).join('')}</div>`;
    return editing?`<div class="portal-preview-frame" style="aspect-ratio:${geo.width}/${geo.height};--preview-width:${geo.width}px;--preview-height:${geo.height}px">${stage}</div>`:stage;
  }
  function homeHtml() {return `<section class="portal-world portal-${esc(config.id)}" aria-label="${esc(config.title)}">${stageHtml(load(),profile())}</section>`;}
  function motionHtml() {return `<button class="portal-motion" data-portal-motion aria-pressed="${motionOff()}">减少动画：${motionOff()?'已开启':'未开启'}</button>`;}
  function settingsHtml() {
    edit={layout:load(),device:profile(),selected:config.places[0].id};
    return `<section class="card portal-settings">${motionHtml()}${window.SCENE_FX?.settingsHtml()||window.SCENE_CLOCK?.settingsHtml()||''}<h3>地点排布 <small>预览与主页使用同一坐标，拖动后保存</small></h3><div class="portal-editor-tools"><label>布局<select data-portal-device><option value="desktop" ${edit.device==='desktop'?'selected':''}>电脑 / 横屏</option><option value="narrow" ${edit.device==='narrow'?'selected':''}>平板 / 竖屏</option></select></label><label>地点<select data-portal-selected>${config.places.map(p=>`<option value="${esc(p.id)}">${esc(placeName(p,edit.layout))}</option>`).join('')}</select></label><label>地点名称<input data-portal-name maxlength="24" placeholder="留空恢复默认名称"></label><label>横向位置 %<input data-portal-x type="number" min="5" max="95" step="0.1"></label><label>纵向位置 %<input data-portal-y type="number" min="5" max="95" step="0.1"></label></div><div data-portal-preview>${stageHtml(edit.layout,edit.device,true)}</div><p class="small muted">鼠标或笔拖动地点；选中后也可用方向键移动（Shift加快）。两套位置独立保存，名称在横竖屏共用；每个地图各自保存。名称最多24字，留空使用默认名，只影响本机界面。</p><div class="row"><button data-portal-save class="primary">保存排布与名称</button><button data-portal-reset>恢复当前布局默认位置</button><button data-portal-name-reset>恢复所选地点默认名</button><button data-portal-reload>撤销未保存调整</button><span data-portal-status role="status"></span></div></section>`;
  }
  function status(s) {const el=document.querySelector('[data-portal-status]');if(el)el.textContent=s;}
  function syncEditor() {
    if(!edit)return;
    const xy=edit.layout[edit.device][edit.selected];
    const x=document.querySelector('[data-portal-x]'),y=document.querySelector('[data-portal-y]'),select=document.querySelector('[data-portal-selected]');
    if(x)x.value=xy.x;if(y)y.value=xy.y;if(select)select.value=edit.selected;
    const name=document.querySelector('[data-portal-name]');if(name&&document.activeElement!==name)name.value=edit.layout.names[edit.selected]||'';
    document.querySelectorAll('[data-portal-selected] option').forEach(o=>{const p=config.places.find(p=>p.id===o.value);if(p)o.textContent=placeName(p,edit.layout);});
    document.querySelectorAll('[data-portal-point]').forEach(b=>{const p=edit.layout[edit.device][b.dataset.portalPoint];b.style.setProperty('--px',p.x+'%');b.style.setProperty('--py',p.y+'%');b.style.setProperty('--portal-y',p.y/100);b.setAttribute('aria-pressed',String(b.dataset.portalPoint===edit.selected));const label=b.querySelector('b'),nm=placeName(config.places.find(p=>p.id===b.dataset.portalPoint),edit.layout);if(label&&label.textContent!==nm)label.outerHTML=signHtml(nm);});
  }
  function sizePreview() {
    previewResize?.disconnect();const frame=document.querySelector('.portal-preview-frame');if(!frame)return;
    const update=()=>{if(!frame.isConnected)return previewResize?.disconnect();const stage=frame.querySelector('.portal-stage'),width=parseFloat(frame.style.getPropertyValue('--preview-width'));stage.style.setProperty('--preview-scale',frame.clientWidth/width);};
    previewResize=new ResizeObserver(update);previewResize.observe(frame);update();
  }
  function redrawEditor() {const slot=document.querySelector('[data-portal-preview]');if(slot)slot.innerHTML=stageHtml(edit.layout,edit.device,true);syncEditor();sizePreview();}
  function cancelDrag() {if(drag){if(edit)edit.layout[edit.device][drag.id]=drag.before;drag=null;syncEditor();}}
  function mount(view) {
    syncMotion();cancelDrag();document.body.classList.toggle('portal-home',view==='home');
    const bar=document.querySelector('.topbar'),r=bar?.getBoundingClientRect();
    const sidebar=r&&r.height>window.innerHeight*.7&&r.width<300;
    document.documentElement.style.setProperty('--portal-top',sidebar?'0px':Math.max(0,r?.bottom||0)+'px');
    if(view==='settings'){syncEditor();sizePreview();}else previewResize?.disconnect();
  }
  document.addEventListener('click',e=>{
    if(e.target.closest('[data-portal-motion]')){
      const off=!motionOff();try{localStorage.setItem('xrpg-motion',off?'reduced':'full');}catch(err){}
      syncMotion();const b=e.target.closest('[data-portal-motion]');b.setAttribute('aria-pressed',String(motionOff()));b.textContent='减少动画：'+(motionOff()?'已开启':'未开启');return;
    }
    const place=e.target.closest('[data-portal-go]');if(place&&config){const p=config.places.find(p=>p.id===place.dataset.portalGo);if(p)navigate(p);return;}
    if(!edit||!document.querySelector('[data-portal-preview]'))return;
    const point=e.target.closest('[data-portal-point]');if(point){edit.selected=point.dataset.portalPoint;syncEditor();return;}
    if(e.target.closest('[data-portal-save]')){try{const snapshot=JSON.parse(JSON.stringify(edit.layout));localStorage.setItem(layoutKey(),JSON.stringify(snapshot));status('排布与名称已保存');backup(snapshot).then(ok=>{if(document.querySelector('[data-portal-status]'))status(ok?'排布已保存，并作为更新后的默认位置':'本机排布已保存；存档备份暂未完成，可稍后再保存');});window.STUDY_HUD?.refresh();}catch(err){status('保存失败，请检查浏览器存储权限；调整仍保留在当前页面。');}}
    if(e.target.closest('[data-portal-reset]')){cancelDrag();edit.layout[edit.device]=normalize(null,config.places)[edit.device];redrawEditor();status('已恢复默认位置，点击保存生效');}
    if(e.target.closest('[data-portal-name-reset]')){delete edit.layout.names[edit.selected];syncEditor();status('默认名已恢复，点击保存生效');}
    if(e.target.closest('[data-portal-reload]')){cancelDrag();edit.layout=load();redrawEditor();status('已撤销未保存调整');}
  });
  document.addEventListener('input',e=>{
    if(!edit||!e.target.matches('[data-portal-name]'))return;
    const name=e.target.value.replace(/[\x00-\x1f\x7f]/g,'').trim().slice(0,24);
    if(name)edit.layout.names[edit.selected]=name;else delete edit.layout.names[edit.selected];
    syncEditor();status('尚未保存');
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
    const stage=point.closest('[data-portal-stage]'),r=point.getBoundingClientRect?.();
    drag={id:edit.selected,pointer:e.pointerId,before:{...edit.layout[edit.device][edit.selected]},rect:stage.getBoundingClientRect(),map:stage.dataset?(()=>{const g=geometry(edit.device);return {mapHeight:g.height,mapTop:g.top,mapSpan:g.span};})():null,grab:r?{x:e.clientX-(r.left+r.width/2),y:e.clientY-(r.top+r.height/2)}:{x:0,y:0}};point.setPointerCapture(e.pointerId);e.preventDefault();
  });
  document.addEventListener('pointermove',e=>{
    if(!drag||e.pointerId!==drag.pointer)return;
    const r=drag.rect;if(r.width>0&&r.height>0){const x=(e.clientX-drag.grab.x-r.left)/r.width,y=(e.clientY-drag.grab.y-r.top)/r.height,map=drag.map;edit.layout[edit.device][drag.id]={x:clamp(x*100),y:clamp(map?(y*Number(map.mapHeight)-Number(map.mapTop))/Number(map.mapSpan)*100:y*100)};syncEditor();status('尚未保存');}
  });
  document.addEventListener('pointerup',e=>{if(drag&&e.pointerId===drag.pointer)drag=null;});
  document.addEventListener('pointercancel',cancelDrag);
  document.addEventListener('keydown',e=>{
    const point=e.target.closest('[data-portal-point]');if(!point||!edit)return;
    const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];if(!delta)return;
    e.preventDefault();edit.selected=point.dataset.portalPoint;const p=edit.layout[edit.device][edit.selected],step=e.shiftKey?5:1;p.x=clamp(p.x+delta[0]*step);p.y=clamp(p.y+delta[1]*step);syncEditor();status('尚未保存');
  });
  let viewportKey='';
  window.addEventListener('resize',()=>{
    const key=innerWidth+'x'+innerHeight;if(key===viewportKey)return;viewportKey=key;cancelDrag();
    if(document.body.classList.contains('portal-home')){
      const stage=document.querySelector('[data-portal-stage="home"]');if(!stage)return;
      const device=profile(),geo=geometry(device),layout=load();stage.dataset.profile=device;
      stage.dataset.mapHeight=geo.height;stage.dataset.mapTop=geo.top;stage.dataset.mapSpan=geo.span;
      stage.querySelectorAll('[data-portal-go]').forEach(b=>{const p=layout[device][b.dataset.portalGo];b.style.setProperty('--px',p.x+'%');b.style.setProperty('--py',p.y+'%');b.style.setProperty('--portal-y',p.y/100);});mount('home');
    }else if(edit&&document.querySelector('[data-portal-preview]'))redrawEditor();
  });
  document.addEventListener('visibilitychange',syncMotion);
  window.SCENE_PORTAL={configure,homeHtml,settingsHtml,mount,normalize,profile,title};
})();
