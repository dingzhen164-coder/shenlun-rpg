/* 3.0.6模考悟道领取：dashboard.mock_rewards提供待领/已领记录与当前境界预览。
   app/contest调用html，领取走原api与存档锁；不在前端计算或发经验。 */
(() => {
  'use strict';
  const busy=new Set();
  function html(d){
    const records=d?.mock_rewards||[];
    const pending=records.filter(r=>r.status==='pending'), claimed=records.filter(r=>r.status==='claimed').slice(0,3);
    const office=document.body.classList.contains('guantu'),mage=document.body.classList.contains('xuanhuan');
    const name=office?'考核奖励':mage?'考核领悟':'模考悟道', unit=office?'政绩':mage?'经验':'修为', stage=office?'职级':mage?'位阶':'小境界';
    return `<section class="card mock-rewards"><h3>${name}</h3><p class="small muted">成绩超过录入时的预估分可获得一次奖励。领取时按当前${stage}完整晋升所需${unit}计算：入门阶段100%，进阶阶段50%；领取后仍需自己突破。</p>${pending.length?pending.map(r=>`<div class="mock-reward-row"><div><b>${esc(r.name)}</b><span class="small muted"> ${esc(r.score)} 分 · ${esc(r.date)}</span><p class="small">当前${esc(r.preview.realm)} · 完整突破需 ${r.preview.cost} · 本次可领 <b>${r.preview.amount}</b></p></div><button class="primary" data-mock-reward="${esc(r.key)}" ${r.preview.available?'':'disabled'}>领取奖励</button></div>`).join(''):'<p class="small muted">暂无待领取奖励</p>'}${claimed.length?`<details><summary>最近领取记录</summary>${claimed.map(r=>`<p class="small">${esc(r.name)} · ${esc(r.claimed_at)} · 已领取 ${r.reward}</p>`).join('')}</details>`:''}</section>`;
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
