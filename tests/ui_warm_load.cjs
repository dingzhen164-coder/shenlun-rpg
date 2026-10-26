/* 3.8.2 预加载回归：软件打开后空闲时先把常去地点的背景下好（点进去不再从头等）；行测试炼塔不再白下三层拆件图；进页面只等当前时段的图。
   假HOME自编数据；只看浏览器发出的请求，不连AI。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_exam_server.py'],{env:process.env});
let logs='',browser;service.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error(logs||'服务未启动')),20000);service.stdout.on('data',x=>{text+=x;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});service.on('exit',c=>{clearTimeout(timer);reject(Error(logs||'服务退出 '+c));});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,viewport] of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]]){
  const page=await browser.newPage({viewport});page.setDefaultTimeout(60000);const errors=[],urls=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>urls.push(r.url()));
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());
  // 没点任何地方，空闲预加载就应该把这些地点的背景请求出去
  for(const name of ['bank-','skeleton-','contest-','dwelling-','notes','tianji-','train-chang-','political_atlas'])
   await page.waitForFunction(n=>performance.getEntriesByType('resource').some(e=>e.name.includes(n==='political_atlas'?n:'/beauty/page/'+n)),name,{timeout:90000});
  urls.length=0;
  await page.evaluate(()=>go('bank'));await page.locator('.trial-hall').waitFor();
  await page.waitForLoadState('networkidle');
  const bad=urls.filter(u=>/\/beauty\/trial\/(tower|gate|landscape)\.png/.test(u));
  assert.deepEqual(bad,[],'行测试炼塔是一整张画，不该再下三层拆件图');
  assert.equal(await page.locator('.th-panorama').count(),1);
  // 画面上的塔景图用的是当前时段的原生4K，不是先放一张旧图再换
  const src=await page.locator('.th-panorama').getAttribute('src');assert(/bank-(day|dusk|night|dawn)\.webp/.test(src),src);
  assert(!urls.some(u=>u.includes('/hd/369/hall-day.webp')),'塔景图一次到位，不先下旧的 hall-day 再换');
  assert.equal(errors.length,0,errors.join('\n'));
  await page.close();console.log(label+'：空闲预加载常去地点背景、试炼塔不再多下拆件图、塔景一次到位');
 }
 await browser.close();service.kill();
}catch(e){console.error(e);await browser?.close().catch(()=>{});service.kill();process.exit(1);}})();
