/* 3.0.1用户路径：三主题地图、实际按键、设置录入与刷新、焦点/弹窗/草稿保护。
   真实隔离库，无AI；只失败截图，--shot仅保存本次改动的首页。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),fs=require('node:fs');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[])],{env:process.env});
let browser,page,logs='';srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error(logs||'服务未启动')),20000);srv.stdout.on('data',b=>{out+=b;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});srv.on('exit',c=>{clearTimeout(timer);reject(Error('服务退出 '+c+' '+logs));});});
async function view(name){await page.waitForFunction(v=>VIEW===v&&!!document.querySelector(v==='home'?'.portal-world':v==='settings'?'.shortcut-settings':'#mapPageTools'),name);}
async function home(){if(await page.evaluate(()=>VIEW)!=='home'){await page.locator('[data-map-home]').click();await view('home');}}
(async()=>{try{
 const base=await ready;browser=await chromium.launch(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{});page=await browser.newPage({viewport:{width:1280,height:860}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await view('home');
 const shape=await page.evaluate(()=>{const r=document.querySelector('.portal-world').getBoundingClientRect();return {top:r.top,left:r.left,width:r.width,height:r.height,screen:[innerWidth,innerHeight]};});
 assert.equal(shape.top,0);assert.equal(shape.left,0);assert.equal(shape.width,shape.screen[0]);assert.equal(shape.height,shape.screen[1]);
 assert.equal(await page.locator('.topbar').isVisible(),false);assert.equal(await page.locator('#banner').isVisible(),false);assert.equal(await page.locator('.portal-caption').count(),0);assert.equal(await page.locator('[data-portal-go="settings"]').count(),0);
 const ids=await page.locator('[data-portal-go]').evaluateAll(es=>es.map(e=>e.dataset.portalGo));
 for(const id of ids){await home();await page.locator(`[data-portal-go="${id}"]`).click();
  if(id==='journal'){await page.locator('.narrative-dialog').waitFor();await page.keyboard.press('Escape');await page.locator('.narrative-dialog').waitFor({state:'detached'});assert.equal(await page.evaluate(()=>VIEW),'home');}
  else if(id==='guide'||id==='story'){await page.locator('.xc-guide-dialogue').waitFor();await page.keyboard.press('Escape');await page.locator('.xc-guide-dialogue').waitFor({state:'detached'});}
  else{await view(id==='bank'?'train':id);assert.equal(await page.locator('.topbar').isVisible(),false);assert.equal(await page.locator('[data-map-home]').isVisible(),true);}
 }
 await home();await page.keyboard.press('Tab');await view('dwelling');await page.keyboard.press('Tab');await view('home');
 await page.keyboard.press('Shift+Tab');assert.equal(await page.evaluate(()=>VIEW),'home');
 await page.keyboard.press('Escape');await view('settings');assert.equal(await page.locator('#bgmBtn').isVisible(),true);assert.equal(await page.locator('[data-portal-motion]').isVisible(),true);
 await page.locator('[data-shortcut-record="settings"]').click();await page.keyboard.press('Tab');assert.match(await page.locator('[data-shortcut-status]').textContent(),/不能相同/);
 await page.keyboard.press('F2');await page.locator('[data-shortcut-record="dwelling"]').click();await page.keyboard.press('F3');await page.locator('[data-shortcut-save]').click();await page.locator('[data-shortcut-status]').filter({hasText:'快捷键已保存'}).waitFor();
 assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('map-shortcuts-v1'))),{settings:'F2',dwelling:'F3'});
 await page.evaluate(()=>render());assert.equal(await page.locator('#bgmBtn').isVisible(),true);assert.ok((await page.locator('#todayPill').textContent()).length>4);
 await page.keyboard.press('F2');await view('home');await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>VIEW),'home');
 await page.reload();await view('home');await page.keyboard.press('F3');await view('dwelling');await page.keyboard.press('F3');await view('home');
 await page.keyboard.press('F2');await view('settings');await page.locator('[data-portal-x]').focus();await page.keyboard.press('F3');assert.equal(await page.evaluate(()=>VIEW),'settings');await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>VIEW),'settings');
 if(subject){
  const other=subject==='申论'?'行测':'申论';
  async function switchTo(s){const b=page.locator(`button[data-subject="${s}"]`);await b.evaluate(el=>{for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});await Promise.all([page.waitForEvent('load'),b.click()]);await view('home');await page.waitForFunction(s=>DASH_REF().subject===s,s);}
  await switchTo(other);await page.keyboard.press('F3');await view('dwelling');await page.keyboard.press('F2');await view('settings');
  assert.equal(await page.locator('[data-shortcut-value="settings"]').inputValue(),'F2');await switchTo(subject);await page.keyboard.press('F2');await view('settings');
 }
 await page.locator('[data-shortcut-reset]').click();await page.locator('[data-shortcut-save]').click();await page.locator('[data-shortcut-status]').filter({hasText:'快捷键已保存'}).waitFor();await page.locator('[data-map-home]').click();await view('home');
 // 所有主题都保留手记，保存失败/延迟时设置快捷键不能丢草稿。
 await page.locator('[data-portal-go="notes"]').click();await view('notes');await page.waitForFunction(()=>!!window.NOTES);
 await page.evaluate(()=>{document.activeElement.blur();window.oldNavigationFlush=NOTES.flush;NOTES.flush=()=>new Promise(r=>window.releaseNavigationFlush=r);});
 await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>VIEW),'notes');await page.waitForFunction(()=>!!window.releaseNavigationFlush);await page.evaluate(()=>releaseNavigationFlush(false));await page.waitForTimeout(80);assert.equal(await page.evaluate(()=>VIEW),'notes');
 await page.evaluate(()=>{NOTES.flush=oldNavigationFlush;});await home();
 await page.setViewportSize({width:800,height:1280});await page.evaluate(()=>document.documentElement.dataset.theme='dark');await page.locator('.portal-world').waitFor();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),true);assert.equal(await page.locator('[data-portal-go="dwelling"]').isVisible(),true);
 if(process.argv.includes('--shot')){fs.mkdirSync('ui-artifacts/map-navigation',{recursive:true});await page.screenshot({path:'ui-artifacts/map-navigation/'+(subject||'mage')+'.png'});}
 assert.deepEqual(errors,[]);console.log('地图/快捷键/录入持久化/草稿与焦点保护通过：'+(subject||'法考'));
}catch(e){if(page){fs.mkdirSync('ui-artifacts/map-navigation',{recursive:true});await page.screenshot({path:'ui-artifacts/map-navigation/failure-'+(subject||'mage')+'.png'}).catch(()=>{});}throw e;}
finally{if(browser)await browser.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
