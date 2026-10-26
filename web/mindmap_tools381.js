/* 导图阅读工具：展开/层级/聚焦/搜索/定位；各峰及藏经阁共用，不新增第三方依赖。
 * 折叠偏好按库/科目/文件/结构存本机；聚焦用独立只读实例，绝不把裁掉分支的树写回原文件。
 * mindmap.js传入现有实例、同构造器和生命周期回调，关闭时destroy撤销全部监听。
 */
(() => {
 'use strict';
 const clone=value=>JSON.parse(JSON.stringify(value));
 function entries(tree){const out=[],walk=(n,path,parent)=>{if(!n||!n.data||out.length>50000)return;out.push({node:n,path,parent});(n.children||[]).forEach((c,i)=>walk(c,path+'.'+i,path));};walk(tree,'0',null);return out;}
 function textOf(node){return String(node?.data?.text||'').normalize('NFKC').toLocaleLowerCase();}
 function signature(tree){let h=2166136261;for(const row of entries(tree)){const s=row.path+':'+textOf(row.node);for(let i=0;i<s.length;i++)h=Math.imul(h^s.charCodeAt(i),16777619);}return(h>>>0).toString(16);}
 const folds=tree=>Object.fromEntries(entries(tree).filter(r=>r.node.children?.length).map(r=>[r.path,r.node.data.expand!==false]));
 function restore(tree,snapshot){for(const r of entries(tree))if(typeof snapshot?.[r.path]==='boolean')r.node.data.expand=snapshot[r.path];}
 function attach({inst,Mind,root,context,touchPan,onPosition}){
  const canvas=root.querySelector('#lnCanvas');let focus=null,overlay=null,selected='',selectedPath='',destroyed=false,restored=false,rendering=false,searchTimer=0,saveTimer=0;
  let matches=[],at=-1,query='',searchSnapshot=null;const highlighted=new Set();
  const dataOf=map=>{const d=map.getData();return d.root||d;};
  const original=dataOf(inst),scope=typeof DASH==='undefined'?{}:DASH;let badges=null;
  const key='mindmap-tools381:'+encodeURIComponent([scope.subject,scope.vault,context.board,context.name,signature(original)].join('\n'));
  let prefs={};try{const v=localStorage.getItem(key);if(v&&v.length<300000)prefs=JSON.parse(v)||{};}catch(_){}
  const active=()=>focus||inst;
  const all=()=>entries(active().renderer.renderTree||dataOf(active()));
  const bar=document.createElement('div');bar.className='mm381-tools';bar.setAttribute('aria-label','导图阅读工具');
  bar.innerHTML='<div class="mm381-actions"><button type="button" data-mm381="toggle" disabled>展开／收起分支</button><button type="button" data-mm381="focus" disabled>聚焦分支</button><button type="button" data-mm381="unfocus" hidden>← 返回整图</button><details class="mm381-more"><summary>展开与定位 ▾</summary><div><button type="button" data-mm381="expand">全部展开</button><button type="button" data-mm381="collapse">收起至主干</button><label><span>展开层级</span><select data-mm381-level aria-label="展开到第几层"><option value="">选择层级</option><option value="1">主干（第1层）</option><option value="2">第2层</option><option value="3">第3层</option><option value="4">第4层</option></select></label><button type="button" data-mm381="fit">适应屏幕</button><button type="button" data-mm381="center">回到中心</button><button type="button" data-mm381="locate" disabled>定位选中节点</button><button type="button" data-mm381="reset">100%显示</button></div></details><output class="mm381-scale" aria-label="当前导图缩放比例">100%</output></div><div class="mm381-search"><input type="search" maxlength="120" placeholder="搜索节点…" aria-label="搜索导图节点"><output data-mm381-count role="status">0/0</output><button type="button" data-mm381="prev" disabled aria-label="上一个匹配节点">↑</button><button type="button" data-mm381="next" disabled aria-label="下一个匹配节点">↓</button><button type="button" data-mm381="clear" aria-label="清除导图搜索">×</button></div><p class="mm381-selection" role="status">点击一个节点，可折叠、聚焦或定位。</p>';
  root.querySelector('.ln-reading-body').before(bar);
  const button=name=>bar.querySelector('[data-mm381="'+name+'"]');
  function save(){if(destroyed)return;clearTimeout(saveTimer);saveTimer=setTimeout(()=>{if(destroyed||focus||query)return;try{prefs.folds=folds(dataOf(inst));localStorage.setItem(key,JSON.stringify(prefs));}catch(_){}},180);}
  function select(node){if(!node)return;const uid=node.getData?.('uid')||node.nodeData?.data?.uid;if(uid)selected=uid;const row=all().find(r=>r.node.data.uid===selected);selectedPath=row?.path||'';refresh();}
  function refresh(){
   if(destroyed||!root.isConnected)return;
   const rows=all(),row=rows.find(r=>r.node.data.uid===selected),has=!!row,count=row?entries(row.node).length-1:0;
   button('toggle').disabled=!count;button('focus').disabled=!has||!row.parent||!!focus;button('locate').disabled=!has;
   button('focus').hidden=!!focus;button('unfocus').hidden=!focus;
   const hint=bar.querySelector('.mm381-selection');hint.textContent=row?(focus?'聚焦阅读 · ':'')+String(row.node.data.text||'')+(count?' · '+(row.node.data.expand===false?'已收起 '+count+' 个下级节点':'含 '+count+' 个下级节点'):' · 叶节点'):(focus?'聚焦阅读：返回整图后可继续编辑。':'点击一个节点，可折叠、聚焦或定位。');
   if(count)button('toggle').textContent=row.node.data.expand===false?'展开分支（'+count+'）':'收起分支（'+count+'）';else button('toggle').textContent='展开／收起分支';
   const scale=active().view.getTransformData()?.state?.scale;bar.querySelector('.mm381-scale').textContent=Math.round((Number(scale)||1)*100)+'%';
   bar.querySelector('[data-mm381-count]').textContent=(matches.length?at+1:0)+'/'+matches.length;
   button('prev').disabled=button('next').disabled=!matches.length;
   root.classList.toggle('mm381-focused',!!focus);root.dataset.mm381Nodes=String(rows.length);
   for(const el of highlighted){el.classList.remove('mm381-hit','mm381-current');}highlighted.clear();
   if(query)for(const r of matches){const node=active().renderer.findNodeByUid?.(r.node.data.uid),el=node?.group?.node;if(!el)continue;el.classList.add('mm381-hit');el.classList.toggle('mm381-current',r.node.data.uid===matches[at]?.node.data.uid);highlighted.add(el);}
   const host=overlay||canvas;if(!badges||badges.parentElement!==host){badges?.remove();badges=document.createElement('div');badges.className='mm381-badges';badges.setAttribute('aria-hidden','true');host.append(badges);}badges.replaceChildren();
   const area=host.getBoundingClientRect(),byPath=new Map(rows.map(r=>[r.path,r]));
   if(area.width&&area.height)for(const r of rows){
    if(r.node.data.expand!==false||!r.node.children?.length)continue;let hidden=false,p=r.parent;while(p){if(byPath.get(p)?.node.data.expand===false){hidden=true;break;}p=byPath.get(p)?.parent;}if(hidden)continue;
    const el=active().renderer.findNodeByUid?.(r.node.data.uid)?.group?.node;if(!el)continue;const box=el.getBoundingClientRect();if(box.right<area.left||box.left>area.right||box.bottom<area.top||box.top>area.bottom)continue;
    const count=document.createElement('span');count.textContent=String(entries(r.node).length-1);count.className='mm381-fold-count';count.style.left=Math.max(0,Math.min(area.width-32,box.right-area.left+3))+'px';count.style.top=Math.max(0,box.top-area.top)+'px';badges.append(count);
   }
  }
  function render(map=active()){rendering=true;try{map.render(()=>{rendering=false;refresh();});}catch(error){rendering=false;throw error;}}
  function clearSearch(){clearTimeout(searchTimer);if(searchSnapshot){restore(active().renderer.renderTree,searchSnapshot);searchSnapshot=null;render();}query='';matches=[];at=-1;bar.querySelector('input').value='';refresh();}
  function mutate(callback){clearSearch();callback(active().renderer.renderTree);render();save();onPosition?.();}
  function locate(uid){if(!uid)return;active().execCommand('GO_TARGET_NODE',uid,()=>{refresh();onPosition?.();});}
  function search(next=0){
   const value=textOf({data:{text:bar.querySelector('input').value.trim()}});
   if(!value){clearSearch();return;}
   if(value!==query){if(!searchSnapshot)searchSnapshot=folds(dataOf(active()));query=value;matches=all().filter(r=>textOf(r.node).includes(query));at=matches.length?0:-1;}
   else if(matches.length)at=(at+next+matches.length)%matches.length;
   if(matches.length){const row=matches[at],rows=all();for(const r of rows)if(row.path.startsWith(r.path+'.'))r.node.data.expand=true;render();selected=row.node.data.uid;selectedPath=row.path;locate(selected);}refresh();
  }
  function bind(map){map.on('node_active',node=>{if(map===active())select(node);});map.on('node_click',node=>{if(map===active())select(node);});map.on('view_data_change',()=>{if(map===active())refresh();});map.on('node_tree_render_end',()=>{
   if(destroyed||map!==active())return;
   if(map===inst&&!restored){restored=true;if(!context.manage&&prefs.folds){restore(inst.renderer.renderTree,prefs.folds);render(inst);return;}}
   refresh();if(restored&&!rendering&&!query&&!focus)save();
  });}
  bind(inst);
  const actions={
   expand:()=>mutate(tree=>entries(tree).forEach(r=>r.node.data.expand=true)),
   collapse:()=>mutate(tree=>entries(tree).forEach(r=>r.node.data.expand=r.path==='0')),
   toggle:()=>mutate(tree=>{const row=entries(tree).find(r=>r.node.data.uid===selected);if(row)row.node.data.expand=row.node.data.expand===false;}),
   fit:()=>{active().view.fit();onPosition?.();refresh();},
   center:()=>{active().renderer.setRootNodeCenter();onPosition?.();refresh();},
   locate:()=>locate(selected),
   reset:()=>{active().view.setScale?.(1);active().renderer.setRootNodeCenter();onPosition?.();refresh();},
   clear:clearSearch,prev:()=>search(-1),next:()=>search(1),
   focus:()=>{
    const row=all().find(r=>r.node.data.uid===selected);if(!row?.parent||focus)return;
    // renderer节点含库的_node循环引用；聚焦只取getData导出的纯数据。
    clearSearch();const clean=entries(dataOf(inst)).find(r=>r.node.data.uid===selected);if(!clean)return;
    const source=clone(clean.node);source.data.expand=true;overlay=document.createElement('div');overlay.className='mm381-focus-canvas';overlay.setAttribute('aria-label','当前分支聚焦阅读');canvas.append(overlay);
    // 编辑入口聚焦时，隐藏在下面的编辑实例也必须停用快捷键。
    inst.setMode('readonly');
    try{focus=new Mind({...inst.opt,el:overlay,data:source,readonly:true,fit:false,viewData:null});}catch(error){overlay.remove();overlay=null;inst.setMode(context.manage?'edit':'readonly');throw error;}
    bind(focus);touchPan(focus,overlay);focus.on('node_tree_render_end',()=>{if(!focus||destroyed)return;if(!overlay.dataset.fitted){overlay.dataset.fitted='true';focus.view.fit();}});selected=source.data.uid;selectedPath='0';refresh();
   },
   unfocus:()=>{if(!focus)return;clearSearch();try{focus.destroy();}catch(_){}focus=null;overlay?.remove();overlay=null;inst.setMode(context.manage?'edit':'readonly');selected='';selectedPath='';refresh();}
  };
  bar.addEventListener('click',event=>{const b=event.target.closest('button[data-mm381]');if(!b||b.disabled)return;try{actions[b.dataset.mm381]?.();}catch(error){showError(error);}});
  bar.querySelector('select').onchange=event=>{const value=Number(event.target.value);if(value)mutate(tree=>entries(tree).forEach(r=>r.node.data.expand=r.path.split('.').length-1<value));event.target.value='';};
  bar.querySelector('input').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>search(),200);};
  bar.querySelector('input').onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();search(event.shiftKey?-1:1);}if(event.key==='Escape'){event.preventDefault();clearSearch();}};
  return {active,refresh,destroy(){if(destroyed)return;clearTimeout(searchTimer);clearTimeout(saveTimer);if(!context.manage&&!focus&&!query){try{prefs.folds=folds(dataOf(inst));localStorage.setItem(key,JSON.stringify(prefs));}catch(_){}}destroyed=true;try{focus?.destroy();}catch(_){}badges?.remove();overlay?.remove();bar.remove();root.classList.remove('mm381-focused');}};
 }
 window.MINDMAP_TOOLS381={attach,entries,signature,folds,restore};
})();
