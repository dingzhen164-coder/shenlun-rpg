/* 导图简化：无新增整排工具，原生折叠/字重/缩放/双指平移/只读与位置偏好，三设备。 */
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
const service=spawn('python3',['tests/ui_layout_server.py','行测'],{env:process.env});let logs='',browser,page;service.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let s='';const t=setTimeout(()=>no(Error(logs)),20000);service.stdout.on('data',b=>{s+=b;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});});
(async()=>{try{const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,width,height]of [['desktop',1280,860],['portrait',800,1280],['landscape',1280,800]]){
  page=await browser.newPage({viewport:{width,height},hasTouch:true});const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/api/mindmap/save'))writes.push(r.postData());});
  await page.addInitScript(()=>{let lib;Object.defineProperty(window,'simpleMindMap',{configurable:true,get:()=>lib,set:v=>{lib=v;const M=v.default||v,render=M.prototype.render;M.prototype.render=function(...a){if(this.opt?.el?.id==='lnCanvas')window.__map381=this;return render.apply(this,a);};}});});
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.locator('#splash').waitFor({state:'hidden'});
  await page.evaluate(async()=>{const data={root:{data:{text:'自编根'},children:[{data:{text:'第一主干'},children:[{data:{text:'研究节点'}}]},{data:{text:'第二主干'}}]}};const list=await api('/api/mindmap');if(!list.boards.some(b=>b.board==='逻辑填空'&&b.maps.some(m=>m.name==='精简导图')))await api('/api/mindmap/create',{board:'逻辑填空',name:'精简导图',data});window.__source381=JSON.stringify((await api('/api/mindmap/get',{board:'逻辑填空',name:'精简导图',readonly:true})).data);await MINDMAP.open('逻辑填空','精简导图',false);});
  await page.locator('#lnCanvas svg text').first().waitFor();await page.waitForFunction(()=>!!document.querySelector('.mm381-reading'));
  assert.equal(await page.locator('.mm381-tools,[data-mm381],.mm381-search,.mm381-focus-canvas').count(),0,'新增工具整排与功能入口应真正移除');
  assert.equal(await page.locator('.ln-reading-body').getAttribute('data-mode'),height>width?'map':'split');
  const weight=await page.locator('#lnCanvas svg text').evaluateAll(xs=>Object.fromEntries(xs.map(x=>[x.textContent,getComputedStyle(x).fontWeight])));assert.equal(weight['自编根'],'700');assert.equal(weight['第一主干'],'600');assert.equal(weight['研究节点'],'500');
  await page.locator('#lnCanvas svg text').filter({hasText:/^第一主干$/}).hover();
  await page.evaluate(()=>{const r=__map381.renderer.findNodeByUid(__map381.getData().children[0].data.uid);if(!r._expandBtn?.node)throw Error('原生折叠按钮缺失');r._expandBtn.node.dispatchEvent(new MouseEvent('click',{bubbles:true}));});
  await page.waitForFunction(()=>__map381.getData().children[0].data.expand===false);
  const scale=await page.evaluate(()=>__map381.view.getTransformData().state.scale);await page.locator('#lnZoomIn').click();await page.waitForFunction(old=>__map381.view.getTransformData().state.scale>old,scale);
  const pan=await page.evaluate(()=>{const el=document.querySelector('#lnCanvas'),old={...__map381.view.getTransformData().state};const send=(type,xy)=>el.dispatchEvent(new TouchEvent(type,{bubbles:true,cancelable:true,touches:xy.map(([x,y],i)=>new Touch({identifier:i,target:el,clientX:x,clientY:y}))}));send('touchstart',[[100,200],[180,200]]);send('touchmove',[[130,240],[250,240]]);send('touchend',[]);const next=__map381.view.getTransformData().state;return old.scale===next.scale&&(old.x!==next.x||old.y!==next.y);});assert(pan);
  await page.locator('[data-ln-mode=document]').click();await page.locator('#lnBack').click();await page.evaluate(()=>MINDMAP.open('逻辑填空','精简导图',false));await page.locator('#lnCanvas svg text').first().waitFor({state:'attached'});await page.waitForFunction(()=>document.querySelector('.ln-reading-body').dataset.mode==='document');
  await page.waitForFunction(()=>__map381.getData().children[0].data.expand===false);
  assert.equal(await page.evaluate(async()=>JSON.stringify((await api('/api/mindmap/get',{board:'逻辑填空',name:'精简导图',readonly:true})).data)===__source381),true,'只读折叠不能写原文');assert.equal(writes.length,0);assert.deepEqual(errors,[]);await page.close();console.log(label+'：无额外工具排/原生折叠/分级字重/缩放/双指平移/只读偏好通过');
 }
}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
