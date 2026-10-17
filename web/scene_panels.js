/* 场景内容框：fixed_layout.mount调用，宽高偏好仅保存在本机，不改学习存档。
   scene-panels-v1={width:50,height:100}；设置六组折叠、分区上下排时共用尺寸。 */
(() => {
  'use strict';
  const KEY='scene-panels-v1', defaults={width:50,height:100};
  let prefs={...defaults};
  const clamp=(v,fallback)=>typeof v==='number'&&Number.isFinite(v)?Math.max(40,Math.min(100,Math.round(v/5)*5)):fallback;
  try {const p=JSON.parse(localStorage.getItem(KEY));if(p&&typeof p==='object')prefs={width:clamp(p.width,50),height:clamp(p.height,100)};}catch(_){}
  function apply(root) {
    for(const [key,value]of [['--scene-panel-width',prefs.width+'%'],['--scene-panel-height',Math.max(0,root.clientHeight)*prefs.height/100+'px']])if(root.style.getPropertyValue(key)!==value)root.style.setProperty(key,value);
  }
  function controls() {
    const card=document.createElement('div');card.className='card scene-panel-settings';
    card.innerHTML=`<h3>内容框大小</h3><p class="small muted">设置与普通内容框的大小。研习分区只调整宽度、保持满高；天机台全宽，大比与试炼卷宗全屏。即时生效，只保存在这台设备。</p><div class="scene-panel-sliders"><label>宽度 <output id="scenePanelWidthValue">${prefs.width}%</output><input id="scenePanelWidth" type="range" min="40" max="100" step="5" value="${prefs.width}"></label><label>高度上限 <output id="scenePanelHeightValue">${prefs.height}%</output><input id="scenePanelHeight" type="range" min="40" max="100" step="5" value="${prefs.height}"></label></div><button type="button" id="scenePanelReset">恢复默认大小</button><p class="small muted">默认宽度为原来的一半，高度沿用可用区域；窄窗口保留必要的阅读宽度。收起的设置会自动缩短，长内容在框内滚动。</p><span class="small muted" id="scenePanelStatus" role="status"></span>`;
    function save() {
      try {localStorage.setItem(KEY,JSON.stringify(prefs));card.querySelector('#scenePanelStatus').textContent='已保存在本机';}
      catch(_) {card.querySelector('#scenePanelStatus').textContent='本次已生效，浏览器未能保存；重新打开后会恢复默认。';}
      apply(document.getElementById('view'));
      for(const [key,id] of [['width','Width'],['height','Height']]){
        card.querySelector('#scenePanel'+id).value=prefs[key];card.querySelector('#scenePanel'+id+'Value').value=prefs[key]+'%';
      }
      window.dispatchEvent(new Event('resize'));
    }
    for(const [key,id] of [['width','Width'],['height','Height']])card.querySelector('#scenePanel'+id).oninput=e=>{prefs[key]=clamp(Number(e.target.value),defaults[key]);save();};
    card.querySelector('#scenePanelReset').onclick=()=>{prefs={...defaults};save();};
    return card;
  }
  function mount(root,route) {
    apply(root);
    if(route==='home')return;
    root.querySelectorAll('.fx-shell,.fx-region-detail,.tj-hub,.tj-issue,.ex-page').forEach(node=>node.classList.add('scene-panel'));
  }
  window.SCENE_PANELS={mount,controls};
})();
