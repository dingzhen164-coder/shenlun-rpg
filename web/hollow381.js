/* 行测轻透框分类：只标记有实际面板的容器，不给布局骨架层层叠磨砂；学习区受保护。
 * 不替换DOM，不改事件/存档；异步模块重绘后重新分类。index.html调用，其他科目不启用。
 */
(() => {
 'use strict';
 const blocked='.train,.tj-q,.yj-stage:not(.ln-stage),.exam-room,.er-run,.er-stage,.er-dialog,.ex-paper,.sl-writing,.nt-book,.nt-pages,.draw-wrap,.wn-pop,.msgs,.question,.wxj-q,.sprint-document-body:has(.question)';
 const paper='.original,.sprint-document-body,.sprint-digest,.wxj-news,.wxj-digest-paper,.tj-news,.tj-cloze,.tj-cl,.an-conv,.ctable,table,.mods,.skb-read,.skb-preview,.skb-editor,.ln-canvas,.ln-document,.ln-reading-body,.yj-slip,.id-detail,.id-content,.chart,.mk-table,.tbl,.roots,.conds,.narrative-paper,.xc-guide-paper,.mock-rewards .fold,.warn,.error,.nt-reader,.ar-body,.ar-text,.md';
 const shells='.fx-panel,.fx-frame,.subpage-heading,.card,.stat,.study-hud-player,.study-hud-world,.lib-head,.fx-settings-group,.fx-settings-section,.study-region-heading,.ln-hall,.yj-hub,.tome-slot,.skb-banner,.skb-side,.id-sidebar,.nt-side,.tj-head,.tj-toc,.wxj-toc,.sprint-index,.wx-heading,.wx-import,.th-dialog,.cs-dialog,.th-block-notes,.th-stele,.task-board,.narrative-quests,.narrative-chapters';
 let pending=false;
 function mount(){
  pending=false;const body=document.body;if(!body)return;
  let dash=typeof DASH!=='undefined'?DASH:null;try{if(!dash&&parent!==window)dash=parent.DASH_REF?.();}catch(_){}
  const enabled=dash?.subject==='\u884c\u6d4b';
  body.classList.toggle('hollow381',enabled);if(!enabled)return;
  const root=document.body;
  for(const el of root.querySelectorAll(shells+','+paper)){
   const excluded=!!el.closest(blocked),isPaper=!excluded&&el.matches(paper);
   el.classList.toggle('hx381-paper',isPaper);
   el.classList.toggle('hx381-shell',!excluded&&!isPaper&&el.matches(shells));
  }
 }
 const schedule=()=>{if(!pending){pending=true;requestAnimationFrame(mount);}};
 function start(){const root=document.getElementById('view')||document.getElementById('app');if(root)new MutationObserver(schedule).observe(root,{childList:true,subtree:true});new MutationObserver(schedule).observe(document.body,{childList:true});mount();}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
 window.HOLLOW_381={mount:schedule};
})();
