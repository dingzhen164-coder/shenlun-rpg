/* 宗门大比/竞技场场景：contest.js先生成原卡片，再mount分配进四页卷宗。
   仅窗口内记住打开页、滚动和焦点，不另建成绩或AI数据；退出后再次进入默认场景。 */
(() => {
  'use strict';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const modes=[['overview','考情','模考与分析'],['review','复盘','逐题复盘'],['trends','战绩','成绩走势'],['entry','录入','成绩录入']];
  function capture(root){const host=root.querySelector('.contest-scene');if(!host)return null;const d=host.querySelector('dialog');return {open:d.open,view:host.dataset.csView,scroll:Object.fromEntries([...host.querySelectorAll('.cs-pane')].map(p=>[p.dataset.csPane,p.scrollTop])),focus:d.contains(document.activeElement)?document.activeElement.id:''};}
  function mount(root,{title,seasonCount=0,mage=false,state=null}={}){
    const source=[...root.children],host=document.createElement('section');host.className='contest-scene '+(mage?'cs-mage':'cs-sect');host.setAttribute('aria-label',title);
    host.innerHTML=`<div class="cs-world"><div class="cs-landscape" aria-hidden="true"></div><div class="cs-mist" aria-hidden="true"></div><div class="cs-heading"><p>${mage?'王立学院 · 实战考核':'青衡宗 · 群峰会试'}</p><h2>${esc(title)}</h2><span>${seasonCount?`已收录 ${seasonCount} 季模考`:'静候入场 · 导入模考后开启修习'}</span></div><nav class="cs-entrances" aria-label="${esc(title)}功能入口">${modes.map(([id,label,full])=>`<button type="button" class="cs-entrance cs-${id}" data-cs-enter="${id}" aria-label="${full}" aria-haspopup="dialog" aria-controls="cs-dialog"><span>${label}</span></button>`).join('')}</nav></div><dialog id="cs-dialog" class="th-dialog cs-dialog scene-panel" aria-labelledby="cs-title"><header class="th-dialog-head"><div><p class="th-eyebrow">${esc(title)} · 修习卷宗</p><h2 id="cs-title"></h2></div><button type="button" data-cs-close>返回场景 ×</button></header><nav class="th-tabs cs-tabs" role="tablist" aria-label="大比功能">${modes.map(([id,label,full])=>`<button type="button" id="cs-tab-${id}" role="tab" data-cs-tab="${id}" aria-controls="cs-pane-${id}">${full}</button>`).join('')}</nav><div class="th-panels">${modes.map(([id])=>`<section class="cs-pane" id="cs-pane-${id}" data-cs-pane="${id}" role="tabpanel" aria-labelledby="cs-tab-${id}"></section>`).join('')}</div><footer class="cs-foot"><span>成绩、复盘与奖励沿用原有记录</span><button type="button" class="primary" data-cs-save hidden>保存成绩单</button></footer></dialog>`;
    const pane=id=>host.querySelector('[data-cs-pane='+id+']');
    for(const node of source){
      let id='overview';
      if(node.matches('.rv-card'))id='review';
      else if(node.matches('#mkForm,#mkMarksCard')||node.tagName==='P')id='entry';
      else if(node.matches('.contest-grid')||/六大模块|历次大比/.test(node.querySelector('h3')?.textContent||''))id='trends';
      pane(id).append(node);
    }
    for(const [id] of modes)if(!pane(id).children.length)pane(id).innerHTML=`<div class="th-empty"><p>尚无${id==='review'?'可复盘题目':id==='trends'?'成绩记录':'可用模考资料'}。</p><p class="small muted">先到资料库导入模考试卷，原有记录会在这里显示。</p><button type="button" data-cs-library>前往资料库</button></div>`;
    root.append(host);const dialog=host.querySelector('dialog');let view=state?.view||'overview',opener=null;
    function select(id){if(!modes.some(m=>m[0]===id))return;view=id;host.dataset.csView=id;host.querySelector('#cs-title').textContent=modes.find(m=>m[0]===id)[2];host.querySelectorAll('[data-cs-tab]').forEach(b=>{const on=b.dataset.csTab===id;b.setAttribute('aria-selected',String(on));b.tabIndex=on?0:-1;});host.querySelectorAll('.cs-pane').forEach(p=>p.hidden=p.dataset.csPane!==id);host.querySelector('[data-cs-save]').hidden=id!=='entry'||!host.querySelector('#mkSave');}
    function measure(){const r=host.getBoundingClientRect(),style=getComputedStyle(host),w=Math.min(r.width-32,Math.max(360,r.width*(parseFloat(style.getPropertyValue('--scene-panel-width'))||50)/100)),h=Math.min(r.height-32,parseFloat(style.getPropertyValue('--scene-panel-height'))||r.height);for(const [k,v]of Object.entries({width:w,height:h,left:r.left+(r.width-w)/2,top:r.top+(r.height-h)/2}))dialog.style.setProperty('--th-'+k,v+'px');}
    function close(){dialog.close();(opener?.isConnected?opener:host.querySelector('[data-cs-enter='+view+']'))?.focus({preventScroll:true});}
    dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
    host.addEventListener('click',e=>{const b=e.target.closest('button');if(!b||b.disabled)return;if(b.dataset.csEnter){opener=b;select(b.dataset.csEnter);measure();dialog.showModal();host.querySelector('[data-cs-close]').focus();}else if(b.dataset.csTab)select(b.dataset.csTab);else if(b.hasAttribute('data-cs-close'))close();else if(b.hasAttribute('data-cs-save'))host.querySelector('#mkSave')?.click();else if(b.hasAttribute('data-cs-library')){dialog.close();go('skeleton');}});
    host.addEventListener('keydown',e=>{const b=e.target.closest('[data-cs-tab]');if(!b)return;const all=[...host.querySelectorAll('[data-cs-tab]')],i=all.indexOf(b);let j;if(e.key==='ArrowRight')j=(i+1)%all.length;else if(e.key==='ArrowLeft')j=(i+all.length-1)%all.length;else if(e.key==='Home')j=0;else if(e.key==='End')j=all.length-1;else return;e.preventDefault();select(all[j].dataset.csTab);all[j].focus();});
    select(view);if(state?.scroll)for(const p of host.querySelectorAll('.cs-pane'))p.scrollTop=state.scroll[p.dataset.csPane]||0;
    const resize=new ResizeObserver(()=>{if(!host.isConnected)return resize.disconnect();measure();});resize.observe(host);
    new MutationObserver((_,o)=>{if(!host.isConnected)return o.disconnect();measure();}).observe(root,{attributes:true,attributeFilter:['style']});
    measure();if(state?.open){dialog.showModal();(state.focus&&host.querySelector('#'+CSS.escape(state.focus))||host.querySelector('[data-cs-close]')).focus({preventScroll:true});}
  }
  window.CONTEST_SCENE={mount,capture};
})();
