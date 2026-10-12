/* 3.0.3自适应角色/备考信息：dashboard提供真实数据，scene_portal提供本机地点名。
   不计算/发放奖励；只展示累计经验/下一境界总阈值，数值刷新与原心跳一致。 */
(() => {
  'use strict';
  let data, current='home';
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
  function mount(d,view) {
    if(d)data=d;if(view)current=view;if(!data)return;
    let root=document.getElementById('studyHud');
    if(!root){root=document.createElement('aside');root.id='studyHud';root.className='study-hud';root.setAttribute('aria-label','角色与备考信息');document.body.insertBefore(root,document.getElementById('banner'));
      const measure=()=>document.documentElement.style.setProperty('--study-workspace-height',Math.ceil(root.getBoundingClientRect().height)+'px');
      const sync=()=>{const h=document.documentElement;h.classList.toggle('study-workspace',['in-chat','nt-full','yj-on','in-sl-exam','focus'].some(c=>h.classList.contains(c))||!!document.querySelector('.sl-writing.sl-card-expanded'));measure();};
      new ResizeObserver(measure).observe(root);
      new MutationObserver(sync).observe(document.documentElement,{attributes:true,attributeFilter:['class']});
      new MutationObserver(sync).observe(document.getElementById('view'),{subtree:true,attributes:true,attributeFilter:['class']});
      sync();}
    const p=data.persona||{},r=data.realm||{},m=data.minutes||{},s=data.study_status||{};
    const terms=data.theme?.terms||{},xp=terms.xp||'修为',realm=terms.realm||'境界';
    const page=(current==='train'&&window.STUDY_REGIONS?.title())||window.SCENE_PORTAL?.title(current)||({settings:'设置',bank:'实战训练',train:'修炼',notes:'手记'}[current])||'当前板块';
    const world=window.SCENE_PORTAL?.title('home')||'主地图';
    const day=s.day>0?`学习第 ${s.day} 天`:'尚未开始';
    const remaining=Number(s.remaining);
    const deadline=Number.isFinite(remaining)?remaining>=0?`距考试 ${remaining} 天`:`考试已过 ${-remaining} 天`:'考试日期待设置';
    root.innerHTML=`<section class="study-hud-player"><div class="study-hud-avatar">${avatar(p)}</div><div class="study-hud-profile"><div class="study-hud-name"><strong>${esc(p.id||p.call||'主角')}</strong><span>${esc(realm)} · ${esc(r.name||'初入')}</span></div>${meter('今日学习（分钟）',m.today,m.goal,'time')}${r.next_xp!=null?meter(xp,data.xp,r.next_xp,'xp'):`<div class="study-hud-cap">${esc(xp)} ${amount(data.xp)} · 已达最高${esc(realm)}</div>`}<small>${r.ready?'可突破至 '+esc(r.next):r.bottleneck?'突破试炼待完成':r.next?'下一'+esc(realm)+'：'+esc(r.next):'继续积累'}</small></div></section><section class="study-hud-world"><div class="study-hud-calendar"><b>${esc(day)}</b><span>${esc(deadline)}</span></div><div class="study-hud-average">平均每日学习 <b>${amount(s.average_minutes)}</b> 分钟</div><div class="study-hud-location"><span aria-hidden="true">⌂</span><strong>${esc(world)}</strong>${current==='home'?'':`<span> / ${esc(page)}</span>`}</div></section>`;
    root.querySelector('img')?.addEventListener('error',e=>{e.target.parentElement.innerHTML=avatar({...p,avatar:''});},{once:true});
  }
  window.STUDY_HUD={mount,refresh:()=>mount()};
})();
