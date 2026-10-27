/* 3.8.2 预加载回归：软件打开后空闲时先把常去地点的背景下好（点进去不再从头等）；行测试炼塔不再白下三层拆件图；进页面只等当前时段的图。
   假HOME自编数据；只看浏览器发出的请求，不连AI。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_exam_server.py'],{env:process.env});
let logs='',browser;service.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error(logs||'服务未启动')),20000);service.stdout.on('data',x=>{text+=x;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});service.on('exit',c=>{clearTimeout(timer);reject(Error(logs||'服务退出 '+c));});});
// 网络事件不受Performance资源缓冲和浏览器测试时钟代理影响，缺项直接报具体地点。
function warmRequests(page,label){
 const remaining=new Set(['bank-','skeleton-','contest-','dwelling-','notes','tianji-','train-chang-','political_atlas']);
 return new Promise((resolve,reject)=>{
  const finish=()=>{clearTimeout(timer);page.off('request',requested);};
  const requested=r=>{for(const n of remaining)if(r.url().includes(n==='political_atlas'?n:'/beauty/page/'+n))remaining.delete(n);if(!remaining.size){finish();resolve();}};
  const timer=setTimeout(()=>{finish();reject(Error(label+'：空闲预加载未请求 '+[...remaining].join('、')));},90000);
  page.on('request',requested);
 });
}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 const phases=[['dawn','06:30:00'],['day','12:00:00'],['dusk','18:00:00'],['night','23:00:00']];
 for(const [label,viewport] of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]])for(const [phase,time] of phases){
  const page=await browser.newPage({viewport});await page.clock.setFixedTime(new Date('2026-10-27T'+time));page.setDefaultTimeout(60000);const errors=[],urls=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>urls.push(r.url()));
  const warmed=warmRequests(page,label+'/'+phase);
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());assert.equal(await page.evaluate(()=>document.documentElement.dataset.scenePhase),phase);
  // 没点任何地方，空闲预加载就应该把这些地点的背景请求出去
  await warmed;
  const peakPhase=phase==='dawn'?'day':phase;
  for(const peak of ['chang','yan','li','shu','zi'])assert(urls.some(u=>u.includes('/beauty/page/train-'+peak+'-'+peakPhase+'.webp')),label+'/'+phase+'：五峰预加载必须和实际显示时段一致 '+peak);
  assert(!urls.some(u=>/train-(chang|yan|li|shu|zi)-dawn\.webp/.test(u)),'不请求不存在的五峰清晨图');
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
  await page.close();console.log(label+'/'+phase+'：空闲预加载常去地点背景、试炼塔不再多下拆件图、塔景一次到位');
 }
 await browser.close();service.kill();
}catch(e){console.error(e);await browser?.close().catch(()=>{});service.kill();process.exit(1);}})();
