/* 试炼塔（2026-11-11 用户反馈）：①题都答完在复盘时离开页面 = 结束复盘，再点试炼塔看到的是主页；
   ②电脑和平板同时开着同一组复盘，一台结束后另一台再点按钮只提示一次并回试炼塔主页，不再一直报“本组已经结束”。自编题、隔离临时库。 */
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
// 每个尺寸一个新的临时库（三道题做完就没有新题了）
function serve(){const service=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','行测','--bank-leave-fixture'],{env:process.env});let logs='';service.stderr.on('data',b=>logs+=b);
 return new Promise((ok,no)=>{let o='';const t=setTimeout(()=>no(Error(logs)),20000);service.stdout.on('data',b=>{o+=b;const m=o.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok({base:m[1],service});}});service.on('exit',()=>{clearTimeout(t);no(Error(logs));});});}
const TASK={type:'bank',board:'论证逻辑',title:'实战',target:'论证逻辑'},AGAIN={type:'bank_review',board:'论证逻辑',title:'错题复练',target:'论证逻辑'};
async function open(browser,base,viewport){const page=await browser.newPage({viewport,hasTouch:true});page.errors=[];page.on('pageerror',e=>page.errors.push(String(e)));await page.goto(base);await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&DASH);return page;}
async function start(page,task=TASK){await page.evaluate(t=>startTask({task:t}),task);await page.waitForSelector('[data-act^="exam_pick:"], [data-act="exam_close"]');}
async function finish(page){for(let i=0;i<3;i++){await page.locator(`[data-act="exam_pick:${i}:B"]`).click();await page.waitForFunction(i=>!document.querySelector(`[data-act="exam_pick:${i}:B"]`)||document.querySelector(`[data-act="exam_pick:${i}:B"]`).textContent.includes('✓'),i);}
 await page.locator('[data-act="exam_submit"]').click();await page.waitForSelector('[data-act="exam_close"]');}
// 从真实触屏事件开始验证，覆盖浏览器的纵向滚动仲裁。
async function swipe(page, dx, dy) {
 await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
 const cdp = await page.context().newCDPSession(page);
 try {
  const target = page.locator('.q-pin .q-text').first();
  await target.waitFor();
  const box = await target.boundingBox();
  assert.equal(await target.evaluate((el, b) => el.contains(document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2)), box), true);
  const x = Math.round(box.x + box.width / 2), y = Math.round(box.y + box.height / 2);
  await cdp.send('Input.dispatchTouchEvent', {type:'touchStart', touchPoints:[{x, y}]});
  for (let i = 1; i <= 4; i++) {
   await cdp.send('Input.dispatchTouchEvent', {type:'touchMove', touchPoints:[{x:x+dx*i/4, y:y+dy*i/4}]});
  }
  await cdp.send('Input.dispatchTouchEvent', {type:'touchEnd', touchPoints:[]});
 } finally { await cdp.detach(); }
}
const runs=page=>page.evaluate(()=>fetch('/api/bank').then(r=>r.json()).then(d=>d.active_runs.length));
(async()=>{let browser,service;try{
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,viewport] of [['desktop',{width:1280,height:860}],['portrait',{width:800,height:1280}],['landscape',{width:1280,height:800}]]){
  const srv=await serve(),base=srv.base;service=srv.service;
  // ① 复盘时离开 → 自动结束复盘
  const page=await open(browser,base,viewport);
  await start(page);
  if (label === 'desktop') {
   let release, received;
   const gate = new Promise(resolve => release = resolve);
   const arrival = new Promise(resolve => received = resolve);
   const delay = async route => { received(); await gate; await route.continue(); };
   await page.route('**/api/session/action', delay, {times:1});
   try {
    await page.locator('[data-act="exam_pick:0:B"]').click();
    await arrival;
    await page.locator('[data-act="exam_pick:1:A"]').waitFor({timeout:1000});
    await page.locator('[data-act="exam_prev"]').click();
    assert.equal(await page.locator('[data-act="exam_pick:0:B"]').textContent(), '✓ B');
    await page.locator('[data-act="exam_pick:0:C"]').click();
    await page.locator('[data-act="exam_next"]').click();
    await page.locator('[data-act="bank_pause"]').click();
   } finally { release(); }
   await page.waitForFunction(() => T.finished);
   await page.locator('.settle').waitFor();
   await page.evaluate(() => SETTLE.close());
   await start(page);
   await page.locator('[data-act="exam_pick:2:A"]').waitFor();
   await page.locator('[data-act="exam_prev"]').click();
   await page.locator('[data-act="exam_pick:1:A"]').waitFor();
   await page.locator('[data-act="exam_prev"]').click();
   assert.equal(await page.locator('[data-act="exam_pick:0:C"]').textContent(), '✓ C');
  }
  if (label === 'portrait') {
   await swipe(page, -120, 4);
   await page.locator('[data-act="exam_pick:1:A"]').waitFor({timeout:3000});
   await swipe(page, 4, 80);
   assert.equal(await page.locator('[data-act="exam_pick:1:A"]').count(), 1, '纵向滑动不翻题');
   await page.locator('.q-pin .q-text').first().evaluate(el => {
    const range = document.createRange();
    range.selectNodeContents(el);
    window.getSelection().addRange(range);
   });
   await swipe(page, -120, 4);
   assert.equal(await page.locator('[data-act="exam_pick:1:A"]').count(), 1, '文字选区内的手势不翻题');
   await page.evaluate(() => window.getSelection().removeAllRanges());
   await swipe(page, 120, 4);
   await page.locator('[data-act="exam_pick:0:A"]').waitFor({timeout:3000});
  }
  await finish(page);assert.equal(await runs(page),1,'复盘中这组还在');
  if (label === 'desktop') {
   let release;
   const gate = new Promise(resolve => release = resolve);
   await page.route('**/api/session/action', async route => { await gate; await route.continue(); }, {times:1});
   try {
    await page.locator('[data-act="exam_rwrong"]').click();
    await page.waitForFunction(() => document.querySelector('.q-pin-head')?.textContent.includes('复盘 第 2/3 题'), null, {timeout:1000});
    await page.locator('[data-act="exam_rnext"]').click();
    await page.waitForFunction(() => document.querySelector('.q-pin-head')?.textContent.includes('复盘 第 3/3 题'), null, {timeout:1000});
    await page.locator('[data-act="exam_rprev"]').click();
    await page.waitForFunction(() => document.querySelector('.q-pin-head')?.textContent.includes('复盘 第 2/3 题'), null, {timeout:1000});
    await page.evaluate(() => go('home'));
   } finally { release(); }
  }
  if (label === 'portrait') {
   await swipe(page, -120, 4);
   await page.locator('[data-act="exam_rprev"]').waitFor({timeout:3000});
   await swipe(page, 120, 4);
   await page.waitForFunction(() => !T.busy && document.querySelector('.q-pin-head')?.textContent.includes('复盘 第 1/3 题'));
  }
  await page.evaluate(()=>go('home'));await page.waitForFunction(()=>fetch('/api/bank').then(r=>r.json()).then(d=>d.active_runs.length===0));
  await page.evaluate(()=>go('bank'));await page.locator('.trial-hall').waitFor();
  assert.equal(await page.locator('[data-act="exam_close"]').count(),0,'再进试炼塔看到主页，不是这组复盘');
  assert.equal(await page.evaluate(()=>T.session),null);
  // 答题中途离开 → 保留，回来接着答（题都做过了，用错题复练再开一组）
  await start(page,AGAIN);await page.locator('[data-act="exam_pick:0:A"]').click();await page.waitForSelector('[data-act^="exam_pick:1:"]');
  await page.evaluate(()=>go('home'));await page.waitForTimeout(300);await page.evaluate(()=>go('bank'));
  await page.waitForSelector('[data-act^="exam_pick:1:"]');assert.equal(await runs(page),1,'答题中离开保留进度');
  // ② 两台设备：平板接上同一组，交卷进复盘；平板结束复盘后电脑再点
  const tablet=await open(browser,base,{width:800,height:1280});
  await start(tablet,AGAIN);await tablet.waitForSelector('[data-act^="exam_pick:1:"]');
  for(const i of [1,2]){await tablet.locator(`[data-act="exam_pick:${i}:A"]`).click();await tablet.waitForTimeout(200);}
  await tablet.locator('[data-act="exam_submit"]').click();await tablet.waitForSelector('[data-act="exam_close"]');
  await page.locator('[data-act^="exam_pick:1:"]').first().click();      // 电脑上点旧题：接上最新进度（已在复盘）
  await page.waitForSelector('[data-act="exam_close"]');
  await tablet.locator('[data-act="exam_close"]').click();await tablet.waitForFunction(()=>T.finished);
  await page.locator('[data-act="exam_rnext"]').click();
  await page.waitForFunction(()=>!T.session);
  await page.locator('.trial-hall').waitFor();
  assert.match(await page.locator('#toast, .toast').last().textContent(),/另一台设备/,'只提示一次');
  assert.equal(await page.locator('.msgs .sys').filter({hasText:'本组已经结束'}).count(),0,'不再堆报错');
  assert.equal(await page.locator('[data-act="exam_close"]').count(),0,'回到试炼塔主页');
  assert.deepEqual(page.errors,[]);assert.deepEqual(tablet.errors,[]);await page.close();await tablet.close();
  console.log(`试炼塔复盘离开/两台设备 ${label}：通过`);service.kill();service=null;
 }
}finally{await browser?.close();service?.kill();}})().catch(e=>{console.error(e);process.exit(1);});
