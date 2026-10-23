/* 只读双栏缩放按钮：左图放缩、右文滚动不变、重开记忆、正文不写回；电脑/平板。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),fs=require('node:fs'),assert=require('node:assert/strict');
const law=!fs.existsSync('rpg/subjects.py'),subject=process.argv.find(x=>x.startsWith('--subject='))?.split('=')[1]||(law?null:'行测');let srv,b,p,fixture;
function service(){srv=spawn('python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),'--reader-fixture'],{env:process.env});let out='',err='';srv.stderr.on('data',b=>err+=b);return new Promise((ok,no)=>{const t=setTimeout(()=>no(Error(err)),20000);srv.stdout.on('data',b=>{out+=b;const f=out.match(/UI-READER (.+)/);if(f)fixture=JSON.parse(f[1]);const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});srv.on('exit',()=>{clearTimeout(t);no(Error(err));});});}
(async()=>{try{b=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});for(const [size,viewport]of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}],['tablet-landscape',{width:1280,height:800}]]){
 const base=await service();p=await b.newPage({viewport});p.setDefaultTimeout(15000);const errors=[],writes=[];p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().endsWith('/api/mindmap/save'))writes.push(r.postData());});await p.goto(base);await p.waitForFunction(()=>!!window.DASH_REF?.());await p.evaluate(()=>go('train'));await p.waitForFunction(()=>!!window.MINDMAP);await p.evaluate(board=>MINDMAP.open(board,board,false),fixture.board);await p.locator('#lnCanvas svg text').first().waitFor();
 await p.waitForFunction(()=>{const e=document.querySelector('#lnCanvas svg text');return e&&e.getBoundingClientRect().width>10;});
 const text=p.locator('#lnCanvas svg text').first(),initial=(await text.boundingBox()).width;await p.locator('#lnMarkdown').evaluate(e=>e.scrollTop=100);const scroll=await p.locator('#lnMarkdown').evaluate(e=>e.scrollTop);assert(await p.locator('[data-ln-mode=split]').evaluate(e=>e.nextElementSibling.id==='lnZoomIn'));
 await p.locator('#lnZoomIn').click();await p.waitForFunction(w=>document.querySelector('#lnCanvas svg text').getBoundingClientRect().width>w*1.03,initial);assert.equal(await p.locator('#lnMarkdown').evaluate(e=>e.scrollTop),scroll);await p.locator('#lnZoomOut').click();await p.waitForFunction(w=>Math.abs(document.querySelector('#lnCanvas svg text').getBoundingClientRect().width-w)<1,initial);
 // 真实触摸事件：先单指、加入第二指、中心向右下移动且指距拉大，再松一指。
 const before=await text.boundingBox();
 const pan=await p.evaluate(()=>{
  const canvas=document.querySelector('#lnCanvas'),r=canvas.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;
  const touch=(id,dx,dy)=>new Touch({identifier:id,target:canvas,clientX:x+dx,clientY:y+dy});
  const fire=(type,ts)=>canvas.dispatchEvent(new TouchEvent(type,{touches:ts,targetTouches:ts,changedTouches:ts,bubbles:true,cancelable:true}));
  fire('touchstart',[touch(1,-30,0)]);fire('touchstart',[touch(1,-30,0),touch(2,30,0)]);
  fire('touchmove',[touch(1,-20,30),touch(2,80,30)]); // 中心+30,+30，指距60→100
  fire('touchend',[touch(1,-20,30)]);fire('touchmove',[touch(1,80,100)]);fire('touchend',[]);
  return getComputedStyle(canvas).touchAction;
 });
 assert.equal(pan,'none');const after=await text.boundingBox();assert(Math.abs(after.width-before.width)<.1,'双指指距变化不改变字号');assert(Math.abs(after.x-before.x-30)<1&&Math.abs(after.y-before.y-30)<1,'双指可上下左右平移，松一指后不跳动');
 await p.locator('#lnCanvas').evaluate(e=>e.dispatchEvent(new WheelEvent('wheel',{deltaX:12,deltaY:18,ctrlKey:true,bubbles:true,cancelable:true})));const wheel=await text.boundingBox();assert(Math.abs(wheel.width-after.width)<.1);assert(Math.abs(wheel.x-after.x+12)<1&&Math.abs(wheel.y-after.y+18)<1,'触控板双轴平移，不触发Ctrl捏合缩放');
 await p.locator('#lnZoomIn').click();await p.waitForFunction(()=>Object.keys(localStorage).some(k=>k.startsWith('mindmap-reading-v1:')&&JSON.parse(localStorage[k]).view));
 await p.locator('[data-ln-mode=document]').click();assert(await p.locator('#lnZoomIn').isDisabled());await p.locator('[data-ln-mode=split]').click();for(const theme of ['light','dark']){await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2&&document.documentElement.scrollHeight<=innerHeight+2&&!scrollY));}
 await p.locator('#lnBack').click();await p.locator('.ln-stage').waitFor({state:'detached'});const scale=await p.evaluate(()=>JSON.parse(localStorage[Object.keys(localStorage).find(k=>k.startsWith('mindmap-reading-v1:'))]).view.state.scale);await p.evaluate(board=>MINDMAP.open(board,board,false),fixture.board);await p.locator('#lnCanvas svg text').first().waitFor();assert.equal(await p.evaluate(()=>JSON.parse(localStorage[Object.keys(localStorage).find(k=>k.startsWith('mindmap-reading-v1:'))]).view.state.scale),scale);assert.equal(writes.length,0);assert.deepEqual(errors,[]);
 if(process.argv.includes('--shots')&&size==='tablet'){fs.mkdirSync('ui-artifacts/zoom359',{recursive:true});await p.screenshot({path:'ui-artifacts/zoom359/'+(subject||'法考')+'.png'});}
 await p.close();srv.kill();console.log((subject||'法考')+' '+size+'：左图缩放、右文不动、只读/重开记忆与固定边界通过');
 }}catch(e){if(p&&!p.isClosed()){fs.mkdirSync('ui-artifacts/zoom359',{recursive:true});await p.screenshot({path:'ui-artifacts/zoom359/failure.png'}).catch(()=>{});}throw e;}finally{srv?.kill();await b?.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
