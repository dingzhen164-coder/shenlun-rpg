/* 3.8.0整卷模拟考试真实HTTP回归：假HOME、自编130题、导入拆分用自编数据，不连AI；电脑/平板横竖屏。
   覆盖：塔前左门进入考场、导入试卷/答案、倒计时、答题卡跳题与交卷确认、暂存续考、时间到、交卷结果、大比按试卷名显示。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_exam_server.py'],{env:process.env});
let logs='',browser,active;service.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error(logs||'考试服务未启动')),20000);service.stdout.on('data',x=>{text+=x;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});service.on('exit',c=>{clearTimeout(timer);reject(Error(logs||'服务退出 '+c));});});
const out=path.resolve('ui-artifacts/exam-room');
const NAME='花生26下模拟卷第一套',NAME2='花生26下模拟卷第二套';
async function fits(page,selector){
 const bad=await page.evaluate(sel=>{const e=document.querySelector(sel),r=e.getBoundingClientRect(),b=[];
  if(r.left<-1||r.right>innerWidth+1||r.top<-1||r.bottom>innerHeight+1)b.push('越界 '+sel);
  if(e.scrollWidth>e.clientWidth+2)b.push('横向溢出 '+sel);
  if(document.documentElement.scrollWidth>innerWidth+2)b.push('整页横向溢出');
  for(const x of e.querySelectorAll('button:not(.er-cell)')){const q=x.getBoundingClientRect();if(q.width&&q.height&&(q.right>innerWidth+1||q.bottom>innerHeight+1||q.left<-1))b.push('按钮越界 '+x.textContent.trim().slice(0,8));}
  return b;},selector);
 assert.deepEqual(bad,[]);
}
async function openRoom(page){
 await page.evaluate(()=>go('bank'));await page.locator('.trial-hall').waitFor();
 if(await page.locator('dialog[open]').count())await page.keyboard.press('Escape');
 await page.locator('[data-th-enter=exam]').click();await page.locator('.er-paper').first().waitFor();
}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 const pdf=path.join(os.tmpdir(),'exam-ui-fake.pdf');fs.writeFileSync(pdf,'%PDF-1.4\n% fake\n');
 for(const [label,viewport,fresh]of [['desktop',{width:1280,height:860},true],['tablet',{width:800,height:1280},false],['tablet-landscape',{width:1280,height:800},false]]){
  const page=await browser.newPage({viewport,deviceScaleFactor:1});active=page;page.setDefaultTimeout(10000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.clock.install({time:new Date('2026-10-25T09:00:00')});
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());
  await page.evaluate(()=>go('bank'));await page.locator('.trial-hall').waitFor();
  // 左门改为整卷模考，右门仍是板块；旧“套卷”入口不再出现
  assert.equal(await page.locator('[data-th-enter=sets]').count(),0);assert.equal(await page.locator('[data-th-enter=exam]').count(),1);
  assert((await page.locator('.th-painted-sets,.th-gate-sets').first().textContent()).includes('整卷'));
  await openRoom(page);
  assert((await page.locator('#th-dialog-title').textContent()).includes('整卷'));
  assert((await page.locator('.er-intro').textContent()).includes('120'));
  assert(await page.locator('.er-paper',{hasText:NAME}).count()>=1);
  await fits(page,'.th-dialog[open]');
  const shot=async n=>{if(process.argv.includes('--shots')){fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,label+'-'+n+'.png')});}};await shot('home');
  if(fresh){
   // 导入试卷（拆分用自编数据代替）：要有名字和文件
   await page.locator('.er-import summary').click();
   await page.locator('[data-er-import-form] [type=submit]').click();assert((await page.locator('[data-er-import-note]').textContent()).includes('名字'));
   await page.locator('[data-er-name]').fill(NAME2);await page.locator('[data-er-pdf]').setInputFiles(pdf);
   await page.locator('[data-er-import-form] [type=submit]').click();
   await page.locator('[data-er-season="1002"]').waitFor();assert((await page.locator('.er-ok').textContent()).includes(NAME2));
   assert((await page.locator('[data-er-season="1002"]').textContent()).includes('答案 128/130'));
   // 导入答案：补上缺的两题
   await page.locator('[data-er-answers="1002"]').click();
   await page.locator('[data-er-season="1002"] [data-er-answer-text]').fill('5.B 6.C');
   await page.locator('[data-er-season="1002"] [data-er-answer-form] [type=submit]').click();
   await page.locator('[data-er-season="1002"]:has-text("答案齐全")').waitFor();
  }
  // 开始考试：全屏，倒计时从120分钟起，答题卡在右上角
  await page.locator('[data-er-start="1001"]').click();await page.locator('dialog.er-run[open]').waitFor();
  assert.match(await page.locator('[data-er-clock]').textContent(),/^1(19|20):\d\d$/);
  assert((await page.locator('[data-er-pos]').textContent()).includes('第 1/130 题'));
  const bar=await page.evaluate(()=>{const c=document.querySelector('[data-er-card]').getBoundingClientRect();return {right:innerWidth-c.right,top:c.top};});assert(bar.right<40&&bar.top<20,'答题卡按钮在右上角');
  await fits(page,'dialog.er-run');await shot('run');
  await page.locator('[data-er-choice=A]').click();assert.equal(await page.locator('[data-er-choice=A]').getAttribute('aria-pressed'),'true');
  await page.keyboard.press('B');assert.equal(await page.locator('[data-er-choice=B]').getAttribute('aria-pressed'),'true');assert.equal(await page.locator('[data-er-choice=A]').getAttribute('aria-pressed'),'false');
  await page.keyboard.press('ArrowRight');assert((await page.locator('[data-er-pos]').textContent()).includes('第 2/130 题'));
  await page.keyboard.press('C');await page.locator('[data-er-mark]').click();assert.equal(await page.locator('[data-er-mark]').getAttribute('aria-pressed'),'true');
  // 答题卡：按模块分组，点号码跳题
  await page.locator('[data-er-card]').click();await page.locator('.er-sheet').waitFor();
  const groups=await page.locator('.er-group h4').allTextContents();assert.equal(groups.length,6);assert(groups[0].includes('政治理论')&&groups[0].includes('1–20'));assert(groups[2].includes('言语理解与表达')&&groups[2].includes('36–65'));
  assert(await page.locator('[data-er-jump="1"]').evaluate(e=>e.classList.contains('done')));assert(await page.locator('[data-er-jump="2"]').evaluate(e=>e.classList.contains('mark')));
  await fits(page,'.er-sheet-panel');await shot('sheet');
  await page.locator('[data-er-jump="66"]').click();await page.locator('.er-sheet').waitFor({state:'hidden'});assert((await page.locator('[data-er-pos]').textContent()).includes('第 66/130 题'));
  // 暂存离开 → 列表显示进行中 → 继续时答案、位置还在
  await page.locator('[data-er-leave]').click();await page.locator('dialog.er-run').waitFor({state:'detached'});
  await page.locator('[data-er-season="1001"]:has-text("进行中")').waitFor();assert((await page.locator('[data-er-season="1001"]').textContent()).includes('已答 2 题'));
  await page.locator('[data-er-start="1001"]').click();await page.locator('dialog.er-run[open]').waitFor();
  assert((await page.locator('[data-er-pos]').textContent()).includes('第 3/130 题'),'回到第一道没答的题');
  await page.locator('[data-er-card]').click();assert(await page.locator('[data-er-jump="2"]').evaluate(e=>e.classList.contains('done')&&e.classList.contains('mark')));await page.locator('[data-er-sheet-close]').click();
  // 时间到：显示提示，可继续作答，倒计时变“超时”
  await page.clock.fastForward(7200*1000+5000);await page.locator('[data-er-timeup]').waitFor({state:'visible'});
  assert.match(await page.locator('[data-er-clock]').textContent(),/^超时 \+\d\d:\d\d$/);
  // 交卷：先点一次出现未答确认，选“继续答题”可退回，再确认交卷
  await page.locator('[data-er-card]').click();
  await page.locator('[data-er-submit]').click();assert((await page.locator('[data-er-confirm]').textContent()).includes('还有'));
  await page.locator('[data-er-continue]').click();assert.equal(await page.locator('[data-er-confirm]').isHidden(),true);
  await page.locator('[data-er-submit]').click();await page.locator('[data-er-submit]').click();
  await page.locator('.er-score-num').waitFor();
  const score=Number(await page.locator('.er-score-num').textContent());assert(Number.isFinite(score)&&score>=0);
  assert((await page.locator('.er-meta').textContent()).includes(NAME));assert((await page.locator('.er-meta').textContent()).includes('超时'));
  assert.equal(await page.locator('.er-table tbody tr').count(),6);
  await fits(page,'dialog.er-run');
  if(process.argv.includes('--shots')){fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,label+'-result.png')});}
  // 结果进了宗门大比，用的是试卷名而不是“第N季”
  await page.locator('[data-er-contest]').click();await page.waitForFunction(()=>VIEW==='contest');
  await page.locator('#chScore').waitFor({state:'attached'});assert.equal(await page.locator('dialog[open]').count(),0,'去大比后试炼塔面板已关');
  assert((await page.locator('#chScore .cx').allTextContents()).join('').includes(NAME),'走势图横轴标的是试卷名');
  assert(!(await page.locator('#chScore .legend').textContent()).includes('平均'),'走势图没有大比平均分/最高分线');
  assert(await page.locator('.mk-table').first().textContent().then(t=>t.includes(NAME)&&!t.includes('已击败')));
  assert.equal(errors.length,0,errors.join('\n'));
  if(process.argv.includes('--shots')){await page.screenshot({path:path.join(out,label+'-contest.png')});}
  await page.close();console.log(label+'：整卷模考入口、导入、答题卡、暂存续考、超时、交卷与大比记录');
 }
 await browser.close();service.kill();
}catch(error){console.error(error);if(active&&process.argv.includes('--shots')){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'fail.png')}).catch(()=>{});}await browser?.close().catch(()=>{});service.kill();process.exit(1);}})();
