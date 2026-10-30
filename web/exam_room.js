/* 整卷模拟考试（行测，试炼塔左门“整卷模考”）：试卷列表/导入试卷/导入答案 → 全屏答题页（倒计时、答题卡、自动暂存）→ 交卷批改结果。
   所有判分、记成绩、奖励都在后端 /api/exam/*；这里只负责显示、计时和把作答存给后端。
   trial_hall.js 在 env.examRoom 时用 EXAM_ROOM.paneHtml()/mount() 替换原“套卷”面板；答题页是独立的全屏 <dialog>。 */
(() => {
 'use strict';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const clock=s=>{s=Math.max(0,Math.floor(s));return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');};
 const when=s=>String(s||'').slice(0,10);
 const LETTERS=['A','B','C','D'];
 let home=null,hooks=null,run=null;
 /* 错误必须画在考场自己的面板里：试炼塔面板和答题页都是模态<dialog>（顶层），页面上的toast会被盖在下面，用户看不到失败原因（踩坑记录 2026-10-26）。 */
 const failText=e=>String(e&&e.message||e||'操作失败');
 function homeError(message){const box=home?.querySelector('[data-er-error]');if(!box)return;box.textContent=message||'';box.hidden=!message;if(message)box.scrollIntoView({block:'nearest'});}
 function runError(r,message){const box=r.root.querySelector('[data-er-run-error]');if(!box)return;box.textContent=message||'';box.hidden=!message;}

 /* ------------------------------------------------------------------ 首页：试卷列表、导入 */
 function paneHtml(){return '<div class="er-home" data-er-home><p class="er-note" role="status">正在读取试卷…</p></div>';}
 function readFile(file,limit){
  return new Promise((resolve,reject)=>{
   if(file.size>limit)return reject(Error('文件太大，请控制在 '+Math.round(limit/1048576)+'MB 以内'));
   const r=new FileReader();r.onerror=()=>reject(Error('读取文件失败'));r.onload=()=>resolve(String(r.result));r.readAsDataURL(file);
  });
 }
 // 删除一份导入的套卷（多半是导入重复了）：整份删，题目/图片/作答暂存/大比里这一季的记录都没有了，已发奖励不收回
 async function deletePaper(season,name){
  if(!confirm(`删除「${name}」？\n\n这份试卷的全部题目、图片、作答暂存、草稿笔迹和它在宗门大比里的记录都会删除，不能恢复（已发的奖励不收回，原 PDF 不动）。`))return;
  homeError('');
  try{
   const r=await hooks.api('/api/exam/delete',{season});
   try{const prefix='xrpg-draw:exam:'+season+':';Object.keys(localStorage).filter(k=>k.startsWith(prefix)).forEach(k=>localStorage.removeItem(k));}catch(_){}
   await load();
   home.querySelector('.er-intro')?.insertAdjacentHTML('afterend',`<p class="er-ok" role="status">已删除「${esc(name)}」（${r.questions} 题）。</p>`);
   window.dispatchEvent(new Event('exam-paper-deleted'));
  }catch(error){homeError('删除「'+name+'」失败：'+failText(error));}
 }
 function paperRow(p){
  const last=p.last,running=p.run;
  const keyed=p.keyed>=p.total?`答案齐全`:p.keyed?`答案 ${p.keyed}/${p.total}`:'还没有答案';
  const line=running?`进行中 · 已答 ${running.answered} 题 · 已用 ${clock(running.elapsed)}`
   :last?`最近 ${last.score==null?'未出分':esc(last.score)+' 分'} · 用时 ${esc(last.minutes)} 分钟 · ${esc(when(last.submitted))}${p.attempts>1?' · 共考 '+p.attempts+' 次':''}`:'尚未考过';
  return `<article class="er-paper" data-er-season="${p.season}"><div class="er-paper-main"><b>${esc(p.name)}</b><small>${p.total} 题 · ${esc(keyed)}</small><small class="${running?'er-live':''}">${line}</small></div>
   <div class="er-paper-actions"><button type="button" class="primary" data-er-start="${p.season}">${running?'继续作答':last?'再考一次':'开始考试'}</button>${last?`<button type="button" data-er-result="${p.season}">查看成绩</button>`:''}<button type="button" data-er-answers="${p.season}" aria-expanded="false">${p.keyed>=p.total?'更新答案':'导入答案'}</button>${p.deletable?`<button type="button" class="er-danger" data-er-delete="${p.season}" data-er-pname="${esc(p.name)}" aria-label="删除试卷 ${esc(p.name)}">删除</button>`:''}</div>
   <form class="er-answers" data-er-answer-form="${p.season}" hidden><label><span>粘贴答案（如 <code>1-20 BCDAB…</code> 或每行 <code>1.A 2.B</code>）</span><textarea rows="4" data-er-answer-text></textarea></label><label><span>或选择答案文件（.txt / 答案页 PDF）</span><input type="file" accept=".txt,.pdf,text/plain,application/pdf" data-er-answer-file></label><div class="er-form-row"><button type="submit" class="primary">保存答案</button><span class="er-note" role="status"></span></div></form></article>`;
 }
 function homeHtml(d){
  const ready=d.pymupdf;
  const importer=`<details class="er-import"><summary>＋ 导入模拟试卷</summary><form data-er-import-form><label><span>试卷名称（会原样显示在宗门大比里）</span><input type="text" maxlength="40" placeholder="如：花生26下模拟卷第一套" data-er-name></label><label><span>试卷 PDF（题目 + 选项，约 130 题）</span><input type="file" accept=".pdf,application/pdf" data-er-pdf></label><p class="er-note">${ready?(d.ocr?'支持带文字的 PDF，也支持整页是图片的扫描卷（会用本机的文字识别找题号，约 1～3 分钟）。':'这台电脑没有可用的文字识别，只能导入带文字的 PDF；扫描图片版需要 Mac App 或装了中文 OCR 的 Windows。'):'PDF 缺少 pymupdf 组件，请使用完整电脑安装包。'}</p><div class="er-form-row"><button type="submit" class="primary" ${ready?'':'disabled'}>导入并拆分</button><span class="er-note" role="status" data-er-import-note></span></div></form></details>`;
  return `<p class="er-error" data-er-error role="alert" hidden></p><div class="er-intro"><h3>整卷模拟考试</h3><p>限时 <b>${d.minutes}</b> 分钟，全卷连续作答；交卷后批改并给分，成绩按试卷名称记进“宗门大比”，同时记一次模拟训练。分模块练习请走右边的“板块”。</p>${autoLabel()}</div>${importer}
   <div class="er-list" aria-label="试卷列表">${d.papers.map(paperRow).join('')||'<p class="er-empty">还没有可考的试卷。先用上面的“导入模拟试卷”导入一份 PDF。</p>'}</div>`;
 }
 async function load(){
  if(!home?.isConnected)return;
  try{
   const open=[...home.querySelectorAll('.er-answers:not([hidden])')].map(f=>f.dataset.erAnswerForm);
   const d=await hooks.api('/api/exam/list',{});if(!home?.isConnected)return;
   home.innerHTML=homeHtml(d);open.forEach(n=>{home.querySelector(`[data-er-answer-form="${n}"]`)?.removeAttribute('hidden');});
  }catch(error){if(home?.isConnected)home.innerHTML=`<p class="er-warn">${esc(error.message)}</p>`;}
 }
 function mount(host,h){
  hooks=h;home=host.querySelector('[data-er-home]')||host;
  if(!home.dataset.erBound){
   home.dataset.erBound='1';
   home.addEventListener('click',async e=>{
    const b=e.target.closest('button');if(!b||b.disabled)return;
    if(b.hasAttribute('data-er-start'))return openRun(Number(b.dataset.erStart));
    if(b.hasAttribute('data-er-result'))return openResult(Number(b.dataset.erResult));
    if(b.hasAttribute('data-er-delete'))return deletePaper(Number(b.dataset.erDelete),b.dataset.erPname||'');
    if(b.hasAttribute('data-er-answers')){const f=home.querySelector(`[data-er-answer-form="${b.dataset.erAnswers}"]`);f.hidden=!f.hidden;b.setAttribute('aria-expanded',String(!f.hidden));if(!f.hidden)f.querySelector('textarea').focus();}
   });
   home.addEventListener('change',e=>{if(e.target.matches?.('[data-er-auto]'))setAutoNext(e.target.checked);});
   home.addEventListener('submit',async e=>{
    e.preventDefault();const form=e.target,btn=form.querySelector('[type=submit]');
    if(form.hasAttribute('data-er-import-form')){
     const name=form.querySelector('[data-er-name]').value.trim(),file=form.querySelector('[data-er-pdf]').files[0],note=form.querySelector('[data-er-import-note]');
     if(!name)return void(note.textContent='先给试卷起个名字');if(!file)return void(note.textContent='先选择试卷 PDF');
     btn.disabled=true;homeError('');note.textContent='上传中…';
     const poll=setInterval(async()=>{try{const p=await hooks.api('/api/exam/progress',{});if(p.stage)note.textContent=p.stage+(p.total?` ${p.page}/${p.total}`:'')+(p.question?` · 第${p.question}题`:'')+'（请稍候，别关这个面板）';}catch(_){}},1200);
     try{const data=await readFile(file,40*1048576),r=await hooks.api('/api/exam/import',{name,data});
      note.textContent='';await load();
      const mods=Object.entries(r.modules||{}).map(([k,v])=>k+' '+v).join(' · '),gaps=(r.missing||[]).length;
      home.querySelector('.er-intro')?.insertAdjacentHTML('afterend',`<p class="er-ok" role="status">已导入「${esc(r.name)}」：共 ${r.total} 题${mods?'（'+esc(mods)+'）':''}，其中 ${r.keyed} 题带答案${r.keyed<r.total?'。这份试卷没带答案，可在下面“导入答案”补上，也可以先考，交卷时这些题不判分':''}。${gaps?` <b>有 ${gaps} 道题没认出来（第 ${r.missing.slice(0,12).join('、')} 题），请对照原卷。</b>`:''}${r.total&&r.total!==130?` 注意：不是 130 题，成绩估分会按“题量不一致”处理。`:''}</p>`);
     }catch(error){note.textContent='';homeError('导入「'+name+'」失败：'+failText(error));}
     finally{clearInterval(poll);if(btn.isConnected)btn.disabled=false;}
     return;
    }
    if(form.hasAttribute('data-er-answer-form')){
     const season=Number(form.dataset.erAnswerForm),text=form.querySelector('[data-er-answer-text]').value,file=form.querySelector('[data-er-answer-file]').files[0],note=form.querySelector('.er-note');
     homeError('');btn.disabled=true;note.textContent='保存中…';
     try{
      const body={season,text};
      if(file){if(/\.pdf$/i.test(file.name))body.pdf=await readFile(file,20*1048576);else if(!text.trim())body.text=await file.text();}
      const r=await hooks.api('/api/exam/answers',body);
      let msg=`补上 ${r.filled} 题答案，现有 ${r.keyed}/${r.total} 题`;
      if(r.regraded){msg+=`；已按新答案重新批改，成绩 ${r.regraded.score==null?'—':r.regraded.score} 分`;await hooks.refresh?.();}
      await load();const again=home.querySelector(`[data-er-answer-form="${season}"] .er-note`);if(again){again.textContent=msg;again.parentElement.parentElement.hidden=false;}
     }catch(error){note.textContent='';homeError('保存答案失败：'+failText(error));}
     finally{if(btn.isConnected)btn.disabled=false;}
    }
   });
  }
  load();
 }

 /* ------------------------------------------------------------------ 答题页 */
 function groupsOf(r){
  return r.modules.map(m=>{
   const nums=r.questions.filter(q=>q.module===m.name).map(q=>q.num);
   return {name:m.name,display:m.display,nums,from:Math.min(...nums),to:Math.max(...nums)};
  });
 }
 const answered=r=>Object.values(r.answers).filter(Boolean).length;
 function elapsedNow(r){return r.base+(r.running?Math.floor((Date.now()-r.t0)/1000):0);}

 // 选完答案自动跳下一题（只用于整卷模考；有即时对错的练习不跳）。本机偏好，默认开
 const autoNext=()=>{try{return localStorage.getItem('er.autoNext')!=='0';}catch(_){return true;}};
 const setAutoNext=on=>{try{localStorage.setItem('er.autoNext',on?'1':'0');}catch(_){}};
 const autoLabel=()=>`<label class="er-auto"><input type="checkbox" data-er-auto ${autoNext()?'checked':''}> 选完答案自动跳下一题</label>`;
 // 草稿按钮只画笔头（和首页右上角的笔同一个图标）；字号放大/缩小沿用答题页的同一个本机偏好（chatLayout.fs，初始大小不变）
 const PEN_SVG='<svg class="er-pen-ico" viewBox="0 0 24 24" aria-hidden="true" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M16.5 3.5l4 4L8 20l-5 1 1-5z"/><path d="M14 6l4 4"/></svg>';
 const sizeTools=()=>window.READING_TOOLS?.html?window.READING_TOOLS.html():'';
 function runShell(r){
  const d=document.createElement('dialog');d.className='er-run';d.setAttribute('aria-label','整卷模拟考试 · '+r.name);
  d.innerHTML=`<header class="er-bar"><button type="button" class="er-leave" data-er-leave aria-label="暂存并离开考场">✕</button><div class="er-title"><b>${esc(r.name)}</b><small data-er-pos></small></div>${sizeTools()}<button type="button" class="er-clock" aria-label="暂停倒计时" data-er-clock>--:--</button><button type="button" class="er-pen" data-er-pen aria-pressed="false" aria-label="草稿笔" title="草稿笔">${PEN_SVG}</button><button type="button" class="er-card-btn" data-er-card aria-haspopup="dialog" aria-expanded="false">答题卡 <small data-er-count></small></button></header>
   ${r.warning?`<p class="er-banner" data-er-warning>${esc(r.warning)}</p>`:''}<p class="er-banner er-error" data-er-run-error role="alert" hidden></p><p class="er-banner er-timeup" data-er-timeup hidden role="alert">时间到。可以继续作答，成绩会标记“超时”；也可以现在交卷。</p>
   <div class="er-body" data-er-body></div>
   <footer class="er-foot"><button type="button" data-er-prev>上一题</button><div class="er-choices" role="group" aria-label="选择答案" data-er-choices></div><button type="button" data-er-next>下一题</button></footer>
   <div class="er-rest" data-er-rest hidden role="dialog" aria-modal="true" aria-labelledby="er-rest-title"><div class="er-rest-card"><div class="er-rest-symbol" aria-hidden="true">☕</div><h2 id="er-rest-title">稍作休息</h2><p data-er-rest-progress></p><p>倒计时已暂停，调整好状态再继续。</p><p data-er-rest-error role="alert"></p><button type="button" class="primary" data-er-resume>继续答题</button></div></div>
   <aside class="er-sheet" data-er-sheet hidden role="dialog" aria-label="答题卡"><div class="er-sheet-panel"><header><b>答题卡</b><span class="er-sheet-count" data-er-sheet-count></span>${autoLabel()}<button type="button" data-er-sheet-close aria-label="关闭答题卡">✕</button></header><div class="er-sheet-body" data-er-sheet-body></div><footer><div class="er-legend" aria-hidden="true"><i class="done"></i>已答<i class="mark"></i>标记<i class="cur"></i>当前</div><p class="er-confirm" data-er-confirm hidden></p><div class="er-sheet-actions"><button type="button" data-er-continue hidden>继续答题</button><button type="button" class="primary" data-er-submit>交卷</button></div></footer></div></aside>`;
  return d;
 }

 // 草稿笔：复用全站的 DRAW（draw.js），画布挂进考场 <dialog>（否则会被顶层弹窗盖住）；笔迹按“考试+题号”存在本机，材料题的材料笔迹按材料共用
 function penOpts(r){
  const q=r.questions[r.idx];
  return {key:`exam:${r.season}:q${q.num}`,mkey:q.material?`exam:${r.season}:m${q.material}`:'',host:r.root,button:r.root.querySelector('[data-er-pen]'),
   place:bar=>placePenBar(r,bar),
   inMat:(x,y)=>{const m=r.root.querySelector('.er-material');if(!m)return false;const b=m.getBoundingClientRect();return x>=b.left&&x<=b.right&&y>=b.top&&y<=b.bottom;}};
 }
 // 草稿工具栏停在顶栏中间的空位（不盖住题目、也不盖住右边的计时/答题卡）：用左右边界让浏览器自己居中，不去量按钮宽度
 // （按钮里有表情符号，字体加载前后宽度会变）；放不下先换紧凑样式，再不行工具栏内部可左右滑动。
 function placePenBar(r,bar){
  const head=r.root.querySelector('.er-bar'),leave=head?.querySelector('[data-er-leave]'),clock=head?.querySelector('[data-er-clock]');
  if(!head||!leave||!clock)return;
  const hb=head.getBoundingClientRect(),lb=leave.getBoundingClientRect(),cb=clock.getBoundingClientRect();
  Object.assign(bar.style,{transform:'none',left:Math.round(lb.right+8)+'px',right:Math.round(innerWidth-(cb.left-8))+'px',width:'fit-content',maxWidth:'none',margin:'0 auto',overflowX:'auto'});
  const room=cb.left-8-(lb.right+8);bar.classList.remove('compact');
  if(bar.offsetWidth>room+1)bar.classList.add('compact');
  if(bar.offsetWidth>room+1){bar.style.width='auto';bar.style.margin='0';bar.style.justifyContent='safe center';}   // 紧凑了还放不下：撑满空位，内部可左右滑动
  bar.style.top=Math.round(Math.max(0,hb.top+(hb.height-bar.offsetHeight)/2))+'px';
 }
 // 顶栏或工具栏的宽度之后变了（字体晚加载、窗口缩放）就重新摆，不能压到右边的计时。
 let penRO=null;
 function watchPenBar(r,again){
  penRO?.disconnect();penRO=null;
  if(!window.ResizeObserver)return;
  // 重摆后再补一次：宽度还在跟着字体/换行慢慢稳定
  let t=0;penRO=new ResizeObserver(()=>{cancelAnimationFrame(t);t=requestAnimationFrame(()=>{if(window.DRAW?.state.on){again();setTimeout(()=>{if(window.DRAW?.state.on)again();},160);}else{penRO?.disconnect();penRO=null;}});});
  const head=r.root.querySelector('.er-bar'),bar=r.root.querySelector('.draw-bar');
  [head,head?.querySelector('[data-er-clock]'),head?.querySelector('[data-er-leave]'),bar].forEach(el=>el&&penRO.observe(el));
 }
 function togglePen(r){
  if(!window.DRAW)return;
  const btn=r.root.querySelector('[data-er-pen]');
  if(DRAW.state.on){DRAW.close();btn?.setAttribute('aria-pressed','false');}
  else{DRAW.open(penOpts(r));btn?.setAttribute('aria-pressed','true');const again=()=>{const bar=r.root.querySelector('.draw-bar');if(bar&&DRAW.state.on)placePenBar(r,bar);};requestAnimationFrame(again);setTimeout(again,250);document.fonts?.ready?.then(again);watchPenBar(r,again);}   // 表情符号字体加载后按钮宽度会变，多摆几次
 }
 function closePen(r){
  if(window.DRAW&&DRAW.state.on&&DRAW.state.ext&&DRAW.state.ext.host===r.root)DRAW.close();
  r.root.querySelector('[data-er-pen]')?.setAttribute('aria-pressed','false');
 }
 function renderQuestion(r){
  closePen(r);                                   // 换题前把这题的草稿存好收起
  const q=r.questions[r.idx],body=r.root.querySelector('[data-er-body]');
  const mat=q.material&&r.materials[q.material];
  const same=q.material&&r.lastMaterial===q.material;
  body.innerHTML=`${mat?`<section class="er-material" tabindex="0" aria-label="共用材料">${blocksHtml(mat,true)}</section>`:''}<section class="er-question" tabindex="0" aria-label="第 ${q.num} 题"><div class="er-qhead"><span class="er-qnum">第 ${q.num} 题</span><span class="er-qmodule">${esc(q.board)}</span><button type="button" class="er-mark${r.marks.has(q.num)?' on':''}" data-er-mark aria-pressed="${r.marks.has(q.num)}">${r.marks.has(q.num)?'★ 已标记':'☆ 标记'}</button>${q.original?.length?'<button type="button" class="er-orig-btn" data-er-orig aria-expanded="false">对照原图</button>':''}</div>${blocksHtml(q.blocks,false,true)}${q.original?.length?`<div class="er-original" data-er-original hidden><p class="er-orig-note">识别出的文字可能有误，以原图为准。</p>${blocksHtml(q.original)}</div>`:''}</section>`;
  body.classList.toggle('er-split',!!mat);
  const mp=body.querySelector('.er-material');if(mp&&same&&r.matScroll)mp.scrollTop=r.matScroll;
  mp?.addEventListener('scroll',()=>{r.matScroll=mp.scrollTop;r.lastMaterial=q.material;},{passive:true});
  r.lastMaterial=q.material||'';
  r.root.querySelector('[data-er-pos]').textContent=`第 ${r.idx+1}/${r.questions.length} 题 · ${r.modules.find(m=>m.name===q.module)?.display||q.module}`;
  r.root.querySelector('[data-er-prev]').disabled=r.idx===0;
  r.root.querySelector('[data-er-next]').disabled=r.idx>=r.questions.length-1;
  choices(r);counter(r);
  window.DRAW?.refresh(penOpts(r));              // ✏ 上的小点：这题有草稿
 }
 function choices(r){
  const q=r.questions[r.idx],cur=r.answers[q.num]||'';
  const box=r.root.querySelector('[data-er-choices]'),keep=box.contains(document.activeElement)?document.activeElement.dataset.erChoice:'';
  box.innerHTML=q.choices.map(c=>`<button type="button" class="er-choice${cur===c?' on':''}" data-er-choice="${c}" aria-pressed="${cur===c}">${c}</button>`).join('');
  if(keep)box.querySelector(`[data-er-choice="${keep}"]`)?.focus({preventScroll:true});
 }
 function counter(r){
  const n=answered(r);r.root.querySelector('[data-er-count]').textContent=`${n}/${r.questions.length}`;
 }
 function sheetHtml(r){
  const groups=groupsOf(r);
  return groups.map(g=>{
   const done=g.nums.filter(n=>r.answers[n]).length;
   return `<section class="er-group"><h4>${esc(g.display)} <small>${g.from}–${g.to} · 已答 ${done}/${g.nums.length}</small></h4><div class="er-grid">${g.nums.map(n=>`<button type="button" class="er-cell${r.answers[n]?' done':''}${r.marks.has(n)?' mark':''}${r.questions[r.idx].num===n?' cur':''}" data-er-jump="${n}" aria-label="第${n}题${r.answers[n]?'，已答 '+r.answers[n]:'，未答'}${r.marks.has(n)?'，已标记':''}">${n}</button>`).join('')}</div></section>`;
  }).join('');
 }
 function refreshSheet(r){
  const s=r.root.querySelector('[data-er-sheet]');if(s.hidden)return;
  s.querySelector('[data-er-sheet-body]').innerHTML=sheetHtml(r);
  const left=r.questions.length-answered(r);
  s.querySelector('[data-er-sheet-count]').textContent=`已答 ${answered(r)}/${r.questions.length}${r.marks.size?' · 标记 '+r.marks.size:''}${left?' · 未答 '+left:''}`;
 }
 function openSheet(r,open){
  const s=r.root.querySelector('[data-er-sheet]');s.hidden=!open;
  r.root.querySelector('[data-er-card]').setAttribute('aria-expanded',String(open));
  if(open){resetConfirm(r);refreshSheet(r);s.querySelector('.er-cell.cur')?.scrollIntoView({block:'center'});s.querySelector('[data-er-submit]').focus({preventScroll:true});}
  else r.root.querySelector('[data-er-card]').focus({preventScroll:true});
 }
 function resetConfirm(r){
  const s=r.root.querySelector('[data-er-sheet]');s.querySelector('[data-er-confirm]').hidden=true;s.querySelector('[data-er-continue]').hidden=true;
  const b=s.querySelector('[data-er-submit]');b.textContent='交卷';b.dataset.erSure='';
 }

 /* 暂存：答案、标记、已用秒数。失败只提示一次，不打断作答 */
 // 每题作答用时：只在计时进行、页面可见时累计到当前这一题（休息、切到别的标签页不算）；每秒一次，单次最多记 3 秒，防止挂机被算成做题
 function flushQ(r){
  const now=Date.now();
  if(r.running&&!r.paused&&!r.finished&&r.qMark&&!document.hidden){const q=r.questions[r.idx];if(q){const dt=Math.min(now-r.qMark,3000);if(dt>0)r.qt[q.num]=(r.qt[q.num]||0)+dt/1000;}}
  r.qMark=now;
 }
 const qtimesOf=r=>Object.fromEntries(Object.entries(r.qt).map(([k,v])=>[k,Math.round(v)]).filter(([,v])=>v>0));
 async function persist(r,quiet){
  if(r.saving)return r.saving;
  flushQ(r);r.dirty=false;
  const body={season:r.season,answers:r.answers,marks:[...r.marks],elapsed:elapsedNow(r),paused:!!r.paused,qtimes:qtimesOf(r)};
  r.saving=hooks.api('/api/exam/save',body).then(()=>runError(r,'')).catch(error=>{r.dirty=true;if(!r.warned||!quiet){r.warned=true;runError(r,'答案暂存失败（会继续重试，请别关闭这个页面）：'+failText(error));}}).finally(()=>{r.saving=null;});
  return r.saving;
 }
 function touch(r){r.dirty=true;clearTimeout(r.saveT);r.saveT=setTimeout(()=>persist(r,true),500);}

 function tick(r){
  flushQ(r);
  const left=r.limit-elapsedNow(r),el=r.root.querySelector('[data-er-clock]');
  el.textContent=left>=0?clock(left):'超时 +'+clock(-left);
  el.classList.toggle('low',left<=600&&left>0);el.classList.toggle('over',left<=0);
  if(left<=0&&!r.timeup){r.timeup=true;r.root.querySelector('[data-er-timeup]').hidden=false;}
  r.root.querySelector('[data-er-timeup]').hidden=!r.timeup;
 }
 function stop(r){
  r.running=false;clearInterval(r.timer);clearInterval(r.autosave);clearTimeout(r.saveT);
 }
 function pauseAdd(r){/* 把正在跑的秒数并入基数，再重新计时 */
  r.base=elapsedNow(r);r.t0=Date.now();
 }

 function showRest(r){
  const rest=r.root.querySelector('[data-er-rest]');rest.hidden=!r.paused;
  if(r.paused){rest.querySelector('[data-er-rest-progress]').textContent=`已作答 ${answered(r)} / ${r.questions.length} 题`;rest.querySelector('[data-er-resume]').focus({preventScroll:true});}
 }
 async function restTransition(r,pause){
  if(r.transitioning)return;r.transitioning=true;
  const error=r.root.querySelector('[data-er-rest-error]');error.textContent='';
  if(pause){flushQ(r);pauseAdd(r);r.running=false;r.paused=true;showRest(r);tick(r);}
  if(r.saving)await r.saving;
  if(!pause)r.paused=false;
  await persist(r,false);
  if(r.dirty){r.paused=true;r.running=false;showRest(r);error.textContent='暂停状态暂存失败，请检查连接后重试。';}
  else if(!pause){r.running=true;r.t0=Date.now();r.qMark=Date.now();showRest(r);tick(r);r.root.querySelector('[data-er-clock]').focus({preventScroll:true});}
  r.transitioning=false;
 }

 async function leave(r){
  pauseAdd(r);stop(r);
  try{await persist(r,false);}catch(_){}
  close(r);
 }
 function close(r){
  closePen(r);
  document.removeEventListener('visibilitychange',r.visible);document.removeEventListener('keydown',r.key);
  if(r.root.open)r.root.close();r.root.remove();
  if(run===r)run=null;
  load();
 }

 async function openRun(season){
  if(run)return;
  let data;
  try{data=await hooks.api('/api/exam/begin',{season});}catch(error){return homeError('开始考试失败：'+failText(error));}
  const r={season,name:data.summary.name,questions:data.questions,materials:data.materials,modules:data.modules,
   limit:data.run.limit,base:data.run.elapsed||0,t0:Date.now(),paused:!!data.run.paused,running:!data.run.paused,idx:0,answers:{...(data.run.answers||{})},
   marks:new Set(data.run.marks||[]),warning:data.warning||'',timeup:false,lastMaterial:'',matScroll:0,
   qt:{...(data.run.qtimes||{})},qMark:Date.now()};
  const first=r.questions.findIndex(q=>!r.answers[q.num]);r.idx=first<0?0:first;
  r.root=runShell(r);document.body.appendChild(r.root);run=r;
  r.root.addEventListener('cancel',e=>{if(e.target!==r.root)return;e.preventDefault();if(window.DRAW&&(DRAW.state.on||performance.now()-(DRAW.state.closedAt||-1e9)<400))return DRAW.state.on&&DRAW.close();if(r.paused)return;if(r.root._erDone)return r.root._erDone();if(!r.root.querySelector('[data-er-sheet]').hidden)openSheet(r,false);else leave(r);});
  r.root.addEventListener('click',e=>onClick(r,e));
  r.root.addEventListener('change',e=>{if(e.target.matches?.('[data-er-auto]'))setAutoNext(e.target.checked);});
  window.READING_TOOLS?.bind(r.root);
  r.root.showModal();renderQuestion(r);tick(r);showRest(r);
  r.timer=setInterval(()=>{if(document.hidden){return;}tick(r);},1000);
  r.autosave=setInterval(()=>persist(r,true),30000);
  r.visible=()=>{if(document.hidden)persist(r,true);};document.addEventListener('visibilitychange',r.visible);
  r.key=e=>onKey(r,e);document.addEventListener('keydown',r.key);
  if(!r.paused)r.root.querySelector('.er-choice,[data-er-next]')?.focus({preventScroll:true});
 }
 function go(r,i){
  if(i<0||i>=r.questions.length)return;flushQ(r);r.idx=i;renderQuestion(r);
  r.root.querySelector('.er-question')?.scrollTo?.(0,0);
 }
 function pick(r,letter){
  const q=r.questions[r.idx];
  r.answers[q.num]=r.answers[q.num]===letter?'':letter;
  choices(r);counter(r);touch(r);
  // 选中（不是取消）一个答案后，稍等一下让选中状态看得见，再自动进入下一题；最后一题不跳
  clearTimeout(r.autoT);
  if(r.answers[q.num]&&autoNext()&&r.idx<r.questions.length-1){
   const at=r.idx;r.autoT=setTimeout(()=>{if(r.root.open&&!r.finished&&!r.paused&&!r.transitioning&&r.idx===at)go(r,at+1);},280);
  }
 }
 function onKey(r,e){
  if(r.finished||r.paused||r.transitioning||!r.root.open||e.target.closest('input,textarea,select')||document.documentElement.classList.contains('drawing'))return;
  if(!r.root.querySelector('[data-er-sheet]').hidden)return;
  const k=e.key.toUpperCase();
  if(LETTERS.includes(k)&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&r.questions[r.idx].choices.includes(k)){e.preventDefault();pick(r,k);}
  else if(e.key==='ArrowRight'||e.key==='PageDown'){e.preventDefault();go(r,r.idx+1);}
  else if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();go(r,r.idx-1);}
 }
 async function onClick(r,e){
  const b=e.target.closest('button');if(!b||b.disabled)return;
  if(r.transitioning)return;
  if(b.hasAttribute('data-er-resume')&&r.paused)return restTransition(r,false);
  if(r.paused)return;
  if(b.hasAttribute('data-er-clock'))return restTransition(r,true);
  if(b.hasAttribute('data-er-pen'))return togglePen(r);
  if(b.hasAttribute('data-er-leave'))return leave(r);
  if(b.hasAttribute('data-er-card'))return openSheet(r,true);
  if(b.hasAttribute('data-er-sheet-close'))return openSheet(r,false);
  if(b.hasAttribute('data-er-choice'))return pick(r,b.dataset.erChoice);
  if(b.hasAttribute('data-er-prev'))return go(r,r.idx-1);
  if(b.hasAttribute('data-er-next'))return go(r,r.idx+1);
  if(b.hasAttribute('data-er-orig')){const box=r.root.querySelector('[data-er-original]');if(box){box.hidden=!box.hidden;b.setAttribute('aria-expanded',String(!box.hidden));b.textContent=box.hidden?'对照原图':'收起原图';}return;}
  if(b.hasAttribute('data-er-mark')){const n=r.questions[r.idx].num;r.marks.has(n)?r.marks.delete(n):r.marks.add(n);touch(r);return renderQuestion(r);}
  if(b.hasAttribute('data-er-jump')){const i=r.questions.findIndex(q=>q.num===Number(b.dataset.erJump));openSheet(r,false);return go(r,i);}
  if(b.hasAttribute('data-er-continue'))return resetConfirm(r);
  if(b.hasAttribute('data-er-submit')){
   const left=r.questions.length-answered(r),box=r.root.querySelector('[data-er-confirm]');
   if(!b.dataset.erSure){
    b.dataset.erSure='1';b.textContent='确认交卷';r.root.querySelector('[data-er-continue]').hidden=false;
    box.hidden=false;box.textContent=left?`还有 ${left} 题没有作答，交卷后这些题按未答计。确定交卷吗？`:'全部题目都已作答。确定交卷吗？';
    return;
   }
   return submit(r,b);
  }
 }
 async function submit(r,btn){
  btn.disabled=true;flushQ(r);pauseAdd(r);stop(r);
  try{
   const res=await hooks.api('/api/exam/submit',{season:r.season,answers:r.answers,marks:[...r.marks],elapsed:r.base,qtimes:qtimesOf(r)});
   document.removeEventListener('visibilitychange',r.visible);r.finished=true;
   if(res.events)hooks.events?.(res.events);
   await hooks.refresh?.();
   const detail=await hooks.api('/api/exam/result',{season:r.season}).catch(()=>null);
   showResult(r.root,{...res,rows:detail?.rows||[]},()=>close(r));
  }catch(error){
   btn.disabled=false;r.running=true;r.t0=Date.now();
   r.timer=setInterval(()=>{if(!document.hidden)tick(r);},1000);r.autosave=setInterval(()=>persist(r,true),30000);
   runError(r,'交卷失败，答案没有丢，可以再点一次“交卷”：'+failText(error));
   openSheet(r,false);
  }
 }

 /* ------------------------------------------------------------------ 结果页 */
 function resultBody(x){
  const sum=(k)=>x.modules.reduce((a,m)=>a+m[k],0),ok=x.ok??sum('ok'),bad=x.bad??sum('bad'),blank=x.blank??sum('blank'),nokey=x.nokey??sum('nokey');
  const wrong=(x.rows||[]).filter(r=>r.status==='bad'||r.status==='blank');
  const sec=n=>n==null?'':Math.floor(n/60)+':'+String(n%60).padStart(2,'0');
  const timed=(x.rows||[]).filter(r=>r.sec>0),slow=timed.slice().sort((a,b)=>b.sec-a.sec).slice(0,8);
  const avg=timed.length?Math.round(timed.reduce((a,r)=>a+r.sec,0)/timed.length):0;
  return `<div class="er-score"><span class="er-score-num">${x.score==null?'—':esc(x.score)}</span><span class="er-score-unit">分</span></div>
   <p class="er-meta">${esc(x.name)} · 用时 ${esc(x.minutes??'—')} 分钟${x.overtime?' <b class="er-over-tag">超时</b>':''}${x.attempts>1?' · 第 '+x.attempts+' 次考试':''}</p>
   ${x.basis?`<p class="er-basis">${esc(x.basis)}${x.partial?'：有 '+nokey+' 题没有标准答案，不判分，导入答案后会自动重新批改。':'。'}</p>`:''}
   <div class="er-stats"><span><b>${ok}</b>答对</span><span><b>${bad}</b>答错</span><span><b>${blank}</b>未答</span>${nokey?`<span><b>${nokey}</b>无答案</span>`:''}</div>
   <table class="er-table"><thead><tr><th>模块</th><th>答对/题数</th><th>正确率</th></tr></thead><tbody>${x.modules.map(m=>{const g=m.total-m.nokey;return `<tr><td>${esc(m.display)}</td><td>${m.ok}/${m.total}</td><td>${g?Math.round(100*m.ok/g)+'%':'—'}</td></tr>`;}).join('')}</tbody></table>
   ${wrong.length?`<h4 class="er-wrong-h">错题与未答（${wrong.length}）</h4><div class="er-wrong">${wrong.map(r=>`<span class="er-chip ${r.status}" title="${esc(r.board)}">第${r.num}题 <small>${r.status==='bad'?'你选'+esc(r.mine)+' · 正确'+esc(r.correct):'未答 · 正确'+esc(r.correct||'？')}${r.sec?' · 用时'+sec(r.sec):''}</small></span>`).join('')}</div>`:''}
   ${timed.length?`<h4 class="er-wrong-h">用时最长的题（平均每题 ${sec(avg)}）</h4><div class="er-wrong">${slow.map(r=>`<span class="er-chip ${r.status}" title="${esc(r.board)}">第${r.num}题 <small>${sec(r.sec)} · ${r.status==='ok'?'答对':r.status==='bad'?'答错':r.status==='blank'?'未答':'无答案'}</small></span>`).join('')}</div>`:''}`;
 }
 function showResult(root,x,onClose){
  root.classList.add('er-done');
  root.innerHTML=`<header class="er-bar"><button type="button" class="er-leave" data-er-back aria-label="返回考场入口">✕</button><div class="er-title"><b>${esc(x.name)}</b><small>成绩</small></div></header><div class="er-result" tabindex="0">${resultBody(x)}</div><footer class="er-foot er-result-foot"><span class="er-note">成绩、正确率与各板块复盘已记进“宗门大比”。</span><button type="button" data-er-contest>去宗门大比看复盘</button><button type="button" class="primary" data-er-back>返回</button></footer>`;
  root.onclick=e=>{
   const b=e.target.closest('button');if(!b)return;
   if(b.hasAttribute('data-er-back'))return onClose();
   if(b.hasAttribute('data-er-contest')){onClose();hooks.toContest?.();}
  };
  root._erDone=onClose;
  root.querySelector('.er-result').focus({preventScroll:true});
 }
 async function openResult(season){
  let data;try{data=await hooks.api('/api/exam/result',{season});}catch(error){return homeError('读取成绩失败：'+failText(error));}
  const d=document.createElement('dialog');d.className='er-run er-done';d.setAttribute('aria-label','整卷成绩 · '+data.name);document.body.appendChild(d);
  d.addEventListener('cancel',e=>{if(e.target!==d)return;e.preventDefault();d._erDone?.();});
  d.showModal();showResult(d,data,()=>{d.close();d.remove();load();});
 }

 window.EXAM_ROOM={paneHtml,mount,isOpen:()=>!!run};
})();
