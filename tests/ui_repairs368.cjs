/* 3.6.8仅检查本批界面：繁体书法字、本境界修为、配套题换行字号与答题卡防掌心。
 * 使用临时库、自编题面；不调用真实AI或接触用户资料。 */
const assert=require('node:assert/strict'),fs=require('node:fs');
const {spawn}=require('node:child_process'),{chromium}=require('playwright');
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','行测','--politics-fixture'],{env:process.env});
let logs='',page,browser;srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error(logs)),20000);srv.stdout.on('data',b=>{out+=b;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});srv.on('exit',c=>{clearTimeout(timer);reject(Error('服务退出'+c+logs));});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 page=await browser.newPage({viewport:{width:800,height:1280},hasTouch:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/politics/atlas',async route=>{const response=await route.fetch(),json=await response.json();json.data.questions[0].text='自编题干第一段。\n自编第二段。\nA.自编甲 B.自编乙 C.自编丙 D.自编丁';await route.fulfill({response,json});});
 await page.goto(base);await page.locator('.portal-world').waitFor();await page.locator('#splash').waitFor({state:'hidden'});
 assert.equal(await page.evaluate(()=>SCENE_PORTAL.title('home')),'行测宗');
 const mapping={'peak-chang':'政','peak-yan':'言','peak-li':'邏','peak-shu':'數','peak-zi':'資'};
 for(const [id,char] of Object.entries(mapping))assert.equal(await page.locator(`[data-portal-go="${id}"] .portal-calligraphy`).textContent(),char);
 assert(await page.evaluate(async()=>{await document.fonts.load('40px PeakCalligraphy','言政邏數資');return [...document.fonts].some(f=>f.family==='PeakCalligraphy'&&f.status==='loaded');}),'实际加载离线书法字形，不用系统回退冒充');
 await page.evaluate(()=>STUDY_HUD.mount({...DASH,xp:9999,realm:{...DASH.realm,into:123,need:456,next_xp:20000}},'home'));
 assert.match(await page.locator('.study-hud-meter.xp').textContent(),/123 \/ 456/);
 fs.mkdirSync('ui-artifacts/repairs368',{recursive:true});await page.screenshot({path:'ui-artifacts/repairs368/home-tablet.png'});
 await page.evaluate(()=>{STUDY_REGIONS.select('chang');return go('train');});await page.locator('[data-wx-branch="politics"]').click();await page.locator('[data-wx-exam="2026-10-guokao"]').click();
 const f=page.frameLocator('.wx-atlas-frame');await f.locator('.map').waitFor();await f.locator('[data-go="practice"]').click();
 assert.equal(await f.locator('.question .atlas-qline').count(),3,'保留原题两段题干与同行选项，不再强拆选项');
 assert(await f.locator('.qtext').evaluate(e=>parseFloat(getComputedStyle(e).fontSize)>=18));
 assert(await f.locator('.qtext').evaluate(e=>e.scrollWidth<=e.clientWidth+1),'长题文不横向溢出');
 await page.screenshot({path:'ui-artifacts/repairs368/questions-tablet.png'});
 await page.addScriptTag({path:'web/shenlun_card.js'});
 const result=await page.evaluate(()=>{
  const root=document.createElement('div');root.style.cssText='position:fixed;left:0;top:150px;width:600px;height:650px;z-index:99999;background:white';root.innerHTML=SL_CARD.html({no:1,words:10});document.body.append(root);
  const card={pages:[{strokes:[]}]};let saves=0;const view=SL_CARD.mount(root,{no:1,words:10},card,()=>saves++),c=root.querySelector('.sl-card-ink'),r=c.getBoundingClientRect();
  const fire=(t,kind,id,x)=>c.dispatchEvent(new PointerEvent(t,{pointerType:kind,pointerId:id,clientX:r.left+x,clientY:r.top+90,bubbles:true,button:0,buttons:t==='pointerup'?0:1,pressure:.5}));
  fire('pointerdown','pen',1,30);fire('pointermove','touch',99,500);fire('pointerup','touch',99,500);fire('pointermove','pen',1,60);fire('pointerup','pen',1,60);
  fire('pointerdown','touch',99,500);fire('pointerup','touch',99,500);
  const out={strokes:card.pages[0].strokes, saves};view.destroy();root.remove();return out;
 });
 assert.equal(result.strokes.length,1,'只有Pencil产生一笔');assert.equal(result.saves,1);assert.equal(result.strokes[0].points.length,2);
 assert.deepEqual(errors,[]);console.log('REPAIRS368-UI-OK：五字真实离线字体、本境界进度、配套题原行/字号、Pencil防掌心');
}finally{await browser?.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
