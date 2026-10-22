/* 仅美术验收：五峰三时段真实解码、原位换图、黄昏设置与横竖屏，不触发发布全量检查。 */
const assert=require('node:assert/strict'),fs=require('node:fs');
const {spawn}=require('node:child_process'),{chromium}=require('playwright');
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','行测'],{env:process.env});
let logs='',page,browser;srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((resolve,reject)=>{let s='';const t=setTimeout(()=>reject(Error(logs)),20000);srv.stdout.on('data',b=>{s+=b;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);resolve(m[1]);}});srv.on('exit',()=>{clearTimeout(t);reject(Error(logs));});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 fs.mkdirSync('ui-artifacts/art368',{recursive:true});
 for(const [name,width,height] of [['desktop',1440,960],['tablet-portrait',820,1180]]){
  page=await browser.newPage({viewport:{width,height},deviceScaleFactor:2,hasTouch:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());
  await page.locator('#splash').waitFor({state:'hidden'});
  for(const peak of name==='desktop'?['chang','yan','li','shu','zi']:['yan']){
   await page.evaluate(async peak=>{await go('home');STUDY_REGIONS.select(peak);await go('train');},peak);
   await page.evaluate(()=>{window.__art368View=document.querySelector('#view').firstElementChild;});
   for(const time of ['day','dusk','night']){
    await page.evaluate(time=>{localStorage.setItem('scene-time',time);SCENE_FX.apply();},time);
    await page.waitForFunction(expected=>document.body.style.getPropertyValue('--ds-page-art').includes(expected),`train-${peak}-${time}.webp`);
    const info=await page.evaluate(async()=>{
     const src=document.body.style.getPropertyValue('--ds-page-art').match(/url\(["']?(.*?)["']?\)$/)[1];
     const im=new Image();im.src=src;await im.decode();
     return{size:[im.naturalWidth,im.naturalHeight],src,phase:document.documentElement.dataset.scenePhase,relight:document.body.dataset.sceneRelight,
      same:window.__art368View===document.querySelector('#view').firstElementChild,filter:getComputedStyle(document.querySelector('#bgLayer')).filter,
      overflow:document.documentElement.scrollWidth>innerWidth+2};
    });
    assert.deepEqual(info.size,[3840,2880]);assert(info.src.includes(`beauty/page/train-${peak}-${time}.webp`),'浏览器沿美术别名访问新版4K资源');
    assert.equal(info.phase,time);assert(info.same,'切时段不重建练习界面');assert(!info.overflow);
    if(time!=='day'){assert.equal(info.relight,'native','独立夜景/黄昏不重复调色');assert.equal(info.filter,'none');}
    if(peak==='yan')await page.screenshot({path:`ui-artifacts/art368/${name}-${time}.png`});
   }
  }
  await page.evaluate(()=>go('settings'));await page.locator('[data-fx-group="navigation"]>summary').click();
  await page.locator('select[data-scene-time]').selectOption('dusk');
  assert.equal(await page.evaluate(()=>localStorage.getItem('scene-time')),'dusk');
  assert.deepEqual(errors,[]);await page.close();console.log(name+'：三时段4K/原位切图/无横溢出/黄昏设置通过');
 }
 console.log('ART368-UI-OK');
}catch(e){if(page&&!page.isClosed())await page.screenshot({path:'ui-artifacts/art368/failure.png'}).catch(()=>{});throw e;}finally{await browser?.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
