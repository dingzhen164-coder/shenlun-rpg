/* 3.3.2场景内容框交互：六组折叠、输入保留、本机尺寸恢复、上下两栏和内部滚动。
   只起隔离临时资料/假HOME服务；电脑和平板，不连接真实AI。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const service=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),'--journey-fixture'],{env:process.env});
let logs='',browser,active;service.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error(logs||'服务启动超时')),20000);service.stdout.on('data',x=>{text+=x;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});service.on('exit',c=>{clearTimeout(timer);reject(Error('服务退出 '+c+logs));});});
const out=path.resolve('ui-artifacts/scene-panels');
async function reveal(page,selector){await page.locator(selector).waitFor({state:'attached'});await page.locator(selector).evaluate(el=>{for(let p=el;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});}
async function range(page,id,value){await page.locator(id).evaluate((el,value)=>{el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));},String(value));}
async function fits(page){
 const bad=await page.evaluate(()=>{
  const errors=[],root=document.documentElement;
  if(root.scrollHeight>innerHeight+2||root.scrollWidth>innerWidth+2||scrollY)errors.push('整页溢出');
  for(const el of document.querySelectorAll('.scene-panel,.fx-region-work>.card')){
   const r=el.getBoundingClientRect();if(r.width&&r.height&&(r.left<0||r.right>innerWidth+1||r.top<0||r.bottom>innerHeight+1))errors.push('框越界 '+el.className);
  }return errors;
 });assert.deepEqual(bad,[]);
}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,viewport] of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]]){
  const page=await browser.newPage({viewport});active=page;const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>!document.querySelector('#splash')||getComputedStyle(document.querySelector('#splash')).opacity==='0');await page.evaluate(()=>go('settings'));await page.waitForSelector('.fx-settings-group');
  assert.equal(await page.locator('.fx-settings-group').count(),6);
  assert.equal(await page.locator('.fx-settings-group[open]').count(),0,'初次仅显示六组标题');
  const box=await page.locator('.fx-settings').boundingBox();assert(Math.abs(box.x+box.width/2-viewport.width/2)<2);assert(Math.abs(box.width-Math.min(960,viewport.width))<2,'固定阅读宽度');await fits(page);
  assert.equal(await page.locator('#scenePanelWidth,#scenePanelHeight,#cwR,#chR,#cfR').count(),0,'移除重复尺寸与字号设置');
  if(process.argv.includes('--shots')&&label==='desktop'){fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,'settings-'+(subject||'法考')+'.png')});}
  await reveal(page,'#sModel');await page.locator('#sModel').fill('未保存的自编模型');const count=await page.locator('#view input').count();
  const ai=page.locator('.fx-settings-group[data-fx-group="ai"]');await ai.locator(':scope>summary').click();await ai.locator(':scope>summary').click();
  assert.equal(await page.locator('#sModel').inputValue(),'未保存的自编模型');assert.equal(await page.locator('#view input').count(),count);
  await page.locator('.fx-settings-group').evaluateAll(es=>es.forEach(e=>e.open=true));
  const list=page.locator('.fx-settings-list');await list.evaluate(el=>{el.scrollTop=el.scrollHeight;});assert(await list.evaluate(el=>el.scrollTop>0),'长设置在框内滚动');
  await page.evaluate(()=>localStorage.setItem('scene-panels-v1',JSON.stringify({width:40,height:40})));
  await page.reload();await page.evaluate(()=>go('settings'));await page.waitForSelector('.fx-settings');
  assert(Math.abs((await page.locator('.fx-settings').boundingBox()).width-box.width)<2,'旧尺寸偏好不再压窄窗口');
  await page.evaluate(async subject=>{const board=subject==='行测'?'片段阅读':subject==='申论'?(DASH.tree[0]?.board||'归纳概括'):'民法';await api('/api/cards/add',{deck:board,type:'问答',front:'自编条件是什么？',back:'先说明适用条件。'});await api('/api/mindmap/create',{board,name:'自编知识图'});},subject);
  await page.evaluate(peak=>{STUDY_REGIONS.select(peak);return go('train');},subject==='行测'?'yan':'');if(subject!=='行测')await page.locator('[data-study-region]').first().click();   // 行测五峰无选择页：直接进辨言峰
  await page.waitForSelector('.fx-region-work');
  for(const theme of ['light','dark']){
   await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await fits(page);
   const a=await page.locator('.yj-hall').boundingBox(),b=await page.locator('.ln-hall').boundingBox();
   assert(a&&b&&a.height>70&&b.height>70,'两栏同时可见');assert(a.y+a.height<=b.y+1,'玉简和导图上下排列');assert(Math.abs(a.x-b.x)<2,'两栏对齐');
  }
  if(process.argv.includes('--shots')&&label==='desktop'){await page.evaluate(()=>document.documentElement.dataset.theme='light');await page.screenshot({path:path.join(out,'region-'+(subject||'法考')+'.png')});}
  await page.evaluate(()=>go('settings'));await page.waitForSelector('.fx-settings');await fits(page);
  await page.locator('#view details').evaluateAll(nodes=>nodes.forEach(n=>n.open=true));
  assert(await page.locator('.fx-settings-list').evaluate(el=>el.scrollWidth<=el.clientWidth+2),'最窄尺寸展开设置不应横向溢出');
  await page.evaluate(()=>go('train'));await page.waitForSelector('.fx-region-work');await fits(page);
  assert.deepEqual(errors,[]);await page.close();console.log((subject||'法考')+' '+label+'：六组设置、输入保留、固定尺寸/旧偏好兼容、上下分区与固定滚动通过');
 }
}catch(e){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure-'+(subject||'法考')+'.png')}).catch(()=>{});}throw e;}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exit(1);});
