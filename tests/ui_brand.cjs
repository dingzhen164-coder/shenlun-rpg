/* 真浏览器切换两科、检查统一标题/图标及安装清单，电脑平板明暗截图。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
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
  for(const [name,width,height] of [['desktop',1280,860],['tablet',800,1280]]){await page.setViewportSize({width,height});for(const theme of ['light','dark']){await page.evaluate(t=>{document.documentElement.dataset.theme=t;window.scrollTo(0,0);},theme);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(out,`brand-${subject==='申论'?'shenlun':'xingce'}-${name}-${theme}.png`),fullPage:false});}}
 }
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'brand-result.json'),JSON.stringify({passed:true,screenshots:36,checks:['两科切换','统一标题与科目标识','图标解码及清单链接','两科安装清单统一','电脑平板明暗','申论七页整体视觉','内置背景离线解码','导航避让']},null,2));console.log('BRAND-UI-OK');
 }finally{if(browser)await browser.close();server.kill();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
