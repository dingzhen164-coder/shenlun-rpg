/* 3.0完整循环：真实临时库，原卡片UI提供证据；同伴/陈列/阶段/减少动画/返回。
   没有AI、真实题库或本机配置。仅失败截图，成功可用--shot保存一张预览。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),fs=require('node:fs');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),'--journey-fixture'],{env:process.env});
let logs='',browser,page;srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error(logs||'临时库未启动')),20000);
 srv.stdout.on('data',b=>{out+=b;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});
 srv.on('exit',c=>{clearTimeout(timer);reject(Error('服务退出 '+c+' '+logs));});});
async function open(){await page.locator('[data-narrative="catalogue"]').first().click();await page.locator('.narrative-dialog').waitFor();}
async function home(){await page.locator('#nav [data-view="home"]').click();await page.locator('[data-narrative="catalogue"]').first().waitFor();}
async function card(){await page.getByRole('button',{name:/显示答案|揭示答案/}).click();await page.locator('[data-rate="4"]').click();await page.locator('#yjBack').click();await home();}
async function data(){return page.evaluate(()=>fetch('/api/narrative').then(r=>r.json()));}
async function bounds(){assert.equal(await page.evaluate(()=>{const d=document.querySelector('.narrative-dialog'),r=d.getBoundingClientRect();return document.documentElement.scrollWidth<=innerWidth+2&&r.left>=0&&r.right<=innerWidth&&d.scrollWidth<=d.clientWidth+2;}),true);}
(async()=>{try{
 const base=await ready;browser=await chromium.launch(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{});
 const context=await browser.newContext({viewport:{width:1280,height:860}});page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.locator('[data-portal-motion]').waitFor();
 await page.locator('[data-portal-motion]').click();assert.equal(await page.locator('[data-portal-motion]').getAttribute('aria-pressed'),'true');
 await page.reload();await page.locator('[data-portal-motion]').waitFor();assert.equal(await page.locator('[data-portal-motion]').getAttribute('aria-pressed'),'true');
 assert.equal(await page.evaluate(()=>getComputedStyle(document.querySelector('.portal-cloud')).animationName),'none');
 await open();await page.locator('.narrative-companions summary').click();await page.locator('[data-narrative-chapter="peer_method"]').click();
 await page.locator('[data-narrative-choice="practice"]').click();await page.locator('[data-narrative-choice="continue"]').click();
 await page.locator('[data-narrative="finish"]').click();await page.locator('[data-narrative="replay"]').waitFor();
 const before=await data();assert.equal(before.companions[0].read,true);assert.equal(before.journey.collection.length,0);
 assert.equal(await page.locator('#narrative-title').textContent(),before.companions[0].name);await page.locator('[data-narrative="back"]').click();
 assert.equal(await page.locator('#narrative-title').textContent(),before.guide_profile.character);
 await page.locator('[data-journey-claim="main:study"][data-journey-approach="practice"]').click();
 await page.locator('[data-journey-claim^="daily:"]').first().click();await page.locator('[data-journey-start^="daily:"]').click();
 await card();await open();await page.locator('[data-journey-deliver="main:study"]').click();
 const first=await data();assert.equal(first.journey.collection.length,2);assert.equal(first.world_progress.stage,1);
 await page.locator('[data-journey-claim="main:review"]').click();await page.locator('[data-journey-start="main:review"]').click();
 await page.locator('button[data-yjgo=""]').click();await card();await open();
 await page.locator('[data-journey-deliver="main:review"]').click();await page.locator('[data-journey-deliver^="daily:"]').click();
 const end=await data();assert.equal(end.world_progress.stage,2);assert.equal(end.journey.collection.length,6);
 assert.match(end.companions[0].feedback,/上次选择/);await bounds();
 await page.locator('.journey-collection summary').click();await page.locator('[data-journey-place="main:ornament"]').click();
 await page.locator('[data-narrative="close"]').click();await page.reload();await page.locator('.journey-display').waitFor();
 assert.match(await page.locator('.journey-display').textContent(),/法典|卷宗|竹卷/);await open();
 await page.locator('.world-progress summary').click();await page.locator('[data-world-go="restored"]').click();
 await page.waitForFunction(()=>VIEW==='log');assert.equal(await page.locator('.narrative-dialog').count(),0);
 // 触控竖屏 + 暗色 + 系统减少动画。章/任务状态保持，关闭后学习入口不被挡住。
 await page.setViewportSize({width:800,height:1280});await page.emulateMedia({reducedMotion:'reduce'});
 await home();await page.evaluate(()=>document.documentElement.dataset.theme='dark');await open();await bounds();
 assert.equal(await page.evaluate(()=>getComputedStyle(document.querySelector('.narrative-seal,.narrative-portrait')).animationName),'none');
 await page.locator('.narrative-companions summary').click();await page.locator('[data-narrative-chapter="peer_method"]').click();
 await page.locator('[data-narrative="replay"]').click();await page.locator('[data-narrative="skip"]').click();
 assert.equal((await data()).journey.collection.length,6);
 if(process.argv.includes('--shot')){fs.mkdirSync('ui-artifacts/world',{recursive:true});await page.screenshot({path:'ui-artifacts/world/'+(subject||'mage')+'.png'});}
 assert.equal(await page.evaluate(()=>xcBack()),true);await page.locator('#nav [data-view="train"]').click();await page.waitForFunction(()=>VIEW==='train'&&!document.querySelector('.portal-atmosphere'));
 assert.equal(await page.locator('.portal-atmosphere').count(),0);assert.equal(await page.locator('.narrative-dialog').count(),0);assert.deepEqual(errors,[]);
 console.log('3.0世界/同伴/真实学习循环检查通过：'+(subject||'法考'));
}catch(e){if(page){fs.mkdirSync('ui-artifacts/world',{recursive:true});await page.screenshot({path:'ui-artifacts/world/failure-'+(subject||'mage')+'.png'}).catch(()=>{});}throw e;}
finally{if(browser)await browser.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
