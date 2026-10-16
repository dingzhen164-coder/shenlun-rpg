/* 双模式试炼真实HTTP回归：假HOME、自编题，不连接AI；电脑/平板明暗，无手机。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_trial_server.py'],{env:process.env});
let logs='',browser,active;service.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error(logs||'试炼服务未启动')),20000);service.stdout.on('data',x=>{text+=x;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});service.on('exit',c=>{clearTimeout(timer);reject(Error('试炼服务退出 '+c+' '+logs));});});
const out=path.resolve('ui-artifacts/trial-hall');
async function fits(page){
 const problems=await page.evaluate(()=>{
  const bad=[],frame=document.querySelector('.trial-hall'),r=frame.getBoundingClientRect();
  if(document.documentElement.scrollHeight>innerHeight+2||document.documentElement.scrollWidth>innerWidth+2||scrollY)bad.push('整页溢出');
  if(r.left<0||r.right>innerWidth+1||r.bottom>innerHeight+1)bad.push('框越界');
  if(frame.scrollWidth>frame.clientWidth+2)bad.push('框横向溢出');
  for(const selector of ['.th-tabs','.th-actions','.th-hero']){const e=frame.querySelector(selector),b=e.getBoundingClientRect();if(b.top<r.top||b.bottom>r.bottom+1||!b.height)bad.push('固定区域越界 '+selector);}
  for(const button of frame.querySelectorAll('.th-actions button')){const b=button.getBoundingClientRect();if(b.width&&b.height&&(b.left<r.left||b.right>r.right+1||b.bottom>r.bottom+1))bad.push('操作不可达');}
  const pane=frame.querySelector('.th-pane:not([hidden])');if(pane.scrollWidth>pane.clientWidth+2)bad.push('面板横向溢出');
  return bad;
 });assert.deepEqual(problems,[]);
}
async function pause(page){
 await page.locator('[data-act="bank_pause"]').click();
 await page.waitForFunction(()=>!T.busy&&T.finished);
 await page.locator('.st-btn').waitFor();await page.locator('.st-btn').click();await page.locator('.settle').waitFor({state:'detached'});
 await page.locator('#backHome').click();
 await page.locator('.trial-hall').waitFor();
}
async function choose(page,selector,index){await page.locator(selector).selectOption(String(index));}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,viewport]of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]]){
  const page=await browser.newPage({viewport});active=page;page.setDefaultTimeout(10000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.evaluate(()=>go('bank'));await page.locator('.trial-hall').waitFor();
  await page.locator('.th-tower-art').evaluate(img=>img.decode());assert(await page.locator('.th-tower-art').evaluate(img=>img.naturalHeight>1000));
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);for(const tab of ['sets','blocks','history']){await page.locator(`[data-th-tab="${tab}"]`).click();await fits(page);}}
  if(process.argv.includes('--shots')){await page.evaluate(()=>document.documentElement.dataset.theme='light');await page.mouse.move(viewport.width-70,viewport.height/2);await page.waitForTimeout(500);await page.waitForFunction(()=>!document.querySelector('#splash')||getComputedStyle(document.querySelector('#splash')).opacity==='0');fs.mkdirSync(out,{recursive:true});await page.locator('[data-th-tab="sets"]').click();await page.screenshot({path:path.join(out,label+'-sets.png')});if(label==='desktop'){await page.locator('[data-th-tab="blocks"]').click();await page.screenshot({path:path.join(out,'desktop-blocks.png')});}}
  await page.evaluate(()=>document.documentElement.dataset.theme='light');await page.locator('[data-th-tab="sets"]').click();
  await choose(page,'[data-th-book]',0);await page.locator('[data-th-paper="22"]').click();const selected=await page.locator('#th-pane-sets .th-selection h3').textContent();
  await page.locator('[data-th-tab="blocks"]').click();await choose(page,'[data-th-board]',1);await choose(page,'[data-th-topic]',0);
  const chosenTopic=await page.locator('[data-th-topic]').inputValue();await page.locator('[data-th-tab="sets"]').click();assert.equal(await page.locator('#th-pane-sets .th-selection h3').textContent(),selected);
  await page.reload();await page.waitForFunction(()=>!!window.DASH_REF?.());await page.evaluate(()=>go('bank'));await page.locator('.trial-hall').waitFor();assert.equal(await page.locator('#th-pane-sets .th-selection h3').textContent(),selected);
  await page.locator('[data-th-tab="blocks"]').click();assert.equal(await page.locator('[data-th-topic]').inputValue(),chosenTopic);
  // 续做已经没有剩余新题的知识点复盘，按钮仍应可用，接口沿用原点:板块:知识点。
  await choose(page,'[data-th-topic]',2);assert.equal(await page.locator('.th-start').textContent().then(x=>x.trim()),'继续练习 →');assert(await page.locator('.th-start').isEnabled());
  await page.locator('.th-start').click();await page.waitForFunction(()=>!!T.battle&&!T.busy);assert.equal(await page.evaluate(()=>T.battle.phase),'review');await pause(page);
  // 修改顺序/每组数量仅影响下一组；两模式切换不发新的训练请求。
  await choose(page,'[data-th-topic]','');await page.locator('.bankOrder').selectOption('shuffle');await page.waitForFunction(()=>document.querySelector('.th-save-status')?.textContent.includes('已保存'));
  await page.locator('#bankCount').selectOption('15');await page.waitForFunction(()=>document.querySelector('.th-save-status')?.textContent.includes('已保存'));
  await page.locator('.th-start').click();await page.waitForFunction(()=>!!T.battle&&!T.busy);assert.equal(await page.evaluate(()=>T.battle.total),15);
  await page.locator('[data-act^="exam_pick"]').first().click();await page.waitForFunction(()=>!T.busy);const before=await page.evaluate(()=>({answered:T.battle.answered,position:T.battle.position}));await pause(page);
  await page.locator('.th-start').click();await page.waitForFunction(()=>!!T.battle&&!T.busy);assert.deepEqual(await page.evaluate(()=>({answered:T.battle.answered,position:T.battle.position})),before);await pause(page);
  // 套卷题数不受15题设置限制；此夹具一套跨两板块共6题。
  await page.locator('[data-th-tab="sets"]').click();await page.locator('[data-th-paper="23"]').click();await page.locator('.th-start').click();await page.waitForFunction(()=>!!T.battle&&!T.busy);assert.equal(await page.evaluate(()=>T.battle.total),6);await pause(page);
  await page.locator('[data-th-tab="blocks"]').click();await choose(page,'[data-th-topic]',0);
  // 回炉按整个板块，避免用户误以为只复习当前知识点。
  await page.locator('[data-th-board]').selectOption('0');assert.match(await page.locator('[data-th-review]').textContent(),/本板块/);
  if(await page.locator('[data-th-review]').isEnabled())await page.locator('[data-th-review]').click();else await page.locator('.th-start').click();await page.waitForFunction(()=>!!T.battle&&!T.busy);assert.equal(await page.evaluate(()=>T.battle.mode),'review');await pause(page);
  await page.evaluate(()=>{document.querySelector('#view').style.setProperty('--scene-panel-width','100%');document.querySelector('#view').style.setProperty('--scene-panel-height','310px');});await fits(page);
  await page.evaluate(()=>{document.querySelector('#view').style.removeProperty('--scene-panel-width');FIXED_LAYOUT.refresh();});

  assert.deepEqual(errors,[]);await page.close();console.log(label+'：双模式/知识点、偏好保存、真实续做、套卷题数、板块错题和边界通过');
 }
}catch(error){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});}throw error;}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
