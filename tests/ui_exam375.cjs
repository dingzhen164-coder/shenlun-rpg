/* 4.4.0（原3.7.5位置）：万象峰时政地图管理（新增/编辑范围/删除）、分类时政与易错题五栏检查；自编资料/隔离临时库/不连AI。电脑与平板横竖屏。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs');
const server=spawn('python3',['tests/ui_layout_server.py','行测','--politics-fixture'],{env:process.env});let browser,page,logs='',train='';server.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let text='';const timer=setTimeout(()=>no(Error(logs)),20000);server.stdout.on('data',b=>{text+=b;const f=text.match(/UI-POLITICS (.+)/);if(f)train=f[1];const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [size,width,height] of [['desktop',1280,860],['tablet',800,1280],['landscape',1280,800]]){
  page=await browser.newPage({viewport:{width,height},hasTouch:true,reducedMotion:'reduce'});page.setDefaultTimeout(12000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());
  await page.evaluate(()=>{STUDY_REGIONS.select('chang');return go('train');});await page.locator('[data-wx-branch=politics]').click();
  await page.locator('.wx-exam-manage>summary').click();
  assert.equal(await page.locator('[data-exam-row]').count(),3,'默认3张时政地图');
  await page.locator('[data-wx-exam="2026-10-guokao"]').click();const f=page.frameLocator('.wx-atlas-frame');
  await f.locator('#nav [data-go="category_all"]').click();await f.locator('.sprint-index').waitFor();
  await f.locator('#nav [data-go="wrong"]').click();await f.locator('.sg-room').waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),true,size+'无横向溢出');
  fs.mkdirSync('ui-artifacts/exam375',{recursive:true});await page.screenshot({path:`ui-artifacts/exam375/${size}.png`});assert.deepEqual(errors,[]);await page.close();
 }
 console.log('EXAM375-OK 时政地图管理/分类时政/易错题/电脑与平板横竖屏');
}catch(error){console.error(error.message||error,logs);process.exitCode=1;}finally{await browser?.close();server.kill();}})();
