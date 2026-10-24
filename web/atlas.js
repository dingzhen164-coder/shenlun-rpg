/* 用户提供的时政地图交互，接入程序后端进度与共用词义批注；内容由/api/politics/atlas提供。 */
const EXAM=new URLSearchParams(location.search).get('exam')||'2026-10-guokao';
const api=(url,body={})=>parent.api(url,{...body,exam:EXAM});
function syncAtlasTheme(){
 const palette=getComputedStyle(parent.document.body);
 for(let i=0;i<palette.length;i++){const key=palette[i];if(key.startsWith('--'))document.documentElement.style.setProperty(key,palette.getPropertyValue(key));}
 document.documentElement.dataset.theme=parent.document.documentElement.dataset.theme||'light';
}
syncAtlasTheme();new MutationObserver(syncAtlasTheme).observe(parent.document.documentElement,{attributes:true,attributeFilter:['data-theme','class']});
new MutationObserver(syncAtlasTheme).observe(parent.document.body,{attributes:true,attributeFilter:['class']});
(async()=>{

'use strict';
const {data:D,progress:initialProgress,exam}=await api('/api/politics/atlas');
document.title=exam.title;
document.querySelector('#nav').setAttribute('aria-label',exam.title);
const $=s=>document.querySelector(s),app=$('#app');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state={...initialProgress,digest:initialProgress.digest||{}},lastSnapshot=JSON.parse(JSON.stringify(state)),saveQueue=Promise.resolve();
let view='month',selected=null,tab='understand',filterChapter='all',filterStatus='all',practiceTheme='all',practiceChapter='all',practiceWrong=false,practiceIndex=0,query='',lastView='overview';
const mat=id=>D.materials.find(x=>x.id===id),theme=id=>D.themes.find(x=>x.id===id),cat=id=>D.categories.find(x=>x.id===id);
const statusLabel={new:'未学',review:'待巩固',done:'已掌握'};
const materialsFor=t=>D.materials.filter(m=>m.tags.includes(t));
function toast(t){$('#toast').textContent=t;$('#toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').hidden=true,2800)}
function save(){
 const changes=[];
 for(const field of ['status','attempts','digest'])for(const id of new Set([...Object.keys(lastSnapshot[field]),...Object.keys(state[field])])){
  if(JSON.stringify(lastSnapshot[field][id])!==JSON.stringify(state[field][id]))changes.push({field,id,value:state[field][id]??null});
 }
 lastSnapshot=JSON.parse(JSON.stringify(state));updateSidebar();
 saveQueue=saveQueue.then(async()=>{for(const change of changes)await api('/api/politics/progress',change);}).catch(async e=>{
  toast('进度未保存：'+e.message);
  try{const current=await api('/api/politics/atlas');state={...current.progress,digest:current.progress.digest||{}};lastSnapshot=JSON.parse(JSON.stringify(state));render();}catch(_){}
 });
 return saveQueue;
}
function updateSidebar(){let done=D.materials.filter(m=>state.status[m.id]==='done').length;$('#progressCount').textContent=done+'/'+D.materials.length;$('#progressBar').style.width=(D.materials.length?done/D.materials.length*100:0)+'%';document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('active',b.dataset.go===(['category','theme','material','materials'].includes(view)?'sprint':view)))}
$('#atlasBack').onclick=()=>parent.STUDY_REGIONS.back();
$('#atlasSearch').onclick=()=>{const bar=$('#atlasSearchBar'),open=bar.hidden;bar.hidden=!open;$('#atlasSearch').setAttribute('aria-expanded',String(open));if(open)$('#search').focus();else{query='';$('#search').value='';render();}};
$('#sideTopics').innerHTML=D.categories.map(c=>`<button data-category="${c.id}"><span class="dot" style="background:${c.color}"></span>${c.name}</button>`).join('');
function navigate(v,id=null){view=v;selected=id;query='';$('#search').value='';if(v==='material')tab='original';render();window.scrollTo({top:0,behavior:'instant'})}
// 移除站点大标题和说明，页面首屏直接进入知识与正文。
function head(){return ''}
function crumb(){return ''}
function statusSelect(m){return `<select class="status" data-status="${m.id}" aria-label="${esc(m.title)}学习状态">${Object.entries(statusLabel).map(([v,n])=>`<option value="${v}" ${(state.status[m.id]||'new')===v?'selected':''}>${n}</option>`).join('')}</select>`}
function routeForTheme(id){return cat(theme(id).category)}
function routeForMaterial(m){return routeForTheme(m.tags[0])}
function routeStyle(c){return `--route:${c.color};--route-soft:${c.color}12`}
function routeBadges(m){return `<div class="route-badges">${D.categories.filter(c=>m.tags.some(t=>c.themes.includes(t))).map(c=>`<button style="${routeStyle(c)}" data-category="${c.id}">${c.name}</button>`).join('')}</div>`}
// Discard PDF line wrapping while retaining semantic headings, clauses and options.
function sourceHeadingLevel(text){
 if(/[。；！？]/.test(text))return 0;
 if(/^(?:[一二三四五六七八九十百]+[、．.]|《.*》$)/.test(text))return 1;
 if(/^[（(][一二三四五六七八九十百]+[）)]/.test(text))return 2;
 return 0;
}
function sourceBlocks(text){
 const lines=text.replace(/\r\n?/g,'\n').split('\n').map(l=>l.trim()).filter(Boolean),blocks=[];
 const startsBlock=l=>/^(?:【|[一二三四五六七八九十百]+[、．.]|[（(](?:[一二三四五六七八九十百]+|\d+)[）)]|\d+[.．、]|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]|[A-D][.．、]|第[一二三四五六七八九十]+[，、]|[一二三四五六七八九十]+是|《)/.test(l);
 const heading=l=>sourceHeadingLevel(l)>0||!/[。；！？]/.test(l) && !/\d+[.．]【/.test(l) && ((l.length<=32 && /^(?:[一二三四五六七八九十百]+[、．.]|[（(](?:[一二三四五六七八九十百]+|\d+)[）)]|\d+[.．、])/.test(l)) || /^《.*》$/.test(l));
 let current='';
 for(const line of lines){
  if(current && (startsBlock(line)||/[。！？；：:]$/.test(current)||heading(current)||/^【[^】]+】$/.test(current))){blocks.push(current);current=''}
  if(current && /[A-Za-z]$/.test(current)&&/^[A-Za-z]/.test(line))current+=' ';
  current+=line;
 }
 if(current)blocks.push(current);
 return blocks;
}
// PDF emphasis uses exact source offsets, including simulated bold from text strokes.
function formatOriginal(text,emphasis=[]){
 const weights=[];
 for(let i=0,r=0;i<text.length;i++){
  if(/\s/.test(text[i]))continue;
  while(r<emphasis.length&&i>=emphasis[r][1])r++;
  weights.push(r<emphasis.length&&i>=emphasis[r][0]&&i<emphasis[r][1]);
 }
 let cursor=0;
 const inline=block=>{
  let output='',active=false;
  for(const c of block){
   const emphasized=/\s/.test(c)?active:!!weights[cursor++];
   if(emphasized!==active){output+=emphasized?'<strong class="source-emphasis">':'</strong>';active=emphasized}
   output+=esc(c);
  }
  return output+(active?'</strong>':'');
 };
 return sourceBlocks(text).map(b=>{
  const content=inline(b),level=sourceHeadingLevel(b);let cls='';
  if(level){const tag=level===1?'h2':'h3';return `<${tag} class="source-heading source-main-heading" data-source-level="${level}">${esc(b)}</${tag}>`}   // 标题一律不加红
  if(/^【[^】]+】$/.test(b))cls='source-label';
  else if(b.length<=64&&/^(?:[一二三四五六七八九十百]+[、．.]|[（(](?:[一二三四五六七八九十百]+|\d+)[）)]|\d+[.．、]|《)/.test(b)&&!/[。；！？]/.test(b))return `<h3 class="source-heading">${esc(b)}</h3>`;   // 标题一律不加红（content只用于正文）
  else if(/^(?:[（(]\d+[）)]|[①②③④⑤⑥⑦⑧⑨⑩]|第[一二三四五六七八九十]+[，、]|[一二三四五六七八九十]+是)/.test(b))cls='source-item';
  return `<p${cls?` class="${cls}"`:''}>${content}</p>`;
 }).join('');
}
function tags(m){return `<div class="tags">${m.tags.map(t=>`<button class="tag" style="${routeStyle(routeForTheme(t))}" data-theme="${t}">${theme(t).name}</button>`).join('')}</div>`}
function card(m){return `<article class="material" style="${routeStyle(routeForMaterial(m))}"><div class="chapter-label">${D.chapters[m.chapter]} · ${m.date}</div><button class="titlebtn" data-material="${m.id}">${esc(m.title)}</button><div class="material-meta">配套${m.questions.length}题</div><p>${esc(m.why)}</p>${routeBadges(m)}<div class="cardfoot"><button class="btn" data-material="${m.id}">展开学习 ↗</button>${statusSelect(m)}</div></article>`}
function categoryView(){const c=cat(selected),ms=D.materials.filter(m=>m.tags.some(t=>c.themes.includes(t)));return crumb([esc(c.name)])+head('LEARNING ROUTE',c.name,c.question+' '+c.desc)+`<div class="topicintro" style="--c:${c.color};${routeStyle(c)}"><strong>这条主线关注什么</strong><p>${{goal:'先定位总体目标、发展要求与阶段任务，再把历史经验和新征程使命放回这条时间线。',engine:'从需求、技术、产业、制度与空间组织五方面，看发展动力怎样形成。',people:'把政策还原为人的就业、收入、成长、健康与居住需求，理解发展成果怎样进入生活。',support:'把组织执行、规则约束、生态可持续与风险治理放在一起看。这些领域也有独立目标，保障只是学习视角。',world:'区分经济开放、国际平台合作与两岸关系；不同对象和场合，对应不同重点表述。'}[c.id]||c.desc}</p></div><div class="toolbar">${c.themes.map(t=>`<button class="btn" data-theme="${t}">${theme(t).name} · ${materialsFor(t).length}</button>`).join('')}</div><div class="section-title"><h2>关联材料</h2><small>${ms.length}份 · 跨章节汇集</small></div><div class="material-grid">${ms.map(card).join('')}</div>`}
function themeView(){const t=theme(selected),c=cat(t.category),ms=materialsFor(t.id);return crumb([`<button data-category="${c.id}">${c.name}</button>`,esc(t.name)])+head('TOPIC CONNECTIONS',t.name,t.question,`<button class="btn primary" data-practice-theme="${t.id}">练相关题目</button>`)+`<div class="topicintro" style="--c:${c.color};${routeStyle(c)}"><strong>理解提示 · 学习框架</strong><p>${t.meaning}</p><strong>做题时分清</strong><p>${t.pitfall}</p></div><div class="section-title"><h2>同一主题，不同出处</h2><button class="btn primary" data-practice-theme="${t.id}">练相关题目</button></div><div class="material-grid">${ms.map(card).join('')}</div>`}
const sourceKinds=['重大会议','讲话','指导','文件'];
function sprintDirectory(){
 const groups=sourceKinds.map((kind,i)=>{const items=D.materials.filter(m=>m.chapter===i&&!m.practice_only);return `<details class="sprint-group" open><summary>${kind}<small>${items.length}份</small></summary><div>${items.map(m=>`<button class="sprint-document titlebtn" data-material="${m.id}"><span>${esc(m.title)}</span><small>共计${Array.from(String(m.original||'').replace(/\s/g,'')).length}字</small></button>`).join('')||'<p class="hint">暂无资料，可在政治理论页统一导入。</p>'}</div></details>`;});
 return `<aside class="sprint-index" aria-label="冲刺学习目录"><div class="sprint-index-label">研习目录</div>${D.materials.some(m=>!m.practice_only)?'':'<p class="empty">尚未加入冲刺学习资料，请返回政治理论页统一导入PDF。</p>'}${groups.join('')}</aside>`;
}
function sprintView(){
 return `<div class="sprint-workspace">${sprintDirectory()}<section class="sprint-welcome"><h2>循目录，读原文</h2><p>从左侧四类目录中选择一份资料，开始研读、消化与精卷。</p></section></div>`;
}
function digestView(m){return m.digestError?`<p class="sprint-digest-tip">${esc(m.digestError)}</p><button class="btn" data-action="retryDigest">重试读取清单</button>`:WANXIANG_DIGEST.html(m.digestData);}
function materialView(){
 const m=mat(selected);if(!m)return sprintView();
 const panel=tab==='original'?`<section class="panel sprint-original"><div class="original">${formatOriginal(m.original,m.originalEmphasis)}</div></section>`:tab==='understand'?digestView(m):m.questions.map(id=>questionCard(D.questions.find(q=>q.id===id))).join('')||'<p class="hint">本份材料暂无精卷题目。</p>';
 return `<div class="atlas-reading-tools"><button class="btn" data-go="sprint">← 时政栏目</button><div class="tabs" role="tablist" aria-label="冲刺学习方式">${[['original','研读'],['understand','消化'],['questions','精卷']].map(([v,n])=>`<button role="tab" aria-selected="${tab===v}" class="${tab===v?'active':''}" data-tab="${v}">${n}</button>`).join('')}</div><span class="atlas-status-inline">${statusSelect(m)}</span></div><div class="sprint-workspace">${sprintDirectory()}<article class="sprint-document-body"><h2 class="sprint-document-title">${esc(m.title)}</h2>${panel}</article></div>`;
}
const draftAnswers={};
function formatQuestion(text){return WANXIANG_TEXT.html(text);}
function questionCard(q){
 q={...q,text:q.text||q.layout_text};
 const a=state.attempts[q.id],m=mat(q.material),multi=(q.answer||'').length>1,draft=draftAnswers[q.id]||'';
 return `<article class="question" id="q${q.id}"><div class="qtop"><span class="chip">第${q.id}题${multi?' · 多选':''}</span><button class="tag" data-material="${m.id}">${esc(m.title)} ↗</button></div><div class="qtext">${formatQuestion(q.text)}</div>${q.answer?`<div class="answer-options" role="group" aria-label="第${q.id}题作答">${['A','B','C','D'].map(v=>`<button ${multi?`data-multi-choice="${q.id}" aria-pressed="${draft.includes(v)}"`:`data-answer="${q.id}"`} data-value="${v}" class="${a?(q.answer.includes(v)?'correct':a.choice.includes(v)?'wrong':''):draft.includes(v)?'selected':''}" ${a?'disabled':''}>${v}</button>`).join('')}</div>${multi&&!a?`<button class="btn primary" data-submit-answer="${q.id}" ${draft?'':'disabled'}>确认作答</button>`:''}`:'<p class="hint">原PDF未提供参考答案，暂不判分；请结合讲义自行核对。</p>'}${a?`<div class="feedback ${a.choice!==q.answer?'wrong':''}"><b>${a.choice===q.answer?'答对了':'需要再辨析'}：你选${esc(a.choice)}，讲义参考答案为${esc(q.answer)}。</b><details class="atlas-answer-analysis"><summary>题目解析</summary><p>${esc(q.analysis||m.trap)}</p></details><button class="btn" data-original="${m.id}">回到讲义找依据</button> <button class="btn" data-retry="${q.id}">重新作答</button></div>`:''}</article>`;
}

let practiceMaterial=null;
const isImportedQuestion=q=>(D.practice_question_ids||[]).includes(q.id);
function practiceList(){return D.questions.filter(q=>isImportedQuestion(q)&&(!practiceMaterial||q.material===practiceMaterial)&&(practiceTheme==='all'||q.tags.includes(practiceTheme))&&(practiceChapter==='all'||mat(q.material).chapter===Number(practiceChapter))&&(!practiceWrong||(state.attempts[q.id]&&state.attempts[q.id].choice!==q.answer)))}
function practiceView(){const qs=practiceList();practiceIndex=Math.min(practiceIndex,Math.max(0,qs.length-1));const attempted=D.questions.filter(q=>isImportedQuestion(q)&&state.attempts[q.id]),correct=attempted.filter(q=>state.attempts[q.id].choice===q.answer);return head('RECALL & PRACTICE','把理解，变成判断依据',`${D.questions.filter(isImportedQuestion).length}道已导入配套题`)+`<div class="practice-stats"><div><b>${attempted.length}</b><span class="hint">已作答</span></div><div><b>${correct.length}</b><span class="hint">当前答对</span></div><div><b>${attempted.length-correct.length}</b><span class="hint">待订正</span></div></div><div class="toolbar"><select id="practiceTheme" aria-label="练习主题"><option value="all">全部主题</option>${D.themes.map(t=>`<option value="${t.id}" ${practiceTheme===t.id?'selected':''}>${t.name}</option>`).join('')}</select><select id="practiceChapter" aria-label="练习章节"><option value="all">全部章节</option>${D.chapters.map((c,i)=>`<option value="${i}" ${String(practiceChapter)===String(i)?'selected':''}>${c}</option>`).join('')}</select><button class="btn ${practiceWrong?'primary':''}" data-action="wrong">${practiceWrong?'✓ ':''}只看错题</button>${practiceMaterial?`<button class="btn" data-action="clearMaterial">清除材料筛选：${esc(mat(practiceMaterial).title)} ×</button>`:''}</div><div class="section-title"><h2>${qs.length?`当前 ${practiceIndex+1} / ${qs.length}`:'没有符合条件的题目'}</h2><div><button class="btn" data-action="prev" ${practiceIndex===0?'disabled':''}>← 上一题</button> <button class="btn" data-action="next" ${practiceIndex>=qs.length-1?'disabled':''}>下一题 →</button></div></div>${qs.length?questionCard(qs[practiceIndex]):`<div class="empty sprint-practice-empty">${D.questions.some(isImportedQuestion)?'当前筛选下没有题目，请调整条件。':'冲刺刷题暂未导入题目。请返回政治理论页，在统一导入区选择“冲刺刷题”添加PDF。'}</div>`}`}
function searchView(){const q=query.trim().toLowerCase(),ts=D.themes.filter(t=>(t.name+t.meaning+t.question).toLowerCase().includes(q)),ms=D.materials.filter(m=>(m.title+m.original+m.why+m.trap+JSON.stringify(m.understanding)).toLowerCase().includes(q)),qs=D.questions.filter(x=>x.text.toLowerCase().includes(q));return head('SEARCH THE ATLAS','找到知识之间的联系',`“${esc(query)}” · ${ts.length}个主题 / ${ms.length}份材料 / ${qs.length}道题`)+`<div class="toolbar">${ts.map(t=>`<button class="btn" data-theme="${t.id}">${t.name} ↗</button>`).join('')}</div><div class="material-grid">${ms.map(card).join('')}</div>${qs.length?`<div class="section-title"><h2>匹配题目</h2><small>前20条 · 点击进入对应材料练习</small></div>${qs.slice(0,20).map(q=>`<button class="relatedbtn" data-question-link="${q.id}"><b>第${q.id}题</b> ${esc(q.text.slice(0,160))}…</button>`).join('')}`:''}${!ms.length&&!qs.length&&!ts.length?'<div class="empty">没有找到匹配内容，试试缩短关键词。</div>':''}`}
function render(){
 const journal=!query&&(view==='month'||view==='topic');
 WORD_NOTES.close();WX_JOURNAL.detach();updateSidebar();document.body.classList.toggle('sprint-reading',view==='material'&&!query);
 $('#atlasSearch').hidden=journal;
 app.classList.toggle('journal-active',journal);app.classList.remove('route-context');app.style.cssText='';
 document.body.classList.toggle('sprint-workspace-open',!query&&['sprint','material','materials'].includes(view));
 if(journal){$('#atlasSearchBar').hidden=true;parent.STUDY_LAMP?.reader(null);const kind=view;WX_JOURNAL.render(app,kind,()=>view===kind&&!!window.frameElement?.isConnected);return;}
 if(window.frameElement?.isConnected)parent.STUDY_LAMP?.reader(!query&&(view==='material'||view==='practice')?{key:'atlas:'+EXAM+':'+(view==='material'?selected:'practice'),board:'政治理论'}:null);
 app.innerHTML=query?searchView():({sprint:sprintView,category:categoryView,theme:themeView,material:materialView,materials:sprintView,practice:practiceView}[view]||sprintView)();
 if(view==='material'&&tab==='original'&&!query){const material=mat(selected);WORD_NOTES.mount(app.querySelector('.original'),{source:'atlas',exam:EXAM,material:selected},{highlights:true,onChange:reading=>{material.reading=reading;}});}
 if(view==='material'&&tab==='understand'&&!query){
  const current=mat(selected);
  if(current.digestData)WANXIANG_DIGEST.bind(app.querySelector('.sprint-digest'),current.digestData,data=>{const y=scrollY;current.digestData=data;render();scrollTo(0,y);});
  else if(!current.digestLoading&&!current.digestError){current.digestLoading=true;api('/api/wanxiang/digest/get',{target:{source:'atlas',exam:EXAM,material:current.id}}).then(data=>{current.digestData=data;}).catch(e=>{current.digestError=e.message;}).finally(()=>{current.digestLoading=false;if(app.isConnected&&view==='material'&&selected===current.id&&tab==='understand')render();});}
 }
 document.querySelectorAll('.sprint-document').forEach(button=>{button.classList.toggle('current',button.dataset.material===selected);if(button.dataset.material===selected)button.setAttribute('aria-current','page');});
}
function startPractice({material=null,t='all',chapter='all',wrong=false}={}){practiceMaterial=material;practiceTheme=t;practiceChapter=chapter;practiceWrong=wrong;practiceIndex=0;navigate('practice')}
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;const d=b.dataset;if(d.go){if(d.go==='practice')startPractice();else navigate(d.go)}else if(d.digest){state.digest[d.digest]=d.value;save();render()}else if(d.category)navigate('category',d.category);else if(d.theme)navigate('theme',d.theme);else if(d.material)navigate('material',d.material);else if(d.chapter!==undefined){filterChapter=d.chapter;filterStatus='all';navigate('materials')}else if(d.tab){tab=d.tab;render()}else if(d.practiceMaterial)startPractice({material:d.practiceMaterial});else if(d.practiceTheme)startPractice({t:d.practiceTheme});else if(d.multiChoice){const old=draftAnswers[d.multiChoice]||'';draftAnswers[d.multiChoice]=old.includes(d.value)?old.replace(d.value,''):[...old,d.value].sort().join('');render()}else if(d.submitAnswer){state.attempts[d.submitAnswer]={choice:draftAnswers[d.submitAnswer],at:new Date().toISOString()};save();render()}else if(d.answer){state.attempts[d.answer]={choice:d.value,at:new Date().toISOString()};save();render()}else if(d.retry){delete draftAnswers[d.retry];delete state.attempts[d.retry];save();render()}else if(d.original){navigate('material',d.original);tab='original';render()}else if(d.questionLink){const q=D.questions.find(q=>q.id===Number(d.questionLink));if(q){navigate('material',q.material);tab='questions';render();document.getElementById('q'+q.id)?.scrollIntoView({block:'center'});}}else if(d.action){switch(d.action){case'retryDigest':mat(selected).digestError='';render();break;case'next':practiceIndex++;render();break;case'prev':practiceIndex--;render();break;case'wrong':practiceWrong=!practiceWrong;practiceIndex=0;render();break;case'clearMaterial':practiceMaterial=null;practiceIndex=0;render();break;case'reviewWrong':startPractice({wrong:true});break;}}});
document.addEventListener('change',e=>{const x=e.target;if(x.dataset.status){state.status[x.dataset.status]=x.value;save();if(view==='progress'||(view==='materials'&&filterStatus!=='all'))render();toast('学习状态已更新')}else if(x.id==='chapterFilter'){filterChapter=x.value;render()}else if(x.id==='statusFilter'){filterStatus=x.value;render()}else if(x.id==='practiceTheme'){practiceTheme=x.value;practiceMaterial=null;practiceIndex=0;render()}else if(x.id==='practiceChapter'){practiceChapter=x.value;practiceMaterial=null;practiceIndex=0;render()}});
let searchTimer;$('#search').addEventListener('input',e=>{query=e.target.value;clearTimeout(searchTimer);searchTimer=setTimeout(render,160)});$('#search').addEventListener('keydown',e=>{if(e.key==='Escape'){query='';e.target.value='';render()}});
for(const event of ['pointerdown','pointermove','keydown','scroll','input','touchmove'])window.addEventListener(event,()=>{if(window.frameElement?.isConnected)parent.STUDY_LAMP?.interaction();},{passive:true,capture:true});
render();

})().catch(e=>{const root=document.getElementById('app');root.textContent='知识地图暂时无法打开：'+e.message;});
