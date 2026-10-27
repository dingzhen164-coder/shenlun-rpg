/* 3.7.5冲刺刷题：整本套卷PDF按“套卷→题号→四个选项”导入，页面可按套卷选择、题号按套卷内编号；自编PDF/隔离临时库/不连AI。电脑与平板横竖屏。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs');
const server=spawn('python3',['tests/ui_layout_server.py','行测','--politics-fixture'],{env:process.env});let browser,page,logs='',train='';server.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let text='';const timer=setTimeout(()=>no(Error(logs)),20000);server.stdout.on('data',b=>{text+=b;const f=text.match(/UI-POLITICS (.+)/);if(f)train=f[1];const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [size,width,height] of [['desktop',1280,860],['tablet',800,1280],['landscape',1280,800]]){
  page=await browser.newPage({viewport:{width,height},hasTouch:true,reducedMotion:'reduce'});page.setDefaultTimeout(12000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());
  await page.evaluate(()=>{STUDY_REGIONS.select('chang');return go('train');});await page.locator('[data-wx-branch=politics]').click();await page.locator('.wx-import>summary').click();
  if(size==='desktop'){
   await page.locator('[name=channel]').selectOption('sprint-quiz');await page.locator('[name=pdf]').setInputFiles(train+'/自编十套卷.pdf');await page.locator('[data-politics-import] [type=submit]').click();
   const note=page.locator('[data-import-result]').filter({hasText:'识别到2套'});await note.waitFor();
   const text=await note.innerText();assert(text.includes('黑十专项卷一党的创新理论 3题')&&text.includes('黑十专项卷二经济与社会 2题'),text);assert(!text.includes('选项不全'),text);
  }
  await page.locator('[data-wx-exam="2026-10-guokao"]').click();const f=page.frameLocator('.wx-atlas-frame');await f.locator('#nav [data-go="practice"]').click();
  const picker=f.locator('#practicePaper');await picker.waitFor();assert.equal(await picker.locator('option').count(),3,'全部套卷 + 两套');
  assert.equal(await f.locator('.section-title h2').first().innerText(),'当前 1 / 5');
  await picker.selectOption({index:1});await f.locator('.section-title h2').filter({hasText:'当前 1 / 3'}).waitFor();
  assert.equal((await f.locator('.question .chip').first().innerText()).trim(),'第1题');
  await f.locator('[data-action="next"]').click();await f.locator('.question .chip').filter({hasText:'第2题'}).waitFor();
  const q2=await f.locator('.qtext').innerText();assert(q2.includes('D.“两个结合”使马克思主义根脉')&&!q2.includes('十个明确'),'第2题的D项不吞下一题：'+q2);
  assert.equal(await f.locator('.answer-options button').count(),4);
  await f.locator('[data-action="next"]').click();await f.locator('.question .chip').filter({hasText:'第3题'}).waitFor();assert((await f.locator('.qtext').innerText()).includes('D.4项'));
  await picker.selectOption({index:2});await f.locator('.section-title h2').filter({hasText:'当前 1 / 2'}).waitFor();assert.equal((await f.locator('.question .chip').first().innerText()).trim(),'第1题');
  if(size==='desktop'){        // 3.8.1：导入答案——按套卷内题号补/改答案，别的套卷不动
   assert.equal(await f.locator('#answerImport').isVisible(),false,'答题页不放答案导入');await f.locator('#nav [data-go=\"sprint\"]').click();await f.locator('#answerImport>summary').click();await f.locator('#answerPaper').selectOption({index:0});await f.locator('#answerText').fill('1.C 2.D');
   await f.locator('[data-import-answers]').click();const status=f.locator('#answerStatus').filter({hasText:'补上'});await status.waitFor();
   const said=await status.innerText();assert(said.includes('改了 2 题')&&said.includes('黑十专项卷一'),said);
  }
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),true,size+'无横向溢出');
  fs.mkdirSync('ui-artifacts/exam375',{recursive:true});await page.screenshot({path:`ui-artifacts/exam375/${size}.png`});assert.deepEqual(errors,[]);await page.close();
 }
 console.log('EXAM375-OK 套卷分开/题号按套卷/四项选项完整/电脑与平板横竖屏');
}catch(error){console.error(error.message||error,logs);process.exitCode=1;}finally{await browser?.close();server.kill();}})();
