/* 4.0.x：宗门大比、试炼塔的场景图必须铺到屏幕最上沿（顶栏牌子浮在画面上）。
   回归：iPad 上大比顶部出现两个月亮（全屏背景层与场景图各露一截）、试炼塔顶部露出一条米黄色空白。
   只测行测科目（申论年度考核沿用原工作区）。用隔离假库，不连AI。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const service=spawn('python3',['tests/ui_layout_server.py','行测','--merge-fixture'],{env:process.env});let browser,logs='';service.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let s='';const t=setTimeout(()=>reject(Error(logs||'临时服务未启动')),20000);service.stdout.on('data',x=>{s+=x;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);resolve(m[1]);}});service.on('exit',c=>{clearTimeout(t);reject(Error('服务退出 '+c+'\n'+logs));});});
const SIZES=[['电脑',{width:1280,height:860}],['平板竖屏',{width:800,height:1280}],['平板横屏',{width:1280,height:800}]];
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [name,viewport]of SIZES)for(const scene of ['day','night']){
  const p=await browser.newPage({viewport,hasTouch:name!=='电脑'});const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.addInitScript(s=>{try{localStorage.setItem('scene-time',s);}catch(_){}},scene);
  await p.goto(base);await p.waitForFunction(()=>!!window.DASH_REF?.());
  for(const [view,sel]of [['contest','.contest-scene'],['bank','.trial-hall']]){
   await p.evaluate(v=>go(v),view);await p.locator(sel).waitFor();await p.waitForTimeout(600);
   const r=await p.evaluate(s=>{const e=document.querySelector(s).getBoundingClientRect(),h=document.querySelector('#studyHud')?.getBoundingClientRect();
     return {top:Math.round(e.top),left:Math.round(e.left),width:Math.round(e.width),height:Math.round(e.height),hudTop:h?Math.round(h.top):null,vw:innerWidth,vh:innerHeight,fx:parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--fx-height'))||innerHeight,
       paint:(()=>{const x=document.querySelector(s==='.contest-scene'?'.cs-landscape':'.th-panorama');const fill=s==='.contest-scene'||document.querySelector('.th-painting')?.classList.contains('th-fill');return x&&fill?Math.round(x.getBoundingClientRect().top):(x?0:null);})(),title:[...document.querySelectorAll('.th-world-title,.th-scene-tools')].map(t=>{const b=t.getBoundingClientRect(),hb=document.querySelector('#studyHud').getBoundingClientRect();return b.top>=hb.bottom-1;})};},sel);
   const tag=`${name}·${scene}·${view}`;
   assert.equal(r.top,0,tag+'：场景必须从屏幕最上沿开始，不能留空白条');assert.equal(r.left,0,tag);assert.equal(r.width,r.vw,tag+'：场景铺满宽度');assert(Math.abs(r.height-r.fx)<=2,tag+'：场景高度等于可视高度 '+JSON.stringify(r));
   assert(r.paint!==null&&r.paint<=1,tag+'：场景图本身必须贴住屏幕最上沿，不能从顶栏下面才开始 '+r.paint);
   assert(r.hudTop>=0,tag+'：顶栏牌子不能被顶出屏幕');
   assert(r.title.every(Boolean),tag+'：试炼塔题字、练习记录按钮必须在顶栏牌子下面，不被牌子盖住');
  }
  if(name!=='电脑'||scene==='night'){/* 大比：全屏背景层与场景图同一张图，只能各自铺满同一尺寸，不会露出第二个月亮 */}
  const same=await p.evaluate(()=>{go('contest');return new Promise(r=>setTimeout(()=>{const a=document.querySelector('#bgLayer').getBoundingClientRect(),b=document.querySelector('.cs-landscape').getBoundingClientRect();r([a.top,a.height,b.top,b.height].map(Math.round));},500));});
  assert.equal(same[0],same[2],name+'：背景层与场景图上沿一致');assert.equal(same[1],same[3],name+'：背景层与场景图高度一致，不会错位露出第二个月亮');
  assert.deepEqual(errors,[]);await p.close();
 }
 console.log('场景图铺到屏幕最上沿：电脑/平板竖横屏×昼夜×大比/试炼塔通过');
}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
