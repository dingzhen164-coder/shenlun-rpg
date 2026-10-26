/* 3.6.4 实浏览器：随机偏好/重载、真实夜景与建筑、动画绘制/停止/销毁、两科平板边界。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const subject=process.argv.find(x=>x.startsWith('--subject='))?.split('=')[1]||'行测';
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',subject],{env:process.env});let browser,logs='',active;srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let s='';const t=setTimeout(()=>no(Error(logs)),20000);srv.stdout.on('data',b=>{s+=b;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});srv.on('exit',()=>{clearTimeout(t);no(Error(logs));});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,viewport]of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}],['landscape',{width:1180,height:820}]]){
  const p=await browser.newPage({viewport});active=p;const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.addInitScript(()=>{
   window.__fx={clear:0,sword:0,meteor:0,detached:0};window.__images=[];
   const NativeImage=window.Image;window.Image=class extends NativeImage{constructor(...args){super(...args);__images.push(this);}};
   const proto=CanvasRenderingContext2D.prototype;
   const clear=proto.clearRect;proto.clearRect=function(...a){if(this.canvas.classList.contains('portal-fx')){__fx.clear++;if(!this.canvas.isConnected)__fx.detached++;}return clear.apply(this,a);};
   const draw=proto.drawImage;proto.drawImage=function(...a){if(this.canvas.classList.contains('portal-fx')&&a[0]?.src?.includes('sword-chibi-'))__fx.sword++;return draw.apply(this,a);};
   const stop=CanvasGradient.prototype.addColorStop;CanvasGradient.prototype.addColorStop=function(...a){if(a[1]==='#f4ead7')__fx.meteor++;return stop.apply(this,a);};
  });
  await p.goto(base);await p.waitForFunction(()=>!!window.DASH_REF?.());
  await p.evaluate(()=>{localStorage.setItem('scene-time','night');localStorage.setItem('scene-season','random');SCENE_FX.apply();});
  const first=await p.evaluate(()=>localStorage.getItem('scene-season-cycle-v1'));await p.reload();await p.waitForFunction(()=>!!window.DASH_REF?.());assert.equal(await p.evaluate(()=>localStorage.getItem('scene-season-cycle-v1')),first);
  await p.waitForFunction(()=>document.querySelector('.portal-atmosphere')?.dataset.fxRunning==='true');
  assert.equal(await p.locator('.portal-atmosphere').getAttribute('data-fx-room'),subject==='申论'?'indoor':'outdoor');
  assert.equal(await p.locator('.portal-fx').evaluate(e=>getComputedStyle(e).pointerEvents),'none');
  await p.evaluate(()=>{window.__homeNode=document.querySelector('.portal-stage');window.__positions=[...document.querySelectorAll('[data-portal-go]')].map(e=>[e.dataset.portalGo,e.style.cssText]);});
  // 正常绘制一帧后减少动画必须真正取消后续绘制，而非不断清空画布。
  await p.waitForTimeout(100);assert((await p.evaluate(()=>__fx.clear))>1);
  await p.evaluate(()=>document.documentElement.dataset.motion='reduced');await p.waitForTimeout(80);const stopped=await p.evaluate(()=>__fx.clear);await p.waitForTimeout(160);assert.equal(await p.evaluate(()=>__fx.clear),stopped);
  await p.evaluate(()=>document.documentElement.dataset.motion='full');await p.waitForFunction(n=>__fx.clear>n,stopped);
  await p.emulateMedia({reducedMotion:'reduce'});await p.waitForTimeout(100);const systemStop=await p.evaluate(()=>__fx.clear);await p.waitForTimeout(120);assert.equal(await p.evaluate(()=>__fx.clear),systemStop);await p.emulateMedia({reducedMotion:'no-preference'});
  // 受控可见性事件验证后台暂停/前台恢复，不依赖headless窗口焦点。
  await p.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});await p.waitForTimeout(100);const hidden=await p.evaluate(()=>__fx.clear);await p.waitForTimeout(120);assert.equal(await p.evaluate(()=>__fx.clear),hidden);
  await p.evaluate(()=>{delete document.hidden;document.dispatchEvent(new Event('visibilitychange'));});await p.waitForFunction(n=>__fx.clear>n,hidden);
  if(subject==='行测'&&label==='desktop'){
   // 等实际动画图片解码，再在同一虚拟时钟下重新启动RAF；不混用安装前后的时间戳。
   await p.waitForFunction(()=>{const imgs=__images.filter(i=>i.src.includes('sword-chibi-'));return imgs.length===3&&imgs.every(i=>i.complete&&i.naturalWidth>0);});
   await p.evaluate(async()=>{await Promise.all(__images.filter(i=>i.src.includes('sword-chibi-')).map(i=>i.decode()));document.documentElement.dataset.motion='reduced';});
   await p.waitForFunction(()=>document.querySelector('.portal-atmosphere').dataset.fxRunning==='false');
   await p.clock.install();await p.evaluate(()=>document.documentElement.dataset.motion='full');await p.clock.runFor(22500);
   assert((await p.evaluate(()=>__fx.sword))>0,'御剑贴图实际进入画布 '+JSON.stringify(await p.evaluate(()=>__fx)));
   assert((await p.evaluate(()=>__fx.meteor))>0,'夜空实际绘制流星');await p.clock.resume();
  }
  assert(await p.evaluate(()=>__homeNode===document.querySelector('.portal-stage')));
  assert.deepEqual(await p.evaluate(()=>[...document.querySelectorAll('[data-portal-go]')].map(e=>[e.dataset.portalGo,e.style.cssText])),await p.evaluate(()=>__positions));
  // 只截本次变更外观，页面离开后不得有孤立画布继续绘制。
  const out=path.resolve('ui-artifacts/scene364');fs.mkdirSync(out,{recursive:true});if(label==='desktop')await p.screenshot({path:path.join(out,subject+'-home-night.png')});
  await p.evaluate(()=>go('dwelling'));await p.waitForFunction(subject=>getComputedStyle(document.querySelector('#bgLayer')).backgroundImage.includes(subject==='行测'?'dwelling-night.webp':'dwelling-growth-night.webp'),subject);
  const frames=await p.evaluate(()=>__fx.clear);await p.waitForTimeout(100);assert.equal(await p.evaluate(()=>__fx.clear),frames);assert.equal(await p.evaluate(()=>__fx.detached),0);
  await p.evaluate(()=>{window.__content=document.querySelector('#view').firstElementChild;localStorage.setItem('scene-time','day');SCENE_FX.apply();});await p.waitForFunction(subject=>getComputedStyle(document.querySelector('#bgLayer')).backgroundImage.includes(subject==='行测'?'dwelling-day.webp':'dwelling-growth.webp'),subject);
  assert(await p.evaluate(()=>__content===document.querySelector('#view').firstElementChild));
  await p.evaluate(()=>{localStorage.setItem('scene-time','night');SCENE_FX.apply();});
  for(const v of ['train','skeleton','notes','tianji','settings',...(subject==='行测'?['bank','contest']:[])]){
   await p.evaluate(v=>go(v),v);await p.waitForFunction(v=>document.body.dataset.sceneRelight==='native'&&(v==='bank'?document.querySelector('.th-panorama')?.src.includes('-night.webp'):getComputedStyle(document.querySelector('#bgLayer')).backgroundImage.includes('-night.webp')),v);
   const selector=v==='bank'?'.th-landscape':v==='contest'?'.cs-landscape':'#bgLayer';
   assert.equal(await p.locator(selector).evaluate(e=>getComputedStyle(e).filter),'none',v);
   if(v==='bank'){
    assert.equal(await p.evaluate(()=>document.body.dataset.trialNight),'true');
    for(const img of await p.locator('[data-night-art]').all()){await img.evaluate(e=>e.decode());assert.match(await img.getAttribute('src'),/-night.webp/);assert(!(await img.evaluate(e=>getComputedStyle(e).filter)).includes('brightness'));}
   }
   assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2||scrollY>0),false,v);
   if(label==='tablet'&&['settings','bank','contest'].includes(v))await p.screenshot({path:path.join(out,subject+'-'+v+'-night.png')});
  }
  await p.evaluate(()=>go('settings'));await p.locator('[data-settings-tab="map"]').count();
  // 地图设置入口沿既有标签，不增加外观/背景设置。
  await p.locator('[data-fx-group="navigation"]>summary').click();
  await p.locator('select[data-scene-season]').selectOption('random');await p.locator('[data-scene-minutes]').selectOption('60');assert(await p.locator('[data-scene-interval]').isVisible());
  await p.locator('[data-scene-minutes]').selectOption('30');assert.equal(await p.evaluate(()=>JSON.parse(localStorage.getItem('scene-season-cycle-v1')).minutes),30);
  await p.locator('select[data-scene-season]').selectOption('spring');assert(!(await p.locator('[data-scene-interval]').isVisible()));assert.equal(await p.evaluate(()=>document.documentElement.dataset.sceneSeason),'spring');assert.equal(await p.evaluate(()=>localStorage.getItem('scene-time')),'night','改变季节不得重置场景时间');
  assert.deepEqual(errors,[]);await p.close();console.log(subject+' '+label+'：夜景/随机/动画生命周期与边界通过');
 }
}finally{await browser?.close();srv.kill();}})().catch(async e=>{console.error(e);process.exitCode=1;});
