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
   // 拆分失败的原因要显示在考场面板里（模态面板盖住页面toast，之前用户只看到“上传并拆分中”然后什么都没有）
   await page.locator('[data-er-name]').fill('拆分失败测试');await page.locator('[data-er-pdf]').setInputFiles(pdf);await page.locator('[data-er-import-form] [type=submit]').click();
   const failure=page.locator('[data-er-error]');await failure.waitFor({state:'visible'});const said=await failure.innerText();assert(said.includes('导入「拆分失败测试」失败')&&said.includes('共解析0题'),said);
   assert.equal(await page.locator('[data-er-import-note]').innerText(),'','失败后“拆分中”提示要消失');
   // 文件选择框的cancel事件会冒泡到<dialog>，过去会把整个试炼面板关掉：重新选一次文件，面板必须还开着
   await page.locator('[data-er-pdf]').setInputFiles(pdf);assert.equal(await page.locator('.th-dialog[open]').count(),1,'重新选文件不能关掉面板');
   const inside=await failure.evaluate(e=>{const d=e.closest('dialog'),r=e.getBoundingClientRect(),t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return !!d&&d.contains(t)});assert(inside,'错误提示没有被别的层盖住');
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
  // 草稿笔：考场头部有按钮；画布挂在考场弹窗里（不被顶层弹窗盖住），能画、按题存；Esc 只收笔不离开考场；换题后回来笔迹还在
  await page.locator('[data-er-pen]').click();await page.locator('.draw-layer.on').waitFor();
  assert(await page.evaluate(()=>document.querySelector('dialog.er-run').contains(document.querySelector('.draw-layer'))),'画布应在考场弹窗内');
  assert.equal(await page.evaluate(()=>{const c=document.querySelector('.draw-layer canvas').getBoundingClientRect();return Math.round(c.width)===innerWidth&&Math.round(c.height)===innerHeight;}),true,'画布铺满屏幕');
  await page.mouse.move(300,300);await page.mouse.down();await page.mouse.move(420,380,{steps:8});await page.mouse.up();
  assert(await page.evaluate(()=>!!localStorage.getItem('xrpg-draw:exam:1001:q1')),'第1题的笔迹已存');
  await shot('pen');
  await page.keyboard.press('Escape');await page.locator('.draw-layer.on').waitFor({state:'detached'}).catch(()=>{});
  assert.equal(await page.locator('.draw-layer.on').count(),0,'Esc 收笔');
  assert.equal(await page.locator('dialog.er-run[open]').count(),1,'Esc 只收笔，不能离开考场');
  assert(await page.locator('[data-er-pen].has').count()===1,'有笔迹的题，✏ 带小点');
  await page.locator('[data-er-next]').click();assert.equal(await page.locator('[data-er-pen].has').count(),0,'第2题没有笔迹');
  await page.locator('[data-er-prev]').click();assert.equal(await page.locator('[data-er-pen].has').count(),1,'回到第1题，笔迹还在');
  await fits(page,'dialog.er-run');
  // 点击时钟暂停，休息期间倒计时冻结、快捷键不作答；刷新后仍在休息。
  const remaining=await page.locator('[data-er-clock]').textContent();
  const pausedSave=page.waitForResponse(r=>r.url().endsWith('/api/exam/save')&&r.request().postDataJSON()?.paused===true);
  await page.locator('[data-er-clock]').click();await page.locator('[data-er-resume]').waitFor();await pausedSave;
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await fits(page,'.er-rest-card');}
  await page.evaluate(()=>document.documentElement.dataset.theme='light');await shot('rest');await page.clock.fastForward(125000);
  assert.equal(await page.locator('[data-er-clock]').textContent(),remaining);
  await page.keyboard.press('A');assert.equal(await page.locator('[data-er-choice=A]').getAttribute('aria-pressed'),'false');
  if(fresh){await page.reload();await page.waitForFunction(()=>!!window.DASH_REF?.());await openRoom(page);await page.locator('[data-er-start="1001"]').click();await page.locator('[data-er-resume]').waitFor();assert.equal(await page.locator('[data-er-clock]').textContent(),remaining);}
  await page.locator('[data-er-resume]').click();await page.locator('[data-er-rest]').waitFor({state:'hidden'});
  await page.clock.fastForward(3000);assert.notEqual(await page.locator('[data-er-clock]').textContent(),remaining);

  // 文字题旁边的“对照原图”：默认收起，点开显示原图，再点收起
  assert.equal(await page.locator('[data-er-original]').isHidden(),true);
  await page.locator('[data-er-orig]').click();assert.equal(await page.locator('[data-er-original] img').isVisible(),true);
  await page.locator('[data-er-orig]').click();assert.equal(await page.locator('[data-er-original]').isHidden(),true);
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
