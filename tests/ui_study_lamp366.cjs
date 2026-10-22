/* 蜡烛真实交互：自编时政/临时库，无真实AI，电脑与平板点击/键盘/阅读自动/后台/过期。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','行测','--politics-fixture'],{env:process.env});let browser,logs='';srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let s='';const t=setTimeout(()=>no(Error(logs)),20000);srv.stdout.on('data',b=>{s+=b;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});srv.on('exit',()=>{clearTimeout(t);no(Error(logs));});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [width,height]of [[1280,860],[820,1180]]){
  const p=await browser.newPage({viewport:{width,height},hasTouch:true}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(base);await p.waitForFunction(()=>!!window.DASH_REF?.());await p.evaluate(()=>go('settings'));
  const candle=p.locator('#todayPill');await candle.waitFor();assert.equal(await candle.getAttribute('role'),'button');
  const start=p.waitForResponse(r=>r.url().endsWith('/api/study-lamp/start'));await candle.click();assert.equal(await candle.getAttribute('aria-pressed'),'true');assert((await start).ok());await p.waitForFunction(()=>!!STUDY_LAMP.token());
  await p.waitForTimeout(1300);const beat=p.waitForRequest(r=>r.url().endsWith('/api/heartbeat')&&!!r.postDataJSON()?.lamp);await candle.click();const body=(await beat).postDataJSON();assert(body.seconds>0&&body.seconds<5,'只报真实已累计秒数');assert.equal(await candle.getAttribute('aria-pressed'),'false');await p.evaluate(()=>{updateStudyDot();STUDY_LAMP.sync();});assert.equal(await candle.getAttribute('aria-pressed'),'false');
  await candle.focus();await p.keyboard.press('Enter');assert.equal(await candle.getAttribute('aria-pressed'),'true');await p.waitForFunction(()=>!!STUDY_LAMP.token());
  assert(await p.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'hidden'});document.dispatchEvent(new Event('visibilitychange'));return !STUDY_LAMP.active()&&!document.querySelector('#todayPill').classList.contains('on');}),'后台立即停计时');
  await p.evaluate(()=>{delete document.visibilityState;document.dispatchEvent(new Event('visibilitychange'));});await p.waitForFunction(()=>!!STUDY_LAMP.token());
  assert(await p.evaluate(()=>{const raw=Date.now;Date.now=()=>raw()+121000;STUDY_LAMP.sync();const off=!STUDY_LAMP.active()&&!document.querySelector('#todayPill').classList.contains('on');Date.now=raw;return off;}),'长时间无操作停计时');
  await p.evaluate(()=>{STUDY_REGIONS.select('chang');return go('train');});await p.locator('[data-wx-branch="politics"]').click();await p.locator('[data-wx-exam="2026-10-guokao"]').click();const f=p.frameLocator('.wx-atlas-frame');await f.locator('.map').waitFor();assert.equal(await candle.getAttribute('aria-pressed'),'false','地图目录不自动计时');
  await f.locator('#nav [data-go="materials"]').click();await f.locator('[data-material="m1"]').first().click();await p.waitForFunction(()=>document.querySelector('#todayPill').classList.contains('on'));await p.waitForFunction(()=>!!STUDY_LAMP.token());
  await candle.click();await f.locator('.tabs [data-tab="original"]').click();await p.evaluate(()=>{STUDY_LAMP.sync();updateStudyDot();});assert.equal(await candle.getAttribute('aria-pressed'),'false','当前阅读手动关闭不会被自动检测反复点亮');
  await f.locator('#atlasBack').click();await p.locator('[data-wx-exam="2026-10-guokao"]').click();await f.locator('.map').waitFor();await f.locator('#nav [data-go="materials"]').click();await f.locator('[data-material="m1"]').first().click();await p.waitForFunction(()=>document.querySelector('#todayPill').classList.contains('on'));
  await p.evaluate(()=>go('tianji'));if(await p.locator('#tjBack').count())await p.locator('#tjBack').click();await p.locator('[data-open="month|2026-10-上"]').click();await p.locator('.tj-news-body').waitFor();assert.equal(await candle.getAttribute('aria-pressed'),'true','打开天机台阅读立即点亮');await p.waitForTimeout(1300);assert.equal(await p.evaluate(()=>lampSec),0,'已有自动计时不重复累计蜡烛秒数');await candle.click();await p.waitForTimeout(5200);assert.equal(await candle.getAttribute('aria-pressed'),'false','原自动检测也遵守手动暂停');
  await p.locator('#tjBack').click();await p.locator('[data-open="month|2026-10-上"]').click();await p.locator('.tj-news-body').waitFor();assert.equal(await candle.getAttribute('aria-pressed'),'true','重新打开阅读恢复自动');
  assert.deepEqual(errors,[]);await p.close();console.log(width+'×'+height+'：蜡烛即点即亮/关、计秒凭据、键盘、阅读自动、手动优先、后台与空闲通过');
 }
 console.log('STUDY-LAMP366-OK');
}finally{await browser?.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
