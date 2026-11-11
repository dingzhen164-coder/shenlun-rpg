/* 申论实操训练中心（2026-11-11 用户需求）：
   ①左侧材料放大镜按钮：字号变大后正文在栏宽里重新换行（不左右拖），勾画按字号分开存，默认字号的勾画不受影响；
   ②右栏只有红格（无打字框/识别按钮），红格高度占满右栏，交卷时识别并弹窗核对，“返回修改”不交卷；
   ③已领取目录“移出”要点两次，移出后题目回到题库，草稿保留，重新领取接着用。电脑与平板横竖屏，自编材料、假AI。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
// 每个尺寸一个新的临时库（第一轮写过、移出过，状态会带到下一轮）
function serve(){const server=spawn(process.env.PYTHON||'python3',['tests/ui_shenlun_layout_server.py'],{env:{...process.env,PYTHONIOENCODING:'utf-8'}});let logs='';server.stderr.on('data',b=>logs+=b);
 return new Promise((ok,no)=>{let t='';const timer=setTimeout(()=>no(Error(logs)),20000);server.stdout.on('data',b=>{t+=b;const m=t.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok({base:m[1],server});}});server.on('exit',c=>{clearTimeout(timer);no(Error('exit '+c+logs));});});}
const pixels=(page,sel)=>page.locator(sel).first().evaluate(el=>{const d=el.getContext('2d').getImageData(0,0,el.width,el.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i])n++;return n;});
(async()=>{let browser,server,page;const errors=[];try{
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [size,width,height] of [['desktop',1280,860],['portrait',800,1280],['landscape',1280,800]]){
  const srv=await serve(),base=srv.base,first=true;server=srv.server;
  // 测试辅助（fixed_ui_helpers）绑定第一张页面，所以三种尺寸共用一张页面，各连各的新临时库
  if(!page){page=await browser.newPage({viewport:{width,height},hasTouch:true});require('./fixed_ui_helpers.cjs').install(page);page.on('pageerror',e=>errors.push(e.message));}
  await page.setViewportSize({width,height});errors.length=0;
  await page.goto(base);await page.evaluate(()=>go('skeleton'));await page.locator('[data-libtab="bank"]').click();await page.locator('#slBankRefresh').click();
  await page.locator('#slFilterRegion').selectOption('验证专用');
  const open=async()=>{await page.locator('.sl-paper summary').filter({hasText:'2026版面验证自编卷'}).click().catch(()=>{});await page.locator('.sl-paper-q').nth(0).locator('[data-slq]').click();await page.locator('.sl-card-ink').waitFor();await page.waitForFunction(()=>document.querySelector('.sl-material-ink')?.width===800&&document.querySelector('.sl-material-ink').height>0);};
  await open();
  // ② 右栏只有红格
  assert.equal(await page.locator('#slAns,#slRecognize,.sl-transcription').count(),0,'没有打字框和识别按钮');
  const fill=await page.evaluate(()=>{const v=document.querySelector('.sl-card-viewport').getBoundingClientRect(),w=document.querySelector('.sl-writing').getBoundingClientRect(),p=document.querySelector('.sl-card-paper').getBoundingClientRect();return {share:v.height/w.height,paperBottom:p.bottom,vpBottom:v.bottom,vpTop:v.top};});
  assert(fill.share>0.7,'红格区占右栏七成以上 '+fill.share.toFixed(2));
  assert(fill.paperBottom<=fill.vpBottom+2&&fill.paperBottom>fill.vpBottom-80,'空白卡一页正好排满右栏高度');
  // ① 材料字号
  const lines=()=>page.locator('.sl-material-text p').first().evaluate(p=>Math.round(p.getBoundingClientRect().height/parseFloat(getComputedStyle(p).lineHeight)/ (p.getBoundingClientRect().height/p.offsetHeight)));
  const before={lines:await lines(),fs:await page.locator('.sl-material-text p').first().evaluate(p=>parseFloat(getComputedStyle(p).fontSize))};
  if(first){ // 默认字号下先画一笔
   await page.locator('[data-mark="pen"]').click();const mb=await page.locator('.sl-material-ink').first().boundingBox();
   await page.mouse.move(mb.x+mb.width*.2,mb.y+30);await page.mouse.down();await page.mouse.move(mb.x+mb.width*.5,mb.y+40,{steps:8});await page.mouse.up();await page.locator('[data-mark="read"]').click();
   await page.locator('#slDraftSave').click();await page.locator('#slSaveStatus').filter({hasText:'已保存'}).waitFor();
  }
  const base100=await pixels(page,'.sl-material-ink');assert(base100>0,'默认字号下的勾画');
  await page.locator('[data-sl-mfs="10"]').click();await page.locator('[data-sl-mfs="10"]').click();
  await page.locator('.sl-material-size output').filter({hasText:'120%'}).waitFor();
  await page.waitForFunction(()=>document.querySelector('.sl-material-ink')?.height>0);
  const after={lines:await lines(),fs:await page.locator('.sl-material-text p').first().evaluate(p=>parseFloat(getComputedStyle(p).fontSize))};
  assert(Math.abs(after.fs-before.fs*1.2)<0.6,'正文字号放大 20%');
  assert(after.lines>before.lines,`放大后重新换行（行数 ${before.lines}→${after.lines}）`);
  const sheet=await page.evaluate(()=>{const s=document.querySelector('.sl-material-scroll');return {sw:s.scrollWidth,cw:s.clientWidth};});
  assert(sheet.sw<=sheet.cw+1,'不用左右拖');
  assert.equal(await pixels(page,'.sl-material-ink'),0,'120% 下没有默认字号的勾画');
  assert.match(await page.locator('.sl-mfs-note').textContent(),/100% 字号下另有勾画/);
  // 120% 下画一笔，回到 100%：默认字号的勾画原样
  await page.locator('[data-mark="highlight"]').click();const hb=await page.locator('.sl-material-ink').first().boundingBox();
  await page.mouse.move(hb.x+hb.width*.3,hb.y+60);await page.mouse.down();await page.mouse.move(hb.x+hb.width*.6,hb.y+60,{steps:8});await page.mouse.up();await page.locator('[data-mark="read"]').click();
  assert(await pixels(page,'.sl-material-ink')>0,'120% 下的勾画');
  await page.locator('[data-sl-mfs="-10"]').click();await page.locator('[data-sl-mfs="-10"]').click();await page.locator('.sl-material-size output').filter({hasText:'100%'}).waitFor();
  await page.waitForFunction(()=>document.querySelector('.sl-material-ink')?.height>0);
  assert.equal(await pixels(page,'.sl-material-ink'),base100,'回到默认字号：原来的勾画一像素不差');
  assert.match(await page.locator('.sl-mfs-note').textContent(),/120% 字号下另有勾画/);
  await page.locator('#slDraftSave').click();await page.locator('#slSaveStatus').filter({hasText:'已保存'}).waitFor();
  const saved=await page.evaluate(()=>fetch('/api/shenlun/answer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({qid:document.querySelector('[data-slq]')?.dataset.slq||''})}).then(r=>r.json()).catch(()=>null));
  // ② 交卷弹窗：返回修改不交卷
  if(first){const b=await page.locator('.sl-card-ink').boundingBox(),v=await page.locator('.sl-card-viewport').boundingBox();const y=Math.max(b.y,v.y)+40;await page.mouse.move(b.x+b.width*.2,y);await page.mouse.down();await page.mouse.move(b.x+b.width*.3,y+20,{steps:8});await page.mouse.up();}
  await page.locator('#slSubmit').click();await page.locator('#slSubmitText').waitFor();
  assert.ok((await page.locator('#slSubmitText').inputValue()).length>0,'识别结果放进核对框');
  await page.locator('#slSubmitCancel').click();await page.locator('#slSubmitText').waitFor({state:'detached'});
  assert.equal(await page.locator('.sl-review-total').count(),0,'返回修改：没有交卷');
  // ③ 移出（先回题库，再进训练中心）
  await page.locator('#slBack').click();await page.waitForFunction(()=>VIEW==='skeleton'&&!!document.querySelector('#slPaperList'));await page.evaluate(()=>go('bank'));await page.locator('.sl-training').waitFor();
  const qid=await page.evaluate(async()=>{const d=await fetch('/api/shenlun/claims',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>r.json());return d.items[0]?.qid||'';});
  assert(qid,'写过的题自动进办理目录');
  await page.locator(`[data-claimed-id="${qid}"]`).evaluate(e=>e.closest('details').open=true);
  const rm=page.locator(`[data-slclaimed-remove="${qid}"]`);await rm.click();assert.equal(await rm.textContent(),'确认移出？','点一次只是确认');
  assert.equal(await page.locator(`[data-claimed-id="${qid}"]`).count(),1);
  await rm.click();await page.locator(`[data-claimed-id="${qid}"]`).waitFor({state:'detached'});
  await page.reload();await page.evaluate(()=>go('bank'));await page.locator('.sl-training').waitFor();
  assert.equal(await page.locator(`[data-claimed-id="${qid}"]`).count(),0,'刷新后不会被草稿拉回目录');
  // 重新领取：草稿还在
  await page.evaluate(q=>fetch('/api/shenlun/claims',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({claim:true,qids:[q]})}),qid);
  await page.reload();await page.evaluate(()=>go('bank'));await page.locator(`[data-claimed-id="${qid}"]`).waitFor({state:'attached'});
  assert.match(await page.locator(`[data-claimed-id="${qid}"]`).textContent(),/已做/,'重新领取接着用原来的草稿');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'无横向溢出');
  assert.deepEqual(errors,[]);console.log(`申论实操训练中心 ${size}：材料字号/红格占满/交卷核对/移出 通过`);server.kill();server=null;
 }
}finally{await browser?.close();server?.kill();}})().catch(e=>{console.error(e);process.exit(1);});
