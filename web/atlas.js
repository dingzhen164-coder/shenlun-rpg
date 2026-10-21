/* 用户提供的时政地图交互，接入程序后端进度与共用词义批注；内容由/api/politics/atlas提供。 */
const api=(url,body)=>parent.api(url,body);
function syncAtlasTheme(){
 const palette=getComputedStyle(parent.document.body);
 for(const key of ['bg','panel','panel2','text','muted','line','gold','accent','accent2','red','shadow'])document.documentElement.style.setProperty('--'+key,palette.getPropertyValue('--'+key));
 document.documentElement.dataset.theme=parent.document.documentElement.dataset.theme||'light';
}
syncAtlasTheme();new MutationObserver(syncAtlasTheme).observe(parent.document.documentElement,{attributes:true,attributeFilter:['data-theme','class']});
new MutationObserver(syncAtlasTheme).observe(parent.document.body,{attributes:true,attributeFilter:['class']});
(async()=>{

'use strict';
const {data:D,progress:initialProgress}=await api('/api/politics/atlas');
const $=s=>document.querySelector(s),app=$('#app');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state=initialProgress,lastSnapshot=JSON.parse(JSON.stringify(state)),saveQueue=Promise.resolve();
let view='overview',selected=null,tab='understand',filterChapter='all',filterStatus='all',practiceTheme='all',practiceChapter='all',practiceWrong=false,practiceIndex=0,query='',lastView='overview';
const mat=id=>D.materials.find(x=>x.id===id),theme=id=>D.themes.find(x=>x.id===id),cat=id=>D.categories.find(x=>x.id===id);
const statusLabel={new:'未学',review:'待巩固',done:'已掌握'};
const materialsFor=t=>D.materials.filter(m=>m.tags.includes(t));
function toast(t){$('#toast').textContent=t;$('#toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').hidden=true,2800)}
function save(){
 const changes=[];
 for(const field of ['status','attempts'])for(const id of new Set([...Object.keys(lastSnapshot[field]),...Object.keys(state[field])])){
  if(JSON.stringify(lastSnapshot[field][id])!==JSON.stringify(state[field][id]))changes.push({field,id,value:state[field][id]??null});
 }
 lastSnapshot=JSON.parse(JSON.stringify(state));updateSidebar();
 saveQueue=saveQueue.then(async()=>{for(const change of changes)await api('/api/politics/progress',change);}).catch(async e=>{
  toast('进度未保存：'+e.message);
  try{const current=await api('/api/politics/atlas');state=current.progress;lastSnapshot=JSON.parse(JSON.stringify(state));render();}catch(_){}
 });
 return saveQueue;
}
function updateSidebar(){let done=D.materials.filter(m=>state.status[m.id]==='done').length;$('#progressCount').textContent=done+'/'+D.materials.length;$('#progressBar').style.width=done/D.materials.length*100+'%';document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('active',b.dataset.go===(view==='category'||view==='theme'?'overview':view==='material'?'materials':view)))}
$('#atlasBack').onclick=()=>parent.STUDY_REGIONS.back();
$('#atlasSearch').onclick=()=>{const bar=$('#atlasSearchBar'),open=bar.hidden;bar.hidden=!open;$('#atlasSearch').setAttribute('aria-expanded',String(open));if(open)$('#search').focus();else{query='';$('#search').value='';render();}};
$('#sideTopics').innerHTML=D.categories.map(c=>`<button data-category="${c.id}"><span class="dot" style="background:${c.color}"></span>${c.name}</button>`).join('');
function navigate(v,id=null){view=v;selected=id;query='';$('#search').value='';if(v==='material')tab='understand';render();window.scrollTo({top:0,behavior:'instant'})}
// 移除站点大标题和说明，页面首屏直接进入知识与正文。
function head(){return ''}
function crumb(){return ''}
function statusSelect(m){return `<select class="status" data-status="${m.id}" aria-label="${esc(m.title)}学习状态">${Object.entries(statusLabel).map(([v,n])=>`<option value="${v}" ${(state.status[m.id]||'new')===v?'selected':''}>${n}</option>`).join('')}</select>`}
function routeForTheme(id){return cat(theme(id).category)}
function routeForMaterial(m){return routeForTheme(m.tags[0])}
function routeStyle(c){return `--route:${c.color};--route-soft:${c.color}12`}
function routeBadges(m){return `<div class="route-badges">${D.categories.filter(c=>m.tags.some(t=>c.themes.includes(t))).map(c=>`<button style="${routeStyle(c)}" data-category="${c.id}">${c.name}</button>`).join('')}</div>`}
function classifiedSources(){return `<div class="section-title"><h2>五条主线，串起四类材料</h2></div><div class="source-routes">${D.categories.map(c=>{const ms=D.materials.filter(m=>m.tags.some(t=>c.themes.includes(t)));return `<details class="source-route" style="${routeStyle(c)}" open><summary>${c.name} · ${c.question}<small>${ms.length}份关联材料</small></summary><div class="source-columns">${D.chapters.map((ch,i)=>{const group=ms.filter(m=>m.chapter===i);return `<section class="source-column"><h3>${ch}<span>${group.length}</span></h3>${group.length?group.map(m=>`<button class="source-link" data-material="${m.id}">${esc(m.title)}</button>`).join(''):'<div class="source-empty">本主线暂无此类材料</div>'}</section>`}).join('')}</div></details>`}).join('')}</div>`}
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
  if(level){const tag=level===1?'h2':'h3';return `<${tag} class="source-heading source-main-heading" data-source-level="${level}">${esc(b)}</${tag}>`}
  if(/^【[^】]+】$/.test(b))cls='source-label';
  else if(b.length<=64&&/^(?:[一二三四五六七八九十百]+[、．.]|[（(](?:[一二三四五六七八九十百]+|\d+)[）)]|\d+[.．、]|《)/.test(b)&&!/[。；！？]/.test(b))return `<h3 class="source-heading">${content}</h3>`;
  else if(/^(?:[（(]\d+[）)]|[①②③④⑤⑥⑦⑧⑨⑩]|第[一二三四五六七八九十]+[，、]|[一二三四五六七八九十]+是)/.test(b))cls='source-item';
  return `<p${cls?` class="${cls}"`:''}>${content}</p>`;
 }).join('');
}
function tags(m){return `<div class="tags">${m.tags.map(t=>`<button class="tag" style="${routeStyle(routeForTheme(t))}" data-theme="${t}">${theme(t).name}</button>`).join('')}</div>`}
function card(m){return `<article class="material" style="${routeStyle(routeForMaterial(m))}"><div class="chapter-label">${D.chapters[m.chapter]} · ${m.date}</div><button class="titlebtn" data-material="${m.id}">${esc(m.title)}</button><div class="material-meta">配套${m.questions.length}题</div><p>${esc(m.why)}</p>${routeBadges(m)}<div class="cardfoot"><button class="btn" data-material="${m.id}">展开学习 ↗</button>${statusSelect(m)}</div></article>`}
function overview(){return head('THE BIG PICTURE','先见全局，再记考点','以中国式现代化为中心，用五个问题串起四章材料。',`<div class="stats"><div><b>5</b><span>学习主线</span></div><div><b>${D.materials.length}</b><span>材料入口</span></div><div><b>${D.questions.length}</b><span>讲义原题</span></div></div>`)+`<section class="map"><div class="map-top"><div class="root-label">一条总方向</div><div class="root">中国式现代化</div></div><div class="map-connector"></div><div class="branches">${D.categories.map((c,i)=>`<div class="branch" style="--c:${c.color};${routeStyle(c)}"><button class="branch-head" data-category="${c.id}"><div class="branch-n">0${i+1} / ${c.question}</div><h3>${c.name}</h3><small>${c.desc}</small></button><div class="theme-list">${c.themes.map(t=>`<button class="themebtn" data-theme="${t}">${theme(t).name}<span>${materialsFor(t).length} ↗</span></button>`).join('')}</div></div>`).join('')}</div><div class="map-foot"><span>目标统领方向 · 动力推动发展 · 民生体现成果 · 保障贯穿过程 · 外部关系拓展环境</span><span>${D.categories.length}条主线 / ${D.themes.length}个主题</span></div></section>${classifiedSources()}<div class="section-title"><h2>也可以，沿着讲义走</h2></div><div class="journey">${D.chapters.map((c,i)=>`<button class="journey-card" data-chapter="${i}"><span class="stepnum">0${i+1}</span><b>${c}</b><p>${['集中研究形势，确定方向和重点','解释部署，在不同场合明确要求','面向具体工作，提出指导要求','明确制度、责任、条件和程序'][i]}</p><div class="hint" style="margin-top:11px">${D.materials.filter(m=>m.chapter===i).length}份材料 →</div></button>`).join('')}</div><div class="section-title"><h2>今天，从这里开始</h2><small>先理解，再回忆，最后练题</small></div><div class="material-grid">${card(D.materials[0])}<div class="material"><div class="chapter-label">建议学习路径 · 30—40分钟</div><h3>中央经济工作会议：五、八、五</h3><p>读懂五个必须 → 对照八项重点任务 → 记准五个着力点的搭配 → 独立作答第1—3题。</p><div class="trap">先回忆：为什么投资于物和投资于人要“紧密结合”？为什么“内需主导”不能改成“投资主导”？</div><div class="cardfoot"><button class="btn primary" data-practice-material="m1">做第1—3题</button></div></div></div>`}
function categoryView(){const c=cat(selected),ms=D.materials.filter(m=>m.tags.some(t=>c.themes.includes(t)));return crumb([esc(c.name)])+head('LEARNING ROUTE',c.name,c.question+' '+c.desc)+`<div class="topicintro" style="--c:${c.color};${routeStyle(c)}"><strong>这条主线关注什么</strong><p>${{goal:'先定位总体目标、发展要求与阶段任务，再把历史经验和新征程使命放回这条时间线。',engine:'从需求、技术、产业、制度与空间组织五方面，看发展动力怎样形成。',people:'把政策还原为人的就业、收入、成长、健康与居住需求，理解发展成果怎样进入生活。',support:'把组织执行、规则约束、生态可持续与风险治理放在一起看。这些领域也有独立目标，保障只是学习视角。',world:'区分经济开放、国际平台合作与两岸关系；不同对象和场合，对应不同重点表述。'}[c.id]}</p></div><div class="toolbar">${c.themes.map(t=>`<button class="btn" data-theme="${t}">${theme(t).name} · ${materialsFor(t).length}</button>`).join('')}</div><div class="section-title"><h2>关联材料</h2><small>${ms.length}份 · 跨章节汇集</small></div><div class="material-grid">${ms.map(card).join('')}</div>`}
function themeView(){const t=theme(selected),c=cat(t.category),ms=materialsFor(t.id);return crumb([`<button data-category="${c.id}">${c.name}</button>`,esc(t.name)])+head('TOPIC CONNECTIONS',t.name,t.question,`<button class="btn primary" data-practice-theme="${t.id}">练相关题目</button>`)+`<div class="topicintro" style="--c:${c.color};${routeStyle(c)}"><strong>理解提示 · 学习框架</strong><p>${t.meaning}</p><strong>做题时分清</strong><p>${t.pitfall}</p></div><div class="section-title"><h2>同一主题，不同出处</h2><button class="btn primary" data-practice-theme="${t.id}">练相关题目</button></div><div class="material-grid">${ms.map(card).join('')}</div>`}
function materialView(){const m=mat(selected),related=D.materials.filter(s=>s.id!==m.id&&s.tags.some(t=>m.tags.includes(t))).sort((a,b)=>b.tags.filter(t=>m.tags.includes(t)).length-a.tags.filter(t=>m.tags.includes(t)).length).slice(0,5);return crumb([`<button data-chapter="${m.chapter}">${D.chapters[m.chapter]}</button>`,esc(m.title)])+head('SOURCE & UNDERSTANDING',esc(m.title),`${D.chapters[m.chapter]} · ${esc(m.date)}`,statusSelect(m))+`<div class="atlas-reading-tools"><div class="tabs" role="tablist" aria-label="阅读与练习">${[['understand','理解与辨析'],['original','讲义原文'],['questions',`配套题 · ${m.questions.length}`]].map(([v,n])=>`<button role="tab" aria-selected="${tab===v}" class="${tab===v?'active':''}" data-tab="${v}">${n}</button>`).join('')}</div><span class="atlas-status-inline">${statusSelect(m)}</span></div><div class="detail-grid"><div>${tab==='understand'?`<section class="panel reading"><div class="panel-label">01 / 回应什么问题 · 理解提示</div><h3>${esc(m.why)}</h3><p>${esc(m.understanding.context)}</p></section><section class="panel reading"><div class="panel-label">02 / 主要抓手 · 讲义要点提炼</div><ul>${m.understanding.actions.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></section><section class="trap study-trap"><b>03 / 容易混在哪里</b><ul>${m.understanding.distinctions.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></section><section class="panel reading" style="margin-top:18px"><div class="panel-label">04 / 合上讲义，试着说清楚</div>${m.understanding.recall.map((x,i)=>`<div class="recall-item"><h3>${i+1}. ${esc(x.question)}</h3><details class="recall-answer"><summary>展开参考答案</summary><p>${esc(x.answer)}</p></details></div>`).join('')}<button class="btn" data-tab="original">核对讲义原文</button> <button class="btn primary" data-tab="questions">独立做配套题</button></section>`:tab==='original'?`<section class="panel"><div class="original">${formatOriginal(m.original,m.originalEmphasis)}</div></section>`:m.questions.map(id=>questionCard(D.questions.find(q=>q.id===id))).join('')}</div><details class="atlas-related"><summary>主题与关联材料</summary><aside><section class="panel"><div class="aside-title">在地图中的位置</div>${tags(m)}</section><section class="panel"><div class="aside-title">继续连接</div>${related.map(s=>`<button class="relatedbtn" data-material="${s.id}">${esc(s.title)}<div class="hint">${D.chapters[s.chapter]}</div></button>`).join('')}</section></aside></details></div>`}
function questionCard(q){const a=state.attempts[q.id],m=mat(q.material);return `<article class="question" id="q${q.id}"><div class="qtop"><span class="chip">第${q.id}题</span><button class="tag" data-material="${m.id}">${esc(m.title)} ↗</button></div><div class="qtext">${esc(q.text)}</div><div class="answer-options" role="group" aria-label="第${q.id}题作答">${['A','B','C','D'].map(v=>`<button data-answer="${q.id}" data-value="${v}" class="${a?(v===q.answer?'correct':v===a.choice?'wrong':''):''}" ${a?'disabled':''}>${v}</button>`).join('')}</div>${a?`<div class="feedback ${a.choice!==q.answer?'wrong':''}"><b>${a.choice===q.answer?'答对了':'需要再辨析'}：你选${esc(a.choice)}，讲义参考答案为${q.answer}。</b><br>核对提示：${esc(m.trap)}<br><button class="btn" style="margin-top:9px" data-original="${m.id}">回到讲义找依据</button> <button class="btn" data-retry="${q.id}">重新作答</button></div>`:''}</article>`}
let practiceMaterial=null;
function practiceList(){return D.questions.filter(q=>(!practiceMaterial||q.material===practiceMaterial)&&(practiceTheme==='all'||q.tags.includes(practiceTheme))&&(practiceChapter==='all'||mat(q.material).chapter===Number(practiceChapter))&&(!practiceWrong||(state.attempts[q.id]&&state.attempts[q.id].choice!==q.answer)))}
function practiceView(){const qs=practiceList();practiceIndex=Math.min(practiceIndex,Math.max(0,qs.length-1));const attempted=D.questions.filter(q=>state.attempts[q.id]),correct=attempted.filter(q=>state.attempts[q.id].choice===q.answer);return head('RECALL & PRACTICE','把理解，变成判断依据',`${D.questions.length}道讲义配套原题`)+`<div class="practice-stats"><div><b>${attempted.length}</b><span class="hint">已作答</span></div><div><b>${correct.length}</b><span class="hint">当前答对</span></div><div><b>${attempted.length-correct.length}</b><span class="hint">待订正</span></div></div><div class="toolbar"><select id="practiceTheme" aria-label="练习主题"><option value="all">全部主题</option>${D.themes.map(t=>`<option value="${t.id}" ${practiceTheme===t.id?'selected':''}>${t.name}</option>`).join('')}</select><select id="practiceChapter" aria-label="练习章节"><option value="all">全部章节</option>${D.chapters.map((c,i)=>`<option value="${i}" ${String(practiceChapter)===String(i)?'selected':''}>${c}</option>`).join('')}</select><button class="btn ${practiceWrong?'primary':''}" data-action="wrong">${practiceWrong?'✓ ':''}只看错题</button>${practiceMaterial?`<button class="btn" data-action="clearMaterial">清除材料筛选：${esc(mat(practiceMaterial).title)} ×</button>`:''}</div><div class="section-title"><h2>${qs.length?`当前 ${practiceIndex+1} / ${qs.length}`:'没有符合条件的题目'}</h2><div><button class="btn" data-action="prev" ${practiceIndex===0?'disabled':''}>← 上一题</button> <button class="btn" data-action="next" ${practiceIndex>=qs.length-1?'disabled':''}>下一题 →</button></div></div>${qs.length?questionCard(qs[practiceIndex]):'<div class="empty">调整筛选，或先完成一些题目后再查看错题。</div>'}`}
function materialsView(){const ms=D.materials.filter(m=>(filterChapter==='all'||m.chapter===Number(filterChapter))&&(filterStatus==='all'||(state.status[m.id]||'new')===filterStatus));return head('SOURCE INDEX','四章材料，一处查找','')+`<div class="toolbar"><select id="chapterFilter" aria-label="材料章节"><option value="all">全部章节</option>${D.chapters.map((c,i)=>`<option value="${i}" ${String(filterChapter)===String(i)?'selected':''}>第${i+1}章 · ${c}</option>`).join('')}</select><select id="statusFilter" aria-label="学习状态"><option value="all">全部学习状态</option>${Object.entries(statusLabel).map(([v,n])=>`<option value="${v}" ${filterStatus===v?'selected':''}>${n}</option>`).join('')}</select><span class="hint" style="align-self:center">${ms.length}份材料</span></div><div class="material-grid">${ms.length?ms.map(card).join(''):'<div class="empty">没有符合筛选条件的材料。</div>'}</div>`}
function progressView(){const done=D.materials.filter(m=>state.status[m.id]==='done'),review=D.materials.filter(m=>state.status[m.id]==='review');return head('YOUR LEARNING TRAIL','看见自己的进展','')+`<div class="practice-stats"><div><b>${done.length}</b><span class="hint">已掌握材料</span></div><div><b>${review.length}</b><span class="hint">待巩固材料</span></div><div><b>${D.materials.length-done.length-review.length}</b><span class="hint">未学材料</span></div></div><div class="progress-grid">${D.categories.map(c=>{const ms=D.materials.filter(m=>m.tags.some(t=>c.themes.includes(t))),n=ms.filter(m=>state.status[m.id]==='done').length;return `<div class="progress-card" style="${routeStyle(c)};border-top:3px solid var(--route)"><h3 style="color:var(--route)">${c.name}</h3><div class="hint">${n} / ${ms.length} 关联材料已掌握</div><div class="progressline"><span style="width:${n/ms.length*100}%;background:${c.color}"></span></div><button class="tag" data-category="${c.id}">沿主线继续 →</button></div>`}).join('')}</div><div class="section-title"><h2>优先巩固</h2><button class="btn" data-action="reviewWrong">重做错题</button></div><div class="material-grid">${review.length?review.map(card).join(''):'<div class="empty">暂未标记待巩固材料。</div>'}</div>`}
function searchView(){const q=query.trim().toLowerCase(),ts=D.themes.filter(t=>(t.name+t.meaning+t.question).toLowerCase().includes(q)),ms=D.materials.filter(m=>(m.title+m.original+m.why+m.trap+JSON.stringify(m.understanding)).toLowerCase().includes(q)),qs=D.questions.filter(x=>x.text.toLowerCase().includes(q));return head('SEARCH THE ATLAS','找到知识之间的联系',`“${esc(query)}” · ${ts.length}个主题 / ${ms.length}份材料 / ${qs.length}道题`)+`<div class="toolbar">${ts.map(t=>`<button class="btn" data-theme="${t.id}">${t.name} ↗</button>`).join('')}</div><div class="material-grid">${ms.map(card).join('')}</div>${qs.length?`<div class="section-title"><h2>匹配题目</h2><small>前20条 · 点击进入对应材料练习</small></div>${qs.slice(0,20).map(q=>`<button class="relatedbtn" data-question-link="${q.id}"><b>第${q.id}题</b> ${esc(q.text.slice(0,160))}…</button>`).join('')}`:''}${!ms.length&&!qs.length&&!ts.length?'<div class="empty">没有找到匹配内容，试试缩短关键词。</div>':''}`}
function render(){WORD_NOTES.close();const activeRoute=!query&&(view==='category'?cat(selected):view==='theme'?routeForTheme(selected):view==='material'?routeForMaterial(mat(selected)):null);app.classList.toggle('route-context',!!activeRoute);app.style.cssText=activeRoute?routeStyle(activeRoute):'';app.innerHTML=query?searchView():({overview,category:categoryView,theme:themeView,material:materialView,materials:materialsView,practice:practiceView,progress:progressView}[view]||overview)();updateSidebar();if(view==='material'&&tab==='original'&&!query)WORD_NOTES.mount(app.querySelector('.original'),{source:'atlas',material:selected});}
function startPractice({material=null,t='all',chapter='all',wrong=false}={}){practiceMaterial=material;practiceTheme=t;practiceChapter=chapter;practiceWrong=wrong;practiceIndex=0;navigate('practice')}
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;const d=b.dataset;if(d.go){if(d.go==='practice')startPractice();else navigate(d.go)}else if(d.category)navigate('category',d.category);else if(d.theme)navigate('theme',d.theme);else if(d.material)navigate('material',d.material);else if(d.chapter!==undefined){filterChapter=d.chapter;filterStatus='all';navigate('materials')}else if(d.tab){tab=d.tab;render()}else if(d.practiceMaterial)startPractice({material:d.practiceMaterial});else if(d.practiceTheme)startPractice({t:d.practiceTheme});else if(d.answer){state.attempts[d.answer]={choice:d.value,at:new Date().toISOString()};save();render()}else if(d.retry){delete state.attempts[d.retry];save();render()}else if(d.original){navigate('material',d.original);tab='original';render()}else if(d.questionLink){startPractice({material:D.questions.find(q=>q.id===Number(d.questionLink)).material});practiceIndex=practiceList().findIndex(q=>q.id===Number(d.questionLink));render()}else if(d.action){switch(d.action){case'next':practiceIndex++;render();break;case'prev':practiceIndex--;render();break;case'wrong':practiceWrong=!practiceWrong;practiceIndex=0;render();break;case'clearMaterial':practiceMaterial=null;practiceIndex=0;render();break;case'reviewWrong':startPractice({wrong:true});break;}}});
document.addEventListener('change',e=>{const x=e.target;if(x.dataset.status){state.status[x.dataset.status]=x.value;save();if(view==='progress'||(view==='materials'&&filterStatus!=='all'))render();toast('学习状态已更新')}else if(x.id==='chapterFilter'){filterChapter=x.value;render()}else if(x.id==='statusFilter'){filterStatus=x.value;render()}else if(x.id==='practiceTheme'){practiceTheme=x.value;practiceMaterial=null;practiceIndex=0;render()}else if(x.id==='practiceChapter'){practiceChapter=x.value;practiceMaterial=null;practiceIndex=0;render()}});
let searchTimer;$('#search').addEventListener('input',e=>{query=e.target.value;clearTimeout(searchTimer);searchTimer=setTimeout(render,160)});$('#search').addEventListener('keydown',e=>{if(e.key==='Escape'){query='';e.target.value='';render()}});
render();

})().catch(e=>{const root=document.getElementById('app');root.textContent='知识地图暂时无法打开：'+e.message;});
