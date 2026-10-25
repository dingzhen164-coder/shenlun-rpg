/* 3.7.4 试炼塔「套卷/板块」选择面板随场景时间变色：早晨/中午浅底深字，傍晚/夜晚深底浅字；
   自动模式按时钟（7点早晨、12点中午、18点傍晚、23点夜晚）；电脑与平板横竖屏均检查文字对比度。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_trial_server.py'],{env:process.env});
let logs='',browser;service.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error(logs||'试炼服务未启动')),20000);service.stdout.on('data',x=>{text+=x;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});});
const lum=c=>{const k=c.startsWith('color(')?255:1,[r,g,b]=c.replace(/^[a-z]+\((?:srgb)?/,'').match(/[\d.]+/g).slice(0,3).map(Number).map(v=>v*k).map(v=>{v/=255;return v<=.03928?v/12.92:((v+.055)/1.055)**2.4;});return .2126*r+.7152*g+.0722*b;};
const contrast=(a,b)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 const cases=[['早晨','2026-10-24T07:00:00',false,'dawn'],['中午','2026-10-24T12:00:00',false,'day'],['傍晚','2026-10-24T18:00:00',true,'dusk'],['晚上','2026-10-24T23:00:00',true,'night']];
 for(const [label,viewport] of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}],['tablet-landscape',{width:1280,height:800}]]){
  for(const [name,time,dark,phase] of cases){
   const context=await browser.newContext({viewport});const page=await context.newPage();await page.clock.install({time:new Date(time)});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.evaluate(()=>go('bank'));await page.locator('.trial-hall').waitFor();
   assert.equal(await page.evaluate(()=>document.documentElement.dataset.scenePhase),phase,`${label}${name}：自动模式时段不对`);
   const left=(await page.locator('[data-th-enter=exam]').count())?'exam':'sets';
   for(const mode of ['blocks',left]){
    await page.locator(`[data-th-enter=${mode}]`).click();
    const s=await page.locator('.th-dialog[open]').evaluate(d=>{const cs=getComputedStyle(d),act=getComputedStyle(d.querySelector('.th-actions')),pick=d.querySelector('.th-pane:not([hidden]) :is(.th-choice b,.th-selection h3,.er-intro h3)');return {text:getComputedStyle(pick||d).color,paper:act.backgroundColor,before:getComputedStyle(d,'::before').backgroundImage,filter:getComputedStyle(d,'::before').filter,after:getComputedStyle(d,'::after').backgroundImage};});
    assert.match(s.before,/selection\.webp/,`${label}${name}${mode}：背景图丢失`);
    assert.ok(contrast(s.text,s.paper)>=4.5,`${label}${name}${mode}：文字对比度不足 ${contrast(s.text,s.paper).toFixed(2)}`);
    assert.equal(lum(s.paper)<.2,dark,`${label}${name}${mode}：底色明暗不符合${name}（${s.paper}）`);
    if(phase==='night')assert.equal(s.filter,'none');else assert.notEqual(s.filter,'none',`${label}${name}：背景图未调色`);
    await page.locator('[data-th-close]').click();
   }
   assert.deepEqual(errors,[]);await context.close();
  }
 }
 console.log('试炼塔选择面板随时间变色通过：早晨/中午/傍晚/晚上 × 电脑/平板横竖屏');
}catch(error){console.error(error.message||error,logs);process.exitCode=1;}finally{await browser?.close();service.kill();}})();
