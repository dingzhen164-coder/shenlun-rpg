/* 申论红格答题卡。固定逻辑坐标保存笔迹，屏幕格线与OCR导出的纯笔迹分开。
   文字核对后由shenlun.js提交原有证据批改；本组件不润色答案、不算分。 */
(() => {
  const blank=()=>({strokes:[]});
  // 工具条放在“我的作答”顶栏里，随顶栏固定；红格区域只放纸张和翻页。
  function tools(){return `<span class="sl-card-tools sl-pen-tools" role="toolbar" aria-label="答题卡工具"><button class="ghost small" data-card="pen" aria-pressed="true">✏ 黑笔</button><button class="ghost small" data-card="eraser" aria-pressed="false">⌫ 橡皮</button><button class="ghost small" data-card="undo">↶ 撤销</button><button class="ghost small" data-card="redo">↷ 重做</button><label class="small sl-finger-chip"><input type="checkbox" id="slFinger">手指写字</label><label class="small">纸张 <select id="slCardZoom"><option value="1">适宽大格</option><option value="1.25">125%</option><option value="1.5">150%</option><option value="2">200%</option></select></label><button class="ghost small" data-card="expand">专注书写</button></span>`;}
  function html(q){return `<div class="sl-card-viewport"><div class="sl-card-paper"><canvas class="sl-card-grid" aria-hidden="true"></canvas><canvas class="sl-card-ink" aria-label="申论手写答题卡"></canvas></div></div><div class="row sl-card-pager"><button class="ghost small" data-card="prev">上一页</button><span id="slCardPage" class="small"></span><button class="ghost small" data-card="next">下一页</button><button class="ghost small" data-card="add">加页</button><span class="spacer"></span><button class="primary small" id="slRecognize">识别手写文字</button></div><p class="small muted">红格作答，笔写字、手指拖动滚动；不再需要切换滚动模式。红格不参与识别，识别后请核对原文再交卷。</p>`;}
  function mount(root,q,card,changed){
    // 有笔迹的旧卡沿用25列，空白卡用15列大格；不搬动旧笔迹。
    if(!card.pages.some(p=>p.strokes.length))card.layout=2;
    const large=card.layout===2,columns=large?15:25,cell=large?64:40,left=large?40:20,capacity=large?300:500;
    while(card.pages.length<Math.min(10,Math.max(1,Math.ceil((q.words||500)/capacity))))card.pages.push(blank());
    const ink=root.querySelector('.sl-card-ink'),grid=root.querySelector('.sl-card-grid');
    const rows=Math.min(20,Math.max(1,Math.ceil((q.words||500)/columns))),height=80+rows*cell;
    ink.width=grid.width=1040;ink.height=grid.height=height;
    const ctx=ink.getContext('2d'),gc=grid.getContext('2d');let page=0,tool='pen',current=null,redo=[],pan=null;
    const stroke=(c,s)=>{if(!s.points.length)return;c.save();c.globalCompositeOperation=s.erase?'destination-out':'source-over';c.strokeStyle=c.fillStyle='#171717';c.lineWidth=s.width;c.lineCap=c.lineJoin='round';c.beginPath();c.moveTo(...s.points[0]);if(s.points.length===1){c.arc(...s.points[0],s.width/2,0,2*Math.PI);c.fill();}else{s.points.slice(1).forEach(p=>c.lineTo(...p));c.stroke();}c.restore();};
    function paint(){gc.fillStyle='#fff';gc.fillRect(0,0,1040,height);gc.strokeStyle='#dc315d';gc.lineWidth=1;gc.font='18px sans-serif';gc.fillStyle='#ad2243';gc.fillText(`第${q.no}题 · ${q.words||'不限'}字`,20,32);
      for(let r=0;r<=rows;r++){gc.beginPath();gc.moveTo(left,60+r*cell);gc.lineTo(left+columns*cell,60+r*cell);gc.stroke();}
      for(let c=0;c<=columns;c++){gc.beginPath();gc.moveTo(left+c*cell,60);gc.lineTo(left+c*cell,60+rows*cell);gc.stroke();}
      ctx.clearRect(0,0,1040,height);card.pages[page].strokes.forEach(s=>stroke(ctx,s));if(current)stroke(ctx,current);
      root.querySelector('#slCardPage').textContent=`第${page+1}/${card.pages.length}页 · 每页${rows*columns}格 · 每行${columns}格`;
    }
    const point=e=>{const r=ink.getBoundingClientRect();return [Math.min(left+columns*cell,Math.max(left,(e.clientX-r.left)*1040/r.width)),Math.min(60+rows*cell,Math.max(60,(e.clientY-r.top)*height/r.height))];};
    let pointer=null,pointerType='',lastPen=-Infinity; const guard=window.PEN_GUARD?PEN_GUARD.make(ink):null;
    const finishStroke=()=>{if(!current)return;guard?.idle();card.pages[page].strokes.push(current);current=null;pointer=null;pointerType='';redo=[];paint();changed();};
    const begin=e=>{pointer=e.pointerId;pointerType=e.pointerType;current={erase:tool==='eraser',width:tool==='eraser'?20:3,points:[point(e)]};stroke(ctx,current);if(guard)guard.idle(finishStroke);};
    ink.onpointerdown=e=>{if(e.pointerType==='pen')lastPen=performance.now();if(e.pointerType==='touch'&&(pointerType==='pen'||performance.now()-lastPen<1200))return;if(e.button!==0)return;if(e.pointerType==='touch'&&!root.querySelector('#slFinger').checked){const sc=ink.closest('.fx-scroll,.sl-writing'),vp=root.querySelector('.sl-card-viewport');pan={id:e.pointerId,x:e.clientX,y:e.clientY,top:sc.scrollTop,left:vp.scrollLeft,sc,vp};try{ink.setPointerCapture(e.pointerId);}catch(_){}return;}e.preventDefault();if(guard){const had=!!current;if(had)finishStroke();guard.down(had);}try{ink.setPointerCapture(e.pointerId);}catch(_){}begin(e);};
    ink.onpointermove=e=>{if(pan&&pan.id===e.pointerId){pan.sc.scrollTop=pan.top+pan.y-e.clientY;pan.vp.scrollLeft=pan.left+pan.x-e.clientX;return;}if(guard&&guard.missedDown(e,!!current)){try{ink.setPointerCapture(e.pointerId);}catch(_){}begin(e);}if(!current||e.pointerId!==pointer||e.pointerType!==pointerType)return;if(e.pointerType==='pen')lastPen=performance.now();if(current&&guard&&guard.lifted(e,true)){finishStroke();return;}if(!current)return;e.preventDefault();if(guard)guard.idle(finishStroke);const start=current.points.length-1;((e.getCoalescedEvents?.().length?e.getCoalescedEvents():[e])).forEach(x=>current.points.push(point(x)));stroke(ctx,{...current,points:current.points.slice(start)});};
    ink.onpointerup=ink.onpointercancel=e=>{if(pan&&pan.id===e.pointerId){pan=null;return;}if(e.pointerId!==pointer||e.pointerType!==pointerType)return;if(guard&&guard.lateUp(e))return;finishStroke();};
    root.querySelectorAll('[data-card]').forEach(b=>b.onclick=()=>{const action=b.dataset.card;if(action==='expand'){const box=root.querySelector('.sl-writing');box.classList.toggle('sl-card-expanded');b.textContent=box.classList.contains('sl-card-expanded')?'退出专注':'专注书写';}else if(action==='pen'||action==='eraser'){tool=action;root.querySelectorAll('[data-card="pen"],[data-card="eraser"]').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.card===tool)));}else if(action==='undo'&&card.pages[page].strokes.length){redo.push(card.pages[page].strokes.pop());changed();}else if(action==='redo'&&redo.length){card.pages[page].strokes.push(redo.pop());changed();}else if(action==='prev'&&page>0){page--;redo=[];}else if(action==='next'&&page<card.pages.length-1){page++;redo=[];}else if(action==='add'&&card.pages.length<10){card.pages.push(blank());page=card.pages.length-1;redo=[];changed();}paint();});
    const paper=root.querySelector('.sl-card-paper'),viewport=root.querySelector('.sl-card-viewport');
    const size=()=>{if(root.isConnected)paper.style.width=Math.round(viewport.clientWidth*Number(root.querySelector('#slCardZoom').value))+'px';};
    root.querySelector('#slCardZoom').onchange=size;
    const observer=new ResizeObserver(()=>{if(!root.querySelector('.sl-card-ink')||root.querySelector('.sl-card-ink')!==ink){observer.disconnect();return;}size();});observer.observe(viewport);
    const finger=root.querySelector('#slFinger');try{finger.checked=localStorage.getItem('sl.finger')==='1';}catch(_){}finger.onchange=()=>{try{localStorage.setItem('sl.finger',finger.checked?'1':'0');}catch(_){}};
    paint();size();
    return {destroy(){observer.disconnect();},images(){return card.pages.filter(p=>p.strokes.some(s=>!s.erase&&s.points.length)).map(p=>{const c=document.createElement('canvas');c.width=1040;c.height=height;const x=c.getContext('2d');p.strokes.forEach(s=>stroke(x,s));const out=document.createElement('canvas');out.width=1040;out.height=height;const o=out.getContext('2d');o.fillStyle='#fff';o.fillRect(0,0,1040,height);o.drawImage(c,0,0);return out.toDataURL('image/png');});},paint};
  }
  window.SL_CARD={html,tools,mount};
})();
