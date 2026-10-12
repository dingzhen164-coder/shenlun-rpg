/* 离线人物/纪事界面：app.js注入api/go/授业回调，只在home/dwelling展示入口。
   服务端保存稳定节点与选择；inkjs@2.4.0解析本地编译剧情，变量取服务器facts。
   关闭/切页保留已保存进度，异步回包以epoch隔离，不创建训练会话或修改成绩。 */
(() => {
  'use strict';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const cache=new Map();
  let dashboard,handlers,data,dialog,epoch=0,pending=false,focusBack,brief=false;
  function homeHtml(d) {
    if(!d)return '';
    const j=d.journey,display=j&&!j.error?Object.values(j.placements).map(id=>j.collection.find(c=>c.id===id)).filter(Boolean):[];
    return `<div class="narrative-entry"><button data-narrative="person">与${esc(d.profile.character)}交谈</button><button data-narrative="catalogue">${esc(d.profile.title)}${d.unread?` · ${d.unread}段未读`:''}</button><button data-narrative="catalogue">任务与收藏</button></div>${display.length?`<div class="journey-display" aria-label="个人空间陈列">${display.map(c=>`<span>${esc(c.title)}</span>`).join('')}</div>`:''}`;
  }
  function mount(d,view,h) {dashboard=d;handlers=h;if(!['home','dwelling'].includes(view))close();}
  function close() {
    epoch++;
    if(!dialog)return false;
dialog.close();dialog.remove();dialog=null;
    if(focusBack?.isConnected)focusBack.focus();
    return true;
  }
  function frame(body) {
    const p=data.profile;
    const image=p.portrait?`<img class="narrative-portrait" src="${esc(p.portrait)}" alt="${esc(p.character)}">`:`<div class="narrative-seal" aria-hidden="true">${esc(p.mark)}</div>`;
    dialog.innerHTML=`<header class="narrative-heading"><div><small>${esc(p.title)} · 人物对话</small><h2 id="narrative-title">${esc(p.character)}</h2><span>${esc(p.role)}</span></div><button data-narrative="close" aria-label="保存进度并收起对话">收起 ×</button></header><div class="narrative-body"><aside class="narrative-person">${image}<p>${esc(p.intro)}</p><label><input type="checkbox" data-narrative-brief ${brief?'checked':''}> 简短模式</label><small>内置对话 · 无需AI</small></aside><section class="narrative-paper" aria-label="对话内容">${body}<p class="narrative-error" role="alert"></p></section></div>`;
    dialog.querySelectorAll('button:not([data-narrative="close"])').forEach(b=>b.disabled=pending||b.disabled);
  }
  function memoriesHtml() {
    return `<details class="narrative-memory"><summary>人物记忆 · ${data.memories.length}件真实记录</summary>${data.memories.length?data.memories.map(m=>`<p>${esc(m.text)}<small>${esc(m.date)} · ${esc(m.source)}</small></p>`).join(''):'<p>还没有学习事件。可以直接开始学习。</p>'}</details>`;
  }
  function catalogue() {
    const expanded=Array.from(dialog?.querySelectorAll('.journey-collection[open],.journey-space[open]')||[]).map(e=>e.className);
    const top=dialog?.scrollTop||0;
    frame(`<p class="narrative-lead">${esc(data.profile.greeting)}</p>${journeyHtml()}<div class="narrative-chapters">${data.chapters.map(c=>`<div><b>${esc(c.title)}</b><small>${esc(c.unlocked?(c.read?(c.skipped?'已跳过 · 可重读':'已读 · 可重读'):c.started?'已保存 · 可继续':'未读'):c.condition)}</small><button data-narrative-chapter="${esc(c.id)}" ${c.unlocked?'':'disabled'}>${c.read?'查看 / 重读':c.started?'继续':'阅读'}</button></div>`).join('')}</div><div class="narrative-actions"><button data-narrative="study">${esc(data.profile.study)}</button><button data-narrative="review">${esc(data.profile.review)}</button><button data-narrative="tutor">请教具体问题（AI）</button>${data.world==='xingce'?'<button data-narrative="legacy">原五章宗门纪事</button>':''}</div>${memoriesHtml()}`);
    expanded.forEach(name=>dialog.querySelector('.'+name)?.setAttribute('open',''));
    dialog.scrollTop=top;
  }
  function journeyHtml() {
    const j=data.journey;if(!j)return '';
    if(j.error)return `<p class="journey-warning" role="alert">${esc(j.error)}；学习功能照常可用。</p>`;
    const statuses={available:'可领取',active:'进行中',completed:'已核验 · 待交付',delivered:'已交付'};
    const slots={desk:'案头',shelf:'书架',wall:'纪念墙'};
    const criterion=data.world==='office'?'一次正式批改或卡片复习':'一次正式题库作答、卡片复习或原训练评阅';
    return `<section class="journey-panel" aria-label="学习任务与收藏"><h3>${esc(j.title)}</h3><p>${esc(j.text)}</p><small>领取后完成${esc(criterion)}，再回来交付。第二段需要一次新的复习、复练或正式批改。今日委托以原功课整项完成为准；未完成的每日委托次日到期，主线可跨日继续。收藏只作纪念，不增加成绩或学时。</small><div class="journey-tasks">${j.tasks.map(t=>`<article class="journey-task"><b>${esc(t.title)}</b><small>${!t.unlocked?'先交付上一段':esc(statuses[t.status])}${t.task.title?' · '+esc(t.task.title):''}</small>${t.proof.source?`<small>依据：${esc(t.proof.source)} · ${esc(t.proof.date)}</small>`:''}<div class="journey-buttons">${t.unlocked&&t.status==='available'?`<button data-journey-claim="${esc(t.id)}" data-journey-task="${esc(t.task.id||'')}" data-journey-approach="study">领取${t.kind==='study'?' · 课程研习':''}</button>${t.kind==='study'?`<button data-journey-claim="${esc(t.id)}" data-journey-approach="practice">领取 · 以题检验</button>`:''}`:''}${t.status==='active'?`<button data-journey-start="${esc(t.id)}">去学习</button>`:''}${t.status==='completed'?`<button data-journey-deliver="${esc(t.id)}">交付成果</button>`:''}</div></article>`).join('')}</div><details class="journey-collection"><summary>收藏册 · ${j.collection.length}件</summary>${j.collection.map(c=>`<article><h4>${esc(c.title)}</h4><p>${esc(c.text)}</p><small>${esc(c.date)} · ${esc(c.reason)} · ${esc(c.author)}</small><button data-journey-place="${esc(c.id)}" data-journey-slot="${esc(c.slot)}">陈列在${slots[c.slot]}</button></article>`).join('')||'<p>还没有收藏。先领取一段学习任务。</p>'}</details><details class="journey-space"><summary>${esc(data.profile.room)}陈列</summary>${Object.entries(slots).map(([slot,title])=>{const id=j.placements[slot],c=j.collection.find(c=>c.id===id);return `<p>${title}：${c?esc(c.title):'尚未陈列'}${c?` <button data-journey-place="" data-journey-slot="${slot}">收起</button>`:''}</p>`;}).join('')}</details><button data-journey-refresh>刷新学习状态</button></section>`;
  }
  async function journeyCommand(action,button) {
    if(pending||!dialog)return;
    const token=epoch;pending=true;
    try {
      const j=data.journey;
      const body={world:data.world,revision:j.revision,action,id:button.dataset['journey'+({claim:'Claim',deliver:'Deliver',place:'Place'}[action])],
                  task_id:button.dataset.journeyTask,approach:button.dataset.journeyApproach,slot:button.dataset.journeySlot};
      const result=action==='refresh'?(await handlers.api('/api/narrative')).journey:await handlers.api('/api/journey',body);
      if(token!==epoch||!dialog)return;
      data.journey=result;if(dashboard?.narrative)dashboard.narrative.journey=result;
      delete data.scene;pending=false;catalogue();
      if(action!=='refresh')handlers.updated?.();
    } catch(e){if(token===epoch)failure(e);}
    finally{pending=false;}
  }
  async function compiled(world) {
    if(!cache.has(world)){
      const r=await fetch(`stories/${encodeURIComponent(world)}.json`);
      if(!r.ok)throw Error('剧情文件未载入，请刷新后重试');
      cache.set(world,await r.json());
    }
    return cache.get(world);
  }
  async function showScene(token=epoch) {
    const snapshot=data,scene=snapshot.scene;
    const source=await compiled(snapshot.world);
    if(token!==epoch||!dialog||snapshot!==data)return;
    const story=new inkjs.Story(source);
    for(const [k,v] of Object.entries(snapshot.facts))story.variablesState[k]=!!v;
    story.ChoosePathString(scene.node);
    const lines=[];let guard=0;
    while(story.canContinue&&guard++<50){const s=story.Continue().trim();if(s)lines.push(s);}
    const pairs=story.currentChoices.map(c=>({ink:c,server:scene.choices.find(x=>x.text===c.text.trim())}));
    if(pairs.some(p=>!p.server)||pairs.length!==scene.choices.length)throw Error('剧情与当前规则不一致，请刷新并检查版本');
    const readLines=brief?lines.slice(-1):lines;
    const transcript=scene.transcript.length?scene.transcript:scene.record;
    frame(`<div class="narrative-chapter-title"><h3>${esc(scene.title)}</h3><span>${scene.read?'已读 · 重读不改学习记录':'进度自动保存'}</span></div><div class="narrative-text">${readLines.map(s=>`<p>${esc(s)}</p>`).join('')}</div><div class="narrative-choices">${pairs.map(p=>`<button data-narrative-choice="${esc(p.server.id)}">${esc(p.ink.text)}</button>`).join('')}</div><div class="narrative-actions">${scene.end&&!scene.read?'<button class="primary" data-narrative="finish">记入纪事</button>':''}${!scene.end?'<button data-narrative="skip">跳过本章</button>':''}${scene.read||scene.end?'<button data-narrative="replay">从头重读</button>':''}<button data-narrative="back">章节目录</button><button data-narrative="study">${esc(data.profile.study)}</button></div><details class="narrative-transcript"><summary>对话记录</summary>${transcript.map(t=>`<div>${t.lines.map(s=>`<p>${esc(s)}</p>`).join('')}<p class="narrative-your-choice">我的选择：${esc(t.choice)}</p></div>`).join('')||'<p>尚未选择分支。</p>'}</details>${memoriesHtml()}`);
    dialog.querySelector('.narrative-paper').scrollTop=0;
  }
  function failure(e) {const el=dialog?.querySelector('.narrative-error');if(el)el.textContent=e.message||String(e);else handlers?.error?.(e);}
  async function open() {
    if(pending||!dashboard?.narrative)return;
    window.XC_GUIDE?.close();
    close();focusBack=document.activeElement;const token=++epoch;
    pending=true;
    try {
      const fresh=await handlers.api('/api/narrative');
      if(token!==epoch)return;
      data=fresh;
      try{brief=localStorage.getItem('narrative-brief:'+data.world)==='1';}catch(e){brief=false;}
      dialog=document.createElement('dialog');dialog.className='narrative-dialog';dialog.setAttribute('aria-labelledby','narrative-title');
      document.body.appendChild(dialog);dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
      pending=false;catalogue();dialog.showModal();dialog.querySelector('[data-narrative="close"]').focus();
    } catch(e){if(token===epoch)failure(e);}
    finally{pending=false;}
  }
  async function command(action,chapter,choice) {
    if(pending||!dialog)return;
    const token=epoch;pending=true;
    const controls=[...dialog.querySelectorAll('button:not([data-narrative="close"])')].map(b=>[b,b.disabled]);
    controls.forEach(([b])=>b.disabled=true);
    try {
      const body={world:data.world,action,chapter:chapter||data.scene?.chapter,revision:data.revision,node:data.scene?.node};
      if(choice)body.choice=choice;
      const result=await handlers.api('/api/narrative',body);
      if(token!==epoch||!dialog)return;
      data=result;pending=false;await showScene(token);
      dialog?.querySelector('.narrative-choices button, .narrative-actions button')?.focus();
    } catch(e){
      if(token===epoch){
        failure(e);
        if(action==='open'&&e.message.includes('节点已更新')){
          const reset=document.createElement('button');reset.textContent='从头重读（保留已读记录）';reset.dataset.narrativeRestart=chapter;
          dialog?.querySelector('.narrative-error')?.appendChild(reset);
        }
      }
    }
    finally {
      pending=false;
      if(token===epoch&&dialog)controls.forEach(([b,disabled])=>{if(b.isConnected)b.disabled=disabled;});
    }
  }
  document.addEventListener('click',e=>{
    const journey=e.target.closest('[data-journey-claim],[data-journey-deliver],[data-journey-place],[data-journey-start],[data-journey-refresh]');
    if(journey&&!journey.disabled&&dialog&&!pending){
      if(journey.hasAttribute('data-journey-start')){
        const task=data.journey.tasks.find(t=>t.id===journey.dataset.journeyStart);close();
        if(task?.task.id)handlers.task?.(task.task);else handlers.study?.();
        return;
      }
      const action=journey.hasAttribute('data-journey-claim')?'claim':journey.hasAttribute('data-journey-deliver')?'deliver':journey.hasAttribute('data-journey-place')?'place':'refresh';
      return journeyCommand(action,journey);
    }
    const button=e.target.closest('[data-narrative],[data-narrative-chapter],[data-narrative-choice],[data-narrative-restart]');if(!button||button.disabled)return;
    if(button.dataset.narrative==='close')return close();
    if(button.dataset.narrative==='person'||button.dataset.narrative==='catalogue')return open();
    if(!dialog||pending)return;
    if(button.dataset.narrativeRestart)return command('replay',button.dataset.narrativeRestart);
    if(button.dataset.narrativeChapter)return command('open',button.dataset.narrativeChapter);
    if(button.dataset.narrativeChoice)return command('choose',null,button.dataset.narrativeChoice);
    const action=button.dataset.narrative;
    if(['finish','skip','replay'].includes(action))return command(action);
    if(action==='back'){delete data.scene;return catalogue();}
    if(['study','review','tutor','legacy'].includes(action)){close();handlers?.[action]?.();}
  });
  document.addEventListener('change',e=>{
    if(!e.target.matches('[data-narrative-brief]')||!dialog||pending)return;
    brief=e.target.checked;try{localStorage.setItem('narrative-brief:'+data.world,brief?'1':'0');}catch(err){}
    if(data.scene)showScene().catch(failure);
  });
  window.NARRATIVE={homeHtml,mount,open,close};
})();
