/* 试炼塔统一入口：app.shizhanHtml供给bank/library只读目录，bind接原训练接口。
   全高塔景通过左右石门打开原生dialog卷宗；本机trial-hall-v1按科目/资料库记选择，不写学习存档。
   计分、抽题、复盘、续做全部交回原bank训练流程，不在此处生成成绩。 */
(() => {
  'use strict';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let model=null;
  const ratio=(n,d)=>d?Math.max(0,Math.min(1,n/d)):0;
  const pct=(n,d)=>d?Math.round(n/d*100)+'%':'—';
  const meter=(n,d,label)=>`<div class="th-meter" role="progressbar" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="${d||1}" aria-valuenow="${Math.min(n,d)||0}"><i style="width:${ratio(n,d)*100}%"></i></div>`;
  const empty=text=>`<div class="th-empty"><span aria-hidden="true">◇</span><p>${esc(text)}</p><p class="small muted">可前往资料库导入题目，再回来选择练习。</p></div>`;
  function read(key){try{const p=JSON.parse(localStorage.getItem(key));if(p&&typeof p==='object')return {mode:p.mode==='blocks'?'blocks':'sets',motion:p.motion==='still'?'still':'auto',startedWorkbook:p.startedWorkbook,...Object.fromEntries(['book','paper','board','topic','blockPaper','blockMode','workbook','period','workbookSlot'].map(k=>[k,typeof p[k]==='string'?p[k]:'']))};}catch(_){}return {mode:'sets',book:'',paper:'',board:'',topic:'',blockPaper:'',blockMode:''};}
  function save(m){try{localStorage.setItem(m.key,JSON.stringify(m.pref));}catch(_){} }
  const books=m=>(m.d.sets||[]).filter(b=>b.sets?.length);
  const boards=m=>m.d.boards.filter(b=>b.total||b.pending||b.wrong||b.active);
  const book=m=>books(m).find(b=>b.book===m.pref.book);
  const paper=m=>book(m)?.sets.find(p=>p.name===m.pref.paper);
  const board=m=>boards(m).find(b=>b.board===m.pref.board);
  const blockPapers=m=>board(m)?.papers||[];
  const blockPaper=m=>blockPapers(m).find(p=>p.name===m.pref.blockPaper);
  const workbooks=m=>m.d.workbooks||[];
  const workbook=m=>workbooks(m).find(w=>w.name===m.pref.workbook);
  const periods=m=>workbook(m)?.periods||[];
  const period=m=>periods(m).find(p=>p.name===m.pref.period);
  const workbookSets=m=>period(m)?.sets||[];
  const workbookSet=m=>workbookSets(m).find(s=>s.slot===m.pref.workbookSlot);
  const canStartWorkbook=s=>!!s&&(s.active||s.total>0&&!s.errors?.length);
  const topics=m=>m.c.boards.find(b=>b.board===m.pref.board)?.topics||[];
  const run=(m,slot)=>(m.d.active_runs||[]).find(r=>r.board===slot);
  function normalize(m){
    const bs=books(m),rs=boards(m);
    if(!book(m))m.pref.book=(bs.find(b=>b.sets.some(p=>p.active))||bs[0])?.book||'';
    const b=book(m);if(!paper(m))m.pref.paper=b?.next||b?.sets[0]?.name||'';
    if(!board(m))m.pref.board=(rs.find(b=>b.active)||rs.find(b=>b.remaining)||rs[0])?.board||'';
    if(!topics(m).some(t=>t.name===m.pref.topic))m.pref.topic='';
    if(!blockPaper(m))m.pref.blockPaper=(blockPapers(m).find(p=>p.active)||blockPapers(m)[0])?.name||'';
    if(m.pref.blockMode==='workbook'&&m.env.subject!=='行测')m.pref.blockMode='';
    const hasActive=p=>p.sets.some(set=>set.active);
    if(!workbook(m)){
      const ws=workbooks(m);
      m.pref.workbook=(ws.find(w=>w.periods.some(hasActive))||ws[0])?.name||'';
    }
    if(!period(m)){
      const ps=periods(m);
      m.pref.period=(ps.find(hasActive)||ps[0])?.name||'';
    }
    if(!workbookSet(m)){
      const sets=workbookSets(m);
      m.pref.workbookSlot=(sets.find(s=>s.active)||sets.find(s=>!s.completed&&canStartWorkbook(s))||sets[0])?.slot||'';
    }
    // 只有刚开始的那套新增了结算记录，且已退出复盘，才默认选中后面一套。
    const selected=workbookSet(m),started=m.pref.startedWorkbook;
    if(selected&&!selected.active&&started?.slot===selected.slot&&selected.completed_count>started.count){
      const sets=workbookSets(m),next=sets.slice(sets.indexOf(selected)+1).find(s=>!s.completed&&canStartWorkbook(s));
      if(next)m.pref.workbookSlot=next.slot;
      delete m.pref.startedWorkbook;save(m);
    }
  }
  function tower(m){return m.d.tower||{layers:100,total:0,current:1,completed:0,floor_done:0,floor_total:0,remaining:0};}
  function stats(m){
    const done=m.d.boards.reduce((n,b)=>n+b.first_total,0),ok=m.d.boards.reduce((n,b)=>n+b.first_correct,0),wrong=m.d.boards.reduce((n,b)=>n+b.wrong,0);
    return `<div class="th-stats"><span><b>${done}</b> 已闯新题</span><span><b>${pct(ok,done)}</b> 首次正确率</span><span><b>${wrong}</b> ${esc(m.env.wrong)}</span></div>`;
  }
  function scene(m){
    if(!m.env.mage||m.env.painted)return paintedScene(m);       // painted：法考也有整张的塔前全景图时，同行测用“整图 + 两座山门热区”
    const t=tower(m),gate=(mode,title)=>`<button type="button" class="th-gate th-gate-${mode==='exam'?'sets':mode}" data-th-enter="${mode}" aria-label="进入${title}试炼" aria-haspopup="dialog" aria-controls="th-dialog"><span class="th-gate-stage"><img src="assets/beauty/trial/gate.png" data-day-art="assets/beauty/trial/gate.png" data-night-art="beauty/trial/gate-night.webp" alt="" aria-hidden="true"><span class="th-gate-label">${title}</span></span></button>`;
    return `<div class="th-world"><div class="th-landscape" aria-hidden="true"></div><div class="th-cloud th-cloud-back" aria-hidden="true"></div><div class="th-art" aria-hidden="true"><div class="th-art-halo"></div><div class="th-tower-stage"><img src="assets/beauty/trial/tower.png" data-day-art="assets/beauty/trial/tower.png" data-night-art="beauty/trial/tower-night.webp" alt="" class="th-tower-art"><span class="th-tower-inscription">${esc(m.env.title)}</span><i class="th-current-light" style="--th-light:${82-ratio(t.current,t.layers)*65}%"></i></div></div><div class="th-cloud th-cloud-front" aria-hidden="true"></div><div class="th-world-title"><p>${esc(m.env.mage?'王立学院 · 知识试炼':'青衡宗 · 百层问道')}</p><span>${t.layers} 层 · ${t.total} 道新题</span></div><div class="th-scene-tools">${m.env.catalogHtml?'<button type="button" data-th-enter="catalog" aria-haspopup="dialog" aria-controls="th-dialog">历年真题 ↗</button>':''}<button type="button" data-th-enter="history" aria-haspopup="dialog" aria-controls="th-dialog">练习记录 ↗</button>${m.env.contestEntry?'<button type="button" data-th-contest>模考与复盘 ↗</button>':''}</div>${m.env.examRoom?gate('exam','整卷'):gate('sets','套卷')}${gate('blocks','板块')}<div class="th-stele"><span>${t.summit?'已登顶':`正在攀登 · 第 <b>${t.current}</b> 层`}</span><p>${t.summit?`已完成 ${t.completed} 道新题`:`本层 ${t.floor_done} / ${t.floor_total} 道 · 再做 ${t.remaining} 道升层`}</p></div></div>`;
  }
  function paintedScene(m){
    const t=tower(m);
    const hero=window.BeautyArt?.heroFor?.('bank')||'assets/beauty/trial/hd/369/hall-day.webp';
    return `<div class="th-world th-painted" style="--th-fill:url(&quot;${esc(hero)}&quot;)"><div class="th-landscape th-panorama-wash" aria-hidden="true"></div><div class="th-painting"><img class="th-panorama" src="${esc(hero)}" alt="云海石台上的完整试炼塔与左右两座山门">${m.env.examRoom?'<button class="th-painted-gate th-painted-sets" data-th-enter="exam" aria-haspopup="dialog" aria-controls="th-dialog"><b>整卷模考</b><span>限时两小时 · 交卷批改</span></button>':'<button class="th-painted-gate th-painted-sets" data-th-enter="sets" aria-haspopup="dialog" aria-controls="th-dialog"><b>套卷试炼</b><span>一卷一程 · 循序问道</span></button>'}<button class="th-painted-gate th-painted-blocks" data-th-enter="blocks" aria-haspopup="dialog" aria-controls="th-dialog"><b>板块修习</b><span>专修一脉 · 精进所长</span></button></div><div class="th-world-title"><p>${esc(m.env.mage?'王立学院 · 知识试炼':'行测宗 · 百层问道')}</p><h2>${esc(m.env.title)}</h2><span>${t.layers} 层试炼 · ${t.total} 道新题</span></div><div class="th-scene-tools">${m.env.catalogHtml?'<button type="button" data-th-enter="catalog" aria-haspopup="dialog" aria-controls="th-dialog">历年真题 ↗</button>':''}<button type="button" data-th-enter="history" aria-haspopup="dialog" aria-controls="th-dialog">练习记录 ↗</button>${m.env.contestEntry?'<button type="button" data-th-contest>模考与复盘 ↗</button>':''}</div><div class="th-stele"><span>${t.summit?'百层登顶':`当前第 <b>${t.current}</b> 层`}</span><p>${t.summit?`已完成 ${t.completed} 道新题`:`本层 ${t.floor_done} / ${t.floor_total} 道 · 再做 ${t.remaining} 道升层`}</p></div></div>`;
  }
  function setsPane(m){
    const bs=books(m),b=book(m),p=paper(m);
    if(!b||!p)return empty('暂无可练习的套卷');
    return `<div class="th-filters"><label>选择题集<select data-th-book>${bs.map((x,i)=>`<option value="${i}" ${x===b?'selected':''}>${esc(x.book)}</option>`).join('')}</select></label></div><div class="th-selection"><span class="th-kicker">${p.active?'未完成 · 可继续':p.done>=p.total?'本套已完成':'本次套卷'}</span><h3>${esc(p.name)}</h3><p>共 ${p.total} 题 · 已完成 ${p.done} 题<span class="th-inline-note">${esc(Object.keys(p.boards||{}).join(' / '))}</span></p>${meter(p.done,p.total,'套卷进度')}</div><div class="th-list-head"><span>选择套卷</span><small>${b.finished} / ${b.sets.length} 套已完成</small></div><div class="th-choice-list" tabindex="0" aria-label="套卷目录">${b.sets.map((x,i)=>`<button type="button" class="th-choice" data-th-paper="${i}" aria-pressed="${x===p}"><span><b>${esc(x.name)}</b><small>${x.active?'进行中':x.done>=x.total?'已完成':'待练习'}</small></span><span class="th-choice-progress">${x.done}<small> / ${x.total}</small></span></button>`).join('')}</div>`;
  }
  function trainingMethod(m){
    const mode=m.pref.blockMode||m.d.order,options=[['seq','按顺序'],['shuffle','乱序']];
    if(!m.env.mage)options.push(['paper','按套卷训练']);
    if(m.env.subject==='行测')options.push(['workbook','按题本训练']);
    return `<label>训练方式<select class="bankOrder">${options.map(([v,label])=>`<option value="${v}" ${v===mode?'selected':''}>${label}</option>`).join('')}</select></label>`;
  }
  function blocksPane(m){
    if(m.pref.blockMode==='workbook')return workbookPane(m);
    const rs=boards(m),b=board(m);
    const method=trainingMethod(m);
    if(!b)return `<div class="th-filters">${method}</div>`+empty('暂无可练习的板块');
    const boardSelect=`<label>选择板块<select data-th-board>${rs.map((x,i)=>`<option value="${i}" ${x===b?'selected':''}>${esc(x.board)}</option>`).join('')}</select></label>`;
    if(m.pref.blockMode==='paper')return `<div class="th-filters">${boardSelect}${method}</div>`+blockPaperPane(m,b);
    const ts=topics(m),topic=ts.find(t=>t.name===m.pref.topic),active=run(m,topic?'点:'+b.board+':'+topic.name:b.board);
    return `<div class="th-filters">${boardSelect}<label>知识点<select data-th-topic><option value="">全部知识点</option>${ts.map((x,i)=>`<option value="${i}" ${x===topic?'selected':''}>${esc(x.name)} · 余 ${x.left} 题</option>`).join('')}</select></label></div><div class="th-selection"><span class="th-kicker">${active?'未完成 · 可继续':'本次板块'}</span><h3>${esc(b.board)}${topic?' · '+esc(topic.name):''}</h3><p>${topic?`剩余 ${topic.left} / ${topic.count} 题`:`剩余 ${b.remaining} / ${b.total} 题`} · 首次正确率 ${pct(b.first_correct,b.first_total)}</p>${meter(topic?topic.count-topic.left:b.total-b.remaining,topic?topic.count:b.total,'板块进度')}</div><div class="th-practice-options">${method}<label>每组题数<select id="bankCount">${[10,15,20].map(n=>`<option value="${n}" ${n===m.d.count?'selected':''}>${n} 题</option>`).join('')}</select></label></div><div class="th-block-notes"><p>每次从未做过的题中练一组，交卷后查看答案与解析。已有练习保留原题目和进度。</p>${b.pending?`<p>${b.pending} 道题待补答案，暂不参与出题。</p>`:''}${b.errors.length?`<details class="th-error"><summary>本板块有 ${b.errors.length} 项资料问题</summary><p>${b.errors.map(esc).join('<br>')}</p></details>`:''}${m.c.boards.find(x=>x.board===b.board)?.more_topics?'<p>此处展示常用知识点；完整目录可在资料库中查看。</p>':''}</div>`;
  }
  function blockPaperPane(m,b){
    const ps=blockPapers(m),p=blockPaper(m);
    return `<div class="th-list-head"><span>选择来源套卷</span><small>${ps.length} 套可练</small></div>
      <div class="th-choice-list" tabindex="0" aria-label="板块来源套卷">${ps.map((x,i)=>`<button class="th-choice" type="button" data-th-block-paper="${i}" aria-pressed="${x===p}"><span><b>${esc(x.name)}</b><small>${x.active?'继续已保存进度':'完整练习本卷的'+esc(b.board)}</small></span><span class="th-choice-progress">${x.total}<small> 道</small></span></button>`).join('')||'<p class="th-empty">没有可用的来源套卷。题目须有试卷信息或规范套卷编号。</p>'}</div>`;
  }
  function workbookStatus(set){
    if(set.active)return '进行中 · 已答 '+set.done+' 题';
    if(set.errors?.length)return '资料错误 · '+esc(set.errors[0])+(set.errors.length>1?'（共 '+set.errors.length+' 项）':'');
    const status=set.completed?'已交卷':set.total?'待练习':'';
    return [status,set.pending?set.pending+' 题待补答案':''].filter(Boolean).join(' · ');
  }
  function workbookPane(m){
    const w=workbook(m),p=period(m),sets=workbookSets(m),selected=workbookSet(m);
    const filters=`<div class="th-filters">${trainingMethod(m)}
      ${w?`<label>老师题本<select data-th-workbook>${workbooks(m).map((x,i)=>`<option value="${i}" ${x===w?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label>`:''}
      ${p?`<label>期数<select data-th-period>${periods(m).map((x,i)=>`<option value="${i}" ${x===p?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label>`:''}</div>`;
    if(!sets.length)return filters+empty('暂无可练习的题本套次');
    return filters+`<div class="th-list-head"><span>选择套次</span><small>本期 ${sets.length} 套</small></div>
      <div class="th-choice-list" tabindex="0" aria-label="题本套次">${sets.map((x,i)=>`<button type="button" class="th-choice" data-th-workbook-set="${i}" aria-pressed="${x===selected}"><span><b>${esc(x.name)}</b><small>${workbookStatus(x)}</small></span><span class="th-choice-progress">${x.total}<small> 道</small></span></button>`).join('')}</div>`;
  }
  function historyPane(m){
    return `<div class="th-list-head"><span>练习记录</span><small>最近 ${m.d.groups.length} 组</small></div><div class="th-choice-list th-history" tabindex="0" aria-label="练习记录">${m.d.groups.map(x=>`<button type="button" class="th-history-row" data-th-history="${x.group}" aria-label="复盘 ${esc(x.label||x.board)} ${esc(x.date)}"><div><b>${esc(x.label||x.board)}</b><small>${esc(x.date)} · ${x.mode==='new'?'新题练习':'错题复习'}</small></div><span><b>${x.correct} / ${x.total}</b><small>${esc(m.env.rank(x.rank))}</small></span></button>`).join('')||'<p class="th-empty">尚未留下练习记录。</p>'}</div>`;
  }
  function footer(m){
    if(m.view==='catalog')return `<div class="th-action-note">历年真题按原年份、卷次与科目练习，未核验答案不判分。</div><button data-th-return type="button">返回塔前</button>`;
    if(m.view==='exam')return `<div class="th-action-note">限时作答，交卷后批改并记进宗门大比；分模块练习请走右边“板块”。</div><button data-th-return type="button">返回塔前</button>`;
    if(m.view==='history')return `<div class="th-action-note">成绩和进度沿用原有练习记录。</div><button data-th-return type="button">返回塔前</button>`;
    if(m.pref.mode==='sets'){
      const p=paper(m);return `<div class="th-action-note">整套练习保留套卷题数，已做过的题不再出。<span class="th-save-status" role="status"></span></div><button class="primary th-start" data-th-start ${!p||!p.active&&p.done>=p.total?'disabled':''}>${p?.active?'继续本套':p&&p.done>=p.total?'本套已完成':'开始本套'} <span aria-hidden="true">→</span></button>`;
    }
    if(m.pref.blockMode==='workbook'){
      const p=workbookSet(m);
      return `<div class="th-action-note">${p?esc(p.name)+' · 可练 '+p.total+' 道'+(p.pending?'，'+p.pending+' 道待补答案':''):''}</div><button class="primary th-start" data-th-start ${canStartWorkbook(p)?'':'disabled'}>${p?.active?'继续本套':p?.completed?'再练本套':'开始本套'} <span aria-hidden="true">→</span></button>`;
    }
    if(m.pref.blockMode==='paper'){
      const p=blockPaper(m),b=board(m);return `<div class="th-action-note">${p?'来源：'+esc(p.name)+' · '+p.total+' 道'+esc(b.board)+'，按原卷题序整组练习。':'请选择可用的来源套卷'}<span class="th-save-status" role="status"></span></div><button class="primary th-start" data-th-start ${!p||b.errors.length?'disabled':''}>${p?.active?'继续本卷板块':'开始本卷板块'} <span aria-hidden="true">→</span></button>`;
    }
    const b=board(m),topic=topics(m).find(t=>t.name===m.pref.topic),active=b&&run(m,topic?'点:'+b.board+':'+topic.name:b.board),remaining=topic?topic.left:b?.remaining;
    return `<div class="th-action-note">交卷后统一判分 · 复习不重复计算新题进度<span class="th-save-status" role="status"></span></div><div class="th-action-buttons"><button data-th-review ${!b||b.active||!b.wrong?'disabled':''}>复习本板块错题${b?.wrong?' '+b.wrong:''}</button><button class="primary th-start" data-th-start ${!b||!active&&(!remaining||b.errors.length)?'disabled':''}>${active?'继续练习':'开始练习'} <span aria-hidden="true">→</span></button></div>`;
  }
  function html(d,c,env){
    const key='trial-hall-v1:'+encodeURIComponent(env.subject+':'+env.scope),pref=read(key),m={d,c,env,key,pref,view:env.examRoom&&pref.mode==='sets'?'exam':pref.mode,busy:false};normalize(m);model=m;
    return `<section class="trial-hall ${env.mage&&!env.painted?'th-mage':'th-sect'} ${pref.motion==='still'?'th-still':''}" aria-label="${esc(env.title)}">${scene(m)}<dialog id="th-dialog" class="th-dialog scene-panel" aria-labelledby="th-dialog-title"><header class="th-dialog-head"><div><p class="th-eyebrow">${esc(env.mage?'学院试炼卷宗':'试炼塔 · 修习卷宗')} · 第 ${tower(m).current} 层</p><h2 id="th-dialog-title">选择试炼</h2></div><button type="button" data-th-close aria-label="关闭练习面板，返回塔前">返回塔前 ×</button></header>${stats(m)}<div class="th-panels">${[env.examRoom?['exam',()=>window.EXAM_ROOM.paneHtml()]:['sets',setsPane],['blocks',blocksPane],['history',historyPane],...(env.catalogHtml?[['catalog',m=>m.env.catalogHtml]]:[])].map(([id,render])=>`<section id="th-pane-${id}" class="th-pane" role="region" aria-label="${esc({sets:'套卷试炼',exam:'整卷模拟考试',blocks:'板块试炼',history:'练习记录',catalog:'历年真题'}[id])}" ${m.view===id?'':'hidden'}>${render(m)}</section>`).join('')}</div><footer class="th-actions">${footer(m)}</footer></dialog></section>`;
  }
  function bind(root,hooks){
    const host=root.querySelector('.trial-hall'),m=model;if(!host||!m||host.dataset.thBound)return;host.dataset.thBound='1';
    const painted=host.querySelector('.th-painted');
    if(painted)painted.insertAdjacentHTML('afterbegin','<div class="th-edge-fill" aria-hidden="true"><i class="th-edge-top"></i><i class="th-edge-bottom"></i><i class="th-edge-left"></i><i class="th-edge-right"></i></div>');
    const dialog=host.querySelector('.th-dialog');let opener=null;
    function close(){dialog.close();opener?.focus({preventScroll:true});}
    dialog.addEventListener('cancel',e=>{if(e.target!==dialog)return;e.preventDefault();close();});     // 文件选择框取消时的cancel事件会冒泡上来，不能把整个面板关掉（踩坑记录 2026-10-26）
    function tabState(){host.dataset.thView=m.view;host.querySelector('#th-dialog-title').textContent={sets:'套卷试炼',exam:'整卷模拟考试',blocks:'板块试炼',history:'练习记录',catalog:'历年真题卷轴'}[m.view];host.querySelectorAll('.th-pane').forEach(p=>p.hidden=p.id!=='th-pane-'+m.view);}
    function actions(){host.querySelector('.th-actions').innerHTML=footer(m);host.querySelectorAll('.th-start,[data-th-review],.bankOrder,#bankCount').forEach(b=>{if(m.busy)b.disabled=true;});}
    function refreshPane(id){host.querySelector('#th-pane-'+id).innerHTML=(id==='sets'?setsPane:blocksPane)(m);actions();}
    function scrollChoice(){
      const list=host.querySelector('.th-pane:not([hidden]) .th-choice-list'),choice=list?.querySelector('[aria-pressed=true]');
      if(choice&&list.clientHeight)list.scrollTop+=choice.getBoundingClientRect().top-list.getBoundingClientRect().top;
    }
    function selectTab(id){m.view=id;if(id==='sets'||id==='blocks'){m.pref.mode=id;save(m);}tabState();actions();if(id==='sets')scrollChoice();}
    host.addEventListener('click',e=>{
      const b=e.target.closest('button');if(!b||b.disabled)return;
      if(b.hasAttribute('data-th-enter')){opener=b;selectTab(b.dataset.thEnter);measure();dialog.showModal();scrollChoice();if(m.view==='exam')window.EXAM_ROOM.mount(host.querySelector('#th-pane-exam'),hooks);host.querySelector('[data-th-close]').focus();return;}
      if(b.hasAttribute('data-th-contest'))return window.go?.('contest');      // 竞技场（大比：模考成绩、走势、复盘）不再占地图，从塔里进
      if(b.hasAttribute('data-th-close'))return close();
      if(b.hasAttribute('data-th-return'))return close();
      if(b.hasAttribute('data-th-history')){const x=m.d.groups.find(x=>x.group===Number(b.dataset.thHistory));if(x){dialog.close();hooks.start({type:'bank_review',group:x.group,board:x.board,title:'练习记录复盘 · '+(x.label||x.board)});}return;}
      if(b.hasAttribute('data-th-paper')){const p=book(m)?.sets[Number(b.dataset.thPaper)];if(!p)return;m.pref.paper=p.name;save(m);const list=host.querySelector('#th-pane-sets .th-choice-list'),top=list.scrollTop;refreshPane('sets');host.querySelector('#th-pane-sets .th-choice-list').scrollTop=top;host.querySelector(`[data-th-paper="${b.dataset.thPaper}"]`)?.focus({preventScroll:true});return;}
      if(b.hasAttribute('data-th-block-paper')||b.hasAttribute('data-th-workbook-set')){
        if(b.hasAttribute('data-th-block-paper'))m.pref.blockPaper=blockPapers(m)[Number(b.dataset.thBlockPaper)].name;
        else {
          const slot=workbookSets(m)[Number(b.dataset.thWorkbookSet)].slot;
          if(slot!==m.pref.workbookSlot)delete m.pref.startedWorkbook;
          m.pref.workbookSlot=slot;
        }
        b.parentElement.querySelector('[aria-pressed=true]')?.setAttribute('aria-pressed','false');
        b.setAttribute('aria-pressed','true');save(m);actions();return;
      }
      if(!b.hasAttribute('data-th-start')&&!b.hasAttribute('data-th-review'))return;
      const review=b.hasAttribute('data-th-review'),p=paper(m),r=board(m);
      if(m.pref.mode==='blocks'&&m.pref.blockMode==='workbook'){
        const set=workbookSet(m);
        if(canStartWorkbook(set)){
          const inReview=set.active&&run(m,set.slot)?.phase==='review';
          m.pref.startedWorkbook={slot:set.slot,count:set.completed_count-(inReview?1:0)};save(m);
          dialog.close();hooks.start({type:'bank',board:set.slot,target:set.slot,title:[workbook(m).name,period(m).name,set.name].join(' · ')});
        }
        return;
      }
      const byPaper=m.pref.mode==='blocks'&&m.pref.blockMode==='paper'&&!review;
      const slot=m.pref.mode==='sets'?'套:'+p.name:byPaper?blockPaper(m).slot:!review&&m.pref.topic?'点:'+r.board+':'+m.pref.topic:r.board;
      dialog.close();
      hooks.start({type:review?'bank_review':'bank',board:slot,target:slot,title:m.pref.mode==='sets'?p.name:byPaper?r.board+' · '+blockPaper(m).name:r.board+(m.pref.topic&&!review?' · '+m.pref.topic:'')});
    });
    host.addEventListener('change',async e=>{
      const el=e.target;
      if(el.matches('[data-th-book]')){m.pref.book=books(m)[Number(el.value)]?.book||'';m.pref.paper='';normalize(m);save(m);refreshPane('sets');scrollChoice();host.querySelector('[data-th-book]').focus();}
      else if(el.matches('[data-th-workbook],[data-th-period]')){
        const bookChanged=el.matches('[data-th-workbook]');
        if(bookChanged){m.pref.workbook=workbooks(m)[Number(el.value)].name;m.pref.period='';}
        else m.pref.period=periods(m)[Number(el.value)].name;
        m.pref.workbookSlot='';normalize(m);save(m);refreshPane('blocks');scrollChoice();host.querySelector(bookChanged?'[data-th-workbook]':'[data-th-period]').focus();
      }
      else if(el.matches('[data-th-board]')){m.pref.board=boards(m)[Number(el.value)]?.board||'';m.pref.topic='';normalize(m);save(m);refreshPane('blocks');host.querySelector('[data-th-board]').focus();}
      else if(el.matches('[data-th-topic]')){m.pref.topic=el.value===''?'':topics(m)[Number(el.value)]?.name||'';save(m);refreshPane('blocks');host.querySelector('[data-th-topic]').focus();}
      else if(el.matches('.bankOrder,#bankCount')){
        if(el.matches('.bankOrder')&&['paper','workbook'].includes(el.value)){m.pref.blockMode=el.value;normalize(m);save(m);refreshPane('blocks');scrollChoice();host.querySelector('.bankOrder').focus();return;}
        if(m.busy)return;
        const field=el.id==='bankCount'?'count':'order',old=m.d[field],value=field==='count'?Number(el.value):el.value;
        let saved=false;m.busy=true;actions();
        try{
          await hooks.api('/api/bank/count',{[field]:value});m.d[field]=value;saved=true;
          if(field==='order'&&m.pref.blockMode){m.pref.blockMode='';save(m);}
        }
        catch(error){el.value=String(old);hooks.error(error);}
        finally{m.busy=false;refreshPane('blocks');host.querySelectorAll('.bankOrder,#bankCount').forEach(n=>n.disabled=false);actions();const status=host.querySelector('.th-save-status');if(status&&saved)status.textContent='已保存，下一组生效';}
      }
    });
    tabState();
    function measure(){
      // 题字以实际建筑图片为坐标，避开object-fit在电脑/平板产生的留白。
      host.querySelectorAll('.th-gate-stage,.th-tower-stage').forEach(stage=>{const img=stage.querySelector('img'),r=stage.parentElement.getBoundingClientRect(),aspect=img.naturalWidth&&img.naturalHeight?img.naturalWidth/img.naturalHeight:2/3,width=Math.min(r.width,r.height*aspect);stage.style.width=width+'px';stage.style.height=width/aspect+'px';});
      const r=root.getBoundingClientRect();
      const painting=host.querySelector('.th-painting');if(painting){const bounds=painting.parentElement.getBoundingClientRect(),contain=Math.min(bounds.width,bounds.height*4/3),
        // 横向铺满：把4:3塔景放大到贴住左右两边，只裁掉底部多出的石阶；塔尖到两座山门一定留在画面内（保留上方78%）。
        // 竖屏等本来就比4:3窄的窗口仍整幅显示；超宽屏幕放大到保留78%为止，剩下的缝由同图模糊延伸补上。
        w=Math.max(contain,Math.min(bounds.width,bounds.height/(0.78*0.75)));
      painting.style.width=w+'px';painting.style.height=w*3/4+'px';painting.classList.toggle('th-fill',w*3/4>bounds.height+1);const side=w<bounds.width-1&&w*3/4>=bounds.height-1;painting.classList.toggle('th-gap',side);painting.parentElement.classList.toggle('th-side-gap',side);
      const vertical=Math.max(0,(bounds.height-w*3/4)/2),horizontal=Math.max(0,(bounds.width-w)/2);
      painting.parentElement.style.setProperty('--th-gap-y',vertical+'px');painting.parentElement.style.setProperty('--th-gap-x',horizontal+'px');painting.parentElement.classList.toggle('th-vertical-gap',vertical>1);}
      for(const [k,v]of Object.entries({width:r.width,height:r.height,left:r.left,top:r.top}))if(dialog.style.getPropertyValue('--th-'+k)!==v+'px')dialog.style.setProperty('--th-'+k,v+'px');
      dialog.classList.toggle('th-compact',r.height<520);
    }
    const resize=new ResizeObserver(()=>{if(!host.isConnected)return resize.disconnect();measure();});resize.observe(host);
    // 尺寸偏好改变只影响卷宗，整幅塔景保持铺满；离开路由后原生dialog随DOM销毁。
    new MutationObserver((_,observer)=>{if(!host.isConnected)return observer.disconnect();measure();}).observe(root,{attributes:true,attributeFilter:['style']});
    host.querySelector('.th-tower-art,.th-panorama')?.addEventListener('error',()=>host.classList.add('th-art-missing'),{once:true});
  }
  window.TRIAL_HALL={html,bind};
})();
