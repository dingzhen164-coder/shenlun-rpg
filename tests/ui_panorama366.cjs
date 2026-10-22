/* 3.6.6高清全景真实像素与铺满验收：隔离HOME/自编资料，覆盖高DPI电脑和平板横竖屏。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','行测'],{env:process.env});let browser,p,logs='';srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let s='';const t=setTimeout(()=>no(Error(logs)),20000);srv.stdout.on('data',b=>{s+=b;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});srv.on('exit',()=>{clearTimeout(t);no(Error(logs));});});
const out=path.resolve('ui-artifacts/panorama366');
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [name,width,height,touch] of [['retina',1512,982,false],['4k',1920,1080,false],['tablet-landscape',1180,820,true],['tablet-wide',1366,1024,true],['tablet-portrait',820,1180,true],['ipad-pro',1024,1366,true]]){
  const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:2,hasTouch:touch});p=await context.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(base);await p.waitForFunction(()=>!!window.DASH_REF?.());
  const before=await p.evaluate(()=>[...document.querySelectorAll('[data-portal-go]')].map(e=>[e.dataset.portalGo,e.style.cssText]));
  for(const season of name==='retina'?['spring','summer','autumn','winter']:['autumn'])for(const time of ['day','night']){
   await p.evaluate(({season,time})=>{localStorage.setItem('scene-season',season);localStorage.setItem('scene-time',time);SCENE_FX.apply();},{season,time});
   const img=p.locator('.portal-'+time);await img.evaluate(i=>i.decode());
   const a=await img.evaluate(i=>{const r=i.getBoundingClientRect(),s=getComputedStyle(i),b=i.parentElement.getBoundingClientRect(),f=getComputedStyle(i.parentElement.querySelector('.portal-landscape-fill'));return{source:[i.naturalWidth,i.naturalHeight],src:i.src,fit:s.objectFit,filter:s.filter,transform:s.transform,fill:f.display,box:[r.left,r.top,r.right,r.bottom],stage:[b.left,b.top,b.right,b.bottom],physicalScale:Math.max(r.width/i.naturalWidth,r.height/i.naturalHeight)*devicePixelRatio,viewport:[innerWidth,innerHeight],overflow:scrollX||scrollY||document.documentElement.scrollWidth>innerWidth+2||document.documentElement.scrollHeight>innerHeight+2};});
   assert.deepEqual(a.source,[3840,2880],'实际解码高清资源');assert(a.src.includes('/hd/'),'新路径避免旧低清缓存');assert.equal(a.fit,'cover');assert.equal(a.filter,'none');assert.equal(a.transform,'none');assert.equal(a.fill,'none','不用模糊补边');assert(a.physicalScale<=1.001,'实测像素足以覆盖高DPI屏幕 '+JSON.stringify(a));
   assert(Math.abs(a.box[0])<1&&Math.abs(a.box[1])<1&&Math.abs(a.box[2]-width)<1&&Math.abs(a.box[3]-height)<1,'全景容器上下左右铺满 '+JSON.stringify(a));assert(!a.overflow,'整页无偏移/溢出');
   assert.deepEqual(await p.evaluate(()=>[...document.querySelectorAll('[data-portal-go]')].map(e=>[e.dataset.portalGo,e.style.cssText])),before,'换季保留地点位置');
   assert.deepEqual(await p.locator('[data-portal-go]').evaluateAll(es=>es.filter(e=>{const r=e.getBoundingClientRect();return r.left<0||r.top<0||r.right>innerWidth+1||r.bottom>innerHeight+1;}).map(e=>e.dataset.portalGo)),[],'两侧地点入口完整');
   if(time==='day'&&['retina','tablet-landscape'].includes(name)&&season==='autumn'){fs.mkdirSync(out,{recursive:true});await p.screenshot({path:path.join(out,name+'.png')});}
  }
  await p.evaluate(()=>go('settings'));await p.locator('[data-fx-group="navigation"]>summary').click();await p.locator('[data-portal-preview] .portal-stage').waitFor();assert.equal(await p.locator('[data-portal-preview] .portal-day').evaluate(e=>getComputedStyle(e).objectFit),'cover','编辑预览规则一致');assert.equal(await p.locator('[data-portal-preview] .portal-stage').getAttribute('data-framing'),'extended');
  assert.deepEqual(errors,[]);await context.close();console.log(name+'：2倍像素密度/高清解码/四边铺满/无模糊补边/地点与预览通过');
 }
 console.log('PANORAMA366-OK');
}catch(e){if(p&&!p.isClosed()){fs.mkdirSync(out,{recursive:true});await p.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});}throw e;}finally{await browser?.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
