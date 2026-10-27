/* ✍ 实操：申论完整真题题库、作答、综合批改（后端 rpg/shenlun_bank.py、shenlun_review.py，接口 /api/shenlun/*）。
   两处用到：
   - 办理殿「实操」厅（HALL = shizhan）：分类选择训练 → 作答 → 批改结果；
   - 档案室「📑 题库」：下载/录入真题、标注主题。
   在作答页写答案会计入“做题”学时：敲键盘时通知后端（节流），后端核对 2 分钟内有操作才算。 */
"use strict";
(() => {
  const S = { page: "list", qid: "", q: null, result: null, busy: false, lastKey: 0, lastPing: 0, stat: "", qs: null };
  const HIT = { full: ["落实", "ok"], half: ["部分落实", "half"], none: ["未落实", "none"] };
  const post = (url, body) => api(url, body || {});
  const rerender = () => (VIEW === "bank" ? renderTrain() : render());

  // ---------------------------------------------------------------- 办理殿 · 实操
  function hallStat() { return S.stat || "作答批改"; }

  async function hallHtml() {
    return S.page === "answer" ? answerHtml() : listHtml();
  }

  async function answerHtml() {
    if (!S.q || S.q.qid !== S.qid) {
      try { S.q = await post("/api/shenlun/question", { qid: S.qid }); }
      catch (e) { S.page = "list"; return `<div class="card muted">${esc(e.message)}</div>` + (await listHtml()); }
    }
    if (S.q.complete_bank) return fullAnswerHtml();
    return '<div class="card muted">这道题不是完整真题，请回档案室重新选择。</div>';
  }

  function bindHall(root) {
    bindBank(root);
    SL_TRAINING.bind(root,open);
    const lib = () => { LIB.tab = "bank"; go("skeleton"); };
    const l1 = root.querySelector("#slToLib"), l2 = root.querySelector("#slToLib2");
    if (l1) l1.onclick = lib;
    if (l2) l2.onclick = lib;
    root.querySelectorAll("[data-slq]").forEach((c) => (c.onclick = () => { open(c.dataset.slq); }));
    const back = root.querySelector("#slBack");
    if (back) back.onclick = async () => { if (!(await leaveAnswer())) return; S.page = "list"; S.result = null;if(S.origin==="library"){LIB.tab="bank";go("skeleton");}else rerender(); };
    const ta = root.querySelector("#slAns");
    if (ta && S.q.complete_bank) { bindFullAnswer(root, ta);SL_TRAINING.bindNavigation(root,S.qid,open); return; }
  }

  async function open(qid,training=false) {
    if(S.opening)return;S.opening=true;
    try {
    if (!(await leaveAnswer())) return;
    S.origin=training?"train":"library";if(!training)SL_TRAINING.clearSession();
    S.draftText = ""; S.draftFor = ""; S.q = null; S.result = null; S.qid = qid;
    if (qid.startsWith("slq-")) {
      try {
        S.q = await post("/api/shenlun/question", { qid });
        const d = await post("/api/shenlun/answer", { qid });
        S.draftText = d.text; S.draftFor = qid; B.revision = d.revision; B.seconds = d.seconds;B.card=d.card||{pages:[]};B.marks=d.material_marks||{};B.confirm=!!d.confirmed_card_hash;B.clockSession=uid();B.clockOn=true;
        B.history = (await post("/api/shenlun/history", { qid })).history; B.dirty = false; B.seq = 0;
        const local = localDraft(qid);
        B.recovery = local && (local.text !== d.text || JSON.stringify(local.card)!==JSON.stringify(d.card) || JSON.stringify(local.material_marks||{})!==JSON.stringify(d.material_marks||{})) ? local : null;
        if (B.recovery && local.revision === d.revision) { S.draftText = local.text;B.card=local.card||B.card;B.marks=local.material_marks||B.marks;B.confirm=false; B.dirty = true; }
      } catch (e) { showError(e); return; }
    }
    HALL = "shizhan"; S.page = "answer";
    await (VIEW === "bank" ? renderTrain() : go("bank"));
    } finally {S.opening=false;}
  }

  function active() {
    return !S.busy && !B.ocrBusy && (!S.q?.complete_bank || B.clockOn) && VIEW === "bank" && HALL === "shizhan" && S.page === "answer" && document.visibilityState === "visible" && Date.now() - S.lastKey < 120000;
  }
  function board() { return S.q ? S.q.type : ""; }

  // ---------------------------------------------------------------- 档案室 · 题库
  async function libHtml() { return `<div class="sl-lib">${await bankHtml(true)}</div>`; }
  function bindLib(root) { bindBank(root); }

  // 完整真题：题干材料与作答分开，参考资料只在批改后展示。
  const B = { papers: [], region: '', year: '', type: '', search: '', topic:'', page: 0, dirty: false, seq: 0, revision: 0, seconds: 0, saving: null, timer: null, history: [], recovery: null, card: {pages:[]}, marks:{}, marksView:null, confirm: false, clockSession: '', clockOn: true, clockTimer: null, cardView: null, ocrBusy:false, clockStamp:0 };
  const localDraft = qid => { try { return JSON.parse(localStorage.getItem('sl.draft.' + qid) || 'null'); } catch (_) { return null; } };
  const keepDraft = () => { try { localStorage.setItem('sl.draft.' + S.qid, JSON.stringify({ text: S.draftText, card:B.card, material_marks:B.marks, revision: B.revision, updated: Date.now() })); } catch (_) {} };
  const uid = () => [...crypto.getRandomValues(new Uint8Array(16))].map(x => x.toString(16).padStart(2, '0')).join('');
  async function listHtml() {
    return SL_TRAINING.html();
  }
  async function bankHtml(importing) {
    const d = await api('/api/shenlun/papers'); B.papers = d.papers;
    const controls = `<div class="card sl-bank-head"><div class="row"><h3>真题档案库 <small>录入 → 作答 → 证据批改 → 修改复练</small></h3><span class="spacer"></span>${importing ? '' : '<button class="ghost small" id="slBankImport">录入真题</button>'}</div>
      <p class="small muted">按题干和给定资料独立作答，交卷前隐藏参考答案。批改建议分供训练使用，评分标准同题固定。</p>
      ${materialStats()}<button class="primary" id="slSourceStart">⬇ 下载并录入公开申论题库</button> <button class="ghost small" id="slBankRefresh">刷新题库</button>
      <div class="small muted" id="slSourceStatus">首次下载约330MB，保存到电脑的申论库；重复录入保留已有题目。</div>
      ${importing ? `<details class="sl-bank-input"><summary>导入自己的题目包（JSON）</summary><p class="small muted">可导入整套或多套；包含title、materials和questions。材料原文、参考答案只存本地。</p><input type="file" id="slPackage" accept=".json"><button class="ghost small" id="slTemplate">下载格式模板</button><div id="slImportMessage" class="small muted"></div></details>
      <details class="sl-bank-input"><summary>手动录入一道题</summary><div class="sl-manual-grid">
      <label>试卷标题<input id="slManualTitle" placeholder="如2026国考行政执法"></label><label>地区<input id="slManualRegion" placeholder="国考 / 贵州"></label>
      <label>题型<select id="slManualType">${['归纳概括','综合分析','提出对策','贯彻执行','大作文'].map(x=>`<option>${x}</option>`).join('')}</select></label>
      <label>满分<input id="slManualScore" type="number" min="1" max="150" value="20"></label><label>字数上限<input id="slManualWords" type="number" min="0" max="5000" value="300"></label></div>
      <label>题干及要求<textarea id="slManualStem" rows="3" placeholder="粘贴完整题干及作答要求"></textarea></label>
      <label>对应给定资料<textarea id="slManualMaterial" rows="7" placeholder="粘贴本题需要的完整材料，保留材料编号"></textarea></label>
      <label>参考答案（可空）<textarea id="slManualReference" rows="3"></textarea></label><button id="slManualSave" class="primary">录入并保存</button><div id="slManualMessage" class="small muted"></div></details>` : ''}</div>`;
    return controls + '<div id="slPaperList">' + paperListHtml() + '</div>';
  }
  function materialStats() {
    const c={};B.papers.forEach(p=>p.questions.forEach(q=>{c[q.material_source]=(c[q.material_source]||0)+1;}));
    const total=Object.values(c).reduce((a,b)=>a+b,0);if(!total)return '';
    return `<p class="small muted sl-material-stats">材料对应：题干写明或已选定 ${(c.stem||0)+(c.manual||0)+(c.import||0)} 题 · 使用全卷 ${(c.whole||0)+(c.single||0)} 题 · 可按引文对应 ${c.quote||0} 题 · 待确认 ${c.all||0} 题（作答时点“选定本题材料”）</p>`;
  }
  function paperListHtml() {
    const regions = [...new Set(B.papers.map(p=>p.region))].sort(), years = [...new Set(B.papers.map(p=>p.year))].sort().reverse();
    const select = (id, values, value, label) => `<select id="${id}" aria-label="${label}"><option value="">${label}</option>${values.map(x=>`<option ${x===value?'selected':''}>${esc(x)}</option>`).join('')}</select>`;
    const filtered = B.papers.filter(p=>(!B.region||p.region===B.region)&&(!B.year||p.year===B.year)&&(!B.search||p.title.includes(B.search))).map(p=>({...p,questions:p.questions.filter(q=>(!B.type||q.type===B.type)&&(!B.topic||q.topics.includes(B.topic)))})).filter(p=>p.questions.length);
    const count = Math.ceil(filtered.length/12); B.page = Math.min(B.page, Math.max(0,count-1));
    const filter = `<div class="card row sl-bank-filters">${select('slFilterRegion',regions,B.region,'全部地区')}${select('slFilterYear',years,B.year,'全部年份')}${select('slFilterType',['归纳概括','综合分析','提出对策','贯彻执行','大作文'],B.type,'全部题型')}${select('slFilterTopic',[...new Set(B.papers.flatMap(p=>p.questions.flatMap(q=>q.topics)))].sort(),B.topic,'全部主题')}<input id="slFilterSearch" placeholder="搜索试卷" value="${esc(B.search)}"><span class="small muted">${filtered.length}套 · ${filtered.reduce((n,p)=>n+p.questions.length,0)}题</span></div>`;
    if (!filtered.length) return filter + '<div class="card sl-empty">还没有匹配的完整真题。可下载公开题库，或在档案室录入自己的题目。</div>';
    return filter + filtered.slice(B.page*12,B.page*12+12).map(p=>`<details class="card sl-paper"><summary><b>${esc(p.title)}</b><span class="tag">${esc(p.region)}</span><span class="small muted">${p.questions.length}题 · ${esc(p.edition)}</span></summary><p class="small muted">${esc(p.source)} · 材料${p.materials}则</p><div class="row">${p.topics.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}<button class="ghost small" data-sl-topic-edit="${esc(p.id)}">标注整卷主题</button>${p.questions.some(q=>q.material_source==='quote')?`<button class="ghost small" data-slmat-auto="${esc(p.id)}" title="题干引用的原文逐字出现在某则材料里的题，自动定为对应材料">按引文对应材料（${p.questions.filter(q=>q.material_source==='quote').length}题）</button>`:''}</div>${p.questions.map(q=>`<div class="sl-paper-q"><span class="tag cur">第${q.no}题 · ${esc(q.type)}</span><span class="small muted">${q.total||'分值待补'}分${q.words?' · '+q.words+'字':''}</span>${q.complete?'':'<span class="tag bad">资料待补全</span>'}${q.material_source==='all'?'<span class="tag" title="题干指明了具体材料，但无法自动对应；作答时可选定">材料待确认</span>':q.material_source==='quote'?'<span class="tag" title="题干引用的原文能在某则材料里找到">材料可按引文对应</span>':''}<p>${esc(q.stem)}</p><div class="row">${q.topics.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}<span class="small muted">${esc(q.topic_scope)}</span><button class="ghost small" data-sl-topic-edit="${esc(q.qid)}">标注本题主题</button></div><button class="primary small" data-slq="${esc(q.qid)}">作答</button></div>`).join('')}</details>`).join('') + `<div class="card row"><button id="slPaperPrev" ${B.page?'':'disabled'}>← 上一页</button><span>第${B.page+1}/${count}页</span><button id="slPaperNext" ${B.page<count-1?'':'disabled'}>下一页 →</button></div>`;
  }
  function bindBank(root) {
    const $ = s=>root.querySelector(s);
    const redraw = () => { const box=$('#slPaperList'); if(box) { box.innerHTML=paperListHtml(); bindBank(root); } };
    for (const [id,key] of [['#slFilterRegion','region'],['#slFilterYear','year'],['#slFilterType','type'],['#slFilterTopic','topic']]) { const el=$(id); if(el)el.onchange=()=>{B[key]=el.value;B.page=0;redraw();}; }
    const search=$('#slFilterSearch'); if(search)search.onchange=()=>{B.search=search.value.trim();B.page=0;redraw();};
    root.querySelectorAll('[data-slq]').forEach(el=>el.onclick=()=>open(el.dataset.slq));
    const prev=$('#slPaperPrev'),next=$('#slPaperNext'); if(prev)prev.onclick=()=>{B.page--;redraw();};if(next)next.onclick=()=>{B.page++;redraw();};
    SL_TRAINING.bindTopics(root,B.papers);
    root.querySelectorAll('[data-slmat-auto]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const d=await post('/api/shenlun/materials',{auto:b.dataset.slmatAuto});toast(`已为${d.done}道题对应材料`);rerender();}catch(e){showError(e);b.disabled=false;}});
    const imp=$('#slBankImport');if(imp)imp.onclick=()=>{LIB.tab='bank';go('skeleton');};
    const refreshBtn=$('#slBankRefresh');if(refreshBtn)refreshBtn.onclick=rerender;
    const status=$('#slSourceStatus'),start=$('#slSourceStart');
    async function progress() {
      if(!status?.isConnected)return;
      try {const d=await post('/api/shenlun/bank_source'); status.textContent=d.message+(d.running?' · '+d.progress+'%':'');start.disabled=d.running;
        if(d.running)setTimeout(progress,1500);
      } catch(e) {status.textContent=e.message;}
    }
    if(start) {start.onclick=async()=>{start.disabled=true;try{await post('/api/shenlun/bank_source',{start:true});progress();}catch(e){showError(e);start.disabled=false;}};progress();}
    const file=$('#slPackage');if(file)file.onchange=async()=>{const f=file.files[0];if(!f)return;const msg=$('#slImportMessage');try{if(f.size>32*1024*1024)throw Error('题目包最大32MB');const papers=JSON.parse(await f.text());const d=await post('/api/shenlun/bank_import',{papers});msg.textContent=`新增${d.added}套，已有${d.skipped}套保留`;toast(msg.textContent);rerender();}catch(e){msg.textContent=e.message;}};
    const template=$('#slTemplate');if(template)template.onclick=()=>{const data={title:'自编示例卷（请替换为你的试卷）',region:'自编',year:'2026',sourceName:'用户提供',materials:[{id:'1',label:'材料1',text:'在这里粘贴完整材料原文'}],questions:[{type:'贯彻执行',text:'在这里粘贴题干和要求',score:20,limit:400,material_ids:['1'],references:[]}]};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='申论题目包模板.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    const manual=$('#slManualSave');if(manual)manual.onclick=async()=>{const msg=$('#slManualMessage');try{const material=$('#slManualMaterial').value.trim();if(!material)throw Error('请填写对应完整材料');const ref=$('#slManualReference').value.trim();const papers={title:$('#slManualTitle').value.trim(),region:$('#slManualRegion').value.trim(),sourceName:'用户录入',materials:[{text:material,label:'对应给定资料'}],questions:[{text:$('#slManualStem').value.trim(),type:$('#slManualType').value,score:Number($('#slManualScore').value),limit:Number($('#slManualWords').value),references:ref?[{organization:'用户提供',answer:ref}]:[]}]};const d=await post('/api/shenlun/bank_import',{papers});msg.textContent=`新增${d.added}套，已有${d.skipped}套保留`;toast(msg.textContent);rerender();}catch(e){msg.textContent=e.message;}};
  }
  // 来源段落优先；无段落时仅做阅读分隔，不冒充原文段落、不改材料内容。
  function materialHtml(text) {
    let paras=String(text||'').split(/\r\n?|\n/).map(x=>x.trim()).filter(Boolean);
    const reading=paras.length===1 && [...paras[0]].length>300;
    if(reading){
      const sentences=paras[0].match(/[^。！？]*[。！？]+[”’」』]*|[^。！？]+$/g)||paras;
      paras=[];let current='';
      for(const sentence of sentences){current+=sentence;if([...current].length>=200){paras.push(current);current='';}}
      if(current)paras.push(current);
    }
    return `${reading?'<p class="small muted sl-paragraph-note">来源未标注段落，以下按句群分隔阅读；不代表原文段落。</p>':''}<div class="sl-material-text">${paras.map(x=>`<p>${esc(x)}</p>`).join('')}</div>`;
  }
  function fullAnswerHtml() {
    const q=S.q, ids=q.material_ids||[], labelOf=id=>(q.all_materials||[]).find(m=>m.id===id)?.label||id;
    const source={manual:'已按你的选择',import:'题目自带',stem:'按题干写明的资料'}[q.material_source]||'';
    const sg=q.suggested_material_ids||[],sgNames=sg.map(labelOf).map(esc).join('、');
    const notice=q.material_source==='all'&&(q.all_materials||[]).length>1
      ? `<p class="small warn sl-material-notice">题干指明了具体材料但无法自动对应，现显示全卷${sg.length?`；${q.suggest_kind==='quote'?'题干引用的原文出现在':'按用词推测相关的是'}“${sgNames}”`:''}；批改按全卷。${sg.length?'<button class="ghost small" id="slMaterialAdopt">采用推测</button>':''}<button class="ghost small" id="slMaterialPick">选定本题材料</button></p>`
      : q.material_source==='whole'&&(q.all_materials||[]).length>1 ? `<p class="small muted sl-material-notice">本题使用全部给定资料（题干没限定具体材料）<button class="ghost small" id="slMaterialPick">调整</button></p>`
      : (q.all_materials||[]).length>1 ? `<p class="small muted sl-material-notice">本题材料：${q.materials.map(m=>esc(m.label)).join('、')}（${source}）<button class="ghost small" id="slMaterialPick">调整</button></p>` : '';
    const tabs=q.materials.length>1?`<div class="sl-material-tabs row" role="tablist" aria-label="本题材料">${q.materials.map((m,i)=>`<button class="ghost small${(q.suggested_material_ids||[]).includes(m.id)?' sl-suggested':''}" role="tab" data-mat-tab="${i}" aria-selected="${i===0}">${esc(m.label)}</button>`).join('')}</div>`:'';
    return `<div class="card sl-exam-heading"><div class="row"><button class="ghost small" id="slBack">← ${S.origin==='train'?'回训练选择':'回档案题库'}</button>${SL_TRAINING.navigation(S.qid)}<span class="tag cur">${esc(q.type)}</span><b>${esc(q.paper_title)} · 第${q.no}题</b><span class="spacer"></span><span>${q.total||'待补分值'}分${q.words?' · '+q.words+'字':''}</span>${q.type==='大作文'?'<button class="ghost small" id="slEssay" title="审题立意、提纲点评">大作文助手</button>':''}<button class="ghost small" id="slSplit" title="调整左右分栏宽度">⇔ 分栏</button><button class="ghost small" id="slStemToggle" aria-expanded="false">展开题干</button></div><div class="sl-task-scroll sl-stem-collapsed"><p class="sl-stem">${esc(q.stem).replace(/\[materialid\](\d+)\[\/materialid\]/g,'').replace(/\n/g,'<br>')}</p>${q.requirement?`<p>${esc(q.requirement)}</p>`:''}<div class="small muted">${esc(q.edition)} · ${esc(q.source)}</div></div></div>
      ${q.complete?'':'<div class="warn">本题缺少材料或分值，可以先保存作答；请在本地训练/题库/申论真题中核对并补全材料、分值后，再刷新题库进行批改。</div>'}
      <div class="sl-full-grid"><section class="card sl-materials${tabs||notice?' sl-has-label':''}"><div class="sl-material-toolbar">${SL_MATERIALS.toolbar()}<div class="sl-material-labels">${tabs}${notice}</div></div><div class="sl-material-scroll">${q.materials.map((m,i)=>`<article data-mat-article="${i}"${i?' class="sl-mat-off"':''}><h4>${esc(m.label)}</h4><div class="sl-sheet-window"><div class="sl-material-sheet" data-material="${i}">${materialHtml(m.text)}<canvas class="sl-material-ink" aria-label="材料${i+1}勾画层"></canvas></div></div></article>`).join('')||'<p class="muted">尚未录入材料</p>'}</div></section>
      <section class="card sl-writing"><div class="row sl-write-top"><h3>我的作答</h3><b id="slElapsed" class="small">作答用时 00:00</b><button class="ghost small" id="slClockPause">暂停计时</button><span class="spacer"></span><span class="small muted" id="slSaveStatus">已保存 · 有效编辑${Math.floor(B.seconds/60)}分钟</span><button class="ghost small" id="slDraftSave">保存</button>${SL_CARD.tools()}</div>
      ${B.recovery?'<button class="ghost small" id="slRecover">恢复本机未保存文字</button>':''}${SL_CARD.html(q)}
      <details class="sl-transcription" open><summary>识别文字核对 / 打字作答</summary><textarea id="slAns" class="sl-ta" spellcheck="false" placeholder="手写识别结果在这里核对；也可直接打字作答。"></textarea><button class="ghost small" id="slConfirmText">确认文字并保存</button><span id="slOcrStatus" class="small muted"></span></details>
      <p class="small muted">材料、题干和本次答案会发给设置中的AI。先建立材料评分标准，再按含义判断；失败不计分，草稿保留。</p>
      ${B.history.length?`<details><summary>历史作答与批改（${B.history.length}稿）</summary>${B.history.map((x,i)=>`<button class="ghost small" data-slhistory="${i}">第${i+1}稿 · ${x.result.total}/${x.result.full}</button>`).join('')}</details>`:''}
      <div class="row sl-submit-row"><span class="small muted" id="slCnt"></span><span class="spacer"></span><button class="primary" id="slSubmit" ${q.complete?'':'disabled'}>交卷 · 综合批改</button></div></section></div>
      <section id="slRes">${S.result?comprehensiveHtml(S.result):''}</section>`;
  }
  // 材料页签、题干折叠、左右分栏：只改显示，不动材料内容和笔迹。
  const SPLITS=[['40:60','40%'],['50:50','50%'],['30:70','30%'],['60:40','60%']];
  const splitIndex=()=>{try{return Math.max(0,SPLITS.findIndex(x=>x[0]===localStorage.getItem('sl.split')));}catch(_){return 0;}};
  function applySplit(root,i){const v=SPLITS[i];root.style.setProperty('--sl-split',v[1]);const b=root.querySelector('#slSplit');if(b)b.textContent='⇔ 分栏 '+v[0];}
  // 大作文助手：立意拆解 → 提纲点评；只给方向和判断，全文仍用原来的作答与综合批改。
  function essayAnglesHtml(a) {
    if(!a)return '<p class="small muted">还没拆解过。点下面按钮，AI会依据题干和材料列出几个可行的立意方向和易写偏的地方（不写范文）。</p>';
    return `<p class="small"><b>任务：</b>${esc(a.task)}</p>${a.angles.map(x=>`<div class="sl-pt"><b>${esc(x.title)}</b><p>${esc(x.thesis)}</p><blockquote class="sl-ev">${esc(x.basis)}</blockquote><p class="small muted">易偏：${esc(x.risk||'—')}</p></div>`).join('')}${a.avoid.length?`<p class="small warn">避免：${a.avoid.map(esc).join('；')}</p>`:''}`;
  }
  function essayReviewHtml(r) {
    if(!r)return '';
    return `<div class="sl-pt"><b>中心论点：${esc(r.thesis.status)}</b><p class="small">${esc(r.thesis.reason)}</p></div>${r.parts.map(x=>`<div class="sl-pt"><blockquote class="sl-ev">${esc(x.quote)}</blockquote><p class="small">${esc(x.comment)}</p></div>`).join('')}${r.material_use.map(x=>`<div class="sl-pt"><blockquote class="sl-ev">${esc(x.quote)}</blockquote>${x.material_quote?`<p class="small muted">材料：${esc(x.material_quote)}</p>`:''}<p class="small">${esc(x.comment)}</p></div>`).join('')}<p><b>先改这一点：</b>${esc(r.next)}</p>`;
  }
  function bindEssay(root) {
    const btn=root.querySelector('#slEssay');if(!btn)return;
    btn.onclick=async()=>{
      const dlg=document.createElement('dialog');dlg.className='sl-essay-dialog card';
      dlg.innerHTML=`<div class="row"><h3>大作文助手</h3><span class="spacer"></span><button class="ghost small" data-essay-close>关闭</button></div>
        <p class="small muted">先审题立意，再写提纲让AI点评，最后写全文。只给方向和判断，不代写；每一步会调用一次AI。</p>
        <section><h4>1. 立意拆解</h4><div id="slEssayAngles" class="small muted">加载中……</div><button class="ghost small" id="slEssayAnglesRun">生成立意拆解</button></section>
        <section><h4>2. 我的提纲</h4><textarea id="slEssayOutline" rows="7" spellcheck="false" placeholder="写出中心论点和各分论点，每条一两句话，不用写成文章。"></textarea>
        <div class="row"><span class="small muted" id="slEssayStatus"></span><span class="spacer"></span><button class="ghost small" id="slEssaySave">保存提纲</button><button class="primary small" id="slEssayReview">提纲点评</button></div><div id="slEssayReviewBox"></div></section>`;
      document.body.append(dlg);dlg.showModal();
      const $=sel=>dlg.querySelector(sel),close=()=>{dlg.close();dlg.remove();};
      dlg.querySelector('[data-essay-close]').onclick=close;dlg.addEventListener('cancel',()=>setTimeout(()=>dlg.remove(),0));
      const run=async(button,action,extra,done)=>{button.disabled=true;const old=button.textContent;button.textContent='处理中……';try{done(await post('/api/shenlun/essay',{qid:S.qid,action,...extra}));}catch(e){toast(e.message);}button.disabled=false;button.textContent=old;};
      const showState=d=>{$('#slEssayAngles').innerHTML=essayAnglesHtml(d.angles);$('#slEssayAnglesRun').textContent=d.angles?'重新生成':'生成立意拆解';$('#slEssayAnglesRun').dataset.again=d.angles?'1':'';$('#slEssayOutline').value=d.outline.text||'';$('#slEssayReviewBox').innerHTML=essayReviewHtml(d.outline.review);};
      try{showState(await post('/api/shenlun/essay',{qid:S.qid}));}catch(e){$('#slEssayAngles').textContent=e.message;}
      $('#slEssayAnglesRun').onclick=e=>run(e.target,'angles',{force:!!$('#slEssayAnglesRun').dataset.again},d=>{$('#slEssayAngles').innerHTML=essayAnglesHtml(d.angles);$('#slEssayAnglesRun').textContent='重新生成';$('#slEssayAnglesRun').dataset.again='1';});
      $('#slEssaySave').onclick=e=>run(e.target,'outline_save',{text:$('#slEssayOutline').value},d=>{$('#slEssayStatus').textContent='已保存';$('#slEssayReviewBox').innerHTML=essayReviewHtml(d.outline.review);});
      $('#slEssayReview').onclick=async e=>{const b=e.target;b.disabled=true;const old=b.textContent;b.textContent='点评中……';
        try{await post('/api/shenlun/essay',{qid:S.qid,action:'outline_save',text:$('#slEssayOutline').value});const d=await post('/api/shenlun/essay',{qid:S.qid,action:'outline_review'});$('#slEssayReviewBox').innerHTML=essayReviewHtml(d.outline.review);$('#slEssayStatus').textContent='已点评';}
        catch(err){toast(err.message);}b.disabled=false;b.textContent=old;};
    };
  }
  function bindLayout(root) {
    const $=s=>root.querySelector(s);
    const toggle=$('#slStemToggle'),box=$('.sl-task-scroll');
    toggle.onclick=()=>{const open=box.classList.toggle('sl-stem-collapsed')===false;toggle.setAttribute('aria-expanded',String(open));toggle.textContent=open?'收起题干':'展开题干';};
    let split=splitIndex();applySplit(document.documentElement,split);
    $('#slSplit').onclick=()=>{split=(split+1)%SPLITS.length;applySplit(document.documentElement,split);try{localStorage.setItem('sl.split',SPLITS[split][0]);}catch(_){}window.dispatchEvent(new Event('resize'));};
    const show=i=>{root.querySelectorAll('[data-mat-article]').forEach(a=>a.classList.toggle('sl-mat-off',a.dataset.matArticle!==String(i)));root.querySelectorAll('[data-mat-tab]').forEach(t=>t.setAttribute('aria-selected',String(t.dataset.matTab===String(i))));const sc=$('.sl-material-scroll');if(sc)sc.scrollTop=0;window.dispatchEvent(new Event('resize'));};
    root.querySelectorAll('[data-mat-tab]').forEach(t=>t.onclick=()=>show(t.dataset.matTab));
    const pick=$('#slMaterialPick');
    if(pick)pick.onclick=()=>{
      const q=S.q,chosen=new Set(q.material_source==='all'?(q.suggested_material_ids?.length?q.suggested_material_ids:[]):q.material_ids);
      const dlg=document.createElement('dialog');dlg.className='sl-material-dialog card';
      dlg.innerHTML=`<h3>选定本题用到的材料</h3><p class="small muted">勾选后，左边只显示这些材料，批改也只依据它们。全选或不选等于恢复全卷。</p>${q.all_materials.map(m=>`<label class="row"><input type="checkbox" value="${esc(m.id)}" ${chosen.has(m.id)?'checked':''}> ${esc(m.label)}</label>`).join('')}<div class="row"><button class="ghost" value="cancel">取消</button><span class="spacer"></span><button class="primary" id="slPickOk">确定</button></div>`;
      document.body.append(dlg);dlg.showModal();
      dlg.querySelector('[value="cancel"]').onclick=()=>{dlg.close();dlg.remove();};
      dlg.querySelector('#slPickOk').onclick=async()=>{const ids=[...dlg.querySelectorAll('input:checked')].map(x=>x.value);try{if(!(await flushDraft()))return;await post('/api/shenlun/materials',{qid:S.qid,ids});dlg.close();dlg.remove();open(S.qid,S.origin==='train');}catch(e){toast(e.message);}};
    };
    const adopt=$('#slMaterialAdopt');
    if(adopt)adopt.onclick=async()=>{try{if(!(await flushDraft()))return;await post('/api/shenlun/materials',{qid:S.qid,ids:S.q.suggested_material_ids});open(S.qid,S.origin==='train');}catch(e){toast(e.message);}};
    const best=(S.q.suggested_material_ids||[])[0],idx=best?S.q.materials.findIndex(m=>m.id===best):0;if(idx>0)show(idx);
  }
  function calibrationHtml(c,refs) {
    const run=refs?`<button class="ghost small" id="slCalibrateRun">${c?'重新校准':'开始校准'}</button> <span class="small muted">会让AI批改${Math.min(refs,2)}份参考答案，不计成绩、不给奖励。</span>`:'<span class="small muted">这道题没有参考答案，无法校准。</span>';
    if(!c)return `<p class="small muted">还没有校准过。评分标准由AI根据材料生成，非官方细则；校准能看出它对这道题偏严还是偏松。</p>${run}`;
    return `<p><b>${esc(c.verdict)}</b></p>${c.results.map(x=>x.error?`<p class="small bad">${esc(x.source)}：试批失败（${esc(x.error)}）</p>`:`<p class="small">${esc(x.source)}：${x.total}/${x.full}（得分率${Math.round(x.rate*100)}%，${x.words}字）${x.missed.length?' · 未覆盖：'+x.missed.map(esc).join('、'):''}</p>`).join('')}<p class="small muted">校准于 ${esc(c.created.replace("T"," "))}</p>${run}`;
  }
  function bindCalibration(box) {
    box.addEventListener('toggle',async e=>{
      const d=e.target;if(!d.matches?.('.sl-calibrate')||!d.open||d.dataset.loaded)return;d.dataset.loaded='1';
      const body=d.querySelector('.sl-calibrate-body');
      try{const r=await post('/api/shenlun/calibrate',{qid:S.qid,standard_hash:d.dataset.hash});body.innerHTML=calibrationHtml(r.saved,Number(d.dataset.refs));}catch(err){body.textContent=err.message;}
    },true);
    box.addEventListener('click',async e=>{
      const btn=e.target.closest('#slCalibrateRun');if(!btn)return;const d=btn.closest('.sl-calibrate'),body=d.querySelector('.sl-calibrate-body');
      btn.disabled=true;body.insertAdjacentHTML('afterbegin','<p class="thinking small">正在用参考答案试批……</p>');
      try{const r=await post('/api/shenlun/calibrate',{qid:S.qid,run:true});body.innerHTML=calibrationHtml(r.saved,Number(d.dataset.refs));}
      catch(err){body.innerHTML=`<p class="small bad">${esc(err.message)}</p>`+calibrationHtml(null,Number(d.dataset.refs));}
    });
  }
  function comprehensiveHtml(r) {
    const points=r.points.map(x=>`<div class="sl-pt ${x.hit}"><div class="row"><b>${esc(x.name)}</b><span class="tag">${HIT[x.hit][0]}</span><span class="spacer"></span><span>${x.earned}/${x.score}</span></div><p class="sl-point-action">${x.hit==='full'?'核心含义已覆盖，保持。':esc(x.suggestion||x.reason||'补充该核心含义。')}</p><details class="sl-point-detail"><summary>查看材料与作答证据</summary><p class="small"><b>材料依据：</b>${esc(x.material_quote)}</p><blockquote class="sl-ev"><b>你的原句：</b>${esc(x.evidence||'未体现')}</blockquote><p class="small">${esc(x.reason)}</p></details></div>`).join('');
    return `<div class="card sl-pishi"><div class="row"><h3>领导批示 · 综合批改</h3><span class="spacer"></span><b class="sl-review-total">${r.total}/${r.full}</b></div><p>${esc(r.summary)}</p><div class="row">${r.parts.map(x=>`<span class="tag">${esc(x.name)} ${x.earned}/${x.full}</span>`).join('')}<span class="small muted">${r.words}字${r.answer_seconds!==undefined?' · 作答用时'+Math.floor(r.answer_seconds/60)+'分'+r.answer_seconds%60+'秒':''} · ${esc(r.method)}</span></div><p class="small muted">${esc(r.scoring_note)}${r.word_warning?' · '+esc(r.word_warning):''}</p></div>
      ${r.comparison?`<div class="card sl-comparison"><h3>修改稿对比</h3><p>上一稿${r.comparison.previous}分 → 本稿${r.total}分（${r.comparison.change>=0?'+':''}${r.comparison.change}）</p><p>改善：${esc(r.comparison.improved.join('、')||'暂无新增命中')}</p><p>退步：${esc(r.comparison.regressed.join('、')||'暂无')}</p></div>`:''}
      <div class="card"><h3>题干任务拆解</h3><p>${esc(r.task)}</p></div>
      ${points?`<div class="card"><h3>材料与作答逐点对照</h3>${points}</div>`:''}
      <div class="sl-review-grid"><div class="card"><h3>结构与表达</h3>${r.dimensions.map(x=>`<div class="sl-pt"><b>${esc(x.name)} · ${x.level}/4档</b><p>${esc(x.reason)}</p><details><summary class="small">查看原句</summary><blockquote class="sl-ev">${esc(x.quote||'尚未体现')}</blockquote></details><p class="small">下一步：${esc(x.improvement||'保持')}</p></div>`).join('')}</div><div class="card"><h3>题型专项检查</h3>${r.checks.map(x=>`<p><b>${esc(x.name)} · ${esc(x.status)}</b><br>${esc(x.reason)}</p>`).join('')||'<p class="muted">本题未返回额外专项检查</p>'}<h3>原句修改建议</h3>${r.revisions.length?`<p class="small ${r.revision_verified?'muted':'warn'}">${r.revision_verified?`将以下修改同时替换原句后共${r.revision_words}字${r.word_limit?' / 上限'+r.word_limit+'字':''}，已由程序核验。`:'历史建议未核验整篇字数，请重新批改后采用。'}</p>`:''}${r.revisions.map(x=>`<div class="sl-pt"><blockquote class="sl-ev">${esc(x.quote)}</blockquote><p><b>建议：</b>${esc(x.rewrite)}</p><p class="small muted">${esc(x.reason)}</p></div>`).join('')||'<p class="muted">优先按采分点缺口修改</p>'}</div></div>
      <details class="card"><summary>交卷后参考资料</summary>${r.references.map(x=>`<h4>${esc(x.source)}</h4><p>${esc(x.answer).replace(/\n/g,'<br>')}</p>`).join('')}${r.analysis?`<h4>来源库解析（非官方细则）</h4><p>${esc(r.analysis).replace(/\n/g,'<br>')}</p>`:''}${!r.references.length&&!r.analysis?'<p>该题未提供参考答案或解析。</p>':''}</details><details class="card sl-calibrate" data-hash="${esc(r.standard_hash)}" data-refs="${r.references.length}"><summary>评分标准校准 <small class="muted">用参考答案试批，看这套标准偏严还是偏松</small></summary><div class="sl-calibrate-body small muted">展开后查看。</div></details><p class="small muted">复盘已保存：${esc(r.review_file)}</p>`;
  }
  function saveLabel(value) {const el=document.getElementById('slSaveStatus');if(el)el.textContent=value;}
  async function flushDraft() {
    clearTimeout(B.timer);
    if(B.saving)return B.saving;
    B.saving=(async()=>{
      while(B.dirty&&S.q?.complete_bank){
        const qid=S.qid,text=S.draftText,seq=B.seq,revision=B.revision;
        saveLabel('正在保存……');
        try{const d=await post('/api/shenlun/answer',{save:true,qid,text,revision,card:B.card,material_marks:B.marks,confirm_handwriting:B.confirm});B.revision=d.revision;B.seconds=d.seconds;
          if(B.seq===seq){B.dirty=false;try{localStorage.removeItem('sl.draft.'+qid);}catch(_){}}else keepDraft();
          saveLabel('已保存');
        }catch(e){saveLabel('保存失败，点击“保存”重试');toast(e.message);return false;}
      }return true;
    })();
    try{return await B.saving;}finally{B.saving=null;}
  }
  async function leaveAnswer(){if(S.busy||B.ocrBusy){toast(B.ocrBusy?'正在识别，请等本次识别完成':'正在批改，请等本次批改完成');return false;}B.marksView?.destroy();B.cardView?.destroy();if(!(await flushDraft()))return false;clearInterval(B.clockTimer);B.clockTimer=null;if(S.q?.complete_bank)await clockTick(false);return true;}
  async function clockTick(active){if(!S.q?.complete_bank)return;const qid=S.qid;try{const d=await post('/api/shenlun/card/clock',{qid,session:B.clockSession,active});if(qid!==S.qid)return;B.seconds=d.seconds;B.clockStamp=Date.now();const el=document.getElementById('slElapsed');if(el)el.textContent='作答用时 '+String(Math.floor(d.seconds/60)).padStart(2,'0')+':'+String(d.seconds%60).padStart(2,'0');}catch(e){B.clockOn=false;toast(e.message);}}
  function bindFullAnswer(root,ta) {
    ta.value=S.draftText||'';
    const changed=()=>{S.lastKey=Date.now();B.confirm=false;root.querySelector('#slOcrStatus').textContent='笔迹已修改，请识别并核对文字后确认。';B.dirty=true;B.seq++;keepDraft();saveLabel('未保存');clearTimeout(B.timer);B.timer=setTimeout(flushDraft,800);post('/api/shenlun/active').catch(()=>{});};
    bindLayout(root);
    bindEssay(root);
    bindCalibration(root.querySelector('#slRes'));
    B.cardView=SL_CARD.mount(root,S.q,B.card,changed);
    B.marksView=SL_MATERIALS.mount(root,S.q,B.marks,()=>{S.lastKey=Date.now();B.dirty=true;B.seq++;keepDraft();saveLabel('未保存');clearTimeout(B.timer);B.timer=setTimeout(flushDraft,800);});
    root.querySelector('#slClockPause').onclick=async()=>{B.clockOn=!B.clockOn;root.querySelector('#slClockPause').textContent=B.clockOn?'暂停计时':'继续计时';S.lastKey=Date.now();await clockTick(B.clockOn&&!S.busy);};
    clearInterval(B.clockTimer);S.lastKey=Date.now();clockTick(true);let ticks=0;B.clockTimer=setInterval(()=>{if(!root.isConnected){clearInterval(B.clockTimer);return;}const active=B.clockOn&&!S.busy&&!B.ocrBusy&&!document.hidden&&Date.now()-S.lastKey<120000;if(++ticks%10===0)clockTick(active);const seconds=B.seconds+(active&&B.clockStamp?Math.min(10,Math.floor((Date.now()-B.clockStamp)/1000)):0);root.querySelector('#slElapsed').textContent='作答用时 '+String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');},1000);
    root.querySelector('.sl-materials').onpointerdown=()=>{S.lastKey=Date.now();};
    root.querySelector('#slRecognize').onclick=async()=>{const btn=root.querySelector('#slRecognize');btn.disabled=true;B.ocrBusy=true;try{await clockTick(false);if(!(await flushDraft()))return;const seq=B.seq;const images=B.cardView.images();if(!images.length)throw Error('先在答题卡上写字');root.querySelector('#slOcrStatus').textContent='正在识别原文……';const d=await post('/api/shenlun/card/recognize',{qid:S.qid,revision:B.revision,images});if(seq!==B.seq)throw Error('识别期间笔迹已修改，请重新识别');ta.value=d.text;ta.oninput();root.querySelector('#slOcrStatus').textContent=d.engine+'：请核对错字、标点和段落，再确认文字。';}catch(e){root.querySelector('#slOcrStatus').textContent=e.message;}finally{btn.disabled=false;B.ocrBusy=false;S.lastKey=Date.now();}};
    root.querySelector('#slConfirmText').onclick=async()=>{B.confirm=true;B.dirty=true;B.seq++;if(await flushDraft())root.querySelector('#slOcrStatus').textContent='文字已确认，可以提交批改。';};
    const count=()=>{const n=[...ta.value.replace(/\s/g,'')].length;root.querySelector('#slCnt').textContent=n+'字'+(S.q.words?' / '+S.q.words:'');};
    ta.oninput=()=>{B.confirm=false;S.lastKey=Date.now();S.draftText=ta.value;B.dirty=true;B.seq++;keepDraft();count();saveLabel('未保存');clearTimeout(B.timer);B.timer=setTimeout(flushDraft,800);if(Date.now()-S.lastPing>15000){S.lastPing=Date.now();post('/api/shenlun/active').catch(()=>{});}};count();
    root.querySelector('#slDraftSave').onclick=flushDraft;
    const recover=root.querySelector('#slRecover');if(recover)recover.onclick=()=>{ta.value=B.recovery.text;B.card=B.recovery.card||B.card;B.marks=B.recovery.material_marks||B.marks;B.marksView?.destroy();B.marksView=SL_MATERIALS.mount(root,S.q,B.marks,()=>ta.oninput());B.cardView?.destroy();B.cardView=SL_CARD.mount(root,S.q,B.card,changed);ta.oninput();recover.remove();};
    root.querySelectorAll('[data-slhistory]').forEach(b=>b.onclick=()=>{S.result=B.history[Number(b.dataset.slhistory)].result;root.querySelector('#slRes').innerHTML=comprehensiveHtml(S.result);});
    root.querySelector('#slSubmit').onclick=async()=>{if(S.busy||!ta.value.trim())return;S.busy=true;const btn=root.querySelector('#slSubmit');btn.disabled=true;ta.disabled=true;
      try{await clockTick(false);if(!(await flushDraft()))throw Error('答案尚未保存，请先重试保存');btn.textContent='建立标准并阅卷中……';root.querySelector('#slRes').innerHTML='<div class="card thinking">领导正在核对题干、材料与作答证据……</div>';
        const r=await post('/api/shenlun/comprehensive',{qid:S.qid,answer:S.draftText,revision:B.revision,submission_id:(B.pending?.text===S.draftText&&B.pending.qid===S.qid?B.pending.id:(B.pending={text:S.draftText,qid:S.qid,id:uid()}).id)});B.pending=null;S.result=r;root.querySelector('#slRes').innerHTML=comprehensiveHtml(r);B.history=(await post('/api/shenlun/history',{qid:S.qid})).history;handleEvents(r.events);await refresh();
      }catch(e){root.querySelector('#slRes').innerHTML=`<div class="card warn">${esc(e.message)}。答案草稿仍保留；若网络断开，重试会核对本次交卷记录。</div>`;}
      S.busy=false;btn.disabled=false;ta.disabled=false;btn.textContent='交卷 · 综合批改';};
    if(B.dirty)B.timer=setTimeout(flushDraft,800);
  }
  document.addEventListener('visibilitychange',()=>{if(document.getElementById('slElapsed'))clockTick(!document.hidden&&B.clockOn&&!S.busy&&!B.ocrBusy);});
  addEventListener('beforeunload',e=>{if(B.dirty){keepDraft();e.preventDefault();e.returnValue='';}});
  window.SHENLUN = { focused:()=>S.page==='answer'&&!!S.q?.complete_bank, hallStat, hallHtml, bindHall, libHtml, bindLib, active, board, flush: leaveAnswer };
})();
