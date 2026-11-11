/* 万象峰冲刺学习·研习目录（2026-11-11 用户需求）：目录往下翻后点一份资料，目录停在原位不跳回顶部；
   收起的分组和上次读的那份记在本机，重进时目录直接露出上次那份。自编资料、隔离临时库，电脑与平板横竖屏。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const server=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','行测','--politics-fixture','--sprint-many'],{env:process.env});let logs='';server.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let text='';const timer=setTimeout(()=>no(Error(logs)),30000);server.stdout.on('data',b=>{text+=b;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});server.on('exit',()=>{clearTimeout(timer);no(Error(logs));});});
let browser;
async function enter(page){await page.evaluate(()=>{STUDY_REGIONS.select('chang');return go('train');});await page.locator('[data-wx-branch=politics]').click();await page.locator('[data-wx-exam]').first().click();const f=page.frameLocator('.wx-atlas-frame');await f.locator('#nav [data-go=sprint]').click();await f.locator('.sprint-workspace').waitFor();return f;}
const visible=(f,sel)=>f.locator('.sprint-index').evaluate((idx,sel)=>{const a=idx.getBoundingClientRect(),b=idx.querySelector(sel).getBoundingClientRect();return b.top>=a.top-1&&b.bottom<=a.bottom+1;},sel);
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [size,width,height] of [['desktop',1280,860],['portrait',800,1280],['landscape',1280,800]]){
  const page=await browser.newPage({viewport:{width,height},hasTouch:true,reducedMotion:'reduce'});page.setDefaultTimeout(15000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());
  let f=await enter(page);
  await f.locator('.sprint-index').evaluate(i=>{i.scrollTop=i.scrollHeight;});
  const top0=await f.locator('.sprint-index').evaluate(i=>i.scrollTop);assert(top0>100,'目录可以往下翻 '+top0);
  const pick=await f.locator('.sprint-index').evaluate(idx=>{const a=idx.getBoundingClientRect();const all=[...idx.querySelectorAll('.sprint-document')];for(let i=all.length-2;i>=0;i--){const b=all[i].getBoundingClientRect();if(b.top>=a.top&&b.bottom<=a.bottom)return all[i].dataset.material;}return '';});
  assert(pick,'有一份完全看得见的靠后资料');
  await f.locator(`.sprint-index [data-material="${pick}"]`).click();await f.locator('.sprint-document-body').waitFor();
  await f.locator(`.sprint-index [data-material="${pick}"].current`).waitFor();
  const top1=await f.locator('.sprint-index').evaluate(i=>i.scrollTop);assert(Math.abs(top1-top0)<2,`点资料后目录停在原位 ${top0}→${top1}`);
  // 切页签（消化）也不跳
  await f.locator('[data-tab=understand]').click();await f.locator('[data-tab=understand].active').waitFor();
  assert(Math.abs(await f.locator('.sprint-index').evaluate(i=>i.scrollTop)-top0)<2,'切页签后目录不动');
  // 收起一个分组，离开再进：分组保持收起，上次那份露在目录里
  await f.locator('.sprint-group[data-kind="讲话"]>summary').click();
  await page.evaluate(()=>go('home'));await page.waitForTimeout(300);
  f=await enter(page);
  assert.equal(await f.locator('.sprint-group[data-kind="讲话"]').evaluate(d=>d.open),false,'收起的分组记住了');
  const lastKind=await f.locator(`.sprint-index [data-material="${pick}"]`).evaluate(b=>b.closest('details').dataset.kind);
  if(lastKind!=='讲话'){await f.locator(`.sprint-index [data-material="${pick}"].last`).waitFor();assert(await visible(f,`[data-material="${pick}"]`),'重进时上次那份露在目录里');}
  assert.deepEqual(errors,[]);await page.close();console.log(`研习目录位置 ${size}：通过`);
 }
}finally{await browser?.close();server.kill();}})().catch(e=>{console.error(e);process.exit(1);});
