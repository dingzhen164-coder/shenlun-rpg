/* 3.8.1导图：真实库折叠/搜索/聚焦只读/偏好及双指平移；自编临时资料，不连AI。 */
const assert=require('node:assert/strict'),fs=require('node:fs'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','行测'],{env:process.env});
let logs='',browser,page;service.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let output='';const timer=setTimeout(()=>no(Error(logs)),20000);service.stdout.on('data',b=>{output+=b;const m=output.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});service.on('exit',()=>{clearTimeout(timer);no(Error(logs));});});
const click=name=>page.locator('[data-mm381="'+name+'"]').click();
const state=()=>page.evaluate(()=>({tree:__map381.getData(),scale:__map381.view.getTransformData().state.scale}));
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,width,height]of [['desktop',1280,860],['portrait',800,1280],['landscape',1280,800]].filter(([label])=>!process.argv.includes('--desktop')||label==='desktop')){
  page=await browser.newPage({viewport:{width,height},hasTouch:true});const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/api/mindmap/save'))writes.push(r.postData());});
  await page.addInitScript(()=>{let library;Object.defineProperty(window,'simpleMindMap',{configurable:true,get:()=>library,set:value=>{library=value;const Mind=value.default||value,render=Mind.prototype.render;Mind.prototype.render=function(...args){if(this.opt?.el?.id==='lnCanvas')window.__map381=this;return render.apply(this,args);};}});});
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.locator('#splash').waitFor({state:'hidden'});
  await page.evaluate(()=>{window.__errors381=[];const report=showError;window.showError=e=>{__errors381.push(String(e.stack||e));return report(e);};});
  await page.evaluate(async()=>{const data={root:{data:{text:'3.8.1自编根节点'},children:[{data:{text:'第一主干'},children:[{data:{text:'稳定支持基础研究'},children:[{data:{text:'长期稳定投入'}}]},{data:{text:'竞争性支持研究'}}]},{data:{text:'第二主干'},children:[{data:{text:'制度性开放'}}]}]}};const list=await api('/api/mindmap');if(!list.boards.some(b=>b.board==='逻辑填空'&&b.maps.some(m=>m.name==='自编381')))await api('/api/mindmap/create',{board:'逻辑填空',name:'自编381',data});window.__source381=JSON.stringify((await api('/api/mindmap/get',{board:'逻辑填空',name:'自编381',readonly:true})).data);await MINDMAP.open('逻辑填空','自编381',false);});
  await page.locator('.mm381-tools').waitFor();await page.locator('#lnCanvas svg text').first().waitFor();await page.waitForTimeout(150);
  assert.equal(await page.locator('.ln-reading-body').getAttribute('data-mode'),height>width?'map':'split');
  const weight=await page.locator('#lnCanvas svg text').evaluateAll(xs=>Object.fromEntries(xs.map(x=>[x.textContent,getComputedStyle(x).fontWeight])));assert.equal(weight['3.8.1自编根节点'],'700');assert.equal(weight['第一主干'],'600');assert.equal(weight['稳定支持基础研究'],'500');
  await page.locator('.mm381-more>summary').click();await click('collapse');
  await page.waitForFunction(()=>__map381.getData().children[0].data.expand===false);
  await page.locator('.mm381-fold-count').first().waitFor();
  assert(await page.locator('.mm381-fold-count').count()>0,'收起分支应显示隐藏节点数');
  await page.locator('.mm381-search input').fill('研究');await page.waitForFunction(()=>document.querySelector('[data-mm381-count]').textContent==='1/2');
  assert.equal((await state()).tree.children[0].data.expand,true,'搜索自动展开祖先路径');await click('next');await page.waitForFunction(()=>document.querySelector('[data-mm381-count]').textContent==='2/2');
  await click('clear');await page.waitForFunction(()=>__map381.getData().children[0].data.expand===false);
  await click('expand');await page.locator('.mm381-more>summary').click();
  await page.locator('#lnCanvas svg text').filter({hasText:/^第一主干$/}).click();await click('focus');await page.locator('.mm381-focus-canvas svg text').first().waitFor();
  assert.equal((await state()).tree.children.length,2,'聚焦不得裁剪原始树');assert(!(await page.locator('.mm381-focus-canvas').textContent()).includes('第二主干'));
  await click('unfocus');assert.equal(await page.locator('.mm381-focus-canvas').count(),0);
  const before=(await state()).scale;await page.locator('#lnZoomIn').click();await page.waitForFunction(old=>__map381.view.getTransformData().state.scale>old,before);assert.match(await page.locator('.mm381-scale').textContent(),/\d+%/);
  const pan=await page.evaluate(()=>{const el=document.querySelector('#lnCanvas'),s=__map381.view.getTransformData().state,old={...s};function send(type,xy){el.dispatchEvent(new TouchEvent(type,{bubbles:true,cancelable:true,touches:xy.map(([x,y],i)=>new Touch({identifier:i,target:el,clientX:x,clientY:y}))}));}send('touchstart',[[100,200],[180,200]]);send('touchmove',[[130,240],[250,240]]);send('touchend',[]);const next=__map381.view.getTransformData().state;return {same:old.scale===next.scale,moved:old.x!==next.x||old.y!==next.y};});assert(pan.same&&pan.moved,'两指改指距仍只平移不缩放');
  await page.locator('[data-ln-mode=document]').click();await page.locator('#lnBack').click();await page.evaluate(()=>MINDMAP.open('逻辑填空','自编381',false));await page.locator('#lnCanvas svg text').first().waitFor({state:'attached'});await page.waitForTimeout(200);assert.equal(await page.locator('.ln-reading-body').getAttribute('data-mode'),'document');
  await page.locator('[data-ln-mode=map]').click();await page.locator('.mm381-more>summary').click();await click('collapse');await page.waitForTimeout(220);await page.locator('#lnBack').click();await page.evaluate(()=>MINDMAP.open('逻辑填空','自编381',false));await page.locator('#lnCanvas svg text').first().waitFor();await page.waitForFunction(()=>__map381.getData().children[0].data.expand===false);
  assert.equal(await page.evaluate(async()=>JSON.stringify((await api('/api/mindmap/get',{board:'逻辑填空',name:'自编381',readonly:true})).data)===__source381),true,'只读折叠与聚焦不能写原文件');assert.equal(writes.length,0);assert.deepEqual(errors,[]);
  await page.locator('#lnBack').click();await page.evaluate(()=>MINDMAP.open('逻辑填空','自编381',true));await page.locator('#lnCanvas svg text').filter({hasText:/^第一主干$/}).click();
  const full=await page.evaluate(()=>JSON.stringify(__map381.getData()));await click('focus');await page.locator('.mm381-focus-canvas svg text').first().waitFor();assert.equal(await page.evaluate(()=>__map381.opt.readonly),true);
  await page.locator('.mm381-focus-canvas').click({position:{x:20,y:20}});await page.keyboard.press('Tab');await page.keyboard.press('Delete');assert.equal(await page.evaluate(()=>JSON.stringify(__map381.getData())),full,'编辑入口聚焦快捷键不得改底层原树');assert.equal(await page.locator('.ln-stage').count(),1,'聚焦快捷键不能关闭导图');await click('unfocus');assert.equal(await page.evaluate(()=>__map381.opt.readonly),false);
  await page.locator('.mm381-more>summary').click();await click('reset');assert.equal((await state()).scale,1);await click('center');await click('fit');await page.locator('.mm381-more>summary').click();
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
  fs.mkdirSync('ui-artifacts/381',{recursive:true});await page.screenshot({path:'ui-artifacts/381/mindmap-'+label+'.png'});await page.close();console.log(label+'：导图折叠/搜索/聚焦/只读/模式和偏好/双指平移通过');
 }
}catch(e){if(page&&!page.isClosed()){console.error(await page.evaluate(()=>window.__errors381));fs.mkdirSync('ui-artifacts/381',{recursive:true});await page.screenshot({path:'ui-artifacts/381/mindmap-failure.png'}).catch(()=>{});}throw e;}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
