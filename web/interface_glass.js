/* 电脑/平板共用轻透界面：本机透明度偏好、外壳分类；正文/答题/手写不受影响。
 * 只改背景和字重，不改节点内容、计时、存档或业务事件。index/时政地图加载。
 */
(() => {
 'use strict';
 const key='interface-transparency-v1',fallback=68;
 const blocked='.train,.tj-q,.yj-stage:not(.ln-stage),.exam-room,.er-run,.er-stage,.er-dialog,.ex-paper,.sl-writing,.nt-book,.nt-pages,.draw-wrap,.wn-pop,.msgs,.question,.wxj-q';
 const paper='.original,.sprint-document-body,.sprint-digest,.wxj-news,.wxj-digest-paper,.tj-news,.tj-cloze,.tj-cl,.an-conv,.ctable,table,.mods,.skb-read,.skb-preview,.skb-editor,.ln-canvas,.ln-document,.ln-reading-body,.yj-slip,.id-detail,.id-content,.chart,.mk-table,.tbl,.roots,.conds,.narrative-paper,.xc-guide-paper,.warn,.error,.nt-reader,.ar-body,.ar-text,.md';
 const shells='.fx-panel,.fx-frame,.card,.stat,.study-hud-player,.study-hud-world,.subpage-place,.subpage-tools,.lib-head,.fx-settings-group,.fx-settings-section,.study-region-heading,.ln-hall,.yj-hub,.skb-banner,.skb-side,.id-sidebar,.nt-side,.tj-head,.tj-toc,.wxj-toc,.sprint-index,.wx-heading,.wx-import,.th-dialog,.cs-dialog,.task-board';
 const value=v=>{const n=Number(v);return Number.isFinite(n)?Math.max(0,Math.min(90,Math.round(n))):fallback;};
 function read(){try{const v=localStorage.getItem(key);return v===null?fallback:value(v);}catch(_){return fallback;}}
 function apply(v=read()){
  document.documentElement.style.setProperty('--interface-panel-alpha',(100-value(v))+'%');
  document.documentElement.style.setProperty('--interface-inner-alpha',((100-value(v))*.6)+'%');
  document.documentElement.style.setProperty('--interface-dialog-alpha',Math.min(96,100-value(v)+10)+'%');
 }
 function mount(){
  document.body.classList.add('interface-glass');
  for(const el of document.querySelectorAll(shells+','+paper+',.ig-shell,.ig-paper')){
   const excluded=!!el.closest(blocked),isPaper=!excluded&&el.matches(paper);
   el.classList.toggle('ig-paper',isPaper);
   el.classList.toggle('ig-shell',!excluded&&!isPaper&&!el.closest(paper)&&el.matches(shells));
  }
 }
 function settingsHtml(){return `<div class="interface-glass-setting"><label for="interfaceTransparency">界面透明度 <output id="interfaceTransparencyValue">${read()}%</output></label><input id="interfaceTransparency" type="range" min="0" max="90" step="1" value="${read()}" aria-describedby="interfaceTransparencyHelp"><p id="interfaceTransparencyHelp" class="small muted">数值越大，背景框越通透。仅调整背景框，文字、做题、手写和正文阅读底色保持清晰。</p></div>`;}
 document.addEventListener('input',e=>{if(e.target.id!=='interfaceTransparency')return;const v=value(e.target.value);try{localStorage.setItem(key,String(v));}catch(_){}apply(v);document.getElementById('interfaceTransparencyValue').textContent=v+'%';});
 window.addEventListener('storage',e=>{if(e.key===key||e.key===null){apply();const input=document.getElementById('interfaceTransparency');if(input){input.value=read();document.getElementById('interfaceTransparencyValue').textContent=read()+'%';}}});
 let pending=false;
 function schedule(){if(pending)return;pending=true;requestAnimationFrame(()=>{pending=false;mount();});}
 function start(){apply();mount();new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true});}
 window.INTERFACE_GLASS={settingsHtml,apply,mount:schedule};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
