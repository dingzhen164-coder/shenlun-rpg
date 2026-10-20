/* 3.5.6 iPad没有Esc：左下角返回钮（与设置齿轮同大）；地图首页隐藏；地图首页铺满整个窗口。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[])],{env:process.env});
let logs='';srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((res,rej)=>{let out='';const t=setTimeout(()=>rej(Error(logs||'服务未启动')),20000);srv.stdout.on('data',b=>{out+=b;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);res(m[1]);}});});
(async()=>{let browser;try{
 const base=await ready;browser=await chromium.launch(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{});
 for(const size of [{width:1280,height:860},{width:800,height:1280}]){
  const page=await browser.newPage({viewport:size});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.locator('.portal-world').waitFor();
  assert.equal(await page.locator('#pageBackBtn').isHidden(),true,'地图首页不显示返回钮');
  const w=await page.locator('.portal-world').boundingBox();assert.ok(w.x===0&&w.y===0&&Math.abs(w.width-size.width)<=1&&Math.abs(w.height-size.height)<=1,'地图首页铺满窗口 '+JSON.stringify(w));
  await page.evaluate(()=>go('bank'));await page.waitForFunction(()=>VIEW==='bank');
  const back=page.locator('#pageBackBtn'),gear=page.locator('#pageSettingsGear');
  await back.waitFor();const b=await back.boundingBox(),g=await gear.boundingBox();
  assert.equal(Math.round(b.width),Math.round(g.width));assert.equal(Math.round(b.height),Math.round(g.height));
  assert.ok(b.x<g.x&&Math.abs(b.y-g.y)<=1&&b.x<=12,'返回钮在左下角、与齿轮同高');
  await back.click();await page.waitForFunction(()=>VIEW==='home');
  await page.evaluate(()=>go('skeleton'));await page.waitForFunction(()=>VIEW==='skeleton');
  await gear.click();await page.waitForFunction(()=>VIEW==='settings');
  await back.click();await page.waitForFunction(()=>VIEW==='skeleton');
  assert.deepEqual(errors,[]);await page.close();
 }
 console.log('BACK-BUTTON-OK '+(subject||'法考'));
}catch(e){console.error(e);process.exitCode=1;}finally{await browser?.close();srv.kill();}})();
