/* 3.0.6模考悟道领取：dashboard.mock_rewards提供待领/已领记录与当前境界预览。
   app/contest调用html，领取走原api与存档锁；不在前端计算或发经验。 */
(() => {
  'use strict';
  const busy=new Set();
  function html(d){
    const records=d?.mock_rewards||[];
    const pending=records.filter(r=>r.status==='pending'), claimed=records.filter(r=>r.status==='claimed'||r.status==='penalized').slice(0,5);
    const office=document.body.classList.contains('guantu'),mage=document.body.classList.contains('xuanhuan');
    const name=office?'考核奖励':mage?'考核领悟':'模考悟道', unit=office?'政绩':mage?'经验':'修为', stage=office?'职级':mage?'位阶':'小境界';
    const performance=d?.mock_reward_rule?.performance||{keep:2,normal:5,collapse:10,tiers:[]};
    const rule=window.SUBJECT0==='行测'?`大比以录分前的历史最高分为峰。刷新高峰或落后不超过 ${performance.keep} 分，且本次成绩高于当前小境界起始分数线，可得一次悟道机缘。未满足奖励条件但落后不超过 ${performance.normal} 分，视为道心平稳，无悟道奖惩。落后 ${performance.collapse} 分及以上则走火入魔，清空当前小境界未固化的修为，已踏入的境界保留。只结算新录分，每场一次，修改日期或成绩不重复结算，旧成绩不追罚。基础录分修为照旧。炼气仍按原完整突破修为奖赏；筑基每次积累当前小境界突破所需修为的 1/${d?.mock_reward_rule?.foundation||6}，金丹及其后诸境每次积累 1/${d?.mock_reward_rule?.advanced||12}。零头向上取整；每次领取最多补满当前小境界（还差多少最多领多少），不会溢出到下一阶段；机缘须手动领取，破境仍由道友亲自完成。`:`成绩超过录入时的预估分可获得一次奖励。领取时按当前${stage}完整晋升所需${unit}计算：入门阶段100%，进阶阶段50%；最多补满当前${stage}、不会溢出，领取后仍需自己突破。`;
    return `<section class="card mock-rewards"><h3>${name}</h3><details><summary>${name}考规 · 查看${window.SUBJECT0==='行测'?'奖惩阶梯':'奖励规则'}</summary><p class="small muted">${rule}</p>${window.SUBJECT0==='行测'?`<ul class="small muted">${performance.tiers.map((t,i)=>`<li>较高峰落后${i===0?'超过 ' : ''}${t.lower} 至不足 ${t.upper} 分：扣当前小境界进度 ${Math.round(t.rate*100)}%</li>`).join('')}</ul>`:''}</details>${pending.length?pending.map(r=>`<div class="mock-reward-row"><div><b>${esc(r.name)}</b><span class="small muted"> ${esc(r.score)} 分 · ${esc(r.date)}</span><p class="small">当前${esc(r.preview.realm)} · 完整突破需 ${r.preview.cost} · 本阶段还差 ${r.preview.remaining} · 本次可领 <b>${r.preview.amount}</b>${r.preview.capped?'（最多补满本阶段，不溢出）':''}</p></div><button class="primary" data-mock-reward="${esc(r.key)}" ${r.preview.available?'':'disabled'}>领取奖励</button></div>`).join(''):'<p class="small muted">暂无待领取奖励</p>'}${claimed.length?`<details><summary>${window.SUBJECT0==='行测'?'最近悟道与奖惩记录':'最近领取记录'}</summary>${claimed.map(r=>`<p class="small">${esc(r.name)} · ${esc(r.claimed_at||r.settled_at)} · ${r.status==='penalized'?`${r.penalty_rate===1?'走火入魔':'道心失守'}，扣除 ${r.penalty} ${unit}`:`已领取 ${r.reward}`}</p>`).join('')}</details>`:''}</section>`;
  }
  document.addEventListener('click',async e=>{
    const b=e.target.closest('[data-mock-reward]');if(!b)return;
    const key=b.dataset.mockReward;if(busy.has(key))return;busy.add(key);b.disabled=true;
    try{const r=await api('/api/mock/rewards/claim',{key});handleEvents(r.events);await refresh();await render();}
    catch(error){showError(error);if(b.isConnected)b.disabled=false;}
    finally{busy.delete(key);}
  });
  window.MOCK_REWARDS={html};
})();
