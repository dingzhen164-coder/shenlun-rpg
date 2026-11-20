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
function navigate(v,id=null){view=v;selected=id;if(v==='material'&&id)saveSprintMemo({last:id});query='';$('#search').value='';if(v==='material')tab='original';render();window.scrollTo({top:0,behavior:'instant'})}
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
function themeView(){const t=theme(selected),c=cat(t.category),ms=materialsFor(t.id);return crumb([`<button data-category="${c.id}">${c.name}</button>`,esc(t.name)])+head('TOPIC CONNECTIONS',t.name,t.question)+`<div class="topicintro" style="--c:${c.color};${routeStyle(c)}"><strong>理解提示 · 学习框架</strong><p>${t.meaning}</p><strong>做题时分清</strong><p>${t.pitfall}</p></div><div class="section-title"><h2>同一主题，不同出处</h2></div><div class="material-grid">${ms.map(card).join('')}</div>`}
const sourceKinds=['重大会议','讲话','指导','文件'];
// 研习目录的位置记忆（2026-11-11）：整页重画会把目录滚动清零（点下面一份就跳回顶部），重画前记下、画完放回；
// 收起的分组和上次读的那份按考试记在本机，重进时目录直接露出上次那份。
const SPRINT_KEY='wx-sprint-'+EXAM;
const sprintMemo=()=>{try{return JSON.parse(localStorage.getItem(SPRINT_KEY)||'{}')||{};}catch(_){return {};}};
const saveSprintMemo=patch=>{try{localStorage.setItem(SPRINT_KEY,JSON.stringify({...sprintMemo(),...patch}));}catch(_){}};
function sprintDirectory(){
 const closed=sprintMemo().closed||[];
 const groups=sourceKinds.map((kind,i)=>{const items=D.materials.filter(m=>m.chapter===i&&!m.practice_only);return `<details class="sprint-group" data-kind="${esc(kind)}" ${closed.includes(kind)?'':'open'}><summary>${kind}<small>${items.length}份</small></summary><div>${items.map(m=>`<button class="sprint-document titlebtn" data-material="${m.id}"><span>${esc(m.title)}</span><small>共计${Array.from(String(m.original||'').replace(/\s/g,'')).length}字</small></button>`).join('')||'<p class="hint">暂无资料，可在政治理论页统一导入。</p>'}</div></details>`;});
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
 return `<article class="question" id="q${q.id}"><div class="qtop"><span class="chip">第${q.no||q.id}题${multi?' · 多选':''}</span><button class="tag" data-material="${m.id}">${esc(m.title)} ↗</button></div><div class="qtext">${formatQuestion(q.text)}</div>${(q.flags||[]).length?`<p class="hint question-flags">${q.flags.includes('选项不全')?'PDF识别到的选项不全，请对照原PDF。 ':''}${q.flags.includes('符号推测')?'个别选项符号是按顺序推测补回的，请对照原PDF核对。':''}</p>`:''}${q.answer?`<div class="answer-options" role="group" aria-label="第${q.id}题作答">${['A','B','C','D'].map(v=>`<button ${multi?`data-multi-choice="${q.id}" aria-pressed="${draft.includes(v)}"`:`data-answer="${q.id}"`} data-value="${v}" class="${a?(q.answer.includes(v)?'correct':a.choice.includes(v)?'wrong':''):draft.includes(v)?'selected':''}" ${a?'disabled':''}>${v}</button>`).join('')}</div>${multi&&!a?`<button class="btn primary" data-submit-answer="${q.id}" ${draft?'':'disabled'}>确认作答</button>`:''}`:'<p class="hint">原PDF未提供参考答案，暂不判分；请结合讲义自行核对。</p>'}${a?`<div class="feedback ${a.choice!==q.answer?'wrong':''}"><b>${a.choice===q.answer?'答对了':'需要再辨析'}：你选${esc(a.choice)}，讲义参考答案为${esc(q.answer)}。</b><details class="atlas-answer-analysis"><summary>题目解析</summary><p>${esc(q.analysis||m.trap)}</p></details><button class="btn" data-original="${m.id}">回到讲义找依据</button> <button class="btn" data-retry="${q.id}">重新作答</button></div>`:''}</article>`;
}

// ---------------------------------------------------------------- 分类时政（月半时政 + 专题时政 + 冲刺学习 按类别汇总）
let catSelectedId=null;
function allClassifiedItems(){
 const out=[];
 for(const g of (D.classified||[]))for(const it of (g.items||[]))out.push(it);
 return out;
}
function categoryAllDirectory(){
 const closed=sprintMemo().catClosed||[];
 const groups=(D.classified||[]).filter(g=>(g.items||[]).length>0);
 if(!groups.length)return `<aside class="sprint-index" aria-label="分类时政目录"><div class="sprint-index-label">分类时政</div><p class="empty">当前时政地图暂无分类时政资料。</p></aside>`;
 return `<aside class="sprint-index" aria-label="分类时政目录"><div class="sprint-index-label">分类时政目录</div>${groups.map(g=>`<details class="sprint-group" data-kind="${esc(g.category)}" ${closed.includes(g.category)?'':'open'}><summary>${esc(g.category)}<small>${g.items.length}项</small></summary><div>${g.items.map(it=>`<button class="sprint-document titlebtn ${it.id===catSelectedId?'current':''}" data-cat-item="${esc(it.id)}"><span>${it.stars?`<em class="wxj-star">${'★'.repeat(it.stars)}</em> `:''}${esc(it.title)}</span><small>${esc(it.source_label)} · ${esc(it.issue_title)}</small></button>`).join('')}</div></details>`).join('')}</aside>`;
}
function categoryAllView(){
 const items=allClassifiedItems();
 if(!catSelectedId&&items.length)catSelectedId=items[0].id;
 const cur=items.find(x=>x.id===catSelectedId)||items[0];
 if(!cur)return `<div class="sprint-workspace">${categoryAllDirectory()}<section class="sprint-welcome"><h2>分类时政研习</h2><p>将本时政地图下的月半时政、专题时政、冲刺学习按农业、经济、科技、外交、党建等类别汇总学习。</p></section></div>`;
 const jumpBtn=cur.source_type==='sprint'?`<button class="btn" data-material="${esc(cur.material_id)}">在「冲刺学习」中打开（含消化与精卷） ↗</button>`:`<button class="btn" data-open-journal="${esc(cur.source_type)}|${esc(cur.issue_id)}|${cur.news_index||0}">在「${esc(cur.source_label)}」中打开（含消化与精卷） ↗</button>`;
 return `<div class="sprint-workspace">${categoryAllDirectory()}<article class="sprint-document-body"><div class="row" style="display:flex;align-items:center;gap:var(--ds-sp-8);flex-wrap:wrap;margin-bottom:var(--ds-sp-12)"><span class="chip">${esc(cur.category)}</span><span class="tag">${esc(cur.source_label)} · ${esc(cur.issue_title)}</span>${cur.date?`<span class="small muted">${esc(cur.date)}</span>`:''}<span style="flex:1"></span>${jumpBtn}</div><h2 class="sprint-document-title">${cur.stars?`<span class="wxj-star">${'★'.repeat(cur.stars)}</span> `:''}${esc(cur.title)}</h2><section class="panel sprint-original"><div class="original">${formatOriginal(cur.text||'')}</div></section></article></div>`;
}

// ---------------------------------------------------------------- 易错题（政治理论独立错题集，思过崖模板格式）
let WRONG_DATA=null,WRONG_CUR='',WRONG_RESULT=null,WRONG_LOADING=false;
const IMG_RE=/\.(png|jpe?g|gif|webp|bmp|svg)$/i;
function wrongImgUrl(raw){
 let s=String(raw||'').trim().replace(/\\/g,'/');
 if(!s||/^https?:\/\//i.test(s)||s.startsWith('/')||s.includes('..'))return '';
 s=s.replace(/^\.\//,'');
 if(!IMG_RE.test(s))return '';
 if(!s.includes('/'))s='assets/'+s;
 return '/vault-file?p='+encodeURIComponent('训练/思过崖/'+s);
}
const mdRender=t=>window.MDLITE?MDLITE.render(t||'',{imgUrl:wrongImgUrl}):`<p>${esc(t)}</p>`;
const mdInline=t=>window.MDLITE?.inline?MDLITE.inline(t||'',{imgUrl:wrongImgUrl}):esc(t);
async function loadWrong(force=false){
 if(WRONG_LOADING)return;
 if(WRONG_DATA&&!force)return;
 WRONG_LOADING=true;
 try{
  WRONG_DATA=await api('/api/politics/wrong');
  const keys=(WRONG_DATA.questions||[]).map(q=>q.key);
  if(!keys.includes(WRONG_CUR))WRONG_CUR=keys[0]||'';
 }catch(e){toast('读取易错题失败：'+e.message);}
 finally{WRONG_LOADING=false;if(view==='wrong')render();}
}
function wrongView(){
 if(!WRONG_DATA&&!WRONG_LOADING){loadWrong();return `<div class="card muted" style="padding:var(--ds-sp-24)">正在读取政治理论易错题…</div>`;}
 const b=WRONG_DATA||{exists:false,file:'训练/万象峰/易错题.md',questions:[],problems:[]};
 const headBar=`<header class="sg-head" style="margin-bottom:var(--ds-sp-12)"><strong class="sg-title">政治理论 · 易错题</strong><span class="small sg-file">${esc(b.file||'训练/万象峰/易错题.md')}</span><span style="flex:1"></span><button type="button" class="ghost small" data-wrong-sync>↻ 同步易错题</button></header>`;
 if(!b.exists||!b.questions.length){
  return `<div class="sg-room sg-paper" style="position:relative;inset:auto;min-height:420px">${headBar}<div class="sg-empty"><p>${b.exists?'易错题文档里还没有读到题目。':'还没有建立政治理论易错题文档。'}</p><p>在本地新建或由 AI Agent 写入 <b>${esc(b.file||'训练/万象峰/易错题.md')}</b>（或在 <code>gk-skill/错题集/政治理论.md</code> 记录后点击右上角「↻ 同步易错题」），格式与思过崖错题模板一致：每道题 <code>## 编号 · 标题</code>，下面 <code>### 原题</code>（题干 + “- A. ……”）、<code>### 答案</code>（正确答案：C；我的选择：B）及出处文件与解析小节。</p></div></div>`;
 }
 const list=b.questions.map(q=>{
  const r=q.record,st=!r?'new':r.last==='ok'?'ok':'bad';
  return `<button type="button" class="sg-q ${q.key===WRONG_CUR?'on':''}" data-wrong-q="${esc(q.key)}" aria-current="${q.key===WRONG_CUR}"><i class="sg-dot ${st}" aria-hidden="true"></i><span>${mdInline(q.title)}</span><small>${st==='new'?'未重做':st==='ok'?'上次对':'上次错'}</small></button>`;
 }).join('');
 const q=b.questions.find(x=>x.key===WRONG_CUR)||b.questions[0];
 const R=WRONG_RESULT&&WRONG_RESULT.key===q.key?WRONG_RESULT:null;
 const opts=Object.entries(q.options||{}).map(([k,v])=>{
  const cls=!R?'':k===R.answer?'right':k===R.choice?'wrong':'dim';
  return `<button type="button" class="sg-opt ${cls}" data-wrong-pick="${k}" ${R?'disabled':''}><b>${k}</b><span>${mdInline(v)}</span></button>`;
 }).join('');
 const verdict=!R?'':`<div class="sg-verdict ${R.ok===null?'':R.ok?'ok':'bad'}" role="status">${R.ok===null?'文档里没写正确答案':R.ok?'✓ 这次做对了':`✗ 又错了：正确答案 ${esc(R.answer)}`}${R.mine?`<span>当时选 ${esc(R.mine)}</span>`:''}</div>`;
 const secs=R?R.sections.map(s=>`<section class="sg-sec"><h4>${mdInline(s.title)}</h4><div class="sg-md">${mdRender(s.md)}</div></section>`).join(''):'';
 const idx=b.questions.findIndex(x=>x.key===q.key),next=b.questions[idx+1];
 const cardHtml=`<article class="sg-card"><strong class="sg-qtitle">${mdInline(q.title)}</strong><div class="sg-md sg-stem">${mdRender(q.stem)}</div><div class="sg-opts is-stack" role="group" aria-label="选项">${opts}</div>${verdict}${secs}<div class="sg-acts">${R?`<button type="button" class="ghost small" data-wrong-redo>再做一次</button>`:''}${next?`<button type="button" class="primary small" data-wrong-q="${esc(next.key)}">下一题 →</button>`:''}</div></article>`;
 return `<div class="sg-room sg-paper" style="position:relative;inset:auto;min-height:520px">${headBar}<div class="sg-body"><nav class="sg-list" aria-label="易错题列表">${list}</nav><div class="sg-main">${cardHtml}</div></div></div>`;
}

function searchView(){const q=query.trim().toLowerCase(),ts=D.themes.filter(t=>(t.name+t.meaning+t.question).toLowerCase().includes(q)),ms=D.materials.filter(m=>(m.title+m.original+m.why+m.trap+JSON.stringify(m.understanding)).toLowerCase().includes(q)),qs=D.questions.filter(x=>x.text.toLowerCase().includes(q));return head('SEARCH THE ATLAS','找到知识之间的联系',`“${esc(query)}” · ${ts.length}个主题 / ${ms.length}份材料 / ${qs.length}道题`)+`<div class="toolbar">${ts.map(t=>`<button class="btn" data-theme="${t.id}">${t.name} ↗</button>`).join('')}</div><div class="material-grid">${ms.map(card).join('')}</div>${qs.length?`<div class="section-title"><h2>匹配题目</h2><small>前20条 · 点击进入对应材料练习</small></div>${qs.slice(0,20).map(q=>`<button class="relatedbtn" data-question-link="${q.id}"><b>第${q.id}题</b> ${esc(q.text.slice(0,160))}…</button>`).join('')}`:''}${!ms.length&&!qs.length&&!ts.length?'<div class="empty">没有找到匹配内容，试试缩短关键词。</div>':''}`}
// 只滚目录自己：当前那份不在可见范围才挪一点；center=true 时放到中间（重进时）
function revealSprint(idx,center){
 const on=idx.querySelector('.sprint-document.current,.sprint-document.last');if(!on||!on.offsetParent)return;
 const a=idx.getBoundingClientRect(),b=on.getBoundingClientRect();
 if(center)idx.scrollTop+=(b.top+b.bottom)/2-(a.top+a.bottom)/2;else if(b.top<a.top)idx.scrollTop-=a.top-b.top+8;else if(b.bottom>a.bottom)idx.scrollTop+=b.bottom-a.bottom+8;
}
function render(){
 const oldIndex=app.querySelector('.sprint-index'),indexTop=oldIndex?oldIndex.scrollTop:null;
 renderPage();
 const idx=app.querySelector('.sprint-index');if(!idx)return;
 const last=sprintMemo().last;
 if(!selected&&last&&view==='sprint')idx.querySelectorAll('.sprint-document').forEach(b=>b.classList.toggle('last',b.dataset.material===last));
 idx.querySelectorAll('details.sprint-group').forEach(d=>d.addEventListener('toggle',()=>{
  const closed=[...idx.querySelectorAll('details.sprint-group:not([open])')].map(x=>x.dataset.kind);
  saveSprintMemo(view==='category_all'?{catClosed:closed}:{closed});
 }));
 if(indexTop!=null)idx.scrollTop=indexTop;
 revealSprint(idx,indexTop==null);
}
function renderPage(){
 const journal=!query&&(view==='month'||view==='topic');
 WORD_NOTES.close();WX_JOURNAL.detach();updateSidebar();document.body.classList.toggle('sprint-reading',view==='material'&&!query);
 $('#atlasSearch').hidden=journal||view==='wrong';
 app.classList.toggle('journal-active',journal);app.classList.remove('route-context');app.style.cssText='';
 document.body.classList.toggle('sprint-workspace-open',!query&&['sprint','material','materials','category_all'].includes(view));
 if(journal){$('#atlasSearchBar').hidden=true;parent.STUDY_LAMP?.reader(null);const kind=view;WX_JOURNAL.render(app,kind,()=>view===kind&&!!window.frameElement?.isConnected);return;}
 if(window.frameElement?.isConnected)parent.STUDY_LAMP?.reader(!query&&(view==='material'||view==='category_all'||view==='wrong')?{key:'atlas:'+EXAM+':'+(view==='material'?selected:view),board:'政治理论'}:null);
 app.innerHTML=query?searchView():({sprint:sprintView,category:categoryView,theme:themeView,material:materialView,materials:sprintView,category_all:categoryAllView,wrong:wrongView}[view]||sprintView)();
 if(view==='material'&&tab==='original'&&!query){const material=mat(selected);WORD_NOTES.mount(app.querySelector('.original'),{source:'atlas',exam:EXAM,material:selected},{highlights:true,bulkHost:app.querySelector('.atlas-reading-tools'),bulkBefore:app.querySelector('.atlas-status-inline'),onChange:reading=>{material.reading=reading;}});}
 if(view==='material'&&tab==='understand'&&!query){
  const current=mat(selected);
  if(current.digestData)WANXIANG_DIGEST.bind(app.querySelector('.sprint-digest'),current.digestData,data=>{const y=scrollY;current.digestData=data;render();scrollTo(0,y);});
  else if(!current.digestLoading&&!current.digestError){current.digestLoading=true;api('/api/wanxiang/digest/get',{target:{source:'atlas',exam:EXAM,material:current.id}}).then(data=>{current.digestData=data;}).catch(e=>{current.digestError=e.message;}).finally(()=>{current.digestLoading=false;if(app.isConnected&&view==='material'&&selected===current.id&&tab==='understand')render();});}
 }
 document.querySelectorAll('.sprint-document[data-material]').forEach(button=>{button.classList.toggle('current',button.dataset.material===selected);if(button.dataset.material===selected)button.setAttribute('aria-current','page');});
}
document.addEventListener('click',async e=>{
 const b=e.target.closest('button');if(!b)return;const d=b.dataset;
 if(d.go){navigate(d.go);return;}
 if(d.catItem){catSelectedId=d.catItem;render();return;}
 if(d.openJournal){
  const [kind,id,nidx]=d.openJournal.split('|');
  view=kind;updateSidebar();
  await WX_JOURNAL.render(app,kind,()=>view===kind&&!!window.frameElement?.isConnected);
  WX_JOURNAL.open(kind,id,'read',Number(nidx)||0);
  return;
 }
 if(d.wrongQ){WRONG_CUR=d.wrongQ;WRONG_RESULT=null;render();return;}
 if('wrongRedo' in d){WRONG_RESULT=null;render();return;}
 if('wrongSync' in d){
  b.disabled=true;b.textContent='同步中…';
  try{await api('/api/siguo/sync',{});WRONG_DATA=null;await loadWrong(true);toast('政治理论易错题已同步');}catch(err){toast(err.message||'同步失败');}
  finally{b.disabled=false;b.textContent='↻ 同步易错题';}
  return;
 }
 if(d.wrongPick){
  try{
   const r=await api('/api/politics/wrong/answer',{key:WRONG_CUR,choice:d.wrongPick});
   WRONG_RESULT=Object.assign({key:WRONG_CUR},r);
   const q=(WRONG_DATA?.questions||[]).find(x=>x.key===WRONG_CUR);
   if(q)q.record=r.record;
   if(r.events?.length&&parent.handleEvents)parent.handleEvents(r.events);
   render();
  }catch(err){toast(err.message||'提交失败');}
  return;
 }
 if(d.digest){state.digest[d.digest]=d.value;save();render()}
 else if(d.category)navigate('category',d.category);
 else if(d.theme)navigate('theme',d.theme);
 else if(d.material)navigate('material',d.material);
 else if(d.chapter!==undefined){filterChapter=d.chapter;filterStatus='all';navigate('materials')}
 else if(d.tab){tab=d.tab;render()}
 else if(d.multiChoice){const old=draftAnswers[d.multiChoice]||'';draftAnswers[d.multiChoice]=old.includes(d.value)?old.replace(d.value,''):[...old,d.value].sort().join('');render()}
 else if(d.submitAnswer){state.attempts[d.submitAnswer]={choice:draftAnswers[d.submitAnswer],at:new Date().toISOString()};save();render()}
 else if(d.answer){state.attempts[d.answer]={choice:d.value,at:new Date().toISOString()};save();render()}
 else if(d.retry){delete draftAnswers[d.retry];delete state.attempts[d.retry];save();render()}
 else if(d.original){navigate('material',d.original);tab='original';render()}
 else if(d.questionLink){const q=D.questions.find(q=>q.id===Number(d.questionLink));if(q){navigate('material',q.material);tab='questions';render();document.getElementById('q'+q.id)?.scrollIntoView({block:'center'});}}
 else if(d.action){if(d.action==='retryDigest'){mat(selected).digestError='';render();}}
});
document.addEventListener('change',e=>{const x=e.target;if(x.dataset.status){state.status[x.dataset.status]=x.value;save();if(view==='progress'||(view==='materials'&&filterStatus!=='all'))render();toast('学习状态已更新')}else if(x.id==='chapterFilter'){filterChapter=x.value;render()}else if(x.id==='statusFilter'){filterStatus=x.value;render()}});
let searchTimer;$('#search').addEventListener('input',e=>{query=e.target.value;clearTimeout(searchTimer);searchTimer=setTimeout(render,160)});$('#search').addEventListener('keydown',e=>{if(e.key==='Escape'){query='';e.target.value='';render()}});
for(const event of ['pointerdown','pointermove','keydown','scroll','input','touchmove'])window.addEventListener(event,()=>{if(window.frameElement?.isConnected)parent.STUDY_LAMP?.interaction();},{passive:true,capture:true});
render();

})().catch(e=>{const root=document.getElementById('app');root.textContent='知识地图暂时无法打开：'+e.message;});
