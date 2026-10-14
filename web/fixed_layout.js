/* 3.0.4固定窗口布局：app.render结束后调用mount，观察模块异步重绘及弹窗。
   原DOM原位移动，保留事件、草稿、API和计时；只在内存记住各模块标签/分页。
   页面不滚动，正文、目录、设置在有界工作区内滚动，操作栏留在内容区外。
   3.0.6将同类卡片分组；法师成长记与公考两主题共用。 */
(() => {
  'use strict';
  let route='home', pending=false, serial=0;
  const choices=new Map(), pageChoices=new Map();
  const make=(tag,cls)=>{const e=document.createElement(tag);if(cls)e.className=cls;return e;};
  function title(node,fallback='概览') {
    const h=node.matches('h2,h3,summary')?node:node.querySelector('h2,h3,summary,.yj-title,.k');
    if(!h)return fallback;
    const copy=h.cloneNode(true);copy.querySelectorAll('small,.small').forEach(x=>x.remove());
    return copy.textContent.trim().replace(/\s+/g,' ').slice(0,28)||fallback;
  }
  function tabs(parent,items,key,initial=0) {
    const nav=make('div','fx-tabs');nav.setAttribute('role','tablist');nav.setAttribute('aria-label','当前模块内容');
    const select=i=>{
      choices.set(key,i);
      items.forEach((item,j)=>{
        item.panel.hidden=j!==i;
        item.button.setAttribute('aria-selected',String(j===i));item.button.tabIndex=j===i?0:-1;
      });
      window.dispatchEvent(new Event('resize'));
    };
    items.forEach((item,i)=>{
      const b=make('button','fx-tab');b.type='button';b.textContent=item.label;b.setAttribute('role','tab');
      item.panel.id=item.panel.id||'fx-panel-'+(++serial);b.id='fx-tab-'+(++serial);
      b.setAttribute('aria-controls',item.panel.id);item.panel.setAttribute('role','tabpanel');item.panel.setAttribute('aria-labelledby',b.id);
      item.button=b;b.onclick=()=>select(i);
      b.onkeydown=e=>{let j=i;if(e.key==='ArrowRight'||e.key==='ArrowDown')j=(i+1)%items.length;else if(e.key==='ArrowLeft'||e.key==='ArrowUp')j=(i+items.length-1)%items.length;else if(e.key==='Home')j=0;else if(e.key==='End')j=items.length-1;else return;e.preventDefault();select(j);items[j].button.focus();};
      nav.append(b);
    });
    parent.prepend(nav);select(Math.min(items.length-1,choices.get(key)??initial));return nav;
  }
  // 一个面板的标题与必要操作固定，正文单独滚动。不克隆带事件的输入和按钮。
  function frame(node,footerSelector='') {
    if(node.dataset.fxFrame)return;
    node.dataset.fxFrame='1';node.classList.add('fx-frame');
    if(node.tagName==='DETAILS')node.open=true;
    const header=node.firstElementChild;
    const keep=header?.matches('h2,h3,summary,.row,.yj-hall-head,.sl-material-toolbar,.tj-ltabs')?header:null;
    const footer=footerSelector?node.querySelector(footerSelector)?.closest('.row,.yj-hall-tools,.narrative-actions'):null;
    const body=make('div','fx-scroll');body.tabIndex=0;body.setAttribute('aria-label',title(node)+'内容');
    const nodes=[...node.childNodes];for(const n of nodes)if(n!==keep&&n!==footer)body.append(n);
    if(keep)keep.classList.add('fx-heading');node.append(body);
    if(footer){footer.classList.add('fx-actions');node.append(footer);}
  }
  function flatten(node) {
    if(node.matches('.grid.g5'))return [node];
    if(node.matches('.log-cols,.log-col')||node.matches('.grid')&&node.querySelector(':scope > .card'))return [...node.children].flatMap(flatten);
    return [node];
  }
  // 3.0.6按稳定控件与功能分组，保留原节点和原保存逻辑。
  function groupedEntries(parts) {
    const groups=new Map(), mode=themeKey();
    const group=(id,label,node,sub=false)=>{if(!groups.has(id))groups.set(id,{id,label,nodes:[],sub});groups.get(id).nodes.push(node);};
    for(const n of parts){
      const name=title(n),has=s=>n.matches(s)||!!n.querySelector(s);
      if(route==='dwelling'){
        if(has('.narrative-dwelling,.xc-guide-scene,.npc.greet')){n.remove();continue;}
        if(has('.hero,.trib-card,.retreat,.mock-rewards'))group('growth',mode==='office'?'仕途与晋升':mode==='mage'?'成长与晋升':'修为与突破',n);
        else if(has('.sancai,.grid.g5'))group('daily',mode==='office'?'学时与出勤':'时辰与日课',n);
        else if(has('.lecture-card'))group('records',mode==='peaks'?'修行记录':'学习记录',n,true);
        else group('other','成长记录',n);
      }else if(route==='settings'){
        if(has('.shortcut-settings,.portal-settings'))group('navigation','地图与操作',n,true);
        else if(has('#ambTheme,#cwR,#xcSize,#slCursorToggle,[data-style]'))group('appearance','外观与声音',n,true);
        else if(has('#sSave'))group('ai','AI与资料',n);
        else if(has('#scheduleSave,[data-subject]')||/改规则/.test(name))group('learning','学习与成长',n);
        else if(has('#updCheck'))group('updates','版本与更新',n);
        else if(has('#lanOn,.scene-utility-tools'))group('device','设备与工具',n);
        else group('other','其他设置',n);
      }else if(route==='contest'){
        if(has('#chScore,#chAcc,#mkPick')||/走势/.test(name))group('charts','成绩走势',n,true);
        else if(has('#mkForm,#mkMarksCard,#ctGo'))group('entry','成绩录入',n);
        else if(has('.contest-hero,.mock-rewards')||/考情分析|年度考核|竞技场|宗门大比/.test(name))group('overview','模考与分析',n);
        else if(has('.mk-table')||/复盘|历次/.test(name))group('history','复盘与档案',n);
        else if(n.matches('p,.small,.warn'))group('overview','模考与分析',n);
        else group('overview','模考与分析',n);
      }else if(route==='log'){
        if(has('#tasks,#leaveBtn'))group('daily',mode==='office'?'日常事务':'每日功课',n);
        else if(has('#bossBtn,#asBtn'))group('exam','考试档案',n);
        else if(/日志/.test(name))group('history','修行日志',n);
        else group('growth',mode==='office'?'成长与资源':'功法与资源',n);
      }else if(route==='bank'){
        if(has('.pagoda-card,#bankCount')||/刷题|试炼/.test(name))group('practice','试炼与练习',n);
        else group('history','练习记录',n);
      }else if(route==='skeleton'){
        group('library','资料与简匣',n);
      }else{
        const id=name==='概览'?'overview':name;
        if(n.matches('p,.small,.warn')&&groups.size)[...groups.values()][groups.size-1].nodes.push(n);
        else group(id,name==='概览'?'内容总览':name,n);
      }
    }
    return [...groups.values()];
  }
  // 所有二级分类原位合并；设置只保留一页折叠卡，不复制或销毁输入控件。
  const folds=new Map();
  function folding(node,key) {
    if(node.dataset.fxFold)return node;
    let fold=node;
    if(node.tagName!=='DETAILS'){
      fold=make('details','fx-fold-card');const summary=make('summary');
      const heading=node.querySelector(':scope > h2,:scope > h3');
      if(heading)summary.append(heading);else summary.textContent=title(node,'设置项');
      fold.append(summary,node);
    }else fold.classList.add('fx-fold-card');
    fold.dataset.fxFold=key;fold.open=folds.get(key)??false;
    fold.addEventListener('toggle',()=>{folds.set(key,fold.open);window.dispatchEvent(new Event('resize'));});return fold;
  }
  function sections(root,key) {
    if(root.querySelector(':scope > .fx-shell'))return;
    const nodes=[...root.children].flatMap(flatten);if(!nodes.length)return;
    const headers=nodes.filter(n=>n.matches('.lib-head,.sl-ui-masthead,.subpage-heading'));
    const entries=groupedEntries(nodes.filter(n=>!headers.includes(n)));if(!entries.length)return;
    const settings=route==='settings',shell=make('section','fx-shell'+(settings?' fx-settings':'')),area=make('div','fx-panels');
    if(settings){
      const panel=make('section','fx-panel'),scroll=make('div','fx-scroll fx-settings-list');scroll.tabIndex=0;
      for(const entry of entries){const group=make('section','fx-settings-group');group.dataset.fxGroup=entry.id;const h=make('h3');h.textContent=entry.label;group.append(h);entry.nodes.forEach((n,i)=>group.append(folding(n,key+':'+entry.id+':'+i)));scroll.append(group);}
      panel.append(scroll);area.append(panel);shell.append(area);root.append(shell);return;
    }
    const items=entries.map(entry=>{
      const panel=make('section','fx-panel'),scroll=make('div','fx-scroll');scroll.tabIndex=0;panel.dataset.fxGroup=entry.id;
      if(entry.id==='records')scroll.classList.add('fx-records-list');
      entry.nodes.forEach(n=>scroll.append(n));
      panel.append(scroll);area.append(panel);return {label:entry.label,panel};
    });
    shell.append(area);root.append(shell);if(items.length>1)tabs(shell,items,key);
    for(const item of items){const rows=new Set();for(const action of item.panel.querySelectorAll('#ctGo')){const row=action.closest('.row,.ct-form');if(!row||rows.has(row))continue;rows.add(row);row.classList.add('fx-actions');item.panel.append(row);}}
  }
  function pageBar(root) {
    const slot=root.querySelector('#studyHud .subpage-nav');if(!slot)return;
    root.querySelectorAll('.fx-shell>.fx-tabs,.lib-head>.lib-tabs,.sl-ui-section-tabs>.lib-tabs').forEach(nav=>slot.append(nav));
    root.querySelectorAll('.lib-head,.sl-ui-masthead').forEach(h=>{if(!h.querySelector('button')||h.matches('.sl-ui-masthead'))h.hidden=true;});
  }
  function paginate(grid,key,kind) {
    if(grid.dataset.fxPages)return;
    const items=[...grid.children];if(!items.length)return;
    grid.dataset.fxPages='1';grid.classList.add('fx-paged-grid');
    const nav=make('div','fx-pager'),prev=make('button'),next=make('button'),status=make('span');
    prev.textContent='← 上一页';next.textContent='下一页 →';prev.type=next.type='button';status.setAttribute('role','status');
    nav.append(prev,status,next);grid.after(nav);
    let page=pageChoices.get(key)||0;
    function update(){
      const narrow=grid.clientWidth<550;const avail=grid.parentElement.clientHeight;
      const columns=Math.max(1,(getComputedStyle(grid).gridTemplateColumns.match(/[\d.]+px/g)||[]).length);
      const size=kind==='regions'?(narrow?(avail<480?2:4):(items.length===5?5:avail<470?4:8)):columns*Math.max(1,Math.floor((avail-100)/310));
      const total=Math.max(1,Math.ceil(items.length/size));page=Math.max(0,Math.min(page,total-1));pageChoices.set(key,page);
      items.forEach((e,i)=>e.hidden=Math.floor(i/size)!==page);
      nav.hidden=total===1;prev.disabled=page===0;next.disabled=page===total-1;status.textContent=`第 ${page+1} / ${total} 页 · 共 ${items.length} 项`;
    }
    prev.onclick=()=>{page--;update();};next.onclick=()=>{page++;update();};
    const resize=new ResizeObserver(()=>{if(grid.isConnected)update();else resize.disconnect();});resize.observe(grid.parentElement);update();
  }
  function regions(root) {
    const select=root.querySelector('.study-regions');
    if(select){select.classList.add('fx-region-select');paginate(select.querySelector('.study-region-grid'),'regions:'+themeKey(),'regions');return true;}
    const heading=root.querySelector('.study-region-heading');if(!heading)return false;
    const host=heading.parentElement;if(host.querySelector('.fx-region-work'))return true;
    const panels=[...host.querySelectorAll(':scope > .yj-hall,:scope > .ln-hall')];
    const work=make('div','fx-region-work');host.append(work);panels.forEach(p=>{frame(p,p.matches('.yj-hall')?'[data-yjadd]':'');work.append(p);});
    tabs(host,panels.map(p=>({panel:p,label:title(p)})),'region:'+themeKey());
    host.classList.add('fx-region-detail');return true;
  }
  function themeKey(){return document.body.classList.contains('guantu')?'office':document.body.classList.contains('xuanhuan')?'mage':'peaks';}
  function notes(root) {
    const n=root.querySelector('.notes');if(!n)return;
    if(!n.dataset.fxNotes){n.dataset.fxNotes='1';const panels=[...n.children].filter(x=>x.matches('.nt-side,.nt-main'));
    if(panels.length>1){const bar=make('div','fx-note-switch');root.prepend(bar);tabs(bar,panels.map((panel,i)=>({panel,label:i===0?'目录':'书写与阅读'})),'notes:'+themeKey(),1);}}
    const main=n.querySelector('.nt-main');if(main&&!main.querySelector('.fx-reader-switch')){const panes=[...main.children].filter(x=>x.matches('.nt-book,.nt-reader'));if(panes.length>1){const bar=make('div','fx-reader-switch');main.prepend(bar);tabs(bar,panes.map((panel,i)=>({panel,label:i===0?'书写':'阅读'})),'note-panes');}}
  }
  function tianji(root) {
    const hub=root.querySelector('.tj-hub');
    if(hub&&!hub.querySelector(':scope > .fx-scroll')){
      const body=make('div','fx-scroll');[...hub.children].filter(x=>!x.matches('.tj-head,.tj-drop')).forEach(x=>body.append(x));hub.append(body);
      body.querySelectorAll('.tj-grid').forEach((g,i)=>paginate(g,'tianji:'+i,'covers'));
    }
    const issue=root.querySelector('.tj-issue');if(!issue)return;
    issue.querySelectorAll('.tj-news').forEach(n=>frame(n,'#tjRead'));
    const area=issue.querySelector('.tj-ibody');if(area&&!area.querySelector(':scope > .tj-read,:scope > .fx-scroll')){const body=make('div','fx-scroll');[...area.children].filter(x=>!x.matches('.tj-bar')).forEach(x=>body.append(x));area.append(body);}
  }
  function shenlun(root) {
    const grid=root.querySelector('.sl-full-grid');if(!grid)return false;
    if(!root.classList.contains('fx-exam'))root.classList.add('fx-exam');
    const writing=grid.querySelector('.sl-writing');if(writing)frame(writing,'#slSubmit');
    const result=root.querySelector('#slRes');
    const examKey='sl-result:'+root.querySelector('.sl-exam-heading b')?.textContent;
    if(!root.querySelector('.fx-exam-switch')){
      const bar=make('div','fx-exam-switch');grid.before(bar);
      const area=make('section','fx-exam-answer');grid.before(area);area.append(grid);
      if(result){result.classList.add('fx-scroll');tabs(bar,[{label:'材料与作答',panel:area},{label:'批改与复盘',panel:result}],examKey,result.textContent.trim()?1:0);}
      const mobile=make('div','fx-material-switch');grid.before(mobile);
      tabs(mobile,[...grid.children].map((panel,i)=>({label:i===0?'给定资料':'我的作答',panel})),'sl-material',1);
    }
    if(result){const signature=result.textContent.trim();if(signature&&result.dataset.fxResult!==signature){result.dataset.fxResult=signature;root.querySelector('.fx-exam-switch .fx-tab:last-child')?.click();}}
    return true;
  }
  function catalog(root) {
    const page=root.querySelector('.ex-content');if(!page||page.querySelector(':scope > .fx-scroll'))return;
    const body=make('div','fx-scroll');const foot=make('div','fx-actions');
    [...page.children].forEach(x=>{if(x.matches('.ex-heading,.ex-study-head,.ex-tabs,[data-message]'))return;if(x.matches('.ex-pagination,.ex-sequence'))foot.append(x);else body.append(x);});
    body.querySelectorAll('.ex-study-actions,.ex-sequence').forEach(x=>foot.append(x));
    page.append(body);if(foot.children.length)page.append(foot);
    // 目录子页会重绘自身，下一轮观察重新分配，不改变原筛选、草稿或题号。
  }
  function overlays() {
    document.querySelectorAll('.yj-stage').forEach(s=>{
      if(s.classList.contains('ln-stage'))return; // 导图自己管理画布/文档，不再套整块滚动框。
      let body=s.querySelector(':scope > .fx-stage-body');
      if(!body){body=make('div','fx-stage-body fx-scroll');[...s.children].filter(x=>!x.matches('.yj-top,.yj-bar')).forEach(x=>body.append(x));s.insertBefore(body,s.querySelector('.yj-bar'));body.tabIndex=0;}
      body.querySelectorAll('#aSave,#iGo,#gGo,#gSave').forEach(button=>{const action=button.closest('.row');if(action){action.classList.add('fx-actions');s.append(action);}});
    });
    document.querySelectorAll('.modal-box,.sl-topic-dialog').forEach(n=>frame(n,'button.primary'));
    document.querySelectorAll('.narrative-dialog').forEach(n=>{
      n.querySelectorAll('.narrative-paper').forEach(p=>{
        if(p.querySelector(':scope > .fx-scroll'))return;
        const body=make('div','fx-scroll');const actions=p.querySelector('.narrative-actions');
        [...p.childNodes].filter(x=>x!==actions&&!x.matches?.('.narrative-chapter-title')).forEach(x=>body.append(x));p.append(body);
        if(actions){actions.classList.add('fx-actions');p.append(actions);}
      });
    });
  }
  function measure() {
    const h=document.documentElement,viewport=window.visualViewport;
    const height=Math.round(viewport?.height||innerHeight);
    const keyboard=height<innerHeight-150;if(h.classList.contains('fx-keyboard')!==keyboard)h.classList.toggle('fx-keyboard',keyboard);
    if(h.style.getPropertyValue('--fx-height')!==height+'px')h.style.setProperty('--fx-height',height+'px');
    const hud=document.getElementById('studyHud');if(hud)h.style.setProperty('--study-workspace-height',Math.ceil(hud.classList.contains('subpage-heading')?hud.getBoundingClientRect().bottom:hud.getBoundingClientRect().height)+'px');
  }
  function apply() {
    pending=false;window.STUDY_HUD?.ensure();const root=document.getElementById('view');if(!root)return;
    if(!document.documentElement.classList.contains('fixed-app'))document.documentElement.classList.add('fixed-app');root.dataset.fxRoute=route;measure();
    if(route!=='home'&&!root.querySelector('.fx-shell')){
      if(root.querySelector('.train')){} // 会话由原消息/输入工作区处理。
      else if(root.querySelector('.notes'))notes(root);
      else if(root.querySelector('.tj-hub,.tj-issue'))tianji(root);
      else if(root.querySelector('.ex-page'))catalog(root);
      else if(shenlun(root)){}
      else if(regions(root)){}
      else {let host=root;while(true){const children=[...host.children].filter(n=>!n.matches('.subpage-heading'));if(children.length!==1||children[0].matches('.card,details,.grid')||!children[0].children.length)break;host=children[0];}host.classList.add('fx-host');sections(host,route+':'+themeKey()+':'+(root.querySelector('[data-libtab].on')?.dataset.libtab||''));}
    }
    pageBar(root);overlays();
  }
  function schedule(){if(!pending){pending=true;requestAnimationFrame(apply);}}
  const observer=new MutationObserver(schedule);observer.observe(document.body,{childList:true,subtree:true});
  new MutationObserver(schedule).observe(document.documentElement,{attributes:true,attributeFilter:['class']});
  window.addEventListener('resize',schedule);window.visualViewport?.addEventListener('resize',schedule);
  window.FIXED_LAYOUT={mount(view){route=view;schedule();},refresh:schedule};
})();
