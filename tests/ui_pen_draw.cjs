/* 做题勾画（draw.js）经真实页面：快速连写、抬笔晚到、落笔被吞，三笔都要保存。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[])],{env:process.env});
let logs='';srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((res,rej)=>{let out='';const t=setTimeout(()=>rej(Error(logs||'服务未启动')),20000);srv.stdout.on('data',b=>{out+=b;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);res(m[1]);}});});
(async()=>{let browser;try{
 const base=await ready;browser=await chromium.launch(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{});
 const page=await browser.newPage({viewport:{width:1280,height:860}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.locator('.portal-world').waitFor();
 await page.evaluate(()=>DRAW.open());await page.locator('.draw-layer canvas').waitFor();
 assert.ok(await page.evaluate(()=>!!window.PEN_GUARD),'pen_guard.js 已加载');
 const counts=await page.evaluate(()=>{const c=document.querySelector('.draw-layer canvas');
  const f=(t,id,x,y)=>c.dispatchEvent(new PointerEvent(t,{pointerType:'pen',pointerId:id,clientX:x,clientY:y,bubbles:true,button:0,buttons:t==='pointerup'?0:1,pressure:t==='pointerup'?0:.5}));
  f('pointerdown',5,100,100);f('pointermove',5,140,110);
  f('pointerdown',5,100,200);f('pointerup',5,140,110);                 // 上一笔的抬笔晚到
  f('pointermove',5,160,210);f('pointermove',5,200,220);f('pointerup',5,200,220);
  f('pointermove',5,300,300);f('pointermove',5,330,320);f('pointermove',5,360,330);f('pointerup',5,360,330);   // 落笔被吞
  return {pts:DRAW.state.strokes.map(s=>s.pts.length),cur:!!DRAW.state.cur};});
 assert.deepEqual(counts.pts.length,3,'三笔都保存 '+JSON.stringify(counts));assert.ok(counts.pts[1]>=3,'新一笔没被晚到的抬笔收掉 '+counts.pts);assert.ok(counts.pts[2]>=3,'落笔被吞也补出这一笔 '+counts.pts);assert.equal(counts.cur,false);
 assert.deepEqual(errors,[]);console.log('PEN-DRAW-OK '+(subject||'法考'));
}catch(e){console.error(e);process.exitCode=1;}finally{await browser?.close();srv.kill();}})();
