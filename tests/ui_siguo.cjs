/* 行测·思过崖（2026-11）：地图入口叫思过崖；七块石碑按图片坐标落在画面里；点碑进入板块、重做选项后才展开解析；
   电脑与平板横竖屏、明暗主题下无横向溢出、无脚本错误。 */
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','行测','--siguo-fixture'],{env:process.env});let logs='';service.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let o='';const t=setTimeout(()=>no(Error(logs)),20000);service.stdout.on('data',b=>{o+=b;const m=o.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});service.on('exit',()=>{clearTimeout(t);no(Error(logs));});});
(async()=>{let browser;try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [size,viewport] of [['desktop',{width:1280,height:860}],['portrait',{width:800,height:1280}],['landscape',{width:1280,height:800}]])for(const theme of ['light','dark']){
  const page=await browser.newPage({viewport});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(t=>{try{localStorage.setItem('theme',t);localStorage.removeItem('sg-pos-v1');}catch(_){}},theme);
  await page.goto(base);await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&DASH);
  const label=await page.evaluate(()=>[...document.querySelectorAll('#nav a')].find(a=>a.dataset.view==='tianji')?.textContent||'');
  assert.match(label,/思过崖/);
  await page.evaluate(()=>go('tianji'));await page.waitForSelector('.sg-stele');
  const geo=await page.evaluate(()=>{const f=document.querySelector('.sg-frame').getBoundingClientRect();const s=[...document.querySelectorAll('.sg-stele')].map(e=>e.getBoundingClientRect());
    return {n:s.length,inside:s.every(r=>r.left>=f.left-1&&r.right<=f.right+1&&r.top>=f.top-1&&r.bottom<=f.bottom+1),ratio:f.width/f.height,sw:document.documentElement.scrollWidth,cw:innerWidth,tabs:document.querySelectorAll('#view .fx-tabs').length};});
  assert.equal(geo.n,7);assert(geo.inside,'石碑都在画面里');assert(Math.abs(geo.ratio-1672/941)<0.02,'画面按原比例');assert(geo.sw<=geo.cw,'无横向溢出');assert.equal(geo.tabs,0,'不被固定布局拆成页签');
  await page.click('[data-sgboard="中心理解"]');await page.waitForSelector('.sg-opt');
  assert.equal(await page.locator('.sg-sec').count(),0,'选之前不展开解析');
  await page.click('[data-sgpick="B"]');await page.waitForSelector('.sg-verdict.bad');
  assert(await page.locator('.sg-opt.right[data-sgpick="C"]').count());
  assert.deepEqual(await page.locator('.sg-sec h4').allTextContents(),['错因分析','一句话教训']);
  assert.equal(await page.evaluate(()=>SIGUO.active()),'片段阅读');
  await page.click('[data-sgback]');await page.waitForSelector('.sg-stele');
  await page.click('[data-sgboard="逻辑填空"]');await page.click('[data-sgpick="B"]');await page.waitForSelector('.sg-verdict.ok');
  const sw=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);assert(sw);
  assert.deepEqual(errors,[]);await page.close();console.log(`思过崖 ${size}/${theme}：入口、七碑坐标、重做判分与解析展开通过`);
 }
}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exit(1);});
