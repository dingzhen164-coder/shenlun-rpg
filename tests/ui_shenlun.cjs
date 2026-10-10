/* 真题录入、草稿重开、两稿批改和桌面/平板主题验证。仅自编材料及假AI。 */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
async function main(){
 const out=path.resolve('ui-artifacts');fs.mkdirSync(out,{recursive:true});
 const server=spawn(process.env.PYTHON||'python',['tests/ui_shenlun_server.py'],{env:{...process.env,PYTHONIOENCODING:'utf-8'}});
 let logs='',browser;server.stderr.on('data',b=>logs+=b);
 try{
 const base=await new Promise((resolve,reject)=>{let t='';const timeout=setTimeout(()=>reject(Error(logs)),20000);server.stdout.on('data',b=>{t+=b;const m=t.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timeout);resolve(m[1]);}});server.on('exit',code=>{clearTimeout(timeout);reject(Error('server '+code+logs));});});
 browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1280,height:860}});const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.goto(base);await page.locator('#nav [data-view="skeleton"]').click();await page.locator('[data-libtab="bank"]').click();
 await page.locator('#slSourceStart').click();await page.locator('#slSourceStatus').filter({hasText:'录入完成'}).waitFor();await page.locator('#slBankRefresh').click();await page.locator('.sl-paper').first().waitFor();
 await page.locator('.sl-bank-input summary').filter({hasText:'手动录入'}).click();
 await page.locator('#slManualTitle').fill('2026手动自编报告');await page.locator('#slManualRegion').fill('自编');await page.locator('#slManualType').selectOption('贯彻执行');await page.locator('#slManualStem').fill('请写一份社区服务优化报告。（20分）不超过300字。');await page.locator('#slManualMaterial').fill('社区走访居民，收集办事需求。\n部门共享资料，减少重复提交。');await page.locator('#slManualReference').fill('隐藏的机构参考答案');await page.locator('#slManualSave').click();await page.locator('.sl-paper summary').filter({hasText:'2026手动自编报告'}).waitFor();
 async function screenshots(prefix){for(const [name,width,height] of [['desktop',1280,860],['tablet',800,1280]]){await page.setViewportSize({width,height});for(const theme of ['light','dark']){await page.evaluate(t=>{document.documentElement.dataset.theme=t;window.scrollTo(0,0);},theme);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no horizontal overflow');await page.screenshot({path:path.join(out,`sl-${prefix}-${name}-${theme}.png`),fullPage:true});}}await page.setViewportSize({width:1280,height:860});}
 await screenshots('bank');await page.locator('#slFilterRegion').selectOption('自编');await page.locator('.sl-paper summary').first().click();await page.locator('[data-slq]').click();await page.locator('#slAns').waitFor();
 assert.equal(await page.locator('.sl-material-text p').count(),2);assert.equal(await page.locator('.sl-material-text p').first().evaluate(el=>parseFloat(getComputedStyle(el).textIndent)/parseFloat(getComputedStyle(el).fontSize)), 2);
 assert.ok(!(await page.locator('body').textContent()).includes('隐藏的机构参考答案'));
 await page.locator('#slAns').fill('走访居民了解需求。');await page.locator('#slDraftSave').click();await page.locator('#slSaveStatus').filter({hasText:'已保存'}).waitFor();await screenshots('answer');
 await page.locator('#slBack').click();await page.locator('.sl-paper summary').filter({hasText:'2026手动自编报告'}).click();await page.locator('[data-slq]').click();assert.equal(await page.locator('#slAns').inputValue(),'走访居民了解需求。');
 await page.locator('#slSubmit').click();await page.locator('.sl-review-total').filter({hasText:'12/20'}).waitFor();await page.locator('#slSubmit:not([disabled])').waitFor();
 await page.locator('#slAns').fill('走访居民了解需求，推动部门共享资料。');await page.locator('#slSubmit').click();await page.locator('.sl-review-total').filter({hasText:'20/20'}).waitFor();await page.locator('.sl-comparison').filter({hasText:'+8'}).waitFor();await page.locator('#slSubmit:not([disabled])').waitFor();assert.equal(await page.locator('.sl-point-detail[open]').count(),0);await page.locator('.sl-point-detail summary').first().click();assert.ok(await page.locator('.sl-point-detail[open] .sl-ev').first().isVisible());await page.locator('.sl-point-detail summary').first().click();assert.ok((await page.locator('#slRes').textContent()).includes('已由程序核验'));await screenshots('review');
 await page.locator('#slBack').click();await page.locator('.sl-paper summary').filter({hasText:'2026手动自编报告'}).click();await page.locator('[data-slq]').click();await page.locator('summary').filter({hasText:'历史作答与批改（2稿）'}).click();await page.locator('[data-slhistory="0"]').click();await page.locator('.sl-review-total').filter({hasText:'12/20'}).waitFor();
 await page.locator('#slBack').click();await page.locator('#slFilterRegion').selectOption('国考');await page.locator('.sl-paper summary').filter({hasText:'2025自编下载验证卷'}).click();await page.locator('[data-slq]').click();
 assert.ok((await page.locator('.sl-paragraph-note').textContent()).includes('不代表原文段落'));assert.ok(await page.locator('.sl-material-text p').count()>1);
 assert.equal(await page.locator('.sl-material-text').textContent(),'社区走访居民，收集办事需求。部门共享资料，减少重复提交。'+'居民提出新的需求。部门持续改进服务！！'.repeat(25));await screenshots('reading');
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'sl-result.json'),JSON.stringify({passed:true,screenshots:16,checks:['下载入口','手动录入','筛选','隐藏参考答案','草稿保存/重开','首次批改','二稿同标准对比','历史重开','桌面平板明暗']},null,2));console.log('SHENLUN-UI-OK');
 }finally{if(browser)await browser.close();server.kill();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
