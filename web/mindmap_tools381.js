/* 导图只保留原生节点展开/折叠，不再创建占行的阅读工具条。
 * 本模块仅记住只读视图的折叠状态，不能写回或裁剪用户文档；mindmap.js负责生命周期。
 */
(() => {
 'use strict';
 function entries(tree){const out=[];function walk(node,path){if(!node?.data||out.length>=50000)return;out.push({node,path});(node.children||[]).forEach((c,i)=>walk(c,path+'.'+i));}walk(tree,'0');return out;}
 function signature(tree){let h=2166136261;for(const row of entries(tree)){const s=row.path+':'+String(row.node.data.text||'').normalize('NFKC').toLocaleLowerCase();for(let i=0;i<s.length;i++)h=Math.imul(h^s.charCodeAt(i),16777619);}return(h>>>0).toString(16);}
 const folds=tree=>Object.fromEntries(entries(tree).filter(r=>r.node.children?.length).map(r=>[r.path,r.node.data.expand!==false]));
 function restore(tree,snapshot){for(const r of entries(tree))if(typeof snapshot?.[r.path]==='boolean')r.node.data.expand=snapshot[r.path];}
 function attach({inst,root,context}){
  const data=()=>{const d=inst.getData();return d.root||d;},scope=typeof DASH==='undefined'?{}:DASH;
  const key='mindmap-tools381:'+encodeURIComponent([scope.subject,scope.vault,context.board,context.name,signature(data())].join('\n'));
  let prefs={},restored=false,dead=false,timer=0;
  try{const raw=localStorage.getItem(key);if(raw&&raw.length<300000)prefs=JSON.parse(raw)||{};}catch(_){}
  function save(){if(dead||context.manage)return;try{prefs.folds=folds(data());localStorage.setItem(key,JSON.stringify(prefs));}catch(_) {}}
  function rendered(){if(dead)return;if(!restored){restored=true;if(!context.manage&&prefs.folds){restore(inst.renderer.renderTree,prefs.folds);inst.render();return;}}clearTimeout(timer);timer=setTimeout(save,180);}
  inst.on('node_tree_render_end',rendered);root.classList.add('mm381-reading');
  return{active:()=>inst,refresh(){},destroy(){if(dead)return;clearTimeout(timer);save();dead=true;inst.off?.('node_tree_render_end',rendered);root.classList.remove('mm381-reading');}};
 }
 window.MINDMAP_TOOLS381={attach,entries,signature,folds,restore};
})();
