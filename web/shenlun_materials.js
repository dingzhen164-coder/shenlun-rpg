/* 真题材料只读勾画：固定800宽正文及透明笔迹一起缩放；草稿material_marks按材料内容指纹存储。
 * SHENLUN负责带revision保存；材料笔迹不会清除答题卡OCR确认，不送AI批改。 */
(() => {
  const WIDTH=800;
  function toolbar(){return `<div class="row sl-marks-tools" role="toolbar" aria-label="材料勾画"><button class="ghost small" data-mark="read" aria-pressed="true">阅读</button><button class="ghost small" data-mark="pen" aria-pressed="false">红笔</button><button class="ghost small" data-mark="highlight" aria-pressed="false">荧光笔</button><button class="ghost small" data-mark="erase" aria-pressed="false">橡皮</button><button class="ghost small" data-mark="undo">撤销</button><button class="ghost small" data-mark="redo">重做</button><label class="small"><input type="checkbox" id="slMaterialFinger">手指书写</label><label class="small">缩放 <select id="slMaterialZoom"><option value="1">适宽</option><option value="1.25">125%</option><option value="1.5">150%</option><option value="2">200%</option></select></label><span class="small muted">笔可勾画 · 手指可滚动</span></div>`;}
  function mount(root,q,marks,changed){
    let mode='read',last=null,pan=null,disposed=false,zoom=1,scale=1;const sheets=[];let history=[],future=[];
    const resize=()=>{if(disposed)return;const available=root.querySelector('.sl-material-scroll').clientWidth-24;scale=Math.max(.25,available/WIDTH)*zoom;for(const s of sheets){s.sheet.style.transform=`scale(${scale})`;s.win.style.width=WIDTH*scale+'px';s.win.style.height=s.canvas.height*scale+'px';}};
    const paint=s=>{const ctx=s.canvas.getContext('2d');ctx.clearRect(0,0,WIDTH,s.canvas.height);for(const stroke of s.data.strokes){ctx.save();ctx.globalCompositeOperation=stroke.tool==='erase'?'destination-out':'source-over';ctx.globalAlpha=stroke.tool==='highlight'?.3:1;ctx.strokeStyle=stroke.tool==='highlight'?'#edbb22':'#c53434';ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=stroke.width;ctx.lineCap='round';ctx.lineJoin='round';ctx.beginPath();stroke.points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));if(stroke.points.length===1){ctx.arc(...stroke.points[0],stroke.width/2,0,Math.PI*2);ctx.fill();}else ctx.stroke();ctx.restore();}};
    const commit=()=>{changed();root.querySelector('[data-mark="undo"]').disabled=!history.length;root.querySelector('[data-mark="redo"]').disabled=!future.length;};
    const observer=new ResizeObserver(resize);observer.observe(root.querySelector('.sl-material-scroll'));
    root.querySelector('#slMaterialZoom').onchange=e=>{zoom=+e.target.value;resize();};
    root.querySelectorAll('[data-mark]').forEach(b=>{b.onclick=()=>{const v=b.dataset.mark;if(v==='undo'||v==='redo'){const from=v==='undo'?history:future,to=v==='undo'?future:history;const op=from.pop();if(!op)return;if(v==='undo')op.s.data.strokes.pop();else op.s.data.strokes.push(op.stroke);to.push(op);paint(op.s);commit();return;}mode=v;root.querySelectorAll('[data-mark]').forEach(x=>{if(!['undo','redo'].includes(x.dataset.mark))x.setAttribute('aria-pressed',String(x.dataset.mark===mode));});for(const s of sheets)s.canvas.style.pointerEvents=mode==='read'?'none':'auto';};});
    root.querySelector('[data-mark="undo"]').disabled=true;root.querySelector('[data-mark="redo"]').disabled=true;
    const ready=Promise.all([...root.querySelectorAll('.sl-material-sheet')].map(async sheet=>{
      const id=q.material_mark_keys[Number(sheet.dataset.material)];if(disposed)return;
      const canvas=sheet.querySelector('canvas'),win=sheet.parentElement;canvas.width=WIDTH;canvas.height=Math.ceil(sheet.scrollHeight);canvas.style.height=canvas.height+'px';
      const data=marks[id]||(marks[id]={width:WIDTH,height:canvas.height,strokes:[]});
      // 不同排版高度不拉伸历史笔迹；正文逻辑宽度、字体和行距保持固定。
      const s={sheet,canvas,win,data,id};sheets.push(s);for(const stroke of data.strokes)history.push({s,stroke});root.querySelector('[data-mark="undo"]').disabled=!history.length;paint(s);
      const point=e=>{const box=canvas.getBoundingClientRect();return [Math.min(WIDTH,Math.max(0,(e.clientX-box.x)*WIDTH/box.width)),Math.min(canvas.height,Math.max(0,(e.clientY-box.y)*canvas.height/box.height))];};
      canvas.onpointerdown=e=>{if(last||mode==='read'||e.button!==0)return;if(e.pointerType==='touch'&&!root.querySelector('#slMaterialFinger').checked){pan={id:e.pointerId,y:e.clientY,top:root.querySelector('.sl-material-scroll').scrollTop};canvas.setPointerCapture(e.pointerId);return;}if(root.querySelector('#slSubmit').disabled&&!q.complete)return;const stroke={tool:mode,width:mode==='highlight'?22:mode==='erase'?24:3,points:[point(e)]};last={s,stroke,pointer:e.pointerId};canvas.setPointerCapture(e.pointerId);data.strokes.push(stroke);paint(s);};
      canvas.onpointermove=e=>{if(pan?.id===e.pointerId){root.querySelector('.sl-material-scroll').scrollTop=pan.top+pan.y-e.clientY;return;}if(!last||last.s!==s||last.pointer!==e.pointerId)return;const batch=e.getCoalescedEvents?.()||[e];for(const event of batch){if(last.stroke.points.length<10000)last.stroke.points.push(point(event));}paint(s);};
      const end=e=>{if(pan?.id===e.pointerId){pan=null;return;}if(!last||last.s!==s||last.pointer!==e.pointerId)return;history.push(last);future=[];last=null;commit();};canvas.onpointerup=end;canvas.onpointercancel=end;canvas.onlostpointercapture=end;
      canvas.style.pointerEvents=mode==='read'?'none':'auto';resize();
    }));
    // 阅读模式自由滚动；书写模式允许手指纵向拖动，触控笔和鼠标由画布接管。
    root.querySelector('#slMaterialFinger').onchange=e=>{for(const s of sheets)s.canvas.style.touchAction='none';};
    return {ready,destroy(){if(last){history.push(last);last=null;changed();}disposed=true;observer.disconnect();}};
  }
  window.SL_MATERIALS={toolbar,mount};
})();
