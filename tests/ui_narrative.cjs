/* 第一批纪事的浏览器回归：临时库，无真实AI。续读、CAS冲突、跳过/重读、
   简短模式、返回、异步离页、触控与布局；不跑与本轮无关的完整发布验证。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),fs=require('node:fs');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[])],{env:process.env});
let logs='';srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error(logs||'服务未启动')),20000);
  srv.stdout.on('data',b=>{out+=b;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});
  srv.on('exit',c=>{clearTimeout(timer);reject(Error('服务退出 '+c+' '+logs));});});
const open=async page=>{await page.locator('[data-narrative="catalogue"],[data-portal-go="journal"]').first().click();await page.locator('.narrative-dialog').waitFor();};
const chapter=async page=>{await page.locator('[data-narrative-chapter="prologue"]').click();await page.locator('[data-narrative-choice="understand"]').waitFor();};
const get=async page=>page.evaluate(()=>fetch('/api/narrative').then(r=>r.json()));
let browser, page;
(async()=>{
 try{
  const base=await ready;
  browser=await chromium.launch(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{});
  const context=await browser.newContext({viewport:{width:1280,height:860}});
  page=await context.newPage();require('./fixed_ui_helpers.cjs').install(page);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.locator('[data-narrative="catalogue"],[data-portal-go="journal"]').first().waitFor();
  const baseline=await page.evaluate(()=>fetch('/api/dashboard').then(r=>r.json()));
  const xp=baseline.xp,minutes=baseline.minutes.today;
  await open(page);assert.equal(await page.locator('[data-narrative-chapter="study_echo"]').isDisabled(),true);
  await chapter(page);assert.equal(await page.locator('[data-narrative-choice="recorded"]').count(),0);
  await page.locator('[data-narrative-choice="understand"]').click();await page.locator('[data-narrative-choice="continue"]').waitFor();
  assert.equal((await get(page)).revision,1);
  await page.keyboard.press('Escape');assert.equal(await page.locator('.narrative-dialog').count(),0);
  await page.reload();await page.locator('[data-narrative="catalogue"],[data-portal-go="journal"]').first().waitFor();await open(page);
  await page.locator('[data-narrative-chapter="prologue"]').click();await page.locator('[data-narrative-choice="continue"]').waitFor();
  assert.match(await page.locator('.narrative-transcript').textContent(),/我想先梳理方法/);
  // 同一服务端存档的另一窗口先推进，旧窗口不能覆盖。
  const other=await context.newPage();await other.goto(base);await open(other);
  await other.locator('[data-narrative-chapter="prologue"]').click();await other.locator('[data-narrative-choice="continue"]').click();
  await other.locator('[data-narrative="finish"]').waitFor();
  await page.locator('[data-narrative-choice="continue"]').click();await page.locator('.narrative-error').filter({hasText:'另一窗口'}).waitFor();
  assert.equal((await get(page)).revision,2);
  await other.locator('[data-narrative="finish"]').click();await other.locator('[data-narrative="replay"]').waitFor();
  await other.locator('[data-narrative="close"]').click();await other.close();
  await page.locator('[data-narrative="close"]').click();await open(page);await page.locator('[data-narrative-chapter="prologue"]').click();
  await page.locator('[data-narrative="replay"]').waitFor();await page.locator('[data-narrative="replay"]').click();await page.locator('[data-narrative-choice="practice"]').waitFor();
  await page.locator('[data-narrative-brief]').check();assert.equal(await page.locator('.narrative-text p').count(),1);
  await page.locator('[data-narrative="skip"]').click();await page.locator('[data-narrative="replay"]').waitFor();
  const after=await page.evaluate(()=>fetch('/api/dashboard').then(r=>r.json()));assert.equal(after.xp,xp);assert.equal(after.minutes.today,minutes);
  assert.equal((await get(page)).chapters[0].read,true);
  // 安卓返回先收起人物，再回地图；不会误退出应用。
  assert.equal(await page.evaluate(()=>xcBack()),true);assert.equal(await page.locator('.narrative-dialog').count(),0);
  // 新对话打开请求晚返回时，导航已离页不得再弹出。
  await page.route('**/api/narrative',async route=>{await new Promise(r=>setTimeout(r,250));await route.continue();});
  await page.locator('[data-narrative="catalogue"],[data-portal-go="journal"]').first().click();await page.evaluate(()=>go('log'));
  await page.waitForTimeout(450);assert.equal(await page.locator('.narrative-dialog').count(),0);await page.unroute('**/api/narrative');
  await page.evaluate(()=>go('home'));await page.locator('[data-narrative="catalogue"],[data-portal-go="journal"]').first().waitFor();
  // 自定义地点在刷新后仍保留。
  await page.evaluate(()=>go('settings'));await page.locator('[data-portal-x]').waitFor({state:'attached'});await page.locator('[data-portal-x]').evaluate(el=>{for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});
  await page.locator('[data-portal-selected]').selectOption('dwelling');await page.locator('[data-portal-x]').fill('24');await page.locator('[data-portal-x]').dispatchEvent('change');await page.locator('[data-portal-save]').click();
  await page.reload();await page.locator('[data-narrative="catalogue"],[data-portal-go="journal"]').first().waitFor();
  const layout=await page.evaluate(()=>JSON.parse(localStorage.getItem('scene-layout:'+DASH_REF().narrative.world.replace('office','guantu'))));
  assert.equal(layout.desktop.dwelling.x,24);
  if((await get(page)).world==='mage'){
    await page.evaluate(()=>go('notes'));
    await page.waitForFunction(()=>VIEW==='notes');
    await page.evaluate(()=>{window.originalNarrativeFlush=NOTES.flush;NOTES.flush=()=>new Promise(r=>window.releaseNarrativeFlush=r);go('home');});
    assert.equal(await page.evaluate(()=>VIEW),'notes');
    await page.evaluate(()=>releaseNarrativeFlush(false));await page.waitForTimeout(60);assert.equal(await page.evaluate(()=>VIEW),'notes');
    await page.evaluate(()=>{NOTES.flush=originalNarrativeFlush;go('home');});await page.locator('[data-narrative="catalogue"],[data-portal-go="journal"]').first().waitFor();
  }
  // 平板深色对话不会横向溢出，选择与触控入口正常；只截本次改动的一张图。
  await page.setViewportSize({width:800,height:1280});await page.evaluate(()=>document.documentElement.dataset.theme='dark');
  await open(page);await page.locator('[data-narrative-chapter="prologue"]').click();await page.locator('[data-narrative="replay"]').waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),true);
  assert.equal(await page.evaluate(()=>{const d=document.querySelector('.narrative-dialog'),r=d.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&d.scrollWidth<=d.clientWidth+2;}),true);
  fs.mkdirSync('ui-artifacts/narrative',{recursive:true});await page.screenshot({path:'ui-artifacts/narrative/dialogue-'+(subject||'mage')+'.png'});
  await page.locator('[data-narrative="study"]').click();await page.waitForFunction(()=>VIEW==='train');assert.equal(await page.locator('.narrative-dialog').count(),0);
  assert.deepEqual(errors,[]);
  console.log('纪事交互检查通过：'+(subject||'法考'));
 }catch(e){if(page){fs.mkdirSync('ui-artifacts/narrative',{recursive:true});await page.screenshot({path:'ui-artifacts/narrative/failure-'+(subject||'mage')+'.png'}).catch(()=>{});}throw e;}
 finally{if(browser)await browser.close();srv.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
