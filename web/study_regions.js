/* 3.0.3修炼分区：app.js调用html/bind，CARDS按简匣路径归类，MINDMAP按板块筛选。
   只保存本次页面选择；不搬动资料、不新增存档、不计算奖励。行测五峰沿用宗门五脉。
   路径中以最深的已知板块为准，兼容“行测::板块::子匣”；未知简匣仍在藏经阁管理。 */
(() => {
  'use strict';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const peaks=[
    {id:'chang',name:'万象峰',subject:'常识与政治理论',hint:'认识天地 · 通晓世事',boards:['常识判断','政治理论']},
    {id:'yan',name:'辨言峰',subject:'言语理解',hint:'见字辨意 · 理清主旨',boards:['片段阅读','逻辑填空'],aliases:['言语理解','成语实词']},
    {id:'li',name:'明理峰',subject:'判断推理',hint:'理清论证 · 识破迷障',boards:['论证逻辑','形式逻辑','一拖五','定义判断','类比推理','图形推理'],aliases:['判断推理']},
    {id:'shu',name:'演数峰',subject:'数量关系',hint:'推演变化 · 寻找解法',boards:['数量关系']},
    {id:'zi',name:'观星峰',subject:'资料分析',hint:'观测数据 · 看清趋势',boards:['资料分析']}
  ];
  let selected='',subject='',images={},branch='',category='',exam='2026-10-guokao';
  const common=[
    {id:'geo',name:'地理',hint:'山川形胜 · 经纬天地',icon:'◎',aliases:['地理','地理常识','地理知识','自然地理','人文地理','中国地理','世界地理']},
    {id:'history',name:'文史',hint:'读史明理 · 文脉千年',icon:'▤',aliases:['文史','文史常识','文史知识','历史','历史常识','人文','人文常识','文化','文化常识']},
    {id:'economy',name:'经济',hint:'经世济用 · 通晓运行',icon:'◈',aliases:['经济','经济常识','经济知识']},
    {id:'science',name:'科技',hint:'格物致知 · 探索万象',icon:'✧',aliases:['科技','科技常识','科技知识','科学','科学常识']}
  ];
  // 复用功能判断，避免申论静态文件的术语替换改写科目比较常量。
  const office=()=>typeof isSL==='function'&&isSL();
  const peaksMode=()=>typeof isSL==='function'&&!isSL();
  function groups(){
    if(peaksMode())return peaks;
    const boards=[...new Set((DASH.tree||[]).map(b=>b.board))];
    const fallback=office()?['归纳概括','综合分析','提出对策','贯彻执行','大作文']:['民法','刑法','民诉','刑诉','行政法','商经知','三国法','理论法'];
    return (boards.length?boards:fallback).map((b,i)=>({id:'board-'+i,name:b,subject:b,hint:office()?'知识办理 · 专题梳理':'典籍研习 · 知识脉络',boards:[b]}));
  }
  function chooseSubject(){if(subject!==DASH.subject){subject=DASH.subject;selected='';branch='';category='';}}
  function active(){chooseSubject();return groups().find(g=>g.id===selected);}
  function belongs(name,id){
    if(id.startsWith('chang-')){
      if(!belongs(name,'chang'))return false;
      const parts=String(name).split('::').map(x=>x.trim());
      const board=[...parts].reverse().find(x=>['政治理论','常识判断'].includes(x));
      if(id==='chang-politics')return board==='政治理论';
      if(board!=='常识判断')return false;
      const found=common.find(c=>parts.some(x=>c.aliases.includes(x)));
      return id==='chang-other'?!found:found?.id===id.slice(6);
    }
    let found;
    for(const part of String(name).split('::')){
      const g=groups().find(g=>[...g.boards,...(g.aliases||[])].includes(part.trim()));
      if(g)found=g.id;
    }
    return found===id;
  }
  // 兼容独立分类板块，以及旧“常识判断”板块下按分类命名的导图；不改原路径。
  function commonMapCategory(board,name){
    const parts=String(board).split('::').map(x=>x.trim());
    const known=[...parts].reverse().find(x=>peaks.some(g=>[...g.boards,...(g.aliases||[])].includes(x)));
    if(known&&known!=='常识判断')return '';
    const direct=[...parts].reverse().map(x=>common.find(c=>c.aliases.includes(x))).find(Boolean);
    if(direct)return direct.id;
    if(known!=='常识判断')return '';
    const words=String(name).split(/::|[\s·•_—–()（）【】\[\]：:、.-]+/).map(x=>x.trim());
    return words.map(x=>common.find(c=>c.aliases.includes(x))).find(Boolean)?.id||'';
  }
  function mountain(i){
    const summit=[110,94,119,102,112][i],snow=[25,34,20,28,24][i];
    // 每座峰一点自己的特征（3.2.x）：万象＝山腰旗幡，辨言＝瀑布，明理＝棋盘平台，演数＝齿轮，观星＝观星台与星点
    const gear=(cx,cy,r)=>`<circle cx="${cx}" cy="${cy}" r="${r}"/><circle cx="${cx}" cy="${cy}" r="${r*.35}"/>`+Array.from({length:8},(_,k)=>{const t=k*Math.PI/4;return `<path d="M${(cx+Math.cos(t)*r).toFixed(1)} ${(cy+Math.sin(t)*r).toFixed(1)}L${(cx+Math.cos(t)*(r+4)).toFixed(1)} ${(cy+Math.sin(t)*(r+4)).toFixed(1)}"/>`;}).join('');
    const extra=[
      `<path d="M${summit-34} 150v-18M${summit-34} 132l12 4-12 4M${summit+26} 168v-16M${summit+26} 152l11 4-11 4"/>`,
      `<path d="M${summit+14} ${snow+48}V196M${summit+20} ${snow+52}V190" stroke-width="3" opacity=".7"/>`,
      `<path d="M${summit-27} ${snow+16}h54v8h-54zM${summit-14} ${snow+16}v8M${summit} ${snow+16}v8M${summit+14} ${snow+16}v8"/>`,
      gear(summit+26,150,13)+gear(summit-22,176,8),
      `<path d="M${summit-11} ${snow+24}a11 11 0 0 1 22 0zM${summit} ${snow+13}v-8M${summit+36} ${snow-4}h8M${summit+40} ${snow-8}v8M${summit-44} ${snow+10}h6M${summit-41} ${snow+7}v6"/>`
    ][i]||'';
    const extraSvg=`<g class="peak-extra" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity=".85">${extra}</g>`;
    return `<svg class="study-peak-art" viewBox="0 0 240 240" aria-hidden="true"><circle cx="174" cy="43" r="22" class="peak-sun"/><path d="M0 178 48 85 96 140 164 66 240 170V240H0Z" class="peak-far"/><path d="M5 234 ${summit} ${snow} 227 234Z" class="peak-mountain"/><path d="M${summit} ${snow} ${summit+23} ${snow+42} ${summit+4} ${snow+29} ${summit-7} ${snow+43} ${summit-22} ${snow+43}Z" class="peak-snow"/><path d="M${summit} ${snow+36} ${summit-13} 128 71 175 37 234H5Z" class="peak-shade"/><path d="M150 232Q76 202 114 172T126 125" class="peak-path"/><path d="M0 199Q62 174 121 201T240 189M0 220Q80 204 147 222T240 213" class="peak-mist"/><path d="M84 185h37m-33-4 15-8 14 8m-22 1v9m15-9v9" class="peak-pavilion"/>${extraSvg}</svg>`;
  }
  async function html(){
    const g=active(),title=SCENE_PORTAL.title('train'),xingce=peaksMode();
    if(!g){try{images=(await api("/api/study-regions")).images||{};}catch(_){images={};}}
    if(!g)return `<section class="study-regions ${xingce?'study-peaks':office()?'study-offices':'study-towers'}" aria-label="${esc(title)}分区选择"><header class="study-regions-heading"><span class="small muted">${xingce?'青衡宗 · 五脉同修':office()?'分题型办理':'分科目研习'}</span><h2>${esc(title)}</h2><p>${xingce?'择一峰而入，专心温简、梳理灵脉。':'选择一个板块，查看对应的记忆卡片与知识导图。'}</p></header><div class="study-region-grid">${groups().map((r,i)=>`<button class="study-region" data-study-region="${esc(r.id)}">${images[r.name]?`<img class="study-region-image" src="${esc(images[r.name])}" alt="${esc(r.name)}" data-region-image="${i}">`:xingce?mountain(i):`<span class="study-region-symbol" aria-hidden="true">${office()?'▤':'♜'}</span>`}<span class="study-region-copy"><b>${esc(r.name)}</b><span>${esc(r.subject)}</span><small>${esc(r.hint)}</small></span></button>`).join('')}</div></section>`;
    if(xingce&&g.id==='chang')return `<section class="wx-workspace${branch==='atlas'?' wx-atlas-workspace':''}">${await changHtml()}</section>`;
    const boards=[...g.boards,...(g.aliases||[])];
    const [cards,maps]=await Promise.all([CARDS.hubHtml({id:g.id,label:g.name,deck:g.boards[0]}),MINDMAP.hubHtml(boards)]);
    return `<header class="study-region-heading" aria-label="${esc(g.name)}"><h2>${esc(g.name)}</h2></header>${cards}${maps}`;
  }
  const icon=kind=>window.WANXIANG_ART?.icon(kind)||'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/></svg>';
  const backButton=label=>`<button class="ghost" data-wx-back>← ${label}</button>`;
  function wxHead(title,subtitle,back){return `<header class="wx-heading">${backButton(back)}<div><small>万象峰 · 研习之境</small><h2>${title}</h2><p>${subtitle}</p></div></header>`;}
  async function changHtml(){
    if(!branch)return `<section class="wx-home">${wxHead('万象峰','观天下之势，识万物之理','主地图')}<div class="wx-gates"><button class="wx-gate wx-politics" data-wx-branch="politics"><span class="wx-art">${icon('politics')}</span><h3 class="wx-title">政治理论</h3><small class="wx-motto">明大势 · 理脉络</small><span class="wx-type-rule" aria-hidden="true"></span><p class="wx-detail">理论脉络 / 时政研读</p><span class="wx-entry-link">启卷研习 <svg viewBox="0 0 28 12" aria-hidden="true"><path d="M1 6h25m-5-5 5 5-5 5"/></svg></span></button><button class="wx-gate wx-common" data-wx-branch="common"><span class="wx-art">${icon('common')}</span><h3 class="wx-title">常识判断</h3><small class="wx-motto">知万物 · 通古今</small><span class="wx-type-rule" aria-hidden="true"></span><p class="wx-detail">地理 / 文史 / 经济 / 科技</p><span class="wx-entry-link">启卷研习 <svg viewBox="0 0 28 12" aria-hidden="true"><path d="M1 6h25m-5-5 5 5-5 5"/></svg></span></button></div></section>`;
    if(branch==='atlas')return `<section class="wx-atlas-shell"><iframe class="wx-atlas-frame" title="考试时政地图" src="political_atlas.html?exam=${encodeURIComponent(exam)}"></iframe></section>`;
    if(branch==='politics'){
      const [cards,catalog]=await Promise.all([CARDS.hubHtml({id:'chang-politics',label:'政治理论',deck:'政治理论'}),api('/api/politics/catalog')]);
      return `${wxHead('政治理论','明大势 · 理脉络','万象峰')}<div class="wx-exam-list">${catalog.exams.map(e=>`<button class="wx-atlas-entry" data-wx-branch="atlas" data-wx-exam="${e.id}"><div><b>${esc(e.title)}</b><small>时政范围：${esc(e.range)}</small><span class="wx-source-counts">${Object.entries(e.counts.kinds).map(([k,v])=>`${k} ${v}`).join(' · ')}<br>共 ${e.counts.total} 项</span></div><span>进入地图 →</span></button>`).join('')}</div>${POLITICS_IMPORT.html(catalog.exams,exam)}${cards}`;
    }
    if(category){
      const item=common.find(c=>c.id===category),label=item?.name||'其他玉简';
      const [cards,maps]=await Promise.all([CARDS.hubHtml({id:'chang-'+category,label,deck:'常识判断'}),item?MINDMAP.hubHtml(null,false,(board,name)=>commonMapCategory(board,name)===category):Promise.resolve('')]);
      return `${wxHead(label,'玉简温习 · 灵脉梳理','常识分类')}${cards||'<div class="card muted">此分类暂无玉简，可在藏经阁管理已有牌组。</div>'}${maps|| (item?'<div class="card muted">此分类暂无灵脉图，可在藏经阁导入或整理。</div>':'')}`;
    }
    const [other,maps]=await Promise.all([CARDS.hubHtml({id:'chang-other',label:'其他玉简',deck:'常识判断'}),MINDMAP.hubHtml(['常识判断'])]);
    return `${wxHead('常识判断','知万物 · 通古今','万象峰')}<div class="wx-categories">${common.map(c=>`<button class="wx-category" data-wx-category="${c.id}"><span class="wx-category-icon">${icon(c.id)}</span><div class="wx-category-copy"><h3 class="wx-title">${c.name}</h3><small class="wx-motto">${c.hint}</small></div><span class="wx-type-rule" aria-hidden="true"></span><span class="wx-entry-link">玉简 · 灵脉 <svg viewBox="0 0 28 12" aria-hidden="true"><path d="M1 6h25m-5-5 5 5-5 5"/></svg></span></button>`).join('')}</div>${other?'<button class="ghost wx-other" data-wx-category="other">其他玉简（保留未归入四类的资料） →</button>':''}${maps}`;
  }
  async function back(){
    if(category)category='';else if(branch==='atlas')branch='politics';else if(branch)branch='';else return go('home');
    await renderTrain();window.STUDY_HUD?.refresh();
  }
  function bind(root){
    window.POLITICS_IMPORT?.bind(root,()=>renderTrain());
    root.querySelectorAll('[data-wx-branch]').forEach(b=>b.onclick=async()=>{branch=b.dataset.wxBranch;if(b.dataset.wxExam)exam=b.dataset.wxExam;category='';await renderTrain();window.STUDY_HUD?.refresh();});
    root.querySelectorAll('[data-wx-category]').forEach(b=>b.onclick=async()=>{category=b.dataset.wxCategory;await renderTrain();window.STUDY_HUD?.refresh();});
    const wb=root.querySelector('[data-wx-back]');if(wb)wb.onclick=back;
    root.querySelectorAll('[data-region-image]').forEach(img=>img.addEventListener('error',()=>{
      if(peaksMode())img.outerHTML=mountain(Number(img.dataset.regionImage));
      else img.outerHTML=`<span class="study-region-symbol" aria-hidden="true">${office()?'▤':'♜'}</span>`;
    },{once:true}));
    root.querySelectorAll('[data-study-region]').forEach(el=>el.onclick=async()=>{selected=el.dataset.studyRegion;await renderTrain();window.STUDY_HUD?.refresh();window.scrollTo(0,0);});
    const regionBack=root.querySelector('[data-study-regions-back]');if(regionBack)regionBack.onclick=async()=>{selected='';if(peaksMode()){go('home');return;}await renderTrain();window.STUDY_HUD?.refresh();window.scrollTo(0,0);};   // 行测五峰在地图上各有入口：返回就回地图，不再经过“问道群峰”选择页
  }
  // 地图上的五峰入口：直接进入某一峰（行测）；传入未知id则回到分区列表
  function select(id){chooseSubject();selected=groups().some(g=>g.id===id)?id:'';branch='';category='';}
  window.STUDY_REGIONS={html,bind,belongs,select,back,title:()=>active()?.name||''};
})();
