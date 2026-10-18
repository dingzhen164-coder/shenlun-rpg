/* 三科同钟昼夜：隔离假HOME/临时美术，电脑平板。只截外观变更的一页供查看。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
// 不依赖真实美术库的优先级回归：专用夜景优先，缺夜图可复用白天图。
function artChoice(files){const values={},classes=new Set(),body={dataset:{},style:{setProperty:(k,v)=>values[k]=v,removeProperty:k=>delete values[k]},classList:{contains:k=>classes.has(k),add:k=>classes.add(k),remove:k=>classes.delete(k)}};
 const context={window:{ART_FILES:files.map(f=>[f,1]),ART_CUSTOM:files},document:{readyState:'loading',body,documentElement:{dataset:{theme:'light',sceneTime:'night'}},querySelector:()=>({textContent:'修为与突破'}),addEventListener:()=>{}}};
 require('node:vm').runInNewContext(fs.readFileSync('web/beauty_art.js','utf8'),context);context.window.BeautyArt.mount('dwelling');return {url:values['--ds-page-art'],kind:body.dataset.sceneRelight};}
assert.match(artChoice(['beauty/page/dwelling-growth-day.webp','beauty/page/dwelling-night.webp']).url,/dwelling-night/);
assert.equal(artChoice(['beauty/page/dwelling-night.webp']).kind,'native');
assert.equal(artChoice(['beauty/page/dwelling-day.webp']).kind,'synthetic');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const service=spawn('python3',['tests/ui_layout_server.py',...(subject?[subject]:[])],{env:process.env});let browser,active,log='';service.stderr.on('data',b=>log+=b);
const ready=new Promise((ok,no)=>{let s='';const t=setTimeout(()=>no(Error(log)),20000);service.stdout.on('data',b=>{s+=b;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});service.on('exit',()=>{clearTimeout(t);no(Error(log));});});
const out=path.resolve('ui-artifacts/daylight339');
async function setTime(p,mode){await p.evaluate(m=>{localStorage.setItem('scene-time',m);SCENE_CLOCK.apply();},mode);await p.waitForTimeout(50);}
(async()=>{try{const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});for(const [size,viewport]of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]]){
 const p=await browser.newPage({viewport});active=p;const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(base);await p.waitForFunction(()=>!!window.DASH_REF?.());
 assert.deepEqual(await p.evaluate(()=>[5.49,5.5,8,17,19.5].map(h=>SCENE_CLOCK.phase(new Date(2026,9,17,Math.floor(h),Math.round(h%1*60))))),['night','dawn','day','dusk','night']);
 for(const theme of ['light','dark']){await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);for(const mode of ['day','night']){
  await setTime(p,mode);await p.evaluate(()=>go('home'));assert(await p.locator('.portal-'+mode).first().isVisible());
  for(const view of ['dwelling','train','skeleton','notes','settings',...(subject==='申论'?[]:['bank','contest'])]){
   await p.evaluate(v=>go(v),view);if(view==='bank'||view==='contest')await p.locator(view==='bank'?'.th-landscape':'.cs-landscape').waitFor();else await p.waitForFunction(()=>document.body.classList.contains('has-page-art'));
   assert.equal(await p.evaluate(()=>document.documentElement.dataset.sceneTime),mode);const filter=await p.locator(view==='bank'?'.th-landscape':view==='contest'?'.cs-landscape':'#bgLayer').evaluate(e=>getComputedStyle(e).filter);
   assert.equal(mode==='night'?filter.includes('brightness'):filter==='none',true,view+' '+theme+' '+mode+' '+filter);
   assert.equal(await p.locator('#view').evaluate(e=>getComputedStyle(e).filter),'none');assert.equal(await p.locator('#studyHud').evaluate(e=>getComputedStyle(e).filter),'none');
   assert.equal(await p.evaluate(()=>scrollY>0||document.documentElement.scrollWidth>innerWidth+2||document.documentElement.scrollHeight>innerHeight+2),false);
  }
 }}
 await p.evaluate(()=>go('dwelling'));const before=await p.locator('#bgLayer').evaluate(e=>getComputedStyle(e).backgroundImage);await p.evaluate(()=>{window.__view=document.querySelector('#view').firstElementChild;window.__requests=0;const raw=fetch;window.fetch=(...a)=>{__requests++;return raw(...a);};});
 await p.evaluate(()=>{document.documentElement.dataset.scenePhase='dusk';document.documentElement.dataset.sceneTime='day';});await p.waitForTimeout(50);const dusk=await p.locator('#bgLayer').evaluate(e=>getComputedStyle(e).filter);assert(dusk.includes('sepia'));
 await setTime(p,'night');assert.equal(await p.locator('#bgLayer').evaluate(e=>getComputedStyle(e).backgroundImage),before);assert(await p.evaluate(()=>__view===document.querySelector('#view').firstElementChild));assert.equal(await p.evaluate(()=>__requests),0);
 if(process.argv.includes('--shots')&&size==='desktop'){fs.mkdirSync(out,{recursive:true});await p.screenshot({path:path.join(out,(subject||'法考')+'-night.png')});await setTime(p,'day');await p.screenshot({path:path.join(out,(subject||'法考')+'-day.png')});}
 await setTime(p,'theme');assert.equal(await p.evaluate(()=>document.documentElement.dataset.sceneTime),'night');await p.evaluate(()=>document.documentElement.dataset.theme='light');await p.waitForFunction(()=>document.documentElement.dataset.sceneTime==='day');
 assert.deepEqual(errors,[]);await p.close();console.log((subject||'法考')+' '+size+'：昼夜/阅读主题独立、主页子页同步、晨昏、无重绘/请求及边界通过');
 }}catch(e){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure-'+(subject||'法考')+'.png')}).catch(()=>{});}throw e;}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
