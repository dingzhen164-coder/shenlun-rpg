/* 3.0.5自适应角色/备考信息：dashboard提供真实数据，scene_portal提供本机地点名。
   不计算/发放奖励；展示当前境界积累/当前境界总需求，数值刷新与原心跳一致。 */
(() => {
  'use strict';
  let lastPaint='',data, current='home',paused=false,drawNode=document.getElementById('drawBtn'),pillNode=document.getElementById('todayPill');
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>Number.isFinite(Number(v))?Math.max(0,Number(v)):0;
  const amount=v=>Math.round(num(v)*10)/10;
  function meter(label,value,target,color) {
    const max=num(target),val=num(value),percent=max?Math.min(100,val/max*100):0;
    return `<div class="study-hud-meter ${color}" role="progressbar" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="${max||1}" aria-valuenow="${max?Math.min(max,val):0}" aria-valuetext="${amount(val)} / ${amount(max)}"><i style="width:${percent}%"></i><span>${esc(label)} ${amount(val)} / ${amount(max)}</span></div>`;
  }
  function avatar(p) {
    if(p.avatar)return `<img src="${esc(p.avatar)}" alt="${esc(p.id||p.call||'主角')}的头像">`;
    return `<svg viewBox="0 0 80 80" role="img" aria-label="默认主角头像"><rect width="80" height="80" fill="#294f52"/><path d="M6 80q3-27 34-27t34 27" fill="#c59a54"/><path d="M26 49h28l-6 17H32z" fill="#efd0a6"/><ellipse cx="40" cy="33" rx="18" ry="22" fill="#f4d9b3"/><path d="M21 39Q10 4 41 4q30 0 18 38l-7-19-26 6z" fill="#382b36"/><path d="M29 35h7m9 0h7M35 47q5 3 10 0" fill="none" stroke="#65462e" stroke-width="2"/></svg>`;
  }
  // 原笔记按钮与计时节点原位搬移；重绘前停放，保留笔迹、事件和计时状态。
  function beforeRender(){
    lastPaint='';
    const tools=document.querySelector('.top-tools');
    for(const id of ['drawBtn','todayPill']){const node=document.getElementById(id)||(id==='drawBtn'?drawNode:pillNode);if(node&&tools)tools.append(node);}
    const root=document.getElementById('studyHud');root?.querySelector('.subpage-nav')?.replaceChildren();if(root?.classList.contains('subpage-heading'))document.body.insertBefore(root,document.getElementById('banner'));
  }
  const symbols={dwelling:'M3 19V10l9-7 9 7v9H3Zm6 0v-7h6v7',train:'m2 20 7-15 5 10 3-7 5 12H2Z',bank:'M6 21V4h12v17M4 21h16M9 8h6M9 12h6M9 16h6',skeleton:'M12 5C8 2 4 3 2 4v16c4-2 7-1 10 1 3-2 6-3 10-1V4c-3-1-7-2-10 1Zm0 0v16',tianji:'M12 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16ZM7 21h10M12 19v2M9 6l-2 3',contest:'m4 3 17 17M3 4l2 5 4-4-5-2Zm17-1L3 20m17-17-5 2 4 4 2-5',notes:'m4 20 3-8L19 2l3 3-10 12-8 3Zm3-8 5 5M4 20l6-6',log:'M6 3h12v18H6V3Zm3 5h6m-6 4h6m-6 4h4',settings:'M12 3v3m0 12v3M3 12h3m12 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8'};
  function compact(root,page,world,m,iconKey=current){
    const draw=document.getElementById('drawBtn')||drawNode,pill=document.getElementById('todayPill')||pillNode;drawNode=draw;pillNode=pill;
    const nav=root.querySelector('.subpage-nav')||document.createElement('div');nav.className='subpage-nav';
    root.classList.add('subpage-heading');root.setAttribute('aria-label','地点与今日学习');
    root.innerHTML=`<div class="subpage-place"><span class="subpage-seal"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${symbols[iconKey]||symbols.dwelling}"/></svg></span><div><small>${esc(world)}</small><h2>${esc(page)}</h2></div></div><div class="subpage-nav"></div><div class="subpage-tools"></div>`;
    root.querySelector('.subpage-nav').replaceWith(nav);
    const tools=root.querySelector('.subpage-tools');if(draw){draw.setAttribute('aria-label','打开笔记草稿');draw.title='笔记草稿：保存当前题目的笔迹';tools.append(draw);}
    if(pill){pill.innerHTML=`<svg class="study-candle" viewBox="0 0 24 32" aria-hidden="true"><path class="candle-flame" d="M12 1c-1 5-5 6-4 10 1 5 9 4 8-1-1-3-3-4-4-9Z"/><path class="candle-body" d="M8 14h8v13H8zM5 29h14M12 11v4"/></svg>${meter('今日（分钟）',m.today,m.goal,'time')}`;tools.append(pill);}
    document.getElementById('view')?.prepend(root);
    // 原藏经阁标题已有分类导航；地点统一由同一标题展示，不重复占位置。
    document.querySelectorAll('#view .lib-head h2').forEach(h=>h.hidden=true);
  }
  function mount(d,view) {
    if(d)data=d;if(view)current=view;if(!data||paused)return;
    let root=document.getElementById('studyHud');
    if(!root){root=document.createElement('aside');root.id='studyHud';root.className='study-hud';root.setAttribute('aria-label','角色与备考信息');document.body.insertBefore(root,document.getElementById('banner'));
      const measure=()=>{const box=root.getBoundingClientRect(),style=document.documentElement.style;style.setProperty('--study-workspace-height',Math.ceil(root.classList.contains('subpage-heading')?box.bottom:box.height)+'px');if(document.body.classList.contains('portal-home'))style.setProperty('--study-hud-height',Math.ceil(box.bottom+12)+'px');};
      const sync=()=>{const h=document.documentElement;h.classList.toggle('study-workspace',['in-chat','nt-full','yj-on','in-sl-exam','focus'].some(c=>h.classList.contains(c))||!!document.querySelector('.sl-writing.sl-card-expanded'));measure();};
      new ResizeObserver(measure).observe(root);
      new MutationObserver(sync).observe(document.documentElement,{attributes:true,attributeFilter:['class']});
      new MutationObserver(sync).observe(document.getElementById('view')||document.body,{subtree:true,attributes:true,attributeFilter:['class']});
      sync();}
    const p=data.persona||{},r=data.realm||{},m=data.minutes||{},s=data.study_status||{};
    const terms=data.theme?.terms||{},xp=terms.xp||'修为',realm=terms.realm||'境界';
    const context=window.STUDY_PAGE_CONTEXT?.();
    const page=(context&&window.SCENE_PORTAL?.title(context.view))||(current==='train'&&window.STUDY_REGIONS?.title())||window.SCENE_PORTAL?.title(current)||({settings:'设置',bank:'实战训练',train:'修炼',notes:'手记'}[current])||'当前板块';
    const world=window.SCENE_PORTAL?.title('home')||'主地图';
    const signature=JSON.stringify([current,page,world,p,r,m,s,data.xp]);
    if(lastPaint===signature&&(current==='home'||document.getElementById('view')?.contains(root)))return;
    lastPaint=signature;
    if(current!=='home'){compact(root,page,world,m,context?.view||current);return;}
    beforeRender();lastPaint=signature;root.classList.remove('subpage-heading');
    const started=s.day>0,remaining=s.remaining==null?NaN:Number(s.remaining);
    const overdue=Number.isFinite(remaining)&&remaining<0;
    const stat=(label,value,unit,full)=>`<div class="study-hud-stat" aria-label="${esc(full)}"><span>${esc(label)}</span><div><b>${esc(value)}</b>${unit?`<small>${esc(unit)}</small>`:''}</div></div>`;
    const stats=stat('学习第',started?amount(s.day):'待启程',started?'天':'',started?`学习第 ${s.day} 天`:'尚未开始')
      +stat(overdue?'考试已过':'距考试',Number.isFinite(remaining)?amount(Math.abs(remaining)):'待设置',Number.isFinite(remaining)?'天':'',Number.isFinite(remaining)?`${overdue?'考试已过':'距考试'} ${Math.abs(remaining)} 天`:'考试日期待设置')
      +stat('日均学习',amount(s.average_minutes),'分钟',`平均每日学习 ${amount(s.average_minutes)} 分钟`);
    const seal=`<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 2 29 16 16 30 3 16Z M16 6 25 16 16 26 7 16Z"/><path d="m10 21 6-12 6 12M8 21h16M16 9v12"/></svg>`;
    root.innerHTML=`<section class="study-hud-player"><div class="study-hud-avatar">${avatar(p)}</div><div class="study-hud-profile"><div class="study-hud-name"><strong>${esc(p.id||p.call||'主角')}</strong><span>${esc(realm)} · ${esc(r.name||'初入')}</span></div>${meter('今日学习（分钟）',m.today,m.goal,'time')}${r.need>0?meter('本境界'+xp,r.into,r.need,'xp'):`<div class="study-hud-cap">已达最高${esc(realm)} · 无下一境界目标</div>`}<small>${r.ready?'可突破至 '+esc(r.next):r.bottleneck?'突破试炼待完成':r.next?'下一'+esc(realm)+'：'+esc(r.next):'继续积累'}</small></div></section><section class="study-hud-world ds-plate"><div class="study-hud-stats">${stats}</div><div class="study-hud-location"><button type="button" data-hud-home aria-label="返回地图：${esc(world)}" title="返回地图">${seal}<span><strong>${esc(world)}</strong>${current==='home'?'':`<span class="study-hud-place"> / ${esc(page)}</span>`}</span></button>${current==='home'?'':`<button type="button" data-hud-settings class="study-hud-settings" aria-label="打开设置" title="打开设置"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 2 3 3-1 1 4 4 2-2 3 1 4-4 1-3 4-2-3-4 1-1-4-4-2 2-3-1-4 4-1Z"/><circle cx="12" cy="12" r="3"/></svg></button>`}</div></section>`;
    root.querySelector('img')?.addEventListener('error',e=>{e.target.parentElement.innerHTML=avatar({...p,avatar:''});},{once:true});
  }
  window.STUDY_HUD={mount,beforeRender,ensure:()=>{const root=document.getElementById('studyHud');if(!paused&&data&&(!root||(current!=='home'&&!document.getElementById('view')?.contains(root))))mount();},suspend:v=>paused=v,refresh:()=>mount()};
})();
