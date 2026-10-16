/* 试炼塔统一入口：app.shizhanHtml供给bank/library只读目录，bind接原训练接口。
   套卷/板块共享场景与操作区；本机trial-hall-v1按科目/资料库记选择，不写学习存档。
   计分、抽题、复盘、续做全部交回原bank训练流程，不在此处生成成绩。 */
(() => {
  'use strict';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let model=null;
  const ratio=(n,d)=>d?Math.max(0,Math.min(1,n/d)):0;
  const pct=(n,d)=>d?Math.round(n/d*100)+'%':'—';
  const meter=(n,d,label)=>`<div class="th-meter" role="progressbar" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="${d||1}" aria-valuenow="${Math.min(n,d)||0}"><i style="width:${ratio(n,d)*100}%"></i></div>`;
  const empty=text=>`<div class="th-empty"><span aria-hidden="true">◇</span><p>${esc(text)}</p><p class="small muted">可前往资料库导入题目，再回来选择练习。</p></div>`;
  function read(key){try{const p=JSON.parse(localStorage.getItem(key));if(p&&typeof p==='object')return {mode:p.mode==='blocks'?'blocks':'sets',...Object.fromEntries(['book','paper','board','topic'].map(k=>[k,typeof p[k]==='string'?p[k]:'']))};}catch(_){}return {mode:'sets',book:'',paper:'',board:'',topic:''};}
  function save(m){try{localStorage.setItem(m.key,JSON.stringify(m.pref));}catch(_){} }
  const books=m=>(m.d.sets||[]).filter(b=>b.sets?.length);
  const boards=m=>m.d.boards.filter(b=>b.total||b.pending||b.wrong||b.active);
  const book=m=>books(m).find(b=>b.book===m.pref.book);
  const paper=m=>book(m)?.sets.find(p=>p.name===m.pref.paper);
  const board=m=>boards(m).find(b=>b.board===m.pref.board);
  const topics=m=>m.c.boards.find(b=>b.board===m.pref.board)?.topics||[];
  const run=(m,slot)=>(m.d.active_runs||[]).find(r=>r.board===slot);
  function normalize(m){
    const bs=books(m),rs=boards(m);
    if(!book(m))m.pref.book=(bs.find(b=>b.sets.some(p=>p.active))||bs[0])?.book||'';
    const b=book(m);if(!paper(m))m.pref.paper=b?.next||b?.sets[0]?.name||'';
    if(!board(m))m.pref.board=(rs.find(b=>b.active)||rs.find(b=>b.remaining)||rs[0])?.board||'';
    if(!topics(m).some(t=>t.name===m.pref.topic))m.pref.topic='';
  }
  function hero(m){
    const t=m.d.tower||{layers:100,total:0,current:1,completed:0,floor_done:0,floor_total:0,remaining:0};
    const done=m.d.boards.reduce((n,b)=>n+b.first_total,0),ok=m.d.boards.reduce((n,b)=>n+b.first_correct,0),wrong=m.d.boards.reduce((n,b)=>n+b.wrong,0);
    return `<header class="th-hero"><div class="th-art" aria-hidden="true"><div class="th-art-halo"></div><img src="assets/beauty/trial/tower.png" alt="" class="th-tower-art"><i class="th-current-light" style="--th-light:${82-ratio(t.current,t.layers)*65}%"></i><i class="th-art-ring"></i></div><div class="th-hero-info"><p class="th-eyebrow">${esc(m.env.mage?'王立学院 · 知识试炼':'青衡宗 · 百层问道')}</p><h2>${esc(m.env.title)}</h2><div class="th-floor">${t.summit?'已登顶':`第 <strong>${t.current}</strong> 层`}</div><p class="th-floor-detail">${t.summit?`已完成 ${t.completed} 道新题`:`本层 ${t.floor_done} / ${t.floor_total} 道 · 再做 ${t.remaining} 道升层`}</p>${meter(t.summit?1:t.floor_done,t.summit?1:t.floor_total,'本层进度')}<p class="th-capacity">${t.layers} 层 · 目标 ${t.total} 道新题</p></div><div class="th-stats"><span><b>${done}</b> 已闯新题</span><span><b>${pct(ok,done)}</b> 首次正确率</span><span><b>${wrong}</b> ${esc(m.env.wrong)}</span></div></header>`;
  }
  function setsPane(m){
    const bs=books(m),b=book(m),p=paper(m);
    if(!b||!p)return empty('暂无可练习的套卷');
    return `<div class="th-filters"><label>选择题集<select data-th-book>${bs.map((x,i)=>`<option value="${i}" ${x===b?'selected':''}>${esc(x.book)}</option>`).join('')}</select></label></div><div class="th-selection"><span class="th-kicker">${p.active?'未完成 · 可继续':p.done>=p.total?'本套已完成':'本次套卷'}</span><h3>${esc(p.name)}</h3><p>共 ${p.total} 题 · 已完成 ${p.done} 题<span class="th-inline-note">${esc(Object.keys(p.boards||{}).join(' / '))}</span></p>${meter(p.done,p.total,'套卷进度')}</div><div class="th-list-head"><span>选择套卷</span><small>${b.finished} / ${b.sets.length} 套已完成</small></div><div class="th-choice-list" tabindex="0" aria-label="套卷目录">${b.sets.map((x,i)=>`<button type="button" class="th-choice" data-th-paper="${i}" aria-pressed="${x===p}"><span><b>${esc(x.name)}</b><small>${x.active?'进行中':x.done>=x.total?'已完成':'待练习'}</small></span><span class="th-choice-progress">${x.done}<small> / ${x.total}</small></span></button>`).join('')}</div>`;
  }
  function blocksPane(m){
    const rs=boards(m),b=board(m);if(!b)return empty('暂无可练习的板块');
    const ts=topics(m),topic=ts.find(t=>t.name===m.pref.topic),active=run(m,topic?'点:'+b.board+':'+topic.name:b.board);
    return `<div class="th-filters"><label>选择板块<select data-th-board>${rs.map((x,i)=>`<option value="${i}" ${x===b?'selected':''}>${esc(x.board)}</option>`).join('')}</select></label><label>知识点<select data-th-topic><option value="">全部知识点</option>${ts.map((x,i)=>`<option value="${i}" ${x===topic?'selected':''}>${esc(x.name)} · 余 ${x.left} 题</option>`).join('')}</select></label></div><div class="th-selection"><span class="th-kicker">${active?'未完成 · 可继续':'本次板块'}</span><h3>${esc(b.board)}${topic?' · '+esc(topic.name):''}</h3><p>${topic?`剩余 ${topic.left} / ${topic.count} 题`:`剩余 ${b.remaining} / ${b.total} 题`} · 首次正确率 ${pct(b.first_correct,b.first_total)}</p>${meter(topic?topic.count-topic.left:b.total-b.remaining,topic?topic.count:b.total,'板块进度')}</div><div class="th-practice-options"><label>出题顺序<select class="bankOrder"><option value="seq" ${m.d.order==='seq'?'selected':''}>按顺序</option><option value="shuffle" ${m.d.order==='shuffle'?'selected':''}>乱序</option></select></label><label>每组题数<select id="bankCount"><option value="10" ${m.d.count===10?'selected':''}>10 题</option><option value="15" ${m.d.count===15?'selected':''}>15 题</option></select></label></div><div class="th-block-notes"><p>每次从未做过的题中练一组，交卷后查看答案与解析。已有练习保留原题目和进度。</p>${b.pending?`<p>${b.pending} 道题待补答案，暂不参与出题。</p>`:''}${b.errors.length?`<details class="th-error"><summary>本板块有 ${b.errors.length} 项资料问题</summary><p>${b.errors.map(esc).join('<br>')}</p></details>`:''}${m.c.boards.find(x=>x.board===b.board)?.more_topics?'<p>此处展示常用知识点；完整目录可在资料库中查看。</p>':''}</div>`;
  }
  function historyPane(m){
    return `<div class="th-list-head"><span>练习记录</span><small>最近 ${m.d.groups.length} 组</small></div><div class="th-choice-list th-history" tabindex="0" aria-label="练习记录">${m.d.groups.map(x=>`<article class="th-history-row"><div><b>${esc(x.label||x.board)}</b><small>${esc(x.date)} · ${x.mode==='new'?'新题练习':'错题复习'}</small></div><span><b>${x.correct} / ${x.total}</b><small>${esc(m.env.rank(x.rank))}</small></span></article>`).join('')||'<p class="th-empty">尚未留下练习记录。</p>'}</div>`;
  }
  function footer(m){
    if(m.view==='history')return `<div class="th-action-note">成绩和进度沿用原有练习记录。</div><button data-th-return type="button">返回练习</button>`;
    if(m.pref.mode==='sets'){
      const p=paper(m);return `<div class="th-action-note">整套练习保留套卷题数，已做过的题不再出。<span class="th-save-status" role="status"></span></div><button class="primary th-start" data-th-start ${!p||!p.active&&p.done>=p.total?'disabled':''}>${p?.active?'继续本套':p&&p.done>=p.total?'本套已完成':'开始本套'} <span aria-hidden="true">→</span></button>`;
    }
    const b=board(m),topic=topics(m).find(t=>t.name===m.pref.topic),active=b&&run(m,topic?'点:'+b.board+':'+topic.name:b.board),remaining=topic?topic.left:b?.remaining;
    return `<div class="th-action-note">交卷后统一判分 · 复习不重复计算新题进度<span class="th-save-status" role="status"></span></div><div class="th-action-buttons"><button data-th-review ${!b||b.active||!b.wrong?'disabled':''}>复习本板块错题${b?.wrong?' '+b.wrong:''}</button><button class="primary th-start" data-th-start ${!b||!active&&(!remaining||b.errors.length)?'disabled':''}>${active?'继续练习':'开始练习'} <span aria-hidden="true">→</span></button></div>`;
  }
  function html(d,c,env){
    const key='trial-hall-v1:'+encodeURIComponent(env.subject+':'+env.scope),pref=read(key),m={d,c,env,key,pref,view:pref.mode,busy:false};normalize(m);model=m;
    return `<section class="trial-hall scene-panel ${env.mage?'th-mage':'th-sect'}" aria-label="${esc(env.title)}">${hero(m)}<nav class="th-tabs" role="tablist" aria-label="刷题模式"><button role="tab" id="th-tab-sets" data-th-tab="sets" aria-controls="th-pane-sets">套卷刷题</button><button role="tab" id="th-tab-blocks" data-th-tab="blocks" aria-controls="th-pane-blocks">板块刷题</button><button role="tab" id="th-tab-history" data-th-tab="history" aria-controls="th-pane-history" class="th-history-tab">练习记录</button></nav><div class="th-panels">${[['sets',setsPane],['blocks',blocksPane],['history',historyPane]].map(([id,render])=>`<section id="th-pane-${id}" class="th-pane" role="tabpanel" aria-labelledby="th-tab-${id}" ${m.view===id?'':'hidden'}>${render(m)}</section>`).join('')}</div><footer class="th-actions">${footer(m)}</footer></section>`;
  }
  function bind(root,hooks){
    const host=root.querySelector('.trial-hall'),m=model;if(!host||!m||host.dataset.thBound)return;host.dataset.thBound='1';
    function tabState(){host.querySelectorAll('[data-th-tab]').forEach(b=>{const active=b.dataset.thTab===m.view;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;});host.querySelectorAll('.th-pane').forEach(p=>p.hidden=p.id!=='th-pane-'+m.view);}
    function actions(){host.querySelector('.th-actions').innerHTML=footer(m);host.querySelectorAll('.th-start,[data-th-review],.bankOrder,#bankCount').forEach(b=>{if(m.busy)b.disabled=true;});}
    function refreshPane(id){host.querySelector('#th-pane-'+id).innerHTML=(id==='sets'?setsPane:blocksPane)(m);actions();}
    function scrollChoice(){const list=host.querySelector('#th-pane-sets .th-choice-list'),choice=list?.querySelector('[aria-pressed=true]');if(choice&&list.clientHeight)list.scrollTop+=choice.getBoundingClientRect().top-list.getBoundingClientRect().top;}
    function selectTab(id){m.view=id;if(id!=='history'){m.pref.mode=id;save(m);}tabState();actions();if(id==='sets')scrollChoice();}
    host.addEventListener('click',e=>{
      const b=e.target.closest('button');if(!b||b.disabled)return;
      if(b.hasAttribute('data-th-tab'))return selectTab(b.dataset.thTab);
      if(b.hasAttribute('data-th-return'))return selectTab(m.pref.mode);
      if(b.hasAttribute('data-th-paper')){const p=book(m)?.sets[Number(b.dataset.thPaper)];if(!p)return;m.pref.paper=p.name;save(m);const list=host.querySelector('#th-pane-sets .th-choice-list'),top=list.scrollTop;refreshPane('sets');host.querySelector('#th-pane-sets .th-choice-list').scrollTop=top;host.querySelector(`[data-th-paper="${b.dataset.thPaper}"]`)?.focus({preventScroll:true});return;}
      if(!b.hasAttribute('data-th-start')&&!b.hasAttribute('data-th-review'))return;
      const review=b.hasAttribute('data-th-review'),p=paper(m),r=board(m);
      const slot=m.pref.mode==='sets'?'套:'+p.name:!review&&m.pref.topic?'点:'+r.board+':'+m.pref.topic:r.board;
      hooks.start({type:review?'bank_review':'bank',board:slot,target:slot,title:m.pref.mode==='sets'?p.name:r.board+(m.pref.topic&&!review?' · '+m.pref.topic:'')});
    });
    host.addEventListener('keydown',e=>{
      const b=e.target.closest('[data-th-tab]');if(!b)return;const all=[...host.querySelectorAll('[data-th-tab]')],i=all.indexOf(b);let j;
      if(e.key==='ArrowRight')j=(i+1)%all.length;else if(e.key==='ArrowLeft')j=(i+all.length-1)%all.length;else if(e.key==='Home')j=0;else if(e.key==='End')j=all.length-1;else return;
      e.preventDefault();selectTab(all[j].dataset.thTab);all[j].focus();
    });
    host.addEventListener('change',async e=>{
      const el=e.target;
      if(el.matches('[data-th-book]')){m.pref.book=books(m)[Number(el.value)]?.book||'';m.pref.paper='';normalize(m);save(m);refreshPane('sets');scrollChoice();host.querySelector('[data-th-book]').focus();}
      else if(el.matches('[data-th-board]')){m.pref.board=boards(m)[Number(el.value)]?.board||'';m.pref.topic='';save(m);refreshPane('blocks');host.querySelector('[data-th-board]').focus();}
      else if(el.matches('[data-th-topic]')){m.pref.topic=el.value===''?'':topics(m)[Number(el.value)]?.name||'';save(m);refreshPane('blocks');host.querySelector('[data-th-topic]').focus();}
      else if(el.matches('.bankOrder,#bankCount')){
        if(m.busy)return;const field=el.id==='bankCount'?'count':'order',old=m.d[field],value=field==='count'?Number(el.value):el.value;m.busy=true;actions();
        try{await hooks.api('/api/bank/count',{[field]:value});m.d[field]=value;}
        catch(error){el.value=String(old);hooks.error(error);}
        finally{m.busy=false;host.querySelectorAll('.bankOrder,#bankCount').forEach(n=>n.disabled=false);actions();const status=host.querySelector('.th-save-status');if(status&&m.d[field]===value)status.textContent='已保存，下一组生效';}
      }
    });
    tabState();
    let positioned=false;const resize=new ResizeObserver(()=>{if(!host.isConnected)return resize.disconnect();host.classList.toggle('th-compact',host.clientHeight<520);if(!positioned&&m.view==='sets'){scrollChoice();positioned=true;}});resize.observe(host);
    host.querySelector('.th-tower-art').addEventListener('error',()=>host.classList.add('th-art-missing'),{once:true});
  }
  window.TRIAL_HALL={html,bind};
})();
