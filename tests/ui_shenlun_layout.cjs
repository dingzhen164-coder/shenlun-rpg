/* 申论作答页版面：材料按题匹配与页签、工具条固定、不再有滚动模式、电脑/平板横竖屏。仅自编材料与假AI。 */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
async function main(){
 const shots=process.env.SL_SHOTS?path.resolve(process.env.SL_SHOTS):'';if(shots)fs.mkdirSync(shots,{recursive:true});
 const server=spawn(process.env.PYTHON||'python',['tests/ui_shenlun_layout_server.py'],{env:{...process.env,PYTHONIOENCODING:'utf-8'}});
 let logs='',browser;server.stderr.on('data',b=>logs+=b);
 try{
 const base=await new Promise((resolve,reject)=>{let t='';const timeout=setTimeout(()=>reject(Error(logs)),20000);server.stdout.on('data',b=>{t+=b;const m=t.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timeout);resolve(m[1]);}});server.on('exit',code=>{clearTimeout(timeout);reject(Error('server exit '+code+logs));});});
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||undefined});
 const page=await browser.newPage({viewport:{width:1280,height:860}});require('./fixed_ui_helpers.cjs').install(page);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.evaluate(()=>go('skeleton'));await page.locator('[data-libtab="bank"]').click();await page.locator('#slBankRefresh').click();
 await page.locator('#slFilterRegion').selectOption('验证专用');
 const open=async n=>{await page.locator('.sl-paper summary').filter({hasText:'2026版面验证自编卷'}).click().catch(()=>{});await page.locator('.sl-paper-q').nth(n).locator('[data-slq]').click();await page.locator('#slAns').waitFor();await page.waitForFunction(()=>document.querySelector('.sl-material-ink')?.width===800);};
 const shot=async name=>{if(shots)await page.screenshot({path:path.join(shots,name+'.png')});};
 const sizes=[['desktop',1280,860],['tablet-landscape',1280,800],['tablet-portrait',800,1280]];
 // 第1题：题干写明资料2，只显示材料2；批改也只用它
 await open(0);
 assert.equal(await page.locator('.sl-material-sheet').count(),1);
 assert.ok((await page.locator('.sl-material-scroll').textContent()).includes('材料2'));
 assert.ok((await page.locator('.sl-material-notice').textContent()).includes('题干写明'));
 // 笔工具在顶栏固定：红格滚到底后仍可见，且没有“滚动模式”
 assert.equal(await page.locator('[data-card="scroll"]').count(),0);
 for(const [name,w,h] of sizes){
  await page.setViewportSize({width:w,height:h});await page.waitForTimeout(250);
  const m=await page.evaluate(()=>{const r=s=>{const e=document.querySelector(s);if(!e)return null;const b=e.getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height};};return {mat:r('.sl-materials'),wr:r('.sl-writing'),ink:r('.sl-card-ink'),pen:r('[data-card="pen"]'),head:r('.sl-exam-heading'),vw:innerWidth,vh:innerHeight,sw:document.documentElement.scrollWidth};});
  assert.ok(m.sw<=m.vw+1,name+' 横向溢出');
  assert.ok(m.head.h<=Math.max(150,m.vh*.2),name+' 题干卡过高 '+m.head.h);
  assert.ok(m.pen&&m.pen.y>=0&&m.pen.y+m.pen.h<=m.vh,name+' 笔按钮不在屏内');
  if(w>=1000)assert.ok(m.mat.w<m.wr.w,name+' 作答区应宽于材料区');
  if(w<900)assert.ok(m.mat.y+m.mat.h<=m.wr.y+2,name+' 竖屏应上材料下红格');
  await page.evaluate(()=>{const s=document.querySelector('.sl-writing .fx-scroll')||document.querySelector('.sl-writing');s.scrollTop=s.scrollHeight;});
  const after=await page.locator('[data-card="pen"]').boundingBox();assert.ok(after.y>=0&&after.y<m.vh,name+' 滚动后笔按钮丢失');
  await page.evaluate(()=>{const s=document.querySelector('.sl-writing .fx-scroll')||document.querySelector('.sl-writing');s.scrollTop=0;});
  await shot('1-'+name);
 }
 await page.setViewportSize({width:1280,height:860});
 // 手指默认滚动红格、不画笔；勾选后才书写
 const ink=page.locator('.sl-card-ink');await ink.scrollIntoViewIfNeeded();
 assert.equal(await page.locator('#slFinger').isChecked(),false);
 // 第2题：资料1～3，三个页签
 await page.locator('#slBack').click();await open(1);
 assert.equal(await page.locator('[data-mat-tab]').count(),3);
 await page.locator('[data-mat-tab="2"]').click();
 assert.equal(await page.locator('[data-mat-article]:not(.sl-mat-off)').getAttribute('data-mat-article'),'2');
 const tb=await page.locator('.sl-material-toolbar').boundingBox();assert.ok(tb.height<=130,'材料工具条过高 '+tb.height);
 assert.equal(await page.locator('.fx-exam-switch').isVisible(),false);
 assert.equal(await page.locator('[data-mat-tab="2"]').getAttribute('aria-selected'),'true');
 await shot('2-tabs');
 // 第3题：题干只有来源库ID，无法匹配 → 整卷并提示选定；手动选定后只剩材料4
 await page.locator('#slBack').click();await open(2);
 assert.equal(await page.locator('[data-mat-tab]').count(),4);
 await page.locator('#slMaterialPick').click();await page.locator('.sl-material-dialog input[value="4"]').check();await page.locator('#slPickOk').click();
 await page.locator('.sl-material-notice').filter({hasText:'已按你的选择'}).waitFor();await page.waitForFunction(()=>document.querySelector('.sl-material-ink')?.width===800);
 assert.equal(await page.locator('.sl-material-sheet').count(),1);
 await shot('3-picked');
 assert.deepEqual(errors,[]);
 }finally{await browser?.close();server.kill();}
}
main().catch(e=>{console.error(e);process.exit(1);});
