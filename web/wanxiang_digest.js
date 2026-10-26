/* PDF消化清单共用显示：整份清单原文保留（小标题、没有空的句子、PDF里的加粗都在），空位只来自PDF，与研读标红独立。
   atlas/journal调用；待补全的空可以点开直接填答案（回车保存并跳到下一个待补全），不判记忆状态。 */
(() => {
 'use strict';
 let openNext='';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const literal=p=>p.b?`<b class="digest-bold">${esc(p.t)}</b>`:esc(p.t);
 function blank(p,data,journal){
  if(p.status==='pending')return `<button type="button" class="digest-pending" data-digest-fill="${esc(p.id)}" aria-label="待补全，点击填写答案" title="没在原文里找到唯一答案，点击自己补全">____<small>待补全</small></button>`;
  const state=data.progress[p.id],cls=journal?'wxj-b '+(state==='remember'?'ok':state==='forgot'?'no':'hid'):'sprint-blank '+(state==='remember'?'remember':state==='forgot'?'forgot':'hidden-answer');
  const title=p.status==='provided'?'清单明确答案':p.status==='filled'?'你补全的答案':'来自配套研读原文';
  const width=Math.min(16,Math.max(2,[...p.a].length));
  return `<button class="${cls}" data-digest-blank="${esc(p.id)}" aria-label="${state?esc(p.a)+'，点击切换记忆状态':'未揭晓空位，点击核对'}" title="${title}" style="--blank-width:${width}em;--w:${width}em">${esc(p.a)}</button>`
   +(p.status==='filled'?`<button type="button" class="digest-edit" data-digest-edit="${esc(p.id)}" data-digest-answer="${esc(p.a)}" aria-label="修改补全的答案" title="修改补全的答案">✎</button>`:'');
 }
 function html(data,journal=false){
  if(!data)return '<p class="sprint-digest-tip" role="status">正在读取消化清单…</p>';
  if(!data.counts.blanks)return '<div class="sprint-empty-digest">尚未导入消化清单。请回到政治理论页，在统一导入区选择“消化清单”，上传PDF即可，程序会按上下文自动匹配到对应的讲义，不用自己选。</div>';
  const seen=data.counts.seen||0;
  const tools=`<div class="digest-tools"><button type="button" class="digest-reset" data-digest-reset ${seen?'':'disabled'} title="${seen?'把这一份清单所有空恢复成没核对过，方便再复习一遍；你补全的答案会保留':'还没有核对过的空，不用重置'}">↺ 重置所有的空${seen?`（已核对 ${seen} 个）`:''}</button></div>`;
  return `<section class="sprint-digest" aria-label="PDF消化清单">${tools}${data.paragraphs.map(row=>row.kind==='h'
   ?`<h3 class="digest-heading">${row.parts.map(p=>esc(p.t)).join('')}</h3>`
   :`<p class="sprint-cloze-paragraph">${row.parts.map(p=>p.t!==undefined?literal(p):blank(p,data,journal)).join('')}</p>`).join('')}</section>`;
 }
 function editor(root,node,id,current,data,onChange){
  const form=document.createElement('span');form.className='digest-fill-edit';
  form.innerHTML=`<input type="text" maxlength="80" value="${esc(current)}" placeholder="填写答案" aria-label="补全答案（回车保存，Esc取消）"><button type="button" class="digest-save" aria-label="保存补全答案">保存</button>`;
  const input=form.querySelector('input'),keep=node.cloneNode(true);let done=false;
  const restore=()=>{if(done)return;done=true;form.replaceWith(keep);bindOne(root,keep,data,onChange);};
  const save=async()=>{
   if(done)return;done=true;const text=input.value;
   const items=data.items,index=items.findIndex(p=>p.id===id),next=items.slice(index+1).find(p=>p.status==='pending');
   openNext=text.trim()&&next?next.id:'';
   input.disabled=true;
   try{const result=await api('/api/wanxiang/digest/fill',{target:data.target,id,text});if(root.isConnected)await onChange(result);}
   catch(error){done=false;input.disabled=false;parent.showError(error);}
  };
  input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();save();}else if(e.key==='Escape'){e.preventDefault();restore();}});
  form.querySelector('.digest-save').onclick=save;
  node.replaceWith(form);input.focus();input.select();
 }
 function bindOne(root,node,data,onChange){
  if(node.matches('[data-digest-fill]'))node.onclick=()=>editor(root,node,node.dataset.digestFill,'',data,onChange);
  else if(node.matches('[data-digest-edit]')){node.onclick=()=>editor(root,node,node.dataset.digestEdit,node.dataset.digestAnswer,data,onChange);}
}
 function bind(root,data,onChange){
  if(!data||!root)return;
  root.querySelectorAll('[data-digest-blank]').forEach(button=>button.onclick=async()=>{
   button.disabled=true;
   try{const id=button.dataset.digestBlank,result=await api('/api/wanxiang/digest/mark',{target:data.target,id,value:data.progress[id]==='remember'?'forgot':'remember'});if(root.isConnected)await onChange(result);}
   catch(error){parent.showError(error);}
   finally{if(button.isConnected)button.disabled=false;}
  });
  root.querySelectorAll('[data-digest-fill],[data-digest-edit]').forEach(node=>bindOne(root,node,data,onChange));
  root.querySelectorAll('[data-digest-reset]').forEach(button=>button.onclick=async()=>{
   if(!confirm('把这一份清单所有的空重置成“没核对过”？\n你补全的答案会保留，其他清单不受影响。'))return;
   button.disabled=true;
   try{const result=await api('/api/wanxiang/digest/reset',{target:data.target});if(root.isConnected)await onChange(result);}
   catch(error){parent.showError(error);button.disabled=false;}
  });
  if(openNext){const target=[...root.querySelectorAll('[data-digest-fill]')].find(n=>n.dataset.digestFill===openNext);openNext='';target?.scrollIntoView({block:'center'});target?.click();}
 }
 window.WANXIANG_DIGEST={html,bind};
})();
