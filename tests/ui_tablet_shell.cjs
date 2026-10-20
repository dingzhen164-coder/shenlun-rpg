/* iPad纵横屏工作区回归：真实临时库、侧栏重绘、笔迹保存、可滚动正文与缩放手势隔离。 */
const assert=require('node:assert/strict'),fs=require('node:fs'),{spawn}=require('node:child_process'),pw=require('playwright');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),'--tablet-fixture'],{env:process.env});
let logs='',browser,page;srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error(logs||'服务启动超时')),20000);srv.stdout.on('data',b=>{out+=b;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});srv.on('exit',c=>{clearTimeout(timer);reject(Error('服务退出'+c+logs));});});
async function settled(){await page.waitForTimeout(180);await page.evaluate(()=>Promise.all(document.getAnimations().filter(a=>Number.isFinite(a.effect?.getComputedTiming().endTime)).map(a=>a.finished.catch(()=>{}))));}
async function readingFits(){await settled();const r=await page.evaluate(()=>{const n=document.querySelector('.notes').getBoundingClientRect(),m=document.querySelector('.nt-main').getBoundingClientRect(),s=document.querySelector('.nt-side');return {side:getComputedStyle(s).display,delta:Math.abs(n.width-m.width),width:document.documentElement.scrollWidth-innerWidth,height:document.documentElement.scrollHeight-innerHeight};});assert.equal(r.side,'none','竖屏目录必须隐藏');assert.ok(r.delta<2,JSON.stringify(r));assert.ok(r.width<=2&&r.height<=2,JSON.stringify(r));}
(async()=>{try{
 const base=await ready,engine=process.env.UI_BROWSER||'chromium';browser=await pw[engine].launch(engine==='chromium'&&process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{});
 const context=await browser.newContext({viewport:{width:820,height:1180},hasTouch:true,userAgent:'Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1'});
 page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 // 桌面浏览器没有iPad硬件安全区：在实际样式响应里替换环境值，验证24px底部手势区。
 await page.route('**/*.css',async route=>{const response=await route.fetch();await route.fulfill({response,body:(await response.text()).replaceAll('env(safe-area-inset-bottom)','24px')});});
 await page.goto(base);await page.locator('.portal-world').waitFor();
 const book=await page.evaluate(()=>api('/api/notes/pdfopen',{p:'训练/手札/自编平板讲义.pdf'}));
 await page.evaluate(()=>go('notes'));await page.locator('.fx-note-switch').waitFor();await readingFits();
 const directory=()=>page.locator('.fx-note-switch .fx-tab').nth(0),reading=()=>page.locator('.fx-note-switch .fx-tab').nth(1);
 await directory().click();await page.locator('[data-nb="'+book.id+'"]').click();await page.locator('#ntPages').waitFor({state:'visible'});await readingFits();
 // 在目录中收起/展开会替换aside节点；返回阅读后新节点也必须保持隐藏。
 await directory().click();await page.locator('#ntSideMin').click();await readingFits();
 await directory().click();await page.locator('#ntSideOpen').click();await reading().click();await readingFits();
 const pageNode=page.locator('.nt-page').first();await pageNode.scrollIntoViewIfNeeded();const c=pageNode.locator('.nt-ink');await c.waitFor();
 await c.evaluate(canvas=>{const r=canvas.getBoundingClientRect();for(const [type,x,y] of [['pointerdown',30,40],['pointermove',65,70],['pointerup',90,95]])canvas.dispatchEvent(new PointerEvent(type,{bubbles:true,pointerType:'pen',pointerId:8,clientX:r.left+x,clientY:r.top+y,buttons:type==='pointerup'?0:1,pressure:type==='pointerup'?0:.5}));});
 assert.equal(await page.evaluate(()=>NOTES.flush()),true);const saved=await page.evaluate(id=>api('/api/notes/get',{id}),book.id);assert.ok(saved.pages[0].strokes.length>0,'实际笔迹必须写入临时库');
 await page.locator('#ntPages').evaluate(e=>e.scrollTop=650);const oldTop=await page.locator('#ntPages').evaluate(e=>e.scrollTop);assert.ok(oldTop>0,'单指滚动所需容器仍可滚动');
 for(const size of [{width:1024,height:1366},{width:1180,height:820},{width:820,height:1180}]){
  await page.setViewportSize(size);await settled();
  if(size.height>size.width){await readingFits();assert.ok(await directory().isVisible());}else{assert.equal(await page.locator('.fx-note-switch').isVisible(),false);assert.equal(await page.locator('.nt-side').isVisible(),true);}
  assert.equal((await page.evaluate(id=>api('/api/notes/get',{id}),book.id)).pages[0].strokes.length,saved.pages[0].strokes.length,'旋转不丢笔迹');
 }
 const gestures=await page.evaluate(()=>{const target=document.querySelector('#ntPages'),event=(type,count)=>{const e=new Event(type,{bubbles:true,cancelable:true});if(count!==undefined)Object.defineProperty(e,'touches',{value:Array.from({length:count},()=>({}))});let reached=false;target.addEventListener(type,()=>{reached=true;},{once:true});target.dispatchEvent(e);return {prevented:e.defaultPrevented,reached};};return {one:event('touchmove',1),two:event('touchmove',2),gesture:event('gesturestart'),action:getComputedStyle(document.documentElement).touchAction};});
 assert.equal(gestures.one.prevented,false,'普通单指翻页不被全局拦截');assert.equal(gestures.two.prevented,true);assert.equal(gestures.two.reached,true,'内部自定义手势仍收到事件');assert.equal(gestures.gesture.prevented,true);assert.match(gestures.action,/pan-x/);assert.doesNotMatch(gestures.action,/pinch-zoom/);
 // 背景延伸到底，但悬浮按钮仍须避开模拟的底部手势区。
 await settled();
 const safe=await page.evaluate(()=>{const b=getComputedStyle(document.body);return {padding:parseFloat(b.paddingBottom),body:document.body.getBoundingClientRect().bottom,height:innerHeight,button:getComputedStyle(document.querySelector('#pageSettingsGear')).bottom};});
 assert.equal(safe.padding,0,'安全区不能让整个页面退让成底部隔层');assert.ok(Math.abs(safe.body-safe.height)<=1,JSON.stringify(safe));
 assert.ok(parseFloat(safe.button)>=24,'悬浮按钮仍避开系统手势区');
 // 浏览器被手动放大后，visualViewport缩小不能误当软键盘并重排整页。
 const viewport=await page.evaluate(()=>{const vv=window.visualViewport;Object.defineProperties(vv,{height:{configurable:true,value:innerHeight/2},scale:{configurable:true,value:2}});window.dispatchEvent(new Event('resize'));return innerHeight;});await settled();
 assert.equal(await page.evaluate(()=>parseInt(document.documentElement.style.getPropertyValue('--fx-height'))),viewport);assert.equal(await page.evaluate(()=>document.documentElement.classList.contains('fx-keyboard')),false);
 await page.evaluate(()=>{delete visualViewport.height;delete visualViewport.scale;window.dispatchEvent(new Event('resize'));});await settled();
 fs.mkdirSync('ui-artifacts/tablet-shell',{recursive:true});await page.screenshot({path:'ui-artifacts/tablet-shell/'+(subject||'法考')+'-portrait.png'});
 assert.deepEqual(errors,[]);console.log('TABLET-SHELL-OK '+(subject||'法考')+' '+engine);
}catch(e){if(page){fs.mkdirSync('ui-artifacts/tablet-shell',{recursive:true});await page.screenshot({path:'ui-artifacts/tablet-shell/failure-'+(subject||'法考')+'.png'}).catch(()=>{});}throw e;}finally{await browser?.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
