/* 申论红格答题卡。固定逻辑坐标保存笔迹，屏幕格线与OCR导出的纯笔迹分开。
   文字核对后由shenlun.js提交原有证据批改；本组件不润色答案、不算分。 */
(() => {
  const blank=()=>({strokes:[]});
  function html(q){return `<div class="sl-card-tools row"><b>红格答题卡</b><button class="ghost small" data-card="expand">放大书写</button><button class="ghost small" data-card="pen">黑笔</button><button class="ghost small" data-card="eraser">橡皮</button><button class="ghost small" data-card="undo">撤销</button><button class="ghost small" data-card="redo">重做</button><button class="ghost small" data-card="scroll">滚动模式</button><label class="small"><input type="checkbox" id="slFinger">允许手指写字</label></div><div class="sl-card-paper"><canvas class="sl-card-grid" aria-hidden="true"></canvas><canvas class="sl-card-ink" aria-label="申论手写答题卡"></canvas></div><div class="row"><button class="ghost small" data-card="prev">上一页</button><span id="slCardPage" class="small"></span><button class="ghost small" data-card="next">下一页</button><button class="ghost small" data-card="add">加页</button><span class="spacer"></span><button class="primary small" id="slRecognize">识别手写文字</button></div><p class="small muted">黑笔书写，红格不参与识别。识别后核对原文再交卷；认不清的字可手动改正。</p>`;}
  function mount(root,q,card,changed){
    if(!card.pages.length)for(let n=0;n<Math.max(1,Math.ceil((q.words||500)/500));n++)card.pages.push(blank());
    const ink=root.querySelector('.sl-card-ink'),grid=root.querySelector('.sl-card-grid');
    const rows=Math.min(20,Math.max(1,Math.ceil((q.words||500)/25))),height=80+rows*40;
    ink.width=grid.width=1040;ink.height=grid.height=height;
    const ctx=ink.getContext('2d'),gc=grid.getContext('2d');let page=0,tool='pen',current=null,redo=[],scroll=false;
    const stroke=(c,s)=>{if(!s.points.length)return;c.save();c.globalCompositeOperation=s.erase?'destination-out':'source-over';c.strokeStyle=c.fillStyle='#171717';c.lineWidth=s.width;c.lineCap=c.lineJoin='round';c.beginPath();c.moveTo(...s.points[0]);if(s.points.length===1){c.arc(...s.points[0],s.width/2,0,2*Math.PI);c.fill();}else{s.points.slice(1).forEach(p=>c.lineTo(...p));c.stroke();}c.restore();};
    function paint(){gc.fillStyle='#fff';gc.fillRect(0,0,1040,height);gc.strokeStyle='#dc315d';gc.lineWidth=1;gc.font='18px sans-serif';gc.fillStyle='#ad2243';gc.fillText(`第${q.no}题 · ${q.words||'不限'}字`,20,32);
      for(let r=0;r<=rows;r++){gc.beginPath();gc.moveTo(20,60+r*40);gc.lineTo(1020,60+r*40);gc.stroke();}
      for(let c=0;c<=25;c++){gc.beginPath();gc.moveTo(20+c*40,60);gc.lineTo(20+c*40,60+rows*40);gc.stroke();}
      ctx.clearRect(0,0,1040,height);card.pages[page].strokes.forEach(s=>stroke(ctx,s));if(current)stroke(ctx,current);
      root.querySelector('#slCardPage').textContent=`第${page+1}/${card.pages.length}页 · 每页${rows*25}格`;
    }
    const point=e=>{const r=ink.getBoundingClientRect();return [Math.min(1020,Math.max(20,(e.clientX-r.left)*1040/r.width)),Math.min(60+rows*40,Math.max(60,(e.clientY-r.top)*height/r.height))];};
    ink.onpointerdown=e=>{if(scroll||e.button!==0||(e.pointerType==='touch'&&!root.querySelector('#slFinger').checked))return;e.preventDefault();ink.setPointerCapture(e.pointerId);current={erase:tool==='eraser',width:tool==='eraser'?20:3,points:[point(e)]};paint();};
    ink.onpointermove=e=>{if(!current)return;e.preventDefault();(e.getCoalescedEvents?e.getCoalescedEvents():[e]).forEach(x=>current.points.push(point(x)));paint();};
    ink.onpointerup=ink.onpointercancel=()=>{if(!current)return;card.pages[page].strokes.push(current);current=null;redo=[];paint();changed();};
    root.querySelectorAll('[data-card]').forEach(b=>b.onclick=()=>{const action=b.dataset.card;if(action==='expand'){const box=root.querySelector('.sl-writing');box.classList.toggle('sl-card-expanded');b.textContent=box.classList.contains('sl-card-expanded')?'收起书写':'放大书写';}else if(action==='pen'||action==='eraser'){tool=action;scroll=false;}else if(action==='scroll')scroll=!scroll;else if(action==='undo'&&card.pages[page].strokes.length){redo.push(card.pages[page].strokes.pop());changed();}else if(action==='redo'&&redo.length){card.pages[page].strokes.push(redo.pop());changed();}else if(action==='prev'&&page>0){page--;redo=[];}else if(action==='next'&&page<card.pages.length-1){page++;redo=[];}else if(action==='add'&&card.pages.length<10){card.pages.push(blank());page=card.pages.length-1;redo=[];changed();}ink.style.pointerEvents=scroll?'none':'auto';root.querySelector('[data-card="scroll"]').classList.toggle('primary',scroll);paint();});
    paint();
    return {images(){return card.pages.filter(p=>p.strokes.some(s=>!s.erase&&s.points.length)).map(p=>{const c=document.createElement('canvas');c.width=1040;c.height=height;const x=c.getContext('2d');p.strokes.forEach(s=>stroke(x,s));const out=document.createElement('canvas');out.width=1040;out.height=height;const o=out.getContext('2d');o.fillStyle='#fff';o.fillRect(0,0,1040,height);o.drawImage(c,0,0);return out.toDataURL('image/png');});},paint};
  }
  window.SL_CARD={html,mount};
})();
