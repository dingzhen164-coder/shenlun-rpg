/* 可配置任务榜：设置生成主/支线纸签；原学习接口计算时长，不用AI。
   配置存于当前科目规则.md，补记沿用静修记录，稳定任务ID与操作ID避免重复。 */
(() => {
 'use strict';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const ident=()=>('t'+Date.now().toString(36)+Math.random().toString(36).slice(2,10));
 const names=()=>document.body.classList.contains('guantu')?{title:'学习任务',main:'重点计划',side:'拓展研习',archive:'学习纪事与原委托'}:document.body.classList.contains('xuanhuan')?{title:'公会委托',main:'主线委托',side:'支线研习',archive:'学院纪事与原委托'}:{title:'任务大殿',main:'主线功课',side:'支线研习',archive:'宗门纪事与原委托'};
 function slip(t,tag,current,target,unit,extra=''){
  const done=current>=target,percent=Math.max(0,Math.min(100,current/target*100));
  return `<article class="qb-slip ${tag==='每日'||tag==='每周'?'qb-main':''}" data-qb-id="${esc(t.id||tag)}" data-complete="${done}"><div class="qb-slip-top"><span>${esc(tag)}</span><span class="qb-stamp">${done?'已达成':'修习中'}</span></div><h3>${esc(t.title)}</h3>${t.board?`<p class="qb-board-name">${esc(t.board)}</p>`:''}<div class="qb-progress"><b>${esc(current)}</b><span> / ${esc(target)} ${unit}</span></div><progress max="${target}" value="${Math.min(current,target)}" aria-label="${esc(t.title)}进度"></progress>${extra}</article>`;
 }
 function html(b){
  if(!b)return '';
  if(b.unavailable)return `<p>${esc(b.unavailable)}</p>`;
  const n=names(),c=b.config;
  return `<section class="qb-wall" aria-label="${n.title}"><header class="qb-plaque"><span>修 习 有 序 · 日 积 月 累</span><h2>${n.title}</h2><small>${esc(b.date)}</small></header><div class="qb-wall-body"><div class="qb-section-title"><h3>${n.main}</h3><small>依学习记录自动更新</small></div><div class="qb-main-grid">${slip({title:c.daily_title},'每日',b.daily_current,c.daily_minutes,'分钟','<p>听课、做题、复习与支线学习均计入。</p>')}${slip({title:c.weekly_title},'每周',b.weekly_current,c.weekly_count,'次',`<p>${esc(b.week)}<br>完成模考并录入成绩后计入。</p><button data-qb-go="contest">前往模考</button>`)}</div><div class="qb-section-title"><h3>${n.side}</h3><small>每日重新计进度 · 时长计入每日主线</small></div><div class="qb-side-grid">${b.tasks.map(t=>slip(t,'支线',t.current,t.minutes,'分钟',`<p>${t.records.length?'今日已记 '+t.records.length+' 笔':'待留下今日学习记录'}</p><button data-qb-record="${esc(t.id)}">记一笔学习</button><form class="qb-record-form" hidden data-qb-form="${esc(t.id)}"><label>本次分钟<input name="minutes" type="number" min="1" max="600" required value="30"></label><label>学习备注<textarea name="note" rows="2" maxlength="2000" placeholder="写下实际学习的内容"></textarea></label><p>仅补记尚未计时的学习；已在程序中计时的时段请勿重复补记。</p><div class="row"><button type="submit">记入学习记录</button><button type="button" data-qb-cancel>取消</button></div><p class="qb-error" role="alert"></p></form>`)).join('')||'<p class="qb-empty">尚未张贴支线任务。到设置的「学习与成长」添加内容，即可生成宣纸任务签。</p>'}</div><footer class="qb-toolbar"><button data-qb-settings>调整任务内容与时间</button><button data-qb-refresh>刷新进度</button><span role="status" class="qb-error"></span></footer></div></section>`;
 }
 function bind(root,b,options){
  let busy=false;
  const valid=()=>root.isConnected;
  root.querySelector('[data-qb-settings]')?.addEventListener('click',()=>options.settings());
  root.querySelector('[data-qb-go]')?.addEventListener('click',()=>options.route('contest'));
  root.querySelector('[data-qb-refresh]')?.addEventListener('click',async()=>{
   if(busy)return;busy=true;const btn=root.querySelector('[data-qb-refresh]');btn.disabled=true;
   try{const result=await options.api('/api/task-board');if(valid())options.changed(result);}
   catch(e){if(valid())root.querySelector('.qb-toolbar .qb-error').textContent=e.message;}
   finally{busy=false;if(btn.isConnected)btn.disabled=false;}
  });
  root.querySelectorAll('[data-qb-record]').forEach(btn=>btn.onclick=()=>{
   const f=root.querySelector(`[data-qb-form="${btn.dataset.qbRecord}"]`);f.hidden=false;btn.hidden=true;f.querySelector('input').focus();
  });
  root.querySelectorAll('[data-qb-form]').forEach(f=>{
   let op=ident();
   f.querySelector('[data-qb-cancel]').onclick=()=>{if(busy)return;f.hidden=true;root.querySelector(`[data-qb-record="${f.dataset.qbForm}"]`).hidden=false;};
   f.onsubmit=async e=>{
    e.preventDefault();if(busy)return;busy=true;const controls=[...f.querySelectorAll('button')];controls.forEach(x=>x.disabled=true);
    try{const result=await options.api('/api/task-board/record',{revision:b.config.revision,id:f.dataset.qbForm,op,minutes:Number(f.elements.minutes.value),note:f.elements.note.value});if(valid())options.changed(result);}
    catch(e){if(valid()){f.querySelector('.qb-error').textContent=e.message;}}
    finally{busy=false;controls.forEach(x=>x.disabled=false);}
   };
  });
 }
 function row(t,boards){return `<div class="qb-setting-row" data-qb-setting-id="${esc(t.id)}"><label>支线内容<input name="title" maxlength="100" value="${esc(t.title)}" placeholder="例如：整理今日错题"></label><label>目标分钟<input name="minutes" type="number" min="1" max="600" value="${t.minutes}"></label><label>所属板块<select name="board"><option value="">不分板块</option>${boards.map(b=>`<option ${b===t.board?'selected':''}>${esc(b)}</option>`).join('')}</select></label><button type="button" data-qb-remove aria-label="移除任务签，保留学习记录">移除</button></div>`;}
 async function settingsHtml(){
  const b=await api('/api/task-board');
  if(b.unavailable)return `<div class="card"><h3>每日任务与任务签</h3><p>${esc(b.unavailable)}</p></div>`;
  const c=b.config;
  return `<div class="card qb-settings" data-qb-revision="${esc(c.revision)}"><h3>每日任务与任务签</h3><p class="small muted">内容会生成任务板上的纸签；每日时长也是当天总学习目标，支线学习包含在内。各科目独立保存，旧学习记录保留。</p><div class="qb-settings-main"><label>每日主线内容<input id="qbDailyTitle" maxlength="100" value="${esc(c.daily_title)}"></label><label>每日目标（分钟）<input id="qbDailyMinutes" type="number" min="1" max="1440" value="${c.daily_minutes}"></label><label>每周主线内容<input id="qbWeeklyTitle" maxlength="100" value="${esc(c.weekly_title)}"></label><label>每周模考（次）<input id="qbWeeklyCount" type="number" min="1" max="7" value="${c.weekly_count}"></label></div><h4>支线任务签</h4><div class="qb-setting-rows">${c.tasks.map(t=>row(t,c.boards)).join('')}</div><p class="small muted">支线可记录主线之外的学习内容，每日进度独立累计；移除纸签不删除学习记录。周任务以周一至周日为一周。</p><div class="row"><button id="qbAddTask" type="button">＋ 添加支线任务签</button><button id="qbSave" type="button" class="primary">保存任务设置</button></div><p id="qbSettingStatus" role="status" class="small muted"></p><script type="application/json" class="qb-boards">${JSON.stringify(c.boards).replace(/</g,'\\u003c')}</script></div>`;
 }
 function bindSettings(){
  const root=document.querySelector('.qb-settings');if(!root)return;
  const boards=JSON.parse(root.querySelector('.qb-boards').textContent),status=root.querySelector('#qbSettingStatus');
  let busy=false;
  root.onclick=e=>{if(e.target.matches('[data-qb-remove]')&&!busy)e.target.closest('.qb-setting-row').remove();};
  root.querySelector('#qbAddTask').onclick=()=>{if(busy)return;if(root.querySelectorAll('.qb-setting-row').length>=24){status.textContent='最多24张支线任务签';return;}root.querySelector('.qb-setting-rows').insertAdjacentHTML('beforeend',row({id:ident(),title:'',minutes:30,board:''},boards));root.querySelector('.qb-setting-row:last-child input').focus();};
  root.querySelector('#qbSave').onclick=async()=>{
   if(busy)return;busy=true;const button=root.querySelector('#qbSave');button.disabled=true;
   const value=id=>root.querySelector(id).value;
   try{
    const tasks=[...root.querySelectorAll('.qb-setting-row')].map(el=>({id:el.dataset.qbSettingId,title:el.querySelector('[name="title"]').value,minutes:Number(el.querySelector('[name="minutes"]').value),board:el.querySelector('[name="board"]').value}));
    const result=await api('/api/task-board/settings',{revision:root.dataset.qbRevision,daily_title:value('#qbDailyTitle'),daily_minutes:Number(value('#qbDailyMinutes')),weekly_title:value('#qbWeeklyTitle'),weekly_count:Number(value('#qbWeeklyCount')),tasks});
    if(root.isConnected){root.dataset.qbRevision=result.config.revision;status.textContent='已保存，任务板会按新内容生成任务签。';}
   }catch(e){if(root.isConnected)status.textContent=e.message;}
   finally{busy=false;if(button.isConnected)button.disabled=false;}
  };
 }
 window.TASK_BOARD={html,bind,settingsHtml,bindSettings,names};
})();
