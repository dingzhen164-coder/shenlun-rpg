/* 3.0.4固定页面验收：隔离示例库，三尺寸/亮暗，模块切换与长正文操作。
   不只检查滚动条：实际尝试滚动页面和内容，检查内容末尾及固定操作可达。 */
const assert=require('node:assert/strict'),{chromium}=require('playwright'),{spawn}=require('node:child_process');
const fs=require('node:fs');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const server=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),'--journey-fixture'],{env:process.env});
let logs='',browser,page;server.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let out='';const t=setTimeout(()=>reject(Error(logs||'服务未启动')),20000);server.stdout.on('data',x=>{out+=x;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);resolve(m[1]);}});server.on('exit',c=>{clearTimeout(t);reject(Error('服务退出 '+c+logs));});});
async function fits(label){
 await page.evaluate(()=>Promise.all(document.getAnimations().filter(a=>isFinite(a.effect?.getComputedTiming().endTime||0)&&a.effect.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>0))));/* 等页面进入动效结束再量 */
 const info=await page.evaluate(()=>{
  const de=document.scrollingElement;window.scrollTo(0,99999);
  const view=document.querySelector('#view').getBoundingClientRect();
  const visible=x=>x.getClientRects().length&&!x.closest('[hidden]');
  const controls=[...document.querySelectorAll('.fx-actions button,.yj-top button,.yj-bar button,.fx-pager:not([hidden]) button')].filter(visible);
  return {scroll:window.scrollY,extra:de.scrollHeight-innerHeight,width:de.scrollWidth-innerWidth,bottom:view.bottom,top:view.top,area:view.height,
   controls:controls.map(x=>{const r=x.getBoundingClientRect();return {text:x.textContent.trim().slice(0,22),top:r.top,bottom:r.bottom,left:r.left,right:r.right};}).filter(r=>r.top<0||r.bottom>innerHeight+2||r.left<-1||r.right>innerWidth+2)};
 });
 assert.equal(info.scroll,0,label+'整页不能滚动');assert.ok(info.extra<=2,label+'页面纵向溢出 '+JSON.stringify(info));
 assert.ok(info.width<=2,label+'页面横向溢出');assert.ok(info.bottom<=await page.evaluate(()=>innerHeight+2),label+'工作区超出窗口');
 assert.ok(info.area>100,label+'工作区被信息栏挤没');assert.deepEqual(info.controls,[],label+'固定操作越界');
}
async function reveal(selector){
 await page.waitForTimeout(100);
 await page.evaluate(selector=>{const e=document.querySelector(selector);if(!e)throw Error('控件不存在 '+selector);
  for(let p=e;p;p=p.parentElement)if(p.hidden&&p.id)document.querySelector(`[aria-controls="${p.id}"]`)?.click();
  for(let p=e;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;
 },selector);await page.waitForTimeout(60);
}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.goto(base);await page.locator('.portal-world').waitFor();
 const routes=['home','dwelling','train','bank','tianji','skeleton','notes','contest','log','settings'];let checked=0;
 for(const size of [{width:1280,height:860},{width:800,height:1280},{width:1024,height:600}])for(const theme of ['light','dark']){
  await page.setViewportSize(size);await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
  for(const route of routes){await page.evaluate(v=>go(v),route);await page.waitForTimeout(100);await fits(`${size.width}/${theme}/${route}`);checked++;
   const labels=await page.locator('.subpage-nav>.fx-tabs>.fx-tab').allTextContents();
   for(let i=0;i<labels.length;i++){await page.locator('.subpage-nav>.fx-tabs>.fx-tab').nth(i).click();await fits(route+'/'+labels[i]);assert.ok((await page.locator('.fx-panel:not([hidden])').innerText()).trim().length>0,'标签内容保留');}
  }
 }
 await page.setViewportSize({width:1280,height:860});await page.evaluate(()=>go('settings'));await reveal('#sModel');
 await page.locator('#sModel').fill('3.0.4未保存示例');const count=await page.locator('#view input').count();
 await page.locator('#sModel').evaluate(e=>e.closest('details').open=false);await reveal('#sModel');assert.equal(await page.locator('#sModel').inputValue(),'3.0.4未保存示例');assert.equal(await page.locator('#view input').count(),count,'切标签不能销毁设置输入');
 const sc=page.locator('.fx-panel:not([hidden])>.fx-scroll');await sc.evaluate(e=>{const long=document.createElement('p');long.textContent='固定区域长文验证。'.repeat(2000);e.append(long);e.scrollTop=e.scrollHeight;});assert.ok(await sc.evaluate(e=>e.scrollTop>0),'长内容在框内滚动');await fits('长设置');
 // 3.3.6空资料不再显示玉简框；先给第一个分区放入隔离自编资料，再验有资料的布局。
 await page.evaluate(async subject=>{const board=subject==='行测'?'片段阅读':DASH.tree[0].board;await api('/api/cards/add',{deck:board,type:'问答',front:'固定布局自编条件',back:'自编答案'});if(subject==='行测')STUDY_REGIONS.select('yan');await go('train');},subject);if(subject!=='行测')await page.locator('[data-study-region]').first().click();   // 行测五峰无选择页，直接进辨言峰
 await page.locator('.yj-hall').waitFor();await page.waitForTimeout(100);await fits('分区详情');
 const deck=await page.evaluate(()=>DASH.tree[0].board+'::固定布局自编');await page.evaluate(async deck=>{await api('/api/cards/add',{deck,type:'问答',front:'长文前面。\n\n'.repeat(200),back:'长文答案。\n\n'.repeat(200)});await CARDS.review(deck);},deck);
 await page.locator('#yjShow').waitFor();await page.waitForTimeout(100);await fits('长卡正面');const body=page.locator('.fx-stage-body');await body.evaluate(e=>e.scrollTop=e.scrollHeight);assert.ok(await body.evaluate(e=>e.scrollTop>0));await fits('长卡末尾');await page.locator('#yjShow').click();await fits('长卡答案');
 await page.locator('#yjBack').click();await page.waitForTimeout(100);await fits('关闭卡片');
 if(process.argv.includes('--shot')){await page.evaluate(()=>go('settings'));await reveal('[data-portal-name]');await page.screenshot({path:'../../outputs/3.0.4-'+(subject||'法考')+'设置预览.png',animations:'disabled'});await page.evaluate(()=>go('train'));await page.locator('[data-study-regions-back]').click();await page.screenshot({path:'../../outputs/3.0.4-'+(subject||'法考')+'分区预览.png',animations:'disabled'});}
 assert.deepEqual(errors,[]);console.log('FIXED-LAYOUT-OK '+(subject||'法师成长记')+'：'+checked+'页面，标签/未保存输入/内部长文/卡片固定操作');
 }catch(e){if(page){fs.mkdirSync('ui-artifacts',{recursive:true});await page.screenshot({path:'ui-artifacts/fixed-layout-failure.png'}).catch(()=>{});}throw e;}finally{await browser?.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
