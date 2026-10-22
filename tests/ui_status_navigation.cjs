/* 3.0.2实际路径：独立页面、时政地图入口、地点改名持久化与常驻HUD不遮挡。 */
const assert=require('node:assert/strict'),{chromium}=require('playwright'),{spawn}=require('node:child_process'),fs=require('node:fs');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),'--journey-fixture'],{env:process.env});
let browser,page,log='';srv.stderr.on('data',b=>log+=b);
const ready=new Promise((resolve,reject)=>{let out='';const t=setTimeout(()=>reject(Error(log)),20000);srv.stdout.on('data',b=>{out+=b;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);resolve(m[1]);}});srv.on('exit',c=>{clearTimeout(t);reject(Error('服务退出'+c+log));});});
async function checkHUD(){
 if(await page.evaluate(()=>VIEW)!=='home'){assert.equal(await page.locator('.subpage-heading').isVisible(),true);assert.equal(await page.locator('.study-hud-player,.study-hud-world').count(),0);assert.equal(await page.locator('#studyHud [role="progressbar"]').count(),1);assert.equal(await page.locator('#studyHud #drawBtn').isVisible(),true);return;}
 assert.equal(await page.locator('.study-hud-player').isVisible(),true);assert.equal(await page.locator('.study-hud-world').isVisible(),true);assert.equal(await page.locator('#studyHud [role="progressbar"]').count(),2);
}
async function go(v){await page.evaluate(v=>go(v),v);assert.equal(await page.evaluate(()=>VIEW),v);await checkHUD();}
(async()=>{try{const base=await ready;browser=await chromium.launch(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{});page=await browser.newPage({viewport:{width:1280,height:860}});require('./fixed_ui_helpers.cjs').install(page);const errors=[];page.on('dialog',d=>d.accept());page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.locator('.portal-world').waitFor();await checkHUD();
 const beat=await page.evaluate(()=>api('/api/heartbeat',{seconds:0}));assert.equal(typeof beat.realm.next_xp,'number');assert.equal(typeof beat.study_status.day,'number');await page.evaluate(beat=>{Object.assign(DASH,{xp:beat.xp,realm:beat.realm,study_status:beat.study_status});DASH.minutes.today=7;updatePill();},beat);assert.match(await page.locator('.study-hud-meter.time').textContent(),/7 \/ /);
 await page.evaluate(()=>go('train'));await page.locator('[data-hall-page="train"]').waitFor();assert.equal(await page.locator('[data-hall]').count(),0);assert.equal(await page.locator('#bankCount,.sl-training').count(),0);
 await go('home');await page.locator('[data-portal-go="bank"]').click();await page.waitForFunction(()=>VIEW==='bank');await page.locator(subject==='申论'?'.sl-training':'.trial-hall').waitFor();assert.equal(await page.locator('[data-hall]').count(),0);assert.equal(await page.locator('[data-hall-page="train"]').count(),0);await checkHUD();
 if(subject!=='申论'){
  const board=await page.evaluate(()=>DASH.tree[0].board);
  await page.evaluate(board=>api('/api/bank/add',{board,topic:'自编条件验证',source:'UI夹具',stem:'自编题：哪项是甲？',options:{A:'甲',B:'乙',C:'丙',D:'丁'},answer:'A',analysis:'选项甲对应题干条件。'}),board);
  await go('bank');await page.locator('[data-th-enter=blocks]').click();await page.locator('.th-start').click();await page.waitForFunction(()=>VIEW==='bank'&&T_TYPE==='bank'&&!T.busy);await page.locator('.train').waitFor();await checkHUD();
  const chatTop=await page.locator('.train').evaluate(x=>x.getBoundingClientRect().top);const hudBottom=await page.locator('#studyHud').evaluate(x=>x.getBoundingClientRect().bottom);assert.ok(chatTop>=hudBottom-1,'试炼聊天区避开紧凑信息带');
  await go('train');await page.locator('[data-hall-page="train"]').waitFor();assert.equal(await page.locator('.train').count(),0);
  await go('bank');await page.locator('.train').waitFor();assert.equal(await page.locator('#toHall').count(),0);await page.keyboard.press('Escape');await page.waitForFunction(()=>VIEW==='home');await page.locator('.portal-world').waitFor();await checkHUD();await go('bank');await page.locator('.train').waitFor();
 }
 await go('home');await page.locator('[data-portal-go="tianji"]').click();await page.locator('.tj-hub').waitFor();assert.equal(await page.evaluate(()=>VIEW),'tianji');await checkHUD();
 for(const view of ['dwelling','skeleton','notes','log','contest','settings'].filter(v=>!(subject==='行测'&&v==='log')))await go(view);
 await page.locator('[data-portal-selected]').selectOption('bank');await page.locator('[data-portal-name]').fill('独立实战入口');await page.locator('[data-portal-x]').fill(subject==='行测'?'60':'81');await page.locator('[data-portal-x]').dispatchEvent('change');await page.locator('[data-portal-save]').click();assert.match(await page.locator('[data-portal-status]').textContent(),/已保存/);
 await go('home');assert.equal(await page.locator('[data-portal-go="bank"] b').textContent(),'独立实战入口');await page.reload();await page.locator('[data-portal-go="bank"]').waitFor();assert.equal(await page.locator('[data-portal-go="bank"] b').textContent(),'独立实战入口');await page.locator('[data-portal-go="bank"]').click();await page.waitForFunction(()=>VIEW==='bank');assert.match(await page.locator('.subpage-place').textContent(),/独立实战入口/);
 await go('home');
 // 本境界积累/完整需求，不再用历史累计经验及下一境界总阈值。
 await page.evaluate(()=>STUDY_HUD.mount({...DASH,xp:1000,realm:{...DASH.realm,into:250,need:750,next_xp:5000},minutes:{today:60,goal:180},study_status:{day:10,remaining:50,average_minutes:90}},VIEW));assert.match(await page.locator('.study-hud-meter.xp').textContent(),/250 \/ 750/);assert.equal(await page.locator('.study-hud-meter.xp').getAttribute('aria-valuenow'),'250');
 await go('settings');await page.locator('[data-portal-selected]').selectOption('bank');await page.locator('[data-portal-name]').fill('<img src=x onerror=alert(1)>');await page.locator('[data-portal-save]').click();await go('home');assert.equal(await page.locator('[data-portal-go="bank"] img').count(),0);
 await go('settings');await page.locator('[data-portal-selected]').selectOption('bank');await page.locator('[data-portal-name-reset]').click();await page.locator('[data-portal-save]').click();await go('home');assert.notEqual(await page.locator('[data-portal-go="bank"] b').textContent(),'独立实战入口');
 for(const viewport of [{width:800,height:1280},{width:1280,height:860}]){await page.setViewportSize(viewport);await page.waitForTimeout(100);await checkHUD();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));const overlaps=await page.evaluate(()=>{const h=[...document.querySelectorAll('.study-hud-player,.study-hud-world')].map(x=>x.getBoundingClientRect());return [...document.querySelectorAll('[data-portal-go]')].filter(x=>{const r=x.getBoundingClientRect();return h.some(a=>Math.min(a.right,r.right)>Math.max(a.left,r.left)&&Math.min(a.bottom,r.bottom)>Math.max(a.top,r.top));}).map(x=>x.dataset.portalGo);});assert.deepEqual(overlaps,[],'HUD不能挡住地图入口 '+JSON.stringify(viewport));}
 // 三主题信息卡：主地图与子页、四种窗口明暗，真实数据不因切页丢失。
 for(const theme of ['light','dark'])for(const viewport of [{width:1280,height:860},{width:800,height:1280},{width:960,height:540}]){
  await page.setViewportSize(viewport);await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
  for(const route of ['home','tianji','dwelling','settings']){
   await go(route);await page.waitForTimeout(80);await checkHUD();
   assert.equal(await page.locator('#mapPageTools,#xcGuideAvatar').count(),0);
   if(route!=='home')continue;
   const fit=await page.evaluate(()=>{const w=document.querySelector('.study-hud-world'),r=w.getBoundingClientRect();return {width:r.width,scroll:w.scrollWidth,client:w.clientWidth,bottom:r.bottom,pageHeight:document.documentElement.scrollHeight,font:parseFloat(getComputedStyle(w.querySelector('.study-hud-stat b')).fontSize)};});
   assert.ok(fit.width<=356,'信息卡按内容定宽，不能填满右侧空白');assert.ok(fit.scroll<=fit.client+1,'信息卡内容不溢出');assert.ok(fit.bottom<viewport.height);assert.ok(fit.pageHeight<=viewport.height+2,'整页继续固定');assert.ok(fit.font>=18,'信息数字保持可读');
  }
 }
 await page.setViewportSize({width:1280,height:860});await page.evaluate(()=>document.documentElement.dataset.theme='light');await go('home');
 await page.evaluate(()=>STUDY_HUD.mount({...DASH,study_status:{day:15,remaining:null,average_minutes:75}},VIEW));
 assert.equal(await page.locator('.study-hud-stat').nth(0).getAttribute('aria-label'),'学习第 15 天');assert.equal(await page.locator('.study-hud-stat').nth(1).getAttribute('aria-label'),'考试日期待设置');assert.equal(await page.locator('.study-hud-stat').nth(2).getAttribute('aria-label'),'平均每日学习 75 分钟');
 await page.evaluate(()=>STUDY_HUD.mount({...DASH,study_status:{day:9999,remaining:-12,average_minutes:120.5}},VIEW));assert.equal(await page.locator('.study-hud-stat').nth(1).getAttribute('aria-label'),'考试已过 12 天');
 await page.setViewportSize({width:800,height:1280});await checkHUD();assert.ok(await page.locator('.study-hud-world').evaluate(x=>x.scrollWidth<=x.clientWidth+1),'较长数字不挤出玉牌');
 await page.setViewportSize({width:1280,height:860});await page.evaluate(()=>STUDY_HUD.mount(DASH,VIEW));
 if(process.argv.includes('--shot')){await page.reload();await go('tianji');await page.waitForTimeout(120);fs.mkdirSync('ui-artifacts/status-navigation',{recursive:true});await page.screenshot({path:'ui-artifacts/status-navigation/'+(subject||'mage')+'.png'});}
 assert.deepEqual(errors,[]);console.log('3.0.7首页信息/子页紧凑标题/无工具栏/日期边界/独立页面与累计进度通过：'+(subject||'法考'));
}catch(e){if(page){fs.mkdirSync('ui-artifacts/status-navigation',{recursive:true});await page.screenshot({path:'ui-artifacts/status-navigation/failure-'+(subject||'mage')+'.png'}).catch(()=>{});}throw e;}finally{if(browser)await browser.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
