/* 真浏览器切换两科、检查统一标题/图标及安装清单，电脑平板明暗截图。 */
const {chromium}=require('playwright'),{spawn,execFileSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
async function main(){
 const out=path.resolve('ui-artifacts');fs.mkdirSync(out,{recursive:true});
 const server=spawn(process.env.PYTHON||'python',['tests/ui_brand_server.py'],{env:{...process.env,PYTHONIOENCODING:'utf-8'}});let logs='',browser;server.stderr.on('data',b=>logs+=b);
 try{
 const base=await new Promise((resolve,reject)=>{let t='';const timer=setTimeout(()=>reject(Error(logs)),20000);server.stdout.on('data',b=>{t+=b;const m=t.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});server.on('exit',c=>{clearTimeout(timer);reject(Error('server '+c+logs));});});
 browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1280,height:860}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);
 async function settings(){
  await page.locator('#nav [data-view="settings"]').click();
  const button=page.locator('[data-subject="行测"]');await button.waitFor({state:'attached'});
  if(await button.evaluate(el=>{const d=el.closest('details');return d&&!d.open;}))await page.locator('details').filter({has:button}).locator('summary').first().click();
  await button.waitFor({state:'visible'});
 }
 for(const subject of ['申论','行测']){
  if(subject==='行测'){await settings();await page.locator('[data-subject="行测"]').click();await page.waitForFunction(()=>document.querySelector('.app-subject')?.textContent==='行测');}
  await settings();
  const dateInput=page.locator('#scheduleStart');await dateInput.waitFor({state:'attached'});await dateInput.evaluate(el=>{const d=el.closest('details');if(d)d.open=true;});
  assert.ok((await page.locator('body').textContent()).includes(subject==='申论'?'仕途备考日程':'修炼备考历'));
  assert.match(await dateInput.inputValue(),/^\d{4}-\d{2}-\d{2}$/);
  await page.waitForFunction(()=>document.querySelector('.app-brand-icon')?.complete&&document.querySelector('.app-brand-icon')?.naturalWidth===192);
  assert.equal(await page.title(),'公考模拟器 · '+subject);assert.equal(await page.locator('.brand span').textContent(),'公考模拟器');assert.equal(await page.locator('.app-subject').textContent(),subject);
  assert.deepEqual(await page.locator('[data-subject]').allTextContents(),['行测','申论']);
  const response=await page.request.get(base+'/manifest.webmanifest'),manifest=await response.json();assert.equal(manifest.name,'公考模拟器');assert.equal(manifest.short_name,'公考模拟器');assert.ok(manifest.description.includes('行测与申论'));
  for(const icon of manifest.icons)assert.equal((await page.request.get(base+'/'+icon.src)).status(),200);
  assert.ok((await page.locator('body').textContent()).includes('gongkao-simulator-mac.zip')===false,'源码运行不显示Mac专用提示');
  if(subject==='申论'){
   assert.ok(await page.locator('body').evaluate(el=>el.classList.contains('sl-office-cursor')));
   const cursorToggle=page.locator('#slCursorToggle');
   await cursorToggle.evaluate(el=>{const d=el.closest('details');if(d)d.open=true;});
   for(const theme of ['light','dark']){
    await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
    await page.locator('.sl-ui-masthead h1').click();await page.locator('.sl-cursor-stamp').waitFor();
    await page.locator('.sl-cursor-stamp').evaluate(el=>el.getAnimations().forEach(a=>{a.pause();a.currentTime=160;}));
    assert.equal(await page.locator('.sl-cursor-effects').evaluate(el=>getComputedStyle(el).pointerEvents),'none');
    await page.screenshot({path:path.join(out,`sl-cursor-desktop-${theme}.png`),animations:'allow'});
    await page.evaluate(()=>SL_CURSOR.sync());
   }
   await page.evaluate(()=>document.querySelector('#scheduleStart').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerType:'mouse',button:0})));
   assert.equal(await page.locator('.sl-cursor-stamp').count(),0);
   await page.evaluate(()=>document.querySelector('.sl-ui-masthead h1').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerType:'touch',button:0})));
   assert.equal(await page.locator('.sl-cursor-stamp').count(),0);
   await page.emulateMedia({reducedMotion:'reduce'});await page.locator('.sl-ui-masthead h1').click();assert.equal(await page.locator('.sl-cursor-stamp').count(),0);await page.emulateMedia({reducedMotion:'no-preference'});
   await cursorToggle.uncheck();assert.ok(await page.locator('body').evaluate(el=>!el.classList.contains('sl-office-cursor')));
   await page.reload();await page.waitForFunction(()=>document.querySelector('.app-subject')?.textContent==='申论');
   assert.ok(await page.locator('body').evaluate(el=>!el.classList.contains('sl-office-cursor')));await settings();
   await page.locator('#slCursorToggle').evaluate(el=>{const d=el.closest('details');if(d)d.open=true;});await page.locator('#slCursorToggle').check();
   for(const asset of ['hall','archive','night']){
    const response=await page.request.get(base+'/assets/shenlun/'+asset+'.webp');assert.equal(response.status(),200);
    assert.ok(await page.evaluate(src=>new Promise(resolve=>{const im=new Image();im.onload=()=>resolve(im.naturalWidth>1000);im.onerror=()=>resolve(false);im.src=src;}),base+'/assets/shenlun/'+asset+'.webp'));
   }
   for(const view of ['home','train','notes','contest','tianji','skeleton','log']){
    await page.locator('#nav [data-view="'+view+'"]').click();
    const title={home:'办公室',train:'办理中心',notes:'公务手账',contest:'年度考核',tianji:'时政简报',skeleton:'档案室',log:'政绩录'}[view];
    await page.waitForFunction(title=>document.querySelector('.sl-ui-masthead h1')?.textContent===title,title);
    if(view==='train')assert.equal(await page.locator('.sl-ui-masthead [data-hall]').count(),2);
    if(view==='skeleton')assert.equal(await page.locator('.sl-ui-masthead [data-libtab]').count(),3);
    if(view==='notes'){
     assert.equal(await page.locator('.sl-ui-masthead [data-ntab]').count(),2);
     await page.locator('.sl-ui-masthead [data-ntab="library"]').click();await page.locator('#ntQ').waitFor();
     await page.locator('#ntSideMin').click();await page.locator('#ntSideOpen').waitFor();
     await page.locator('.sl-ui-masthead [data-ntab="books"]').click();await page.locator('#ntNew').waitFor();
     assert.equal(await page.locator('.sl-ui-masthead [data-ntab]').count(),2);
     assert.equal(await page.locator('.nt-side [data-ntab]').count(),0);
    }
    assert.equal(await page.locator('#nav .sl-ui-icon').count(),8);
    for(const [name,width,height] of [['desktop',1280,860],['tablet',800,1280]]){
     await page.setViewportSize({width,height});
     for(const theme of ['light','dark']){
      await page.evaluate(t=>{document.documentElement.dataset.theme=t;window.scrollTo(0,0);},theme);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'page '+view+' fits '+name);
      if(width>1100)assert.ok(await page.evaluate(()=>document.querySelector('#view').getBoundingClientRect().left>=document.querySelector('.topbar').getBoundingClientRect().right),'sidebar does not cover work');
      await page.screenshot({path:path.join(out,`sl-ui-${view}-${name}-${theme}.png`),fullPage:false,animations:'disabled'});
     }
    }
   }
   await page.setViewportSize({width:1280,height:860});await settings();
  }
  if(subject==='行测'){
   await page.locator('#nav [data-view="home"]').click();await page.locator('.xc-guide-scene').waitFor();
   await page.waitForFunction(()=>document.querySelector('.xc-guide-portrait img')?.naturalWidth===1024);
   for(const [name,width,height] of [['desktop',1280,860],['tablet',800,1280],['phone',390,844]]){
    await page.setViewportSize({width,height});
    for(const theme of ['light','dark']){
     await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
     assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
     await page.locator('.xc-guide-portrait').click();await page.locator('.xc-guide-dialogue').waitFor();
     await page.locator('[data-xc-guide="reveal"]').click();
     assert.equal(await page.locator('.xc-guide-spoken').textContent(),await page.locator('.xc-guide-sr').textContent());
     await page.screenshot({path:path.join(out,`xc-guide-${name}-${theme}.png`),animations:'disabled'});
     await page.keyboard.press('Escape');assert.equal(await page.locator('.xc-guide-dialogue').count(),0);
    }
   }
   await page.emulateMedia({reducedMotion:'reduce'});await page.locator('.xc-guide-portrait').click();
   assert.equal(await page.locator('.xc-guide-spoken').textContent(),await page.locator('.xc-guide-sr').textContent());
   await page.keyboard.press('Escape');await page.emulateMedia({reducedMotion:'no-preference'});
   await page.locator('.xc-guide-scene [data-xc-guide="teach"]').click();await page.locator('#xcGuideAvatar').waitFor();
   assert.equal(await page.locator('.xc-guide-scene').count(),0);
   await page.setViewportSize({width:1280,height:860});await settings();
   assert.ok(await page.locator('body').evaluate(el=>el.classList.contains('xc-spirit-cursor')&&!el.classList.contains('sl-office-cursor')));
   for(const file of ['pointer','inner','outer'])assert.equal((await page.request.get(base+'/assets/xiuxian-cursor/'+file+'.svg')).status(),200);
   await page.locator('#xcSize').evaluate(el=>{const d=el.closest('details');if(d)d.open=true;});
   async function arrayShot(name){await page.locator('#view .card h3').first().click();await page.locator('.xc-cursor-array').waitFor();await page.waitForFunction(()=>[...document.querySelectorAll('.xc-cursor-array img')].every(im=>im.complete&&im.naturalWidth>50));await page.locator('.xc-cursor-array').evaluate(el=>{for(const n of [el,...el.children])n.getAnimations().forEach(a=>{a.pause();a.currentTime=220;});});assert.equal(await page.locator('.xc-cursor-effects').evaluate(el=>getComputedStyle(el).pointerEvents),'none');await page.screenshot({path:path.join(out,name+'.png'),animations:'allow'});await page.evaluate(()=>XC_CURSOR.sync());}
   await page.locator('[data-xc-pref="pointer"]').uncheck();assert.ok(await page.locator('body').evaluate(el=>el.classList.contains('xc-spirit-cursor')&&!el.classList.contains('xc-custom-pointer')));await page.locator('[data-xc-pref="pointer"]').check();
   for(const [name,width,height] of [['desktop',1280,860],['tablet',800,1280]]){await page.setViewportSize({width,height});for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await arrayShot(`xc-cursor-${name}-${theme}`);}}
   await page.setViewportSize({width:1280,height:860});
   await page.locator('[data-xc-pref="click"]').uncheck();await page.locator('.brand').click();assert.equal(await page.locator('.xc-cursor-array').count(),0);await page.locator('[data-xc-pref="click"]').check();
   await page.evaluate(()=>{for(const [id,value] of [['xcSize','180'],['xcTime','1100']]){const b=document.getElementById(id);b.value=value;b.dispatchEvent(new Event('input',{bubbles:true}));}});
   await page.evaluate(()=>{document.querySelector('#scheduleStart').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerType:'mouse',button:0}));document.querySelector('.brand').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerType:'touch',button:0}));});assert.equal(await page.locator('.xc-cursor-array').count(),0);
   await page.emulateMedia({reducedMotion:'reduce'});await page.locator('.brand').click();assert.equal(await page.locator('.xc-cursor-array').count(),0);await page.emulateMedia({reducedMotion:'no-preference'});
   const zip=execFileSync(process.env.PYTHON||'python',['-c',"import sys;sys.path.insert(0,'tests');from test_cursor_assets import pack;sys.stdout.buffer.write(pack())"]);
   await page.locator('#xcZip').setInputFiles({name:'cursor.zip',mimeType:'application/zip',buffer:zip});await page.waitForFunction(()=>document.querySelector('#xcAssetStatus')?.textContent==='已使用本机Mod素材');
   for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await arrayShot(`xc-imported-desktop-${theme}`);}
   await page.locator('[data-xc-pref="enabled"]').uncheck();await page.reload();await page.waitForFunction(()=>document.querySelector('.app-subject')?.textContent==='行测');assert.ok(await page.locator('body').evaluate(el=>!el.classList.contains('xc-spirit-cursor')));await settings();
   assert.equal(await page.locator('#xcAssetStatus').textContent(),'已使用本机Mod素材');await page.locator('#xcBuiltin').evaluate(el=>{const d=el.closest('details');if(d)d.open=true;});await page.locator('#xcBuiltin').click();await page.locator('[data-xc-pref="enabled"]').check();
   assert.equal(await page.locator('#xcSize').inputValue(),'180');assert.equal(await page.locator('#xcTime').inputValue(),'1100');
  }
  for(const [name,width,height] of [['desktop',1280,860],['tablet',800,1280]]){await page.setViewportSize({width,height});for(const theme of ['light','dark']){await page.evaluate(t=>{document.documentElement.dataset.theme=t;window.scrollTo(0,0);},theme);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(out,`brand-${subject==='申论'?'shenlun':'xingce'}-${name}-${theme}.png`),fullPage:false});}}
 }
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'brand-result.json'),JSON.stringify({passed:true,screenshots:44,checks:['两科切换','统一标题与科目标识','图标解码及清单链接','两科安装清单统一','电脑平板明暗','申论七页整体视觉','内置背景离线解码','导航避让','公文鼠标点击透传/触摸避让/输入避让/减少动画/开关重启','行测法阵明暗/本机ZIP导入解码/重启/关闭/恢复内置/两科隔离']},null,2));console.log('BRAND-UI-OK');
 }finally{if(browser)await browser.close();server.kill();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
