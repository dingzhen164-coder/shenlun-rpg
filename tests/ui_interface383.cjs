/* 三尺寸/明暗的真实页面回归：往返导航不残留长框；透明度持久化且不淡化正文/答题。 */
const assert=require('node:assert/strict'),fs=require('node:fs'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1]||'行测';
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',subject],{env:process.env});let logs='',browser,page;
srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let output='';const timer=setTimeout(()=>no(Error(logs)),20000);srv.stdout.on('data',b=>{output+=b;const m=output.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});srv.on('exit',()=>{clearTimeout(timer);no(Error(logs));});});
async function separate(){
 await page.waitForFunction(()=>{const e=document.querySelector('#studyHud');return e&&!e.classList.contains('hx381-shell')&&!e.classList.contains('ig-shell');});
 const actual=await page.locator('#studyHud').evaluate(e=>{const s=getComputedStyle(e);return {background:s.backgroundColor,blur:s.backdropFilter,border:s.borderTopWidth,shadow:s.boxShadow};});
 assert.deepEqual(actual,{background:'rgba(0, 0, 0, 0)',blur:'none',border:'0px',shadow:'none'});
}
async function alpha(locator){return locator.evaluate(e=>{const c=document.createElement('canvas').getContext('2d');c.fillStyle=getComputedStyle(e).backgroundColor;c.fillRect(0,0,1,1);return c.getImageData(0,0,1,1).data[3]/255;});}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [name,width,height]of [['desktop',1280,860],['portrait',800,1280],['landscape',1280,800]])for(const theme of ['light','dark']){
  page=await browser.newPage({viewport:{width,height}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(t=>localStorage.setItem('xrpg-theme',t),theme);await page.goto(base);await page.locator('.study-hud-player').waitFor();await separate();
  for(const route of ['settings','dwelling']){
   await page.evaluate(v=>go(v),route);await page.locator('#studyHud.subpage-heading .subpage-place').waitFor();await separate();
   await page.waitForFunction(()=>document.querySelector('.subpage-place')?.classList.contains('ig-shell'));
   assert((await alpha(page.locator('.subpage-place')))>.2&&(await alpha(page.locator('.subpage-place')))<.5);
   await page.evaluate(()=>go('home'));await page.locator('.study-hud-player').waitFor();await separate();
  }
  const player=page.locator('.study-hud-player');assert(Number(await player.evaluate(e=>getComputedStyle(e).fontWeight))>=600);
  if(await page.locator('.npc-drawer-toggle').count())assert.deepEqual(await page.locator('.npc-drawer-toggle').evaluate(e=>{const s=getComputedStyle(e);return[s.backgroundColor,s.borderTopWidth,s.boxShadow];}),['rgba(0, 0, 0, 0)','0px','none']);
  await page.evaluate(()=>go('settings'));await page.locator('#interfaceTransparency').waitFor({state:'attached'});
  assert(await page.locator('#interfaceTransparency').evaluate(e=>e.closest('[data-fx-group="appearance"]')!==null||e.closest('.fx-settings-group')?.textContent.includes('外观与声音')));
  await page.locator('#interfaceTransparency').evaluate(e=>{e.value='85';e.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.evaluate(()=>go('home'));await page.locator('.study-hud-player').waitFor();await separate();
  assert(Math.abs(await alpha(player)-.15)<.02,'透明度仅应用于背景框');assert.equal(await player.evaluate(e=>getComputedStyle(e).opacity),'1');
  await page.reload();await player.waitFor();assert(Math.abs(await alpha(player)-.15)<.02,'刷新保留本机透明度');
  await page.evaluate(()=>go('settings'));await page.locator('#interfaceTransparency').waitFor({state:'attached'});assert.equal(await page.locator('#interfaceTransparency').inputValue(),'85');
  await page.evaluate(()=>{const wrap=document.createElement('div');wrap.id='protect383';wrap.innerHTML='<div class="train"><div class="card" id="answer383">答题</div></div><div class="original" id="reading383">正文</div>';document.querySelector('#view').append(wrap);});
  await page.waitForFunction(()=>document.querySelector('#reading383')?.classList.contains('ig-paper'));
  assert.equal(await page.locator('#answer383').evaluate(e=>e.classList.contains('ig-shell')||e.classList.contains('hx381-shell')),false);
  assert(await alpha(page.locator('#reading383'))>=.94,'阅读底色不随外壳透明度变化');
  await page.evaluate(()=>document.querySelector('#protect383').remove());
  await page.evaluate(()=>go('skeleton'));await page.waitForFunction(()=>document.querySelector('#view')?.dataset.fxRoute==='skeleton');
  const tabs=await page.locator('[data-libtab]').evaluateAll(es=>es.map(e=>e.dataset.libtab));
  for(const tab of tabs){await page.locator('[data-libtab="'+tab+'"]').click();await page.waitForFunction(t=>document.querySelector('[data-libtab="'+t+'"]')?.classList.contains('on'),tab);
   const surfaces=await page.locator('#view .fx-panel,#view .fx-frame,#view .lib-head,#view .lib-tabs,#view .card').evaluateAll(es=>es.map(e=>{const s=getComputedStyle(e);return[s.backgroundColor,s.borderTopWidth,s.backdropFilter];}));
   for(const surface of surfaces)assert.deepEqual(surface,['rgba(0, 0, 0, 0)','0px','none'],'藏经阁所有页签无容器框：'+tab);
  }
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));assert.deepEqual(errors,[]);
  if(process.argv.includes('--shots')){fs.mkdirSync('ui-artifacts/interface383',{recursive:true});await page.screenshot({path:`ui-artifacts/interface383/${subject}-${name}-${theme}.png`});}
  await page.close();console.log(`${subject} ${name} ${theme}: 导航往返/独立框/透明度记忆/字重/正文保护/藏经阁嵌入通过`);
 }
 // 检查器本身也需守住：裁切外的控件不误报，真实可见重叠必须仍然失败。
 page=await browser.newPage();await page.setContent('<div id="view"><div id="clip383" style="position:relative;width:100px;height:50px;overflow:hidden"><button style="position:absolute;left:120px;top:0;width:70px;height:40px">裁切按钮</button></div><button style="position:absolute;left:130px;top:8px;width:70px;height:40px">可见按钮</button></div>');
 const source=fs.readFileSync('tests/ui_layout_check.cjs','utf8');const inspector=source.slice(source.indexOf('function inspect()'),source.indexOf('\n(async () =>'));
 const inspectPage='(()=>{'+inspector+';return inspect();})()';
 assert(!(await page.evaluate(inspectPage)).some(p=>p.includes('互相压住')),'裁切之外的部分不参与重叠');
 await page.locator('#clip383').evaluate(e=>e.style.overflow='visible');
 assert((await page.evaluate(inspectPage)).some(p=>p.includes('互相压住')),'真实可见重叠不能被过滤掉');await page.close();
}finally{await browser?.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
