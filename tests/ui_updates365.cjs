/* 3.6.5 隔离真实浏览器：四峰留景、八图联动、多人Q版路径、奖惩页面与重复录分。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','行测'],{env:process.env});let browser,p,log='';srv.stderr.on('data',b=>log+=b);
const ready=new Promise((ok,no)=>{let s='';const t=setTimeout(()=>no(Error(log)),20000);srv.stdout.on('data',b=>{s+=b;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});srv.on('exit',()=>{clearTimeout(t);no(Error(log));});});
const out=path.resolve('ui-artifacts/updates365');fs.mkdirSync(out,{recursive:true});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});p=await browser.newPage({viewport:{width:1280,height:860}});const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.addInitScript(()=>{window.__images=[];const NativeImage=window.Image;window.Image=class extends NativeImage{constructor(...args){super(...args);__images.push(this);}};window.__fleet={colors:[],count:0,max:0,heights:[],ys:[],frames:0};const proto=CanvasRenderingContext2D.prototype,c=proto.clearRect,d=proto.drawImage;
  proto.clearRect=function(...a){if(this.canvas.classList.contains('portal-fx')){__fleet.max=Math.max(__fleet.max,__fleet.count);__fleet.count=0;__fleet.frames++;}return c.apply(this,a);};
  proto.drawImage=function(...a){if(this.canvas.classList.contains('portal-fx')&&a[0]?.src?.includes('sword-chibi-')){__fleet.count++;if(!__fleet.colors.includes(a[0].src))__fleet.colors.push(a[0].src);__fleet.heights.push(a[4]);__fleet.ys.push(this.getTransform().f);}return d.apply(this,a);};
 });
 await p.goto(base);await p.waitForFunction(()=>!!window.DASH_REF?.());
 await p.evaluate(()=>{localStorage.setItem('scene-time','day');localStorage.setItem('scene-season','spring');SCENE_FX.apply();});
 await p.evaluate(()=>{window.__map=document.querySelector('.portal-stage');window.__points=[...document.querySelectorAll('[data-portal-go]')].map(e=>[e.dataset.portalGo,e.style.cssText]);});
 for(const season of ['spring','summer','autumn','winter'])for(const time of ['day','night']){
  await p.evaluate(({season,time})=>{localStorage.setItem('scene-season',season);localStorage.setItem('scene-time',time);SCENE_FX.apply();},{season,time});
  await p.waitForFunction(({season,time})=>document.querySelector('.portal-'+time)?.src.includes('home-'+season+'-'+time+'.webp'),{season,time});
  await p.locator('.portal-'+time).evaluate(e=>e.decode());assert(await p.locator('.portal-'+time).isVisible());
  assert(await p.evaluate(()=>__map===document.querySelector('.portal-stage')));assert.deepEqual(await p.evaluate(()=>[...document.querySelectorAll('[data-portal-go]')].map(e=>[e.dataset.portalGo,e.style.cssText])),await p.evaluate(()=>__points));
  if((season==='autumn'&&time==='night')||(season==='winter'&&time==='day'))await p.screenshot({path:path.join(out,season+'-'+time+'.png')});
 }
 await p.reload();await p.waitForFunction(()=>!!window.DASH_REF?.());assert.match(await p.locator('.portal-night').getAttribute('src'),/winter-night/);
 await p.evaluate(()=>{window.__stable=document.querySelector('.portal-stage');localStorage.setItem('scene-season','random');localStorage.setItem('scene-season-minutes','60');localStorage.setItem('scene-season-cycle-v1',JSON.stringify({season:'winter',at:Date.now()-3600100,minutes:60}));SCENE_FX.apply();});
 const selected=await p.evaluate(()=>document.documentElement.dataset.sceneSeason);assert.notEqual(selected,'winter');assert.match(await p.locator('.portal-night').getAttribute('src'),new RegExp(selected+'-night'));assert(await p.evaluate(()=>__stable===document.querySelector('.portal-stage')));
 await p.evaluate(()=>{localStorage.setItem('scene-season','off');SCENE_FX.apply();});const month=await p.evaluate(()=>SCENE_FX.season());assert.match(await p.locator('.portal-night').getAttribute('src'),new RegExp(month+'-night'));
 await p.evaluate(()=>{localStorage.setItem('scene-season','autumn');SCENE_FX.apply();window.__fleet={colors:[],count:0,max:0,heights:[],ys:[],frames:0};});
 await p.waitForFunction(()=>{const imgs=__images.filter(i=>i.src.includes('sword-chibi-'));return imgs.length===3&&imgs.every(i=>i.complete&&i.naturalWidth>0);});
 await p.evaluate(async()=>{await Promise.all(__images.filter(i=>i.src.includes('sword-chibi-')).map(i=>i.decode()));document.documentElement.dataset.motion='reduced';});
 await p.waitForFunction(()=>document.querySelector('.portal-atmosphere').dataset.fxRunning==='false');
 await p.clock.install();await p.evaluate(()=>document.documentElement.dataset.motion='full');await p.clock.runFor(18000);await p.clock.resume();const fleet=await p.evaluate(()=>__fleet);
 assert.equal(fleet.colors.length,3,'三种配色实际绘制');assert(fleet.max>=2&&fleet.max<=4,'同时多人且有数量上限');assert(Math.max(...fleet.heights)<=26&&Math.min(...fleet.heights)>=18,'人物明显缩小');assert(Math.max(...fleet.ys)-Math.min(...fleet.ys)>100,'飞行有显著升降');await p.screenshot({path:path.join(out,'chibi-fleet-night.png')});
 await p.evaluate(async()=>{for(const board of ['逻辑填空','论证逻辑','数量关系','资料分析']){await api('/api/cards/add',{deck:board+'::自编玉简',type:'问答',front:'自编条件',back:'核对条件'});await api('/api/mindmap/create',{board,name:'自编灵脉图'});}});
 for(const viewport of [{width:1280,height:860},{width:800,height:1280},{width:1180,height:820}])for(const theme of ['light','dark']){
  await p.setViewportSize(viewport);await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);
  for(const peak of ['yan','li','shu','zi']){
   await p.evaluate(async peak=>{STUDY_REGIONS.select(peak);await go('train');},peak);await p.locator('.fx-scenic-peak').waitFor();
   const r=await p.locator('.fx-scenic-peak').boundingBox(),view=await p.locator('#view').boundingBox();
   assert(r.width<view.width*.97,'四峰保留左右景物');assert(r.height<view.height*.94,'四峰保留上下景物');assert(Math.abs(r.x+r.width/2-(view.x+view.width/2))<2,'内容居中');
   const cards=await p.locator('.fx-region-work>.card').all();assert.equal(cards.length,2);for(const c of cards){const b=await c.boundingBox();assert(b.height>70&&b.x>=r.x&&b.x+b.width<=r.x+r.width+1);}
   assert.equal(await p.evaluate(()=>scrollY>0||document.documentElement.scrollWidth>innerWidth+2),false);
   if(viewport.width===800&&theme==='light'&&peak==='yan')await p.screenshot({path:path.join(out,'peak-tablet.png')});
  }
 }
 // 首次录分之后的低分即时结算，修改旧季不会重复扣除。
 const result=await p.evaluate(async()=>{
  await api('/api/mock/save',{season:41,score:80,date:'2026-10-22'});
  await api('/api/mock/save',{season:42,score:69,date:'2026-10-22'});const first=await api('/api/dashboard');
  await api('/api/mock/save',{season:42,score:99,date:'2026-10-10'});const second=await api('/api/dashboard');
  return {first,second};
 });
 const penalty=result.first.mock_rewards.find(r=>r.status==='penalized');assert(penalty&&penalty.penalty_rate===1);assert.equal(result.first.xp,result.second.xp);assert.equal(result.first.realm.name,result.second.realm.name);
 await p.evaluate(async()=>{await refresh();await go('contest');});await p.locator('[data-cs-enter=overview]').click();await p.locator('.mock-rewards').waitFor();assert((await p.locator('.mock-rewards').textContent()).includes('走火入魔'));assert((await p.locator('.mock-rewards').textContent()).includes('当前小境界'));assert.deepEqual(errors,[]);
 console.log('3.6.5：八图/随机/重载/不移地标，三色小Q版多人曲线，四峰三尺寸明暗留景，录分奖惩与幂等通过');
}catch(e){if(p&&!p.isClosed())await p.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});throw e;}finally{await browser?.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
