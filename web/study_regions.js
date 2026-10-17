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
  let selected='',subject='',images={};
  // 复用功能判断，避免申论静态文件的术语替换改写科目比较常量。
  const office=()=>typeof isSL==='function'&&isSL();
  const peaksMode=()=>typeof isSL==='function'&&!isSL();
  function groups(){
    if(peaksMode())return peaks;
    const boards=[...new Set((DASH.tree||[]).map(b=>b.board))];
    const fallback=office()?['归纳概括','综合分析','提出对策','贯彻执行','大作文']:['民法','刑法','民诉','刑诉','行政法','商经知','三国法','理论法'];
    return (boards.length?boards:fallback).map((b,i)=>({id:'board-'+i,name:b,subject:b,hint:office()?'知识办理 · 专题梳理':'典籍研习 · 知识脉络',boards:[b]}));
  }
  function chooseSubject(){if(subject!==DASH.subject){subject=DASH.subject;selected='';}}
  function active(){chooseSubject();return groups().find(g=>g.id===selected);}
  function belongs(name,id){
    let found;
    for(const part of String(name).split('::')){
      const g=groups().find(g=>[...g.boards,...(g.aliases||[])].includes(part.trim()));
      if(g)found=g.id;
    }
    return found===id;
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
    const boards=[...g.boards,...(g.aliases||[])];
    const [cards,maps]=await Promise.all([CARDS.hubHtml({id:g.id,label:g.name,deck:g.boards[0]}),MINDMAP.hubHtml(boards)]);
    return `<header class="study-region-heading" aria-label="${esc(g.name)}"><h2>${esc(g.name)}</h2></header>${cards}${maps}`;
  }
  function bind(root){
    root.querySelectorAll('[data-region-image]').forEach(img=>img.addEventListener('error',()=>{
      if(peaksMode())img.outerHTML=mountain(Number(img.dataset.regionImage));
      else img.outerHTML=`<span class="study-region-symbol" aria-hidden="true">${office()?'▤':'♜'}</span>`;
    },{once:true}));
    root.querySelectorAll('[data-study-region]').forEach(el=>el.onclick=async()=>{selected=el.dataset.studyRegion;await renderTrain();window.STUDY_HUD?.refresh();window.scrollTo(0,0);});
    const back=root.querySelector('[data-study-regions-back]');if(back)back.onclick=async()=>{selected='';if(peaksMode()){go('home');return;}await renderTrain();window.STUDY_HUD?.refresh();window.scrollTo(0,0);};   // 行测五峰在地图上各有入口：返回就回地图，不再经过“问道群峰”选择页
  }
  // 地图上的五峰入口：直接进入某一峰（行测）；传入未知id则回到分区列表
  function select(id){chooseSubject();selected=groups().some(g=>g.id===id)?id:'';}
  window.STUDY_REGIONS={html,bind,belongs,select,title:()=>active()?.name||''};
})();
