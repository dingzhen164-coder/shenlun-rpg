/* 两幅启动画面真实解码与失图回退：电脑、平板横竖屏；只用隔离假库。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs');
const srv=spawn('python3',['tests/ui_layout_server.py','行测'],{env:process.env});let logs='',browser,page;
srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let s='';const t=setTimeout(()=>no(Error(logs)),20000);srv.stdout.on('data',b=>{s+=b;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});srv.on('exit',()=>{clearTimeout(t);no(Error(logs));});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [size,width,height]of [['desktop',1280,860],['tablet',800,1280],['tablet-landscape',1280,800]]){
  page=await browser.newPage({viewport:{width,height},deviceScaleFactor:2});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  // 在独立空页面装载相同HTML/CSS/JS，精确控制首屏就绪，不靠睡眠抢短暂加载画面。
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());
  for(const variant of [0,1]){
   await page.evaluate(v=>{document.querySelector('#splash')?.remove();sessionStorage.setItem('loading-art-next',String(v));const el=document.createElement('div');el.id='splash';el.setAttribute('aria-hidden','true');el.dataset.loadingArt='assets/beauty/loading/3610/dawn.webp,assets/beauty/loading/3610/night.webp';el.innerHTML='<img src="icons/icon-192.png" alt=""><b>公考模拟器</b><small>行测</small><div class="splash-bar"><i></i></div>';document.body.append(el);document.querySelector('#view').replaceChildren();},variant);
   await page.addScriptTag({url:base+'/beauty_splash.js'});
   await page.locator('.splash-art').evaluate(img=>img.decode());assert.equal(await page.locator('#splash').getAttribute('data-art'),String(variant));
   const geometry=await page.locator('#splash').evaluate(e=>{const img=e.querySelector('.splash-art'),r=img.getBoundingClientRect(),b=e.querySelector('b').getBoundingClientRect();return {native:[img.naturalWidth,img.naturalHeight],fills:r.width===innerWidth&&r.height===innerHeight,text:b.left>=0&&b.right<=innerWidth&&b.bottom<=innerHeight,animation:getComputedStyle(img).animationName,events:getComputedStyle(e).pointerEvents};});
   assert.deepEqual(geometry.native,[3840,2880]);assert(geometry.fills&&geometry.text);assert.equal(geometry.animation,'none');assert.equal(geometry.events,'none');
   if(process.argv.includes('--shots')&&(size==='tablet'||size==='desktop')){fs.mkdirSync('ui-artifacts/loading3610',{recursive:true});await page.screenshot({path:`ui-artifacts/loading3610/${size}-${variant}.png`});}
   await page.evaluate(()=>document.querySelector('#view').append(document.createElement('section')));await page.locator('#splash').waitFor({state:'detached',timeout:8000});
  }
  assert.deepEqual(errors,[]);await page.close();console.log(size+'：两幅4K启动画面、中央文字边界、正常淡出通过');
 }
 // 资源失败也不能锁住启动；固定6秒上限，不额外延长程序启动。
 page=await browser.newPage();await page.route('**/assets/beauty/loading/**',r=>r.abort());await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.locator('#splash').waitFor({state:'detached',timeout:8000});console.log('加载图缺失回退通过');
}finally{await browser?.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
