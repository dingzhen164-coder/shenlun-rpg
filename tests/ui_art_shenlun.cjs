/* 申论 P1/P2：真实资源、原图渲染、时段切换，以及三种视口的明暗主题。 */
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
// 用户图优先，旧内置页签不得压过新整体场景。
const fs=require('node:fs'),vm=require('node:vm');
function choose(files,custom,subject='申论',scene='dwelling',region=''){
 const values={},classes=new Set(),body={dataset:{},style:{setProperty:(k,v)=>values[k]=v,removeProperty:k=>delete values[k]},classList:{contains:k=>classes.has(k),add:k=>classes.add(k),remove:k=>classes.delete(k)}};
 const ctx={DASH:{subject},window:{ART_FILES:files.map(f=>[f,1]),ART_CUSTOM:custom,STUDY_REGIONS:{title:()=>region}},STUDY_REGIONS:{title:()=>region},document:{readyState:'loading',body,documentElement:{dataset:{scenePhase:'dusk',sceneTime:'day'}},querySelector:()=>({textContent:'仕途与晋升'}),addEventListener:()=>{}}};
 vm.runInNewContext(fs.readFileSync('web/beauty_art.js','utf8'),ctx);ctx.window.BeautyArt.mount(scene);return values['--ds-page-art'];
}
const day='beauty/page/dwelling-dusk.webp',old='beauty/page/dwelling-growth.webp',own='beauty/page/dwelling.webp';
assert.match(choose([day,old],[]),/dwelling-dusk\.webp/);
assert.match(choose([day,old,own],[own]),/dwelling\.webp/);
assert.match(choose([day,old],[old]),/dwelling-growth\.webp/);
for(const scene of ['train','skeleton','tianji','settings']){
 const built=`beauty/page/${scene}-dusk.webp`, own=`beauty/page/${scene}.webp`;
 assert.match(choose([built,own],[], '申论',scene),new RegExp(`${scene}-dusk\\.webp`));
 assert.match(choose([built,own],[own], '申论',scene),new RegExp(`${scene}\\.webp`));
}
const training='beauty/page/train-dusk.webp',topic='beauty/page/train-guina-dusk.webp';
assert.match(choose([training,topic],[],'申论','train','归纳概括'),/train-guina-dusk\.webp/);
const service=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','申论'],{env:process.env});let logs='',browser,page;
service.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let output='';const timer=setTimeout(()=>no(Error(logs)),20000);service.stdout.on('data',b=>{output+=b;const m=output.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});service.on('exit',()=>{clearTimeout(timer);no(Error(logs));});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,width,height] of [['desktop',1280,860],['landscape',1280,800],['portrait',800,1280]]){
  page=await browser.newPage({viewport:{width,height}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.locator('#splash').waitFor({state:'hidden'});
  for(const theme of ['light','dark']){
   await page.evaluate(theme=>{document.documentElement.dataset.theme=theme;},theme);
   for(const scene of (label==='portrait'?['dwelling','bank','contest']:['dwelling','bank','contest','train','skeleton','tianji','settings'])){
    await page.evaluate(scene=>go(scene),scene);
    for(const phase of ['day','dusk','night']){
     await page.evaluate(phase=>{localStorage.setItem('scene-time',phase);SCENE_FX.apply();},phase);
     await page.waitForFunction(({scene,phase})=>document.body.style.getPropertyValue('--ds-page-art').includes(scene+'-'+phase+'.webp'),{scene,phase});
     const info=await page.evaluate(async()=>{const bg=document.querySelector('#bgLayer'), src=document.body.style.getPropertyValue('--ds-page-art').match(/url\(["']?(.*?)["']?\)$/)[1], im=new Image();im.src=src;await im.decode();return {src,size:[im.naturalWidth,im.naturalHeight],art:document.body.dataset.sceneArt,relight:document.body.dataset.sceneRelight,filter:getComputedStyle(bg).filter,shade:getComputedStyle(bg,'::after').opacity,tint:getComputedStyle(bg,'::before').backgroundImage,cover:getComputedStyle(bg).backgroundSize,overflow:document.documentElement.scrollWidth>innerWidth+2};});
     assert(info.src.includes('assets/beauty/page/'+scene+'-'+phase+'.webp'),info.src);assert.deepEqual(info.size,[3840,2880]);assert.equal(info.art,'roomSL4k');assert.equal(info.relight,'native');assert.equal(info.filter,'none');assert.equal(info.shade,'0');assert.equal(info.tint,'none');assert.equal(info.cover,'cover');assert.equal(info.overflow,false);
    }
   }
  }
  assert.deepEqual(errors,[]);await page.close();console.log(label+'：明暗主题、场景三时段原图通过');
 }
}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
