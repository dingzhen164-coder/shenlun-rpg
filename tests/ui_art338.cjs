/* 隔离服务验证三科内置素材的真实HTTP、科目隔离、背景切换与单张申论人物。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const subject=process.argv.find(x=>x.startsWith('--subject='))?.split('=')[1];
const fixture=process.argv.includes('--fixture');
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),...(fixture?['--art-fixture']:[])],{env:process.env});
let logs='',browser;srv.stderr.on('data',x=>logs+=x);
const ready=new Promise((ok,no)=>{let text='';const t=setTimeout(()=>no(Error(logs)),20000);srv.stdout.on('data',x=>{text+=x;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});srv.on('exit',c=>{clearTimeout(t);no(Error('服务退出 '+c+logs));});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,size] of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]]){
  const page=await browser.newPage({viewport:size}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(base);
  await page.waitForFunction(()=>!!window.DASH_REF?.());
  const info=await page.evaluate(()=>({files:ART_FILES,custom:ART_CUSTOM,subject:SUBJECT0}));assert.equal(info.subject,subject||'法考');assert(info.files.length>10);
  for(const [rel] of info.files){const r=await page.request.get(new URL('assets/'+rel,base).href);assert.equal(r.status(),200,rel);assert.match(r.headers()['content-type'],/image|audio|octet-stream/,rel);}
  for(const theme of ['light','dark']){
   await page.evaluate(t=>{document.documentElement.dataset.theme=t;},theme);
   for(const view of ['dwelling','train','skeleton','notes','settings']){
    await page.evaluate(v=>go(v),view);await page.waitForFunction(()=>document.body.classList.contains('has-page-art'));
    const css=await page.locator('#bgLayer').evaluate(e=>getComputedStyle(e).backgroundImage);assert.match(css,/beauty\/page\//,view);
    assert.equal(await page.evaluate(()=>scrollY>0||document.documentElement.scrollHeight>innerHeight+2),false);
   }
   await page.evaluate(async()=>{STUDY_REGIONS.select((DASH.subject==='行测')?'chang':'board-0');await go('train');});
   const css=await page.locator('#bgLayer').evaluate(e=>getComputedStyle(e).backgroundImage);
   if(subject==='行测')assert.match(css,/train-chang/);if(subject==='申论')assert.match(css,/train-guina/);
   if(process.argv.includes('--shots')&&theme==='light'){
    const out=path.resolve('ui-artifacts/art338');fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,(subject||'法考')+'-'+label+'.png')});
   }
  }
  if(subject==='申论'){
   const n=await page.evaluate(()=>fetch('/api/narrative').then(r=>r.json()));assert(n.profile.portraits.calm);if(!fixture)assert.deepEqual(Object.keys(n.profile.portraits),['calm']);
   await page.evaluate(()=>go('home'));await page.locator('[data-portal-go="journal"]').click();await page.locator('.qb-archive>summary').click();await page.locator('[data-narrative-chapter="prologue"]').click();
   const img=page.locator('.narrative-stage img').first();await img.waitFor({state:'attached'});await page.waitForFunction(()=>Array.from(document.querySelectorAll('.narrative-stage img')).some(i=>i.complete&&i.naturalWidth>0));
   await page.locator('.narrative-stage').waitFor();
   if(process.argv.includes('--shots')&&label==='tablet')await page.screenshot({path:path.resolve('ui-artifacts/art338/申论-人物.png')});
  }
  if(fixture){assert(info.custom.length>0);if(subject==='行测'){await page.evaluate(()=>go('dwelling'));assert.match(await page.locator('#bgLayer').evaluate(e=>getComputedStyle(e).backgroundImage),/dwelling(?:-night)?\.webp/);}}
  assert.deepEqual(errors,[]);await page.close();console.log((subject||'法考')+' '+label+'：素材HTTP、主题背景、全页固定与人物通过');
 }
}finally{await browser?.close();srv.kill();}})().catch(e=>{console.error(e);process.exit(1);});
