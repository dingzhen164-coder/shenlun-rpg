/* 六场景/选择厅原生4K，真实HTTP解码、时段原位切图和实际CSS层；三设备。 */
const assert=require('node:assert/strict'),fs=require('node:fs'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_trial_server.py'],{env:process.env});let logs='',browser,page;service.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let output='';const timer=setTimeout(()=>no(Error(logs)),20000);service.stdout.on('data',b=>{output+=b;const m=output.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});service.on('exit',()=>{clearTimeout(timer);no(Error(logs));});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,width,height]of [['desktop',1280,860],['portrait',800,1280],['landscape',1280,800]]){
  page=await browser.newPage({viewport:{width,height},deviceScaleFactor:2});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.locator('#splash').waitFor({state:'hidden'});await page.evaluate(()=>document.body.classList.add('has-bg'));
  for(const scene of ['dwelling','bank','contest','skeleton','tianji','settings']){
   await page.evaluate(scene=>go(scene),scene);await page.evaluate(()=>window.__root381=document.querySelector('#view').firstElementChild);
   for(const phase of (process.argv.includes('--day-only')?['day']:['day','dusk','night'])){
    await page.evaluate(phase=>{localStorage.setItem('scene-time',phase);SCENE_FX.apply();},phase);
    await page.waitForFunction(({scene,phase})=>document.body.style.getPropertyValue('--ds-page-art').includes(scene+'-'+phase+'.webp'),{scene,phase});
    const info=await page.evaluate(async()=>{const src=document.body.style.getPropertyValue('--ds-page-art').match(/url\(["']?(.*?)["']?\)$/)[1],im=new Image();im.src=src;await im.decode();const bg=document.querySelector('#bgLayer');return{size:[im.naturalWidth,im.naturalHeight],art:document.body.dataset.sceneArt,relight:document.body.dataset.sceneRelight,filter:getComputedStyle(bg).filter,shade:getComputedStyle(bg,'::after').opacity,tint:getComputedStyle(bg,'::before').backgroundImage,same:__root381===document.querySelector('#view').firstElementChild,overflow:document.documentElement.scrollWidth>innerWidth+2};});
    assert.deepEqual(info.size,[3840,2880]);assert.equal(info.art,'room381');assert.equal(info.relight,'native');assert.equal(info.filter,'none');assert.equal(info.shade,'0');assert(!/gradient/.test(info.tint));assert(info.same&&!info.overflow,JSON.stringify(info));
    if(scene==='bank'){
     await page.waitForFunction(phase=>document.querySelector('.th-panorama')?.src.includes('bank-'+phase+'.webp'),phase);
     assert.equal(await page.locator('.th-panorama').evaluate(e=>getComputedStyle(e).filter),'none');
     for(const mode of ['blocks','exam']){await page.locator('[data-th-enter='+mode+']').click();const selection=await page.locator('.th-dialog[open]').evaluate(async d=>{const s=getComputedStyle(d,'::before'),src=s.backgroundImage.match(/url\(["']?(.*?)["']?\)$/)[1],im=new Image();im.src=src;await im.decode();return{src,size:[im.naturalWidth,im.naturalHeight],filter:s.filter,shade:getComputedStyle(d,'::after').backgroundImage};});assert(selection.src.includes('selection-'+phase+'.webp'));assert.deepEqual(selection.size,[3840,2880]);assert.equal(selection.filter,'none');assert.equal(selection.shade,'none');await page.locator('[data-th-close]').click();}
    }
    if(phase==='day'||phase==='night'){fs.mkdirSync('ui-artifacts/381',{recursive:true});await page.screenshot({path:'ui-artifacts/381/'+scene+'-'+label+'-'+phase+'.png'});}
   }
   // 非塔清晨沿用昼图且不加晨光滤镜；塔使用独立清晨原画。
   if(process.argv.includes('--day-only'))continue;
   await page.evaluate(()=>{localStorage.setItem('scene-time','day');SCENE_FX.apply();document.documentElement.dataset.scenePhase='dawn';});
   await page.waitForFunction(scene=>document.body.style.getPropertyValue('--ds-page-art').includes(scene+'-'+(scene==='bank'?'dawn':'day')+'.webp'),scene);assert.equal(await page.locator('#bgLayer').evaluate(e=>getComputedStyle(e).filter),'none');
   if(scene==='bank'){await page.locator('[data-th-enter=blocks]').click();assert.match(await page.locator('.th-dialog[open]').evaluate(e=>getComputedStyle(e,'::before').backgroundImage),/selection-dawn\.webp/);await page.locator('[data-th-close]').click();}
  }
  assert.deepEqual(errors,[]);await page.close();console.log(label+(process.argv.includes('--day-only')?'：六场景白天4K/选择厅/边界预验通过':'：六场景三时段4K/原位切换/清晨/选择厅/无重复滤镜遮罩通过'));
 }
}catch(e){if(page&&!page.isClosed()){fs.mkdirSync('ui-artifacts/381',{recursive:true});await page.screenshot({path:'ui-artifacts/381/art-failure.png'}).catch(()=>{});}throw e;}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
