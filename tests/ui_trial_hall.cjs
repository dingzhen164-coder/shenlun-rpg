/* 双模式试炼真实HTTP回归：假HOME、自编题，不连接AI；电脑/平板明暗，无手机。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_trial_server.py'],{env:process.env});
let logs='',browser,active;service.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error(logs||'试炼服务未启动')),20000);service.stdout.on('data',x=>{text+=x;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});service.on('exit',c=>{clearTimeout(timer);reject(Error('试炼服务退出 '+c+' '+logs));});});
const out=path.resolve('ui-artifacts/trial-hall');
async function fits(page){
 const problems=await page.evaluate(()=>{
  const bad=[],scene=document.querySelector('.trial-hall'),frame=scene.querySelector('dialog[open]')||scene,r=frame.getBoundingClientRect();
  if(document.documentElement.scrollHeight>innerHeight+2||document.documentElement.scrollWidth>innerWidth+2||scrollY)bad.push('整页溢出');
  if(r.left<0||r.right>innerWidth+1||r.bottom>innerHeight+1)bad.push('框越界');
  if(frame!==scene&&Math.abs(r.width-scene.parentElement.clientWidth)>3)bad.push('面板未全宽');
  if(frame.scrollWidth>frame.clientWidth+2)bad.push('框横向溢出');
  if(frame===scene){const fx=parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--fx-height'))||innerHeight;if(Math.abs(r.height-fx)>2||Math.abs(r.top)>1)bad.push('塔景未铺满整个屏幕（含顶栏后面）');return bad;}   // 2026-10-29起塔景固定铺满视口，顶栏牌子浮在画面上
  for(const selector of ['.th-actions','.th-dialog-head']){const e=frame.querySelector(selector),b=e.getBoundingClientRect();if(b.top<r.top||b.bottom>r.bottom+1||!b.height)bad.push('固定区域越界 '+selector);}
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
 const mode=await page.locator('.trial-hall').getAttribute('data-th-view');await page.locator('[data-th-enter='+mode+']').click();
}
async function enter(page,mode){if(await page.locator('.th-dialog[open]').count())await page.locator('[data-th-close]').click();await page.locator('[data-th-enter='+mode+']').click();assert.equal(await page.locator('[data-th-tab],.th-tabs').count(),0);}
async function choose(page,selector,index){await page.locator(selector).selectOption(String(index));}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,viewport]of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}],['tablet-landscape',{width:1280,height:800}]]){
  const page=await browser.newPage({viewport,deviceScaleFactor:2});active=page;page.setDefaultTimeout(10000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.evaluate(()=>go('bank'));await page.locator('.trial-hall').waitFor();
  const painted=await page.locator('.th-panorama').count(),left=(await page.locator('[data-th-enter=exam]').count())?'exam':'sets';   // 行测左门是整卷模考（见 ui_exam_room.cjs），法考等仍是套卷练习
  await page.locator(painted?'.th-panorama':'.th-tower-art').evaluate(img=>img.decode());
  if(painted){assert.equal(await page.locator('.th-panorama').evaluate(img=>img.naturalWidth),3840);assert.equal(await page.locator('.th-tower-art,.th-gate img').count(),0);const fit=await page.locator('.th-painting').evaluate(el=>{const r=el.getBoundingClientRect(),s=el.closest('.trial-hall').getBoundingClientRect(),inside=b=>b.left>=s.left-1&&b.right<=s.right+1&&b.top>=s.top-1&&b.bottom<=s.bottom+1;
   // 塔尖（画面上方）、左右山门与中央牌匾必须完整可见；横向要贴住或几乎贴住两侧，只允许裁掉底部多余石阶。
   const gates=[...el.querySelectorAll('.th-painted-gate')].map(g=>g.getBoundingClientRect()),stele=el.closest('.trial-hall').querySelector('.th-stele')?.getBoundingClientRect();
   return{cropped:el.classList.contains('th-fill'),sideGap:Math.max(r.left-s.left,s.right-r.right),topOk:r.top<=s.top+1,gates:gates.length===2&&gates.every(inside),stele:!stele||inside(stele),whole:inside(r),w:s.width,h:s.height};});
  assert(fit.gates&&fit.stele,'山门与牌匾在横竖屏均完整可见');
  if(fit.cropped){assert(fit.topOk,'裁切时塔尖一侧顶端对齐，不裁塔尖');assert(fit.sideGap<=Math.max(2,fit.w*0.07),'横向铺满：左右缝不超过7%宽度（超宽屏由模糊延伸补）');}
  else assert(fit.whole,'竖屏等窄窗口仍整幅显示建筑');}
  else assert(await page.locator('.th-tower-art').evaluate(img=>img.naturalHeight>1000));
  assert.equal(await page.locator('dialog[open]').count(),0);await fits(page);
  if(painted){const gates=await page.locator('.th-painted-gate').evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect();return {top:r.top,width:r.width,height:r.height,offset:(r.left+r.width/2-p.left)/p.width,weight:Number(getComputedStyle(e.querySelector('b')).fontWeight)};}));assert(Math.abs(gates[0].top-gates[1].top)<1&&Math.abs(gates[0].height-gates[1].height)<1&&Math.abs(gates[0].width-gates[1].width)<1,'左右双门热区同尺度同基线');assert(Math.abs(gates[0].offset+gates[1].offset-1)<.01);assert(gates.every(g=>g.height>=44&&g.weight>=600));}
  if(!painted)await page.locator('.th-gate img').first().evaluate(img=>img.decode());
  if(process.argv.includes('--shots')){fs.mkdirSync(out,{recursive:true});await page.waitForFunction(()=>!document.querySelector('#splash')||getComputedStyle(document.querySelector('#splash')).opacity==='0');await page.screenshot({path:path.join(out,label+'-scene.png')});}
  const noTraining=[];const track=req=>{if(/\/api\/session\/start/.test(req.url()))noTraining.push(req.url());};page.on('request',track);
  await page.locator('[data-th-enter='+left+']').click();assert(await page.locator('.th-dialog').evaluate(d=>d.open));
  if(painted&&left==='sets'){await page.evaluate(()=>{document.documentElement.dataset.scenePhase='night';});/* 3.7.4：面板随时间变色，浅字青灰底的断言固定在夜晚，白天另见 ui_trial_phase374 */for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);const ink=await page.locator('.th-choice b').first().evaluate(e=>({color:getComputedStyle(e).color,weight:Number(getComputedStyle(e).fontWeight)}));assert.equal(ink.color,'rgb(255, 244, 210)','青灰背景的题签不能继承浅色主题黑字');assert(ink.weight>=600);await fits(page);}await page.evaluate(()=>document.documentElement.dataset.theme='light');}
  assert.equal(await page.locator('.th-dialog').evaluate(d=>getComputedStyle(d,'::backdrop').backgroundColor),'rgba(0, 0, 0, 0)');
  await page.keyboard.press('Escape');await page.locator('.th-dialog').waitFor({state:'hidden'});assert.equal(await page.locator('dialog[open]').count(),0);assert(await page.locator('[data-th-enter='+left+']').evaluate(b=>b===document.activeElement));
  assert.equal(await page.locator('[data-th-motion]').count(),0);await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator(painted?'.th-panorama':'.th-current-light').evaluate(e=>getComputedStyle(e).animationName),'none');await page.emulateMedia({reducedMotion:'no-preference'});
  await page.locator('[data-th-enter=blocks]').click();await page.locator('[data-th-close]').click();assert.equal(await page.locator('dialog[open]').count(),0);
  await page.locator('[data-th-enter=history]').click();await fits(page);await page.locator('[data-th-close]').click();assert.deepEqual(noTraining,[]);page.off('request',track);
  await page.locator('[data-th-enter='+left+']').click();
  for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);for(const tab of [left,'blocks','history']){await enter(page,tab);await fits(page);}}
  if(process.argv.includes('--shots')){await page.evaluate(()=>document.documentElement.dataset.theme='light');await page.mouse.move(viewport.width-70,viewport.height/2);await page.waitForTimeout(500);await page.waitForFunction(()=>!document.querySelector('#splash')||getComputedStyle(document.querySelector('#splash')).opacity==='0');fs.mkdirSync(out,{recursive:true});await enter(page,left);await page.screenshot({path:path.join(out,label+'-sets.png')});if(label==='desktop'){await enter(page,'blocks');await page.screenshot({path:path.join(out,'desktop-blocks.png')});}}
  await page.evaluate(()=>document.documentElement.dataset.theme='light');await enter(page,left);let selected='';
  if(left==='sets'){await choose(page,'[data-th-book]',0);await page.locator('[data-th-paper="22"]').click();selected=await page.locator('#th-pane-sets .th-selection h3').textContent();}
  await enter(page,'blocks');await choose(page,'[data-th-board]',1);await choose(page,'[data-th-topic]',0);
  const chosenTopic=await page.locator('[data-th-topic]').inputValue();await enter(page,left);if(left==='sets')assert.equal(await page.locator('#th-pane-sets .th-selection h3').textContent(),selected);
  await page.reload();await page.waitForFunction(()=>!!window.DASH_REF?.());await page.evaluate(()=>go('bank'));await page.locator('.trial-hall').waitFor();assert.equal(await page.locator('dialog[open]').count(),0);await page.locator('[data-th-enter='+left+']').click();if(left==='sets')assert.equal(await page.locator('#th-pane-sets .th-selection h3').textContent(),selected);
  await enter(page,'blocks');assert.equal(await page.locator('[data-th-topic]').inputValue(),chosenTopic);
  // 续做已经没有剩余新题的知识点复盘，按钮仍应可用，接口沿用原点:板块:知识点。
  await choose(page,'[data-th-topic]',2);assert.equal(await page.locator('.th-start').textContent().then(x=>x.trim()),'继续练习 →');assert(await page.locator('.th-start').isEnabled());
  await page.locator('.th-start').click();await page.waitForFunction(()=>!!T.battle&&!T.busy);assert.equal(await page.evaluate(()=>T.battle.phase),'review');await pause(page);
  // 修改顺序/每组数量仅影响下一组；两模式切换不发新的训练请求。
  await choose(page,'[data-th-topic]','');await page.locator('.bankOrder').selectOption('shuffle');await page.waitForFunction(()=>document.querySelector('.th-save-status')?.textContent.includes('已保存'));
  await page.locator('#bankCount').selectOption('20');await page.waitForFunction(()=>document.querySelector('.th-save-status')?.textContent.includes('已保存'));
  await page.locator('.th-start').click();await page.waitForFunction(()=>!!T.battle&&!T.busy);assert.equal(await page.evaluate(()=>T.battle.total),20);
  await page.locator('[data-act^="exam_pick"]').first().click();await page.waitForFunction(()=>!T.busy);const before=await page.evaluate(()=>({answered:T.battle.answered,position:T.battle.position}));await pause(page);
  await page.locator('.th-start').click();await page.waitForFunction(()=>!!T.battle&&!T.busy);assert.deepEqual(await page.evaluate(()=>({answered:T.battle.answered,position:T.battle.position})),before);await pause(page);
  // 套卷题数不受20题设置限制；此夹具一套跨两板块共6题。
  if(left==='sets'){await enter(page,'sets');await page.locator('[data-th-paper="23"]').click();await page.locator('.th-start').click();await page.waitForFunction(()=>!!T.battle&&!T.busy);assert.equal(await page.evaluate(()=>T.battle.total),6);await pause(page);}
  // 按套卷板块训练取同一套全部题，包含做过的题，来源始终可见；独立恢复与旧模式互不覆盖。
  if(painted){
  await enter(page,'blocks');await page.locator('.bankOrder').selectOption('paper');
  const source=await page.locator('[data-th-block-paper]').first().locator('b').textContent();await page.locator('[data-th-block-paper]').first().click();
  assert((await page.locator('.th-paper-source').textContent()).includes(source));assert.equal(await page.locator('#bankCount,[data-th-topic]').count(),0);await fits(page);
  const expected=Number((await page.locator('[data-th-block-paper][aria-pressed=true] .th-choice-progress').textContent()).match(/\d+/)[0]);
  await page.locator('.th-start').click();await page.waitForFunction(()=>!!T.battle&&!T.busy);assert.equal(await page.evaluate(()=>T.battle.total),expected);assert((await page.locator('#view').textContent()).includes('来源：'+source));await pause(page);
  assert.equal(await page.locator('.bankOrder').inputValue(),'paper');await page.locator('.th-start').click();await page.waitForFunction(()=>!!T.battle&&!T.busy);assert.equal(await page.evaluate(()=>T.battle.total),expected);await pause(page);
  await page.locator('.bankOrder').selectOption('seq');await page.locator('#bankCount').waitFor();await page.waitForFunction(()=>document.querySelector('.th-save-status')?.textContent.includes('已保存'));
  }
  await enter(page,'blocks');await choose(page,'[data-th-topic]',0);
  // 回炉按整个板块，避免用户误以为只复习当前知识点。
  await page.locator('[data-th-board]').selectOption('0');assert.match(await page.locator('[data-th-review]').textContent(),/本板块/);
  if(await page.locator('[data-th-review]').isEnabled())await page.locator('[data-th-review]').click();else await page.locator('.th-start').click();await page.waitForFunction(()=>!!T.battle&&!T.busy);assert.equal(await page.evaluate(()=>T.battle.mode),'review');await pause(page);
  await page.evaluate(()=>{document.querySelector('#view').style.setProperty('--scene-panel-width','100%');document.querySelector('#view').style.setProperty('--scene-panel-height','310px');});await fits(page);
  await page.evaluate(()=>{document.querySelector('#view').style.removeProperty('--scene-panel-width');FIXED_LAYOUT.refresh();});

  assert.deepEqual(errors,[]);await page.close();console.log(label+'：塔景与双入口、选择面板、偏好保存、续做、套卷/知识点/错题'+(painted?'、原生4K与整卷板块来源':'')+'及边界通过');
 }
}catch(error){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});}throw error;}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
