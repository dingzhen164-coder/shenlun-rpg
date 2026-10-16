/* 3.0.6合并模块与手动领取的真实交互；临时库、自编成绩、无真实AI。 */
const {chromium}=require('playwright');
const {spawn}=require('child_process'),assert=require('assert'),fs=require('fs');
const requested=process.argv.find(x=>x.startsWith('--subject='))?.split('=')[1];
const root=require('path').resolve(__dirname,'..'), out=process.env.UI_ARTIFACT_DIR||root+'/ui-artifacts/grouped-306';fs.mkdirSync(out,{recursive:true});
const reveal=require('./fixed_ui_helpers.cjs').reveal;
(async()=>{const browser=await chromium.launch({...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});let count=0;
try{for(const subject of requested?[requested]:['行测','申论']){
const repo='shenlun-rpg';
const server=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),'--merge-fixture'],{cwd:root});let log='';server.stderr.on('data',b=>log+=b);
try{const url=await new Promise((resolve,reject)=>{let s='';server.stdout.on('data',b=>{s+=b;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m)resolve(m[1]);});server.on('exit',()=>reject(Error(log)));});
const page=await browser.newPage({viewport:{width:1280,height:860}}),errors=[];page.setDefaultTimeout(6000);page.on('pageerror',e=>errors.push(e.message));
await page.goto(url);await page.waitForFunction(()=>!!window.DASH_REF?.());
const route=async v=>{await page.evaluate(v=>go(v),v);await page.waitForTimeout(300);};
await route('dwelling');await page.waitForFunction(()=>!!document.querySelector('[data-fx-group="growth"]'));
assert.equal(await page.locator('.narrative-dwelling,.xc-guide-scene,.npc.greet').count(),0);
assert.equal(await page.locator('#view .fx-shell > .fx-panels > .fx-panel').count(),subject==='行测'?5:3);   // 行测洞府3.1.3：修为与突破/十二经/修行记录/储物袋/修行日志
const before=await page.evaluate(()=>DASH.xp),reward=await page.evaluate(()=>DASH.mock_rewards.find(r=>r.status==='pending').preview.amount);
const claim=page.locator('[data-mock-reward]').first();await reveal(page,claim);await claim.click();
await page.waitForFunction(x=>DASH.xp===x,before+reward);
await page.reload();await page.waitForFunction(()=>!!window.DASH_REF?.());assert.equal(await page.evaluate(()=>DASH.xp),before+reward);
await route('dwelling');await page.screenshot({path:out+'/'+(subject||'法考')+'-成长.png'});
for(const id of ['#lecMin','#prMin','#ssMin']){const field=page.locator(id);await reveal(page,field);await field.evaluate(el=>{for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});await field.fill('7',{timeout:2500});assert.equal(await field.inputValue(),'7');}
await reveal(page,page.locator('#lecMin'));await page.locator('#lecGo').click();await page.waitForFunction(()=>DASH.lectures.some(x=>x.minutes===7));await page.locator('.st-btn').click();await page.locator('.settle').waitFor({state:'detached'});
await route('contest');await page.waitForTimeout(300);
if(subject!=='申论'){
 const charts=page.locator('[data-cs-pane="trends"]');assert.equal(await charts.count(),1);assert.equal(await charts.locator(':scope>.card').count(),2);
 for(const id of ['#chScore','#chAcc','#mkPick']){const field=page.locator(id);await reveal(page,field);assert(await field.isVisible());}
 assert.equal(await page.locator('[data-cs-pane="entry"] #mkMarksCard').count(),1);assert.equal(await page.locator('[data-cs-pane="entry"] #mkForm').count(),1);
 await reveal(page,page.locator('#mkMarksCard'));await page.screenshot({path:out+'/'+(subject||'法考')+'-成绩录入.png'});
}
await route('settings');assert.equal(await page.locator('#view .fx-shell > .fx-panels > .fx-panel').count(),1);
assert.equal(await page.locator('.fx-settings .fx-tabs').count(),0);
for(const selector of ['[data-shortcut-save]','[data-portal-save]','#sSave']){const b=page.locator(selector);await reveal(page,b);assert(await b.isVisible());if(selector!=='#sSave'){await b.click();await page.waitForTimeout(300);}}
await reveal(page,page.locator('[data-portal-save]'));await page.screenshot({path:out+'/'+(subject||'法考')+'-设置.png'});
for(const size of [{width:800,height:1280}]){
 await page.setViewportSize(size);
 for(const v of ['dwelling','contest','settings','log','bank','skeleton']){await route(v);assert(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight+2));count++;}
}
assert.deepEqual(errors,[]);await page.close();console.log((subject||'法考')+'：领取持久化、合并标签、表单可达与两尺寸固定窗口通过');
}finally{server.kill();}}
console.log('3.0.6浏览器交互通过，尺寸页面检查 '+count+' 项');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
