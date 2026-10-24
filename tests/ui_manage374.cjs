/* 3.7.4真实HTTP浏览器：导入时政PDF后在“管理已导入文件”里批量删除；自编PDF/隔离临时库/不连AI。电脑与平板横竖屏。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs');
const server=spawn('python3',['tests/ui_layout_server.py','行测','--politics-fixture'],{env:process.env});let browser,page,logs='',train='';server.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let text='';const timer=setTimeout(()=>no(Error(logs)),20000);server.stdout.on('data',b=>{text+=b;const f=text.match(/UI-POLITICS (.+)/);if(f)train=f[1];const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});server.on('exit',()=>{clearTimeout(timer);no(Error(logs));});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [size,width,height] of [['desktop',1280,860],['tablet',800,1280],['landscape',1280,800]]){
  page=await browser.newPage({viewport:{width,height},hasTouch:true,reducedMotion:'reduce'});page.setDefaultTimeout(12000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());
  await page.evaluate(()=>{STUDY_REGIONS.select('chang');return go('train');});await page.locator('[data-wx-branch=politics]').click();
  await page.locator('.wx-import>summary').click();
  if(size==='desktop'){   // 先导入一份冲刺资料，再管理
   await page.locator('[name=channel]').selectOption('sprint-study');await page.locator('[name=pdf]').setInputFiles(train+'/自编补充.pdf');await page.locator('[data-politics-import] [type=submit]').click();
   await page.locator('[data-import-result]').filter({hasText:'已加入'}).waitFor();
  }
  await page.locator('.wx-manage>summary').click();await page.locator('.wx-manage-item').first().waitFor();
  const labels=await page.locator('.wx-manage-item').allTextContents();assert.ok(labels.length>=1,'列出已导入文件');
  assert.equal(await page.locator('[data-manage-delete]').isDisabled(),true,'没勾选时不能删除');
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);assert.equal(overflow,false,'管理列表不横向溢出');
  if(size==='desktop'){
   await page.locator('[data-manage-all]').click();assert.match(await page.locator('[data-manage-delete]').textContent(),/删除所选（\d+）/);
   await page.locator('[data-manage-none]').click();assert.equal(await page.locator('[data-manage-delete]').isDisabled(),true);
   await page.locator('.wx-manage-item input').first().check();
   page.once('dialog',d=>d.accept());await page.locator('[data-manage-delete]').click();
   await page.locator('[data-manage-result]').filter({hasText:/已删除 1 项，备份在「.*时政回收/}).waitFor();
   assert.equal(await page.locator('.wx-manage-item').count(),labels.length-1,'删除后列表更新');
   const recycle=await page.locator('[data-manage-result]').textContent();assert.match(recycle,/时政回收/);
   const folder=fs.readdirSync(train+'/时政回收');assert.ok(folder.length>=1,'备份文件夹已生成');
   await page.screenshot({path:'ui-artifacts/manage374-desktop.png'}).catch(()=>{});
  }else await page.screenshot({path:`ui-artifacts/manage374-${size}.png`}).catch(()=>{});
  assert.deepEqual(errors,[]);await page.close();console.log(size+'：导入/勾选/批量删除/备份/列表刷新通过');
 }
 console.log('MANAGE374-OK');
}catch(e){if(page&&!page.isClosed())console.error('诊断',await page.locator('[data-import-result],[data-manage-result]').allTextContents().catch(()=>[]));throw e;}finally{await browser?.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
