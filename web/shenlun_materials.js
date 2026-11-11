/* 真题材料只读勾画：固定800宽正文及透明笔迹一起缩放；草稿material_marks按材料内容指纹存储。
 * SHENLUN负责带revision保存；材料笔迹不会清除答题卡OCR确认，不送AI批改。
 * 字号（2026-11-11）：放大镜按钮改正文字号（100%–200%，本机记住），正文在同样的 800 宽里重新换行、整张再按栏宽缩放，
 * 不用左右拖。重新换行后字的位置会变，所以勾画按字号分开存：默认字号用原来的键（材料指纹），其它字号用“指纹@130”这样的键；
 * 在哪个字号下画的，回到那个字号才显示，默认字号下已有的勾画不受影响。 */
(() => {
  const WIDTH=800,FS_KEY='sl.materialFs';
  const fsNow=()=>{try{const v=Number(localStorage.getItem(FS_KEY));return v>=100&&v<=200?Math.round(v/10)*10:100;}catch(_){return 100;}};
  const lens=sign=>`<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6.5"/><path d="m15 15 6 6M6.5 10h7${sign==='+'?'M10 6.5v7':''}"/></svg>`;
  function toolbar(){return `<div class="row sl-marks-tools" role="toolbar" aria-label="材料勾画"><button class="ghost small" data-mark="read" aria-pressed="true">阅读</button><button class="ghost small" data-mark="pen" aria-pressed="false">红笔</button><button class="ghost small" data-mark="highlight" aria-pressed="false">荧光笔</button><button class="ghost small" data-mark="erase" aria-pressed="false">橡皮</button><button class="ghost small" data-mark="undo" aria-label="撤销" title="撤销">↶</button><button class="ghost small" data-mark="redo" aria-label="重做" title="重做">↷</button><label class="small"><input type="checkbox" id="slMaterialFinger">手指书写</label><span class="reading-size-tools sl-material-size" role="group" aria-label="材料字号"><button type="button" data-sl-mfs="-10" aria-label="缩小材料字号" title="缩小材料字号">${lens('-')}</button><output aria-live="polite"></output><button type="button" data-sl-mfs="10" aria-label="放大材料字号" title="放大材料字号">${lens('+')}</button></span><span class="small muted sl-mfs-note" hidden></span></div>`;}
  function mount(root,q,marks,changed,onFont){
    let lastPen=-Infinity;let mode='read',last=null,pan=null,disposed=false,scale=1;const sheets=[];let history=[],future=[];
    const fs=fsNow(),suffix=fs===100?'':'@'+fs;
    root.style.setProperty('--sl-mfs',String(fs/100));
    const sizeBar=root.querySelector('.sl-material-size');
    if(sizeBar){sizeBar.querySelector('output').textContent=fs+'%';sizeBar.querySelector('[data-sl-mfs="-10"]').disabled=fs<=100;sizeBar.querySelector('[data-sl-mfs="10"]').disabled=fs>=200;
      sizeBar.querySelectorAll('button').forEach(b=>b.onclick=()=>{const next=Math.max(100,Math.min(200,fs+Number(b.dataset.slMfs)));try{localStorage.setItem(FS_KEY,String(next));}catch(_){}onFont?.(next);});}
    // 别的字号下画过的勾画：提示一句，切回那个字号才显示
    const note=root.querySelector('.sl-mfs-note');
    if(note){const other=[...new Set(Object.keys(marks).filter(k=>(marks[k].strokes||[]).length&&q.material_mark_keys.some(id=>k.startsWith(id))&&!q.material_mark_keys.some(id=>k===id+suffix)).map(k=>k.includes('@')?k.split('@')[1]+'%':'100%'))];
      note.hidden=!other.length;note.textContent=other.length?`${other.join('、')} 字号下另有勾画`:'';}
    const resize=()=>{if(disposed)return;const available=root.querySelector('.sl-material-scroll').clientWidth-24;root.style.setProperty('--sl-exam-heading-height',root.querySelector('.sl-exam-heading').offsetHeight+'px');scale=Math.max(.25,available/WIDTH);for(const s of sheets){s.sheet.style.transform=`scale(${scale})`;s.win.style.width=WIDTH*scale+'px';s.win.style.height=s.canvas.height*scale+'px';}};
    const draw=(s,stroke)=>{const ctx=s.canvas.getContext('2d');ctx.save();ctx.globalCompositeOperation=stroke.tool==='erase'?'destination-out':'source-over';ctx.globalAlpha=stroke.tool==='highlight'?.3:1;ctx.strokeStyle=stroke.tool==='highlight'?'#edbb22':'#c53434';ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=stroke.width;ctx.lineCap='round';ctx.lineJoin='round';ctx.beginPath();stroke.points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));if(stroke.points.length===1){ctx.arc(...stroke.points[0],stroke.width/2,0,Math.PI*2);ctx.fill();}else ctx.stroke();ctx.restore();};
    const paint=s=>{s.canvas.getContext('2d').clearRect(0,0,WIDTH,s.canvas.height);for(const stroke of s.data.strokes)draw(s,stroke);};
    const commit=()=>{changed();root.querySelector('[data-mark="undo"]').disabled=!history.length;root.querySelector('[data-mark="redo"]').disabled=!future.length;};
    const observer=new ResizeObserver(resize);observer.observe(root.querySelector('.sl-material-scroll'));observer.observe(root.querySelector('.sl-exam-heading'));
    root.querySelectorAll('[data-mark]').forEach(b=>{b.onclick=()=>{const v=b.dataset.mark;if(v==='undo'||v==='redo'){const from=v==='undo'?history:future,to=v==='undo'?future:history;const op=from.pop();if(!op)return;if(v==='undo')op.s.data.strokes.pop();else op.s.data.strokes.push(op.stroke);to.push(op);paint(op.s);commit();return;}mode=v;root.querySelectorAll('[data-mark]').forEach(x=>{if(!['undo','redo'].includes(x.dataset.mark))x.setAttribute('aria-pressed',String(x.dataset.mark===mode));});for(const s of sheets)s.canvas.style.pointerEvents=mode==='read'?'none':'auto';};});
    root.querySelector('[data-mark="undo"]').disabled=true;root.querySelector('[data-mark="redo"]').disabled=true;
    const ready=Promise.all([...root.querySelectorAll('.sl-material-sheet')].map(async sheet=>{
      const id=q.material_mark_keys[Number(sheet.dataset.material)]+suffix;if(disposed)return;
      const canvas=sheet.querySelector('canvas'),win=sheet.parentElement;canvas.width=WIDTH;canvas.height=Math.ceil(sheet.scrollHeight);canvas.style.height=canvas.height+'px';
      const data=marks[id]||(marks[id]={width:WIDTH,height:canvas.height,strokes:[]});
      // 不同排版高度不拉伸历史笔迹；正文逻辑宽度、字体和行距保持固定。
      const s={sheet,canvas,win,data,id};sheets.push(s);for(const stroke of data.strokes)history.push({s,stroke});root.querySelector('[data-mark="undo"]').disabled=!history.length;paint(s);
      const point=e=>{const box=canvas.getBoundingClientRect();return [Math.min(WIDTH,Math.max(0,(e.clientX-box.x)*WIDTH/box.width)),Math.min(canvas.height,Math.max(0,(e.clientY-box.y)*canvas.height/box.height))];};
      const guard=window.PEN_GUARD?PEN_GUARD.make(canvas):null;
      const begin=e=>{const stroke={tool:mode,width:mode==='highlight'?22:mode==='erase'?24:3,points:[point(e)]};last={s,stroke,pointer:e.pointerId};data.strokes.push(stroke);draw(s,stroke);if(guard)guard.idle(()=>end({pointerId:last?.pointer,type:'idle'}));};
      canvas.onpointerdown=e=>{if(e.pointerType==='pen'){lastPen=performance.now();pan=null;}if(e.pointerType==='touch'&&(last||performance.now()-lastPen<1200))return;if(mode==='read'||e.button!==0)return;if(last&&e.pointerType!=='touch'&&guard){end({pointerId:last.pointer,type:'forced'});guard.down(true);}else if(guard)guard.down(false);if(last)return;if(e.pointerType==='touch'&&!root.querySelector('#slMaterialFinger').checked){pan={id:e.pointerId,y:e.clientY,top:root.querySelector('.sl-material-scroll').scrollTop};canvas.setPointerCapture(e.pointerId);return;}if(root.querySelector('#slSubmit').disabled&&!q.complete)return;try{canvas.setPointerCapture(e.pointerId);}catch(_){}begin(e);};
      canvas.onpointermove=e=>{if(guard&&mode!=='read'&&guard.missedDown(e,!!last)&&!(root.querySelector('#slSubmit').disabled&&!q.complete)){try{canvas.setPointerCapture(e.pointerId);}catch(_){}begin(e);}if(e.pointerType==='pen')lastPen=performance.now();if(last&&last.pointer!==e.pointerId)return;if(last&&guard&&guard.lifted(e,true)){end({pointerId:last.pointer,type:'lifted'});return;}if(guard&&last)guard.idle(()=>end({pointerId:last?.pointer,type:'idle'}));if(pan?.id===e.pointerId){root.querySelector('.sl-material-scroll').scrollTop=pan.top+pan.y-e.clientY;return;}if(!last||last.s!==s||last.pointer!==e.pointerId)return;const start=last.stroke.points.length-1,batch=e.getCoalescedEvents?.().length?e.getCoalescedEvents():[e];for(const event of batch){if(last.stroke.points.length<10000)last.stroke.points.push(point(event));}draw(s,{...last.stroke,points:last.stroke.points.slice(start)});};
      const end=e=>{if(pan?.id===e.pointerId){pan=null;return;}if(!last||last.s!==s||last.pointer!==e.pointerId)return;history.push(last);future=[];last=null;paint(s);commit();};canvas.onpointerup=e=>{if(guard&&guard.lateUp(e))return;end(e);};canvas.onpointercancel=end;
      canvas.style.pointerEvents=mode==='read'?'none':'auto';resize();
    }));
    // 阅读模式自由滚动；书写模式允许手指纵向拖动，触控笔和鼠标由画布接管。
    root.querySelector('#slMaterialFinger').onchange=e=>{for(const s of sheets)s.canvas.style.touchAction='none';};
    return {ready,destroy(){if(last){history.push(last);last=null;changed();}disposed=true;observer.disconnect();}};
  }
  window.SL_MATERIALS={toolbar,mount};
})();
