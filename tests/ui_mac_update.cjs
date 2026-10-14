/* Mac 版本与更新入口：三主题隔离库；API模拟新版本，不下载或替换用户程序。 */
const assert=require('node:assert/strict'),{chromium}=require('playwright'),{spawn}=require('node:child_process');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const server=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[])],{env:process.env});
let log='',browser,page;server.stderr.on('data',b=>log+=b);
const ready=new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error(log||'服务未启动')),20000);server.stdout.on('data',b=>{out+=b;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});server.on('exit',()=>{clearTimeout(timer);reject(Error(log||'服务退出'));});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});page=await browser.newPage({viewport:{width:1280,height:860}});page.setDefaultTimeout(7000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let blocked=false,newer=true,applied=0,fail=true;
 const json=(route,data)=>route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 await page.route('**/api/version',r=>json(r,{version:'3.0.7',frozen:true,platform:'darwin'}));
 await page.route('**/api/update/check',r=>json(r,{current:'3.0.7',latest:'9.9.9',newer,frozen:true,windows:false,macos:true,asset_url:'https://example.test/mac.zip',can_apply:!blocked,page:'https://example.test/release',notes:'修复与更新',update_reason:blocked?'请先把 App 移到应用程序，再打开更新':''}));
 await page.route('**/api/update/apply',r=>{assert.equal(r.request().method(),'POST');applied++;return fail?r.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'下载失败；旧应用未改动'})}):json(r,{ok:true,version:'9.9.9'});});
 await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.evaluate(()=>go('settings'));await page.locator('.fx-settings').waitFor();
 await require('./fixed_ui_helpers.cjs').reveal(page,page.locator('#updCheck'));
 assert.match(await page.locator('#updCheck').locator('..').locator('..').innerText(),/Mac App/);
 await page.locator('#updCheck').click();await page.locator('#updApply').waitFor();assert(await page.locator('#updApply').isVisible());
 await page.locator('#updApply').click();await page.waitForFunction(()=>document.getElementById('updApply')&&!document.getElementById('updApply').disabled);assert.equal(applied,1);assert.equal(await page.locator('#updApply').innerText(),'更新并重启');assert(await page.locator('.fx-settings').isVisible(),'失败保留设置页面');
 blocked=true;await page.locator('#updCheck').click();await page.waitForFunction(()=>document.getElementById('updBox').textContent.includes('请先'));assert.equal(await page.locator('#updApply').count(),0);
 blocked=false;newer=false;await page.locator('#updCheck').click();await page.waitForFunction(()=>document.getElementById('updMsg').textContent.includes('已经是最新'));assert.equal(await page.locator('#updApply').count(),0,'再次检查不能残留旧更新按钮');
 newer=true;await page.locator('#updCheck').click();await page.locator('#updApply').waitFor();
 for(const size of [{width:1280,height:860},{width:800,height:1280}]){await page.setViewportSize(size);await page.locator('#updApply').scrollIntoViewIfNeeded();const r=await page.locator('#updApply').boundingBox();assert(r&&r.y>=0&&r.y+r.height<=size.height,'更新按钮在工作区内可达');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2&&document.documentElement.scrollHeight<=innerHeight+2),'固定页面不溢出');}
 fail=false;await page.locator('#updApply').click();await page.waitForFunction(()=>document.body.textContent.includes('马上重新打开'));assert.equal(applied,2);assert.deepEqual(errors,[]);console.log('MAC-UPDATE-UI-OK '+(subject||'法考')+'：Mac按钮、失败重试、目录提示、旧结果清理与电脑/平板边界');
}catch(e){throw e;}finally{await browser?.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
