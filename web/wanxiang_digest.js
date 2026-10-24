/* PDF消化清单共用显示：空位只来自PDF，与研读标红独立。atlas/journal调用，待补全不判记忆状态。 */
(() => {
 'use strict';
 const prefs=new Map();
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function html(data,journal=false){
  if(!data)return '<p class="sprint-digest-tip" role="status">正在读取消化清单…</p>';
  const counts=data.counts,onlyForgot=prefs.get(JSON.stringify(data.target))||false;
  if(!counts.blanks)return '<div class="sprint-empty-digest">尚未导入消化清单。请回到政治理论页，在统一导入区选择“消化清单”，上传PDF即可，程序会按上下文自动匹配到对应的讲义，不用自己选。</div>';
  const rows=data.paragraphs.filter(row=>!onlyForgot||row.parts.some(p=>p.id&&data.progress[p.id]==='forgot'));
  return `<section class="sprint-digest" aria-label="PDF消化清单"><div class="sprint-digest-meta"><span>配套：${esc(data.label)}</span><small>共${counts.blanks}空 · 已核对${counts.seen} · 待补全${counts.pending}</small><label><input type="checkbox" data-digest-filter ${onlyForgot?'checked':''}>只看没记住的</label></div><p class="sprint-digest-tip">空位按清单PDF保留。点空格核对＝记得，再点＝没记住。${counts.pending?'待补全项未找到唯一答案，不自动猜测。':''}</p>${rows.map(row=>`<article class="digest-pdf-row"><small class="sprint-digest-source">${esc(row.title)}</small><p class="sprint-cloze-paragraph">${row.parts.map(p=>{
    if(p.t!==undefined)return esc(p.t);
    if(!p.a)return '<span class="digest-pending" aria-label="待补全，未找到唯一答案">____<small>待补全</small></span>';
    const state=data.progress[p.id],cls=journal?'wxj-b '+(state==='remember'?'ok':state==='forgot'?'no':'hid'):'sprint-blank '+(state==='remember'?'remember':state==='forgot'?'forgot':'hidden-answer');
    return `<button class="${cls}" data-digest-blank="${esc(p.id)}" aria-label="${state?esc(p.a)+'，点击切换记忆状态':'未揭晓空位，点击核对'}" title="${p.status==='provided'?'清单明确答案':'来自配套研读原文'}" style="--blank-width:${Math.min(16,Math.max(2,[...p.a].length))}em;--w:${Math.min(16,Math.max(2,[...p.a].length))}em">${esc(p.a)}</button>`;
   }).join('')}</p></article>`).join('')||'<p class="sprint-digest-tip">没有标为没记住的空位。</p>'}</section>`;
 }
 function bind(root,data,onChange){
  if(!data||!root)return;
  root.querySelector('[data-digest-filter]')?.addEventListener('change',e=>{prefs.set(JSON.stringify(data.target),e.target.checked);Promise.resolve(onChange(data)).catch(error=>parent.showError(error));});
  root.querySelectorAll('[data-digest-blank]').forEach(button=>button.onclick=async()=>{
   button.disabled=true;
   try{const id=button.dataset.digestBlank,result=await api('/api/wanxiang/digest/mark',{target:data.target,id,value:data.progress[id]==='remember'?'forgot':'remember'});if(root.isConnected)await onChange(result);}
   catch(error){parent.showError(error);}
   finally{if(button.isConnected)button.disabled=false;}
  });
 }
 window.WANXIANG_DIGEST={html,bind};
})();
