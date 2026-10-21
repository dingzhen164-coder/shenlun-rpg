/* 3.3.6真实浏览器回归：任务配置/纸签/单次记时、旧委托、横排记录、全宽书架、一级设置。
   电脑/平板，服务只使用临时自编资料与假HOME，不连接AI。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const service=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),'--layout335-fixture'],{env:process.env});
let logs='',browser,active;service.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let s='';const timer=setTimeout(()=>reject(Error(logs||'服务启动超时')),20000);service.stdout.on('data',x=>{s+=x;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});service.on('exit',c=>{clearTimeout(timer);reject(Error('服务退出 '+c+logs));});});
const out=path.resolve('ui-artifacts/task-board');
async function fit(page){assert.deepEqual(await page.evaluate(()=>{const e=[];if(document.documentElement.scrollHeight>innerHeight+2||document.documentElement.scrollWidth>innerWidth+2||scrollY)e.push('整页滚动');for(const el of document.querySelectorAll('.qb-dialog,.qb-wall,.qb-slip,.qb-settings,.fx-records-list>.card')){const r=el.getBoundingClientRect();if(r.width&&r.height&&r.right>innerWidth+1)e.push('横向越界 '+el.className);}return e;}),[]);}
async function open(page){await page.evaluate(()=>go('home'));await page.locator('[data-portal-go="journal"]').click();await page.waitForSelector('.qb-wall');}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 const sizes=process.argv.find(a=>a.startsWith('--sizes='))?.split('=')[1]?.split(',');
 for(const [label,viewport] of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]].filter(([label])=>!sizes||sizes.includes(label))){
  const page=await browser.newPage({viewport});active=page;const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&!!DASH);await page.evaluate(()=>go('settings'));await page.waitForSelector('.fx-settings-group');
  assert.equal(await page.locator('.fx-settings-group').count(),6);
  await page.locator('.fx-settings-group[data-fx-group="ai"]>summary').click();
  assert(await page.locator('#sModel').isVisible(),'一级标题打开即可输入');assert(await page.locator('#sVModel').isVisible(),'识图模型也无二次折叠');
  await page.locator('#sModel').fill('自编未保存草稿');await page.locator('.fx-settings-group[data-fx-group="ai"]>summary').click();await page.locator('.fx-settings-group[data-fx-group="ai"]>summary').click();assert.equal(await page.locator('#sModel').inputValue(),'自编未保存草稿');
  await page.locator('.fx-settings-group[data-fx-group="learning"]>summary').click();
  await page.locator('#qbDailyTitle').fill('每日方法研习');await page.locator('#qbDailyMinutes').fill('240');
  // 服务在同一尺寸循环中持续运行；每次仅保留一项自编任务，不碰真实资料。
  await page.locator('[data-qb-remove]').evaluateAll(es=>es.forEach(e=>e.click()));await page.locator('#qbAddTask').click();
  await page.locator('.qb-setting-row [name="title"]').fill('自编条件与边界');await page.locator('.qb-setting-row [name="minutes"]').fill('20');
  await page.locator('#qbSave').click();await page.locator('#qbSettingStatus').filter({hasText:'已保存'}).waitFor();
  await page.reload();await page.evaluate(()=>go('settings'));await page.waitForSelector('.fx-settings-group');await page.locator('.fx-settings-group[data-fx-group="learning"]>summary').click();assert.equal(await page.locator('#qbDailyMinutes').inputValue(),'240');assert.equal(await page.locator('.qb-setting-row [name="title"]').inputValue(),'自编条件与边界');
  await open(page);assert.equal(await page.locator('.qb-main-grid .qb-slip').count(),2);assert.match(await page.locator('.qb-main-grid').textContent(),/每日方法研习/);assert.equal(await page.locator('.qb-side-grid .qb-slip').count(),1);
  const before=await page.evaluate(()=>api('/api/task-board'));
  await page.locator('[data-qb-record]').click();await page.locator('.qb-record-form [name="minutes"]').fill('20');await page.locator('.qb-record-form [name="note"]').fill('自编内容记录');await page.locator('.qb-record-form button[type="submit"]').click();await page.waitForSelector('.qb-side-grid .qb-slip[data-complete="true"]');
  const after=await page.evaluate(()=>api('/api/task-board'));assert.equal(after.daily_current-before.daily_current,20);assert.equal(after.tasks[0].current,20);await fit(page);
  await page.locator('.qb-archive>summary').click();assert(await page.locator('.journey-panel').isVisible(),'旧委托与收藏保留');
  await page.locator('.qb-archive>summary').click();
  await page.locator('.qb-scroll').evaluate(e=>e.scrollTop=0);
  if(process.argv.includes('--shots')){fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,`board-${subject||'法考'}-${label}.png`)});}
  await page.evaluate(()=>document.documentElement.dataset.theme='dark');await fit(page);await page.evaluate(()=>document.documentElement.dataset.theme='light');
  await page.locator('[data-qb-settings]').click();await page.waitForSelector('.fx-settings-group[data-fx-group="learning"][open]');assert(await page.locator('#qbDailyMinutes').isVisible(),'任务板可直达任务设置');
  await page.evaluate(()=>go('dwelling'));await page.waitForSelector('.fx-tabs');
  const records=page.locator('.fx-tab').filter({hasText:/修行记录|学习记录/});await records.click();
  const boxes=await page.locator('.fx-records-list>.card').evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width};}));assert.equal(boxes.length,3);assert(boxes.every(b=>Math.abs(b.y-boxes[0].y)<2),'三张录入横向同排');assert(boxes[0].x<boxes[1].x&&boxes[1].x<boxes[2].x);await fit(page);
  await page.locator('.fx-records-list .form-fold').evaluateAll(es=>es.forEach(e=>e.open=true));
  assert(await page.locator('.fx-records-list>.card').evaluateAll(es=>es.every(e=>e.scrollWidth<=e.clientWidth+2)),'三栏录入表单展开后不横向溢出');
  await page.locator('#lecMin').fill('35');assert.equal(await page.locator('#lecMin').inputValue(),'35');
  if(subject==='行测'){
   await page.evaluate(()=>go('tianji'));await page.waitForSelector('.tj-hub');const widths=await page.evaluate(()=>[document.querySelector('.tj-hub').clientWidth,document.querySelector('#view').clientWidth]);assert(widths[0]>=widths[1]-4,'天机台全宽');
  }
  await page.evaluate(()=>{STUDY_REGIONS.select('');return go('train');});await page.locator(subject==='行测'?'[data-study-region="yan"]':'[data-study-region]').first().click();await page.waitForSelector('.fx-region-work');assert.equal(await page.locator('.yj-empty,.yj-moved,[data-yjgear],.ln-slot').count(),0,'空分区没有制作提示和空导图');await fit(page);
  assert.deepEqual(errors,[]);await page.close();console.log((subject||'法考')+' '+label+'：任务签、保存重启、单次累计、旧委托、横排/全宽/一级设置通过');
 }
}catch(e){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure-'+(subject||'法考')+'.png')}).catch(()=>{});}throw e;}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exit(1);});
