/* 3.0.3修炼分区：app.js调用html/bind，CARDS按简匣路径归类，MINDMAP按板块筛选。
   只保存本次页面选择；不搬动资料、不新增存档、不计算奖励。行测五峰沿用宗门五脉。
   路径中以最深的已知板块为准，兼容“行测::板块::子匣”；未知简匣仍在藏经阁管理。 */
(() => {
  'use strict';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const peaks=[
    {id:'yan',name:'辨言峰',subject:'言语理解',hint:'见字辨意 · 理清主旨',boards:['片段阅读','逻辑填空'],aliases:['言语理解','成语实词']},
    {id:'shu',name:'演数峰',subject:'数量关系',hint:'推演变化 · 寻找解法',boards:['数量关系']},
    {id:'li',name:'明理峰',subject:'判断推理',hint:'理清论证 · 识破迷障',boards:['论证逻辑','形式逻辑','一拖五','定义判断','类比推理','图形推理'],aliases:['判断推理']},
    {id:'zi',name:'观星峰',subject:'资料分析',hint:'观测数据 · 看清趋势',boards:['资料分析']},
    {id:'chang',name:'万象峰',subject:'常识与政治理论',hint:'认识天地 · 通晓世事',boards:['常识判断','政治理论']}
  ];
  let selected='',subject='';
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
    return `<svg class="study-peak-art" viewBox="0 0 240 240" aria-hidden="true"><circle cx="174" cy="43" r="22" class="peak-sun"/><path d="M0 178 48 85 96 140 164 66 240 170V240H0Z" class="peak-far"/><path d="M5 234 ${summit} ${snow} 227 234Z" class="peak-mountain"/><path d="M${summit} ${snow} ${summit+23} ${snow+42} ${summit+4} ${snow+29} ${summit-7} ${snow+43} ${summit-22} ${snow+43}Z" class="peak-snow"/><path d="M${summit} ${snow+36} ${summit-13} 128 71 175 37 234H5Z" class="peak-shade"/><path d="M150 232Q76 202 114 172T126 125" class="peak-path"/><path d="M0 199Q62 174 121 201T240 189M0 220Q80 204 147 222T240 213" class="peak-mist"/><path d="M84 185h37m-33-4 15-8 14 8m-22 1v9m15-9v9" class="peak-pavilion"/></svg>`;
  }
  async function html(){
    const g=active(),title=SCENE_PORTAL.title('train'),xingce=peaksMode();
    if(!g)return `<section class="study-regions ${xingce?'study-peaks':office()?'study-offices':'study-towers'}" aria-label="${esc(title)}分区选择"><header class="study-regions-heading"><span class="small muted">${xingce?'青衡宗 · 五脉同修':office()?'分题型办理':'分科目研习'}</span><h2>${esc(title)}</h2><p>${xingce?'择一峰而入，专心温简、梳理灵脉。':'选择一个板块，查看对应的记忆卡片与知识导图。'}</p></header><div class="study-region-grid">${groups().map((r,i)=>`<button class="study-region" data-study-region="${esc(r.id)}">${xingce?mountain(i):`<span class="study-region-symbol" aria-hidden="true">${office()?'▤':'♜'}</span>`}<span class="study-region-copy"><b>${esc(r.name)}</b><span>${esc(r.subject)}</span><small>${esc(r.hint)}</small><em>进入${xingce?'山峰':office()?'办理室':'研习区'} →</em></span></button>`).join('')}</div><p class="small muted study-regions-foot">资料沿用原来的板块与简匣。自定义的未分类资料可在「${esc(SCENE_PORTAL.title('skeleton'))}」中查看和整理。</p></section>`;
    const boards=[...g.boards,...(g.aliases||[])];
    const [cards,maps]=await Promise.all([CARDS.hubHtml({id:g.id,label:g.name,deck:g.boards[0]}),MINDMAP.hubHtml(boards)]);
    return `<header class="study-region-heading"><button data-study-regions-back>← ${xingce?'返回五峰': '返回分区'}</button><div><h2>${esc(g.name)}</h2><p class="small muted">${esc(g.subject)} · ${esc(g.hint)}</p></div></header>${cards}${maps}`;
  }
  function bind(root){
    root.querySelectorAll('[data-study-region]').forEach(el=>el.onclick=async()=>{selected=el.dataset.studyRegion;await renderTrain();window.STUDY_HUD?.refresh();window.scrollTo(0,0);});
    const back=root.querySelector('[data-study-regions-back]');if(back)back.onclick=async()=>{selected='';await renderTrain();window.STUDY_HUD?.refresh();window.scrollTo(0,0);};
  }
  window.STUDY_REGIONS={html,bind,belongs,title:()=>active()?.name||''};
})();
