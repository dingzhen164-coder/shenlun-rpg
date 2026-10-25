/* 3.7.6消化清单整份保留与待补全填写：标题/普通句子/不再显示配套统计行；点待补全的空填答案，回车保存并跳到下一个；自编PDF/隔离临时库。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs');
const server=spawn('python3',['tests/ui_layout_server.py','行测','--politics-fixture','--wanxiang373-fixture'],{env:process.env});let browser,page,logs='',train='';server.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let text='';const timer=setTimeout(()=>no(Error(logs)),20000);server.stdout.on('data',b=>{text+=b;const f=text.match(/UI-POLITICS (.+)/);if(f)train=f[1];const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});server.on('exit',()=>{clearTimeout(timer);no(Error(logs));});});
async function enter(){await page.evaluate(()=>{STUDY_REGIONS.select('chang');return go('train');});await page.locator('[data-wx-branch=politics]').click();await page.locator('[data-wx-exam]').first().click();const f=page.frameLocator('.wx-atlas-frame');await f.locator('#nav [data-go=sprint]').click();await f.locator('.sprint-workspace').waitFor();return f;}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});fs.mkdirSync('ui-artifacts/digest376',{recursive:true});
 for(const [size,width,height] of [['desktop',1280,860],['tablet',800,1280],['landscape',1280,800]]){
  page=await browser.newPage({viewport:{width,height},hasTouch:true,reducedMotion:'reduce'});page.setDefaultTimeout(12000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());
  if(size==='desktop'){
   await page.evaluate(()=>{STUDY_REGIONS.select('chang');return go('train');});await page.locator('[data-wx-branch=politics]').click();await page.locator('.wx-import>summary').click();await page.locator('[name=channel]').selectOption('digest');
   await page.locator('[name=pdf]').setInputFiles(train+'/自编完整清单.pdf');await page.locator('[data-politics-import] [type=submit]').click();await page.locator('[data-import-result]').filter({hasText:'待补全'}).waitFor();
  }
  const f=await enter();await f.locator('[data-material=m1]').click();await f.locator('.original[data-highlights-ready=true]').waitFor();await f.locator('[data-tab=understand]').click();await f.locator('.sprint-digest').waitFor();
  // 整份保留：小标题、没有空的普通句子都在；不再有配套/统计/只看没记住/来源行
  assert.equal((await f.locator('.digest-heading').first().textContent()).trim(),'一、自编小标题');
  assert((await f.locator('.sprint-digest').innerText()).includes('自编的普通句子，没有空也要原样保留。'),'没有空的句子也保留');
  assert.equal(await f.locator('.sprint-digest-meta,.sprint-digest-source,[data-digest-filter],.sprint-digest-tip').count(),0,'清单页不再显示配套、统计、来源和说明行');
  const pending=f.locator('[data-digest-fill]');assert.equal(await pending.count(),size==='desktop'?2:1,'没出处的空待补全（电脑端先补全了一个，平板端还剩一个）');
  if(size==='desktop'){
   // 补全：点第一个待补全 → 输入 → 回车保存 → 自动打开下一个待补全 → Esc 取消
   await pending.first().click();const input=f.locator('.digest-fill-edit input');await input.waitFor();await input.fill('自编答案甲');await input.press('Enter');
   await f.locator('.sprint-blank[data-digest-blank]').filter({hasText:'自编答案甲'}).waitFor();
   await f.locator('.digest-fill-edit input').waitFor();assert.equal(await f.locator('[data-digest-fill]').count(),0,'保存后自动打开下一个待补全，它正在输入');await f.locator('.digest-fill-edit input').press('Escape');await f.locator('[data-digest-fill]').waitFor();assert.equal(await f.locator('.digest-fill-edit').count(),0);
   // 补全后的空可以核对记忆状态，也可以用 ✎ 改答案
   const filled=f.locator('[data-digest-blank]').filter({hasText:'自编答案甲'});await filled.click();await f.locator('.sprint-blank.remember').waitFor();
   await f.locator('[data-digest-edit]').click();await f.locator('.digest-fill-edit input').fill('改后的答案');await f.locator('.digest-fill-edit input').press('Enter');
   await f.locator('.sprint-blank.remember').filter({hasText:'改后的答案'}).waitFor();
  }else{
   const edit=f.locator('.digest-fill-edit');assert.equal(await edit.count(),0);
  }
  const over=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);assert(!over,size+'无横向溢出');
  await page.screenshot({path:`ui-artifacts/digest376/${size}.png`});assert.deepEqual(errors,[]);await page.close();
 }
 console.log('DIGEST376-OK 整份保留/无统计说明行/待补全填写与回车跳下一个/改答案/电脑与平板横竖屏');
}catch(error){console.error(error.message||error,logs);process.exitCode=1;}finally{await browser?.close();server.kill();}})();
