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
 assert.ok((await page.locator('.sl-material-stats').textContent()).includes('待确认 1 题'));
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
 // 专注书写：材料栏收起、红格占满，工具条仍在；再点恢复。不再有独立全屏层
 await page.locator('[data-card="expand"]').click();
 assert.equal(await page.locator('.sl-card-expanded').count(),0);
 const focus=await page.evaluate(()=>({m:document.querySelector('.sl-materials').getBoundingClientRect().width,w:document.querySelector('.sl-writing').getBoundingClientRect().width,vw:innerWidth}));
 assert.ok(focus.m<5&&focus.w>focus.vw*.9,'专注书写应收起材料栏 '+JSON.stringify(focus));
 assert.ok(await page.locator('[data-card="pen"]').isVisible());await shot('5-focus');
 await page.locator('[data-card="expand"]').click();
 assert.ok((await page.locator('.sl-materials').boundingBox()).width>200);
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
 // 批改后：“查看批改/返回作答”切换，评分标准校准可用且不计成绩
 await page.locator('#slBack').click();await open(0);
 await page.locator('#slAns').fill('走访居民了解需求，推动部门共享资料。');await page.locator('#slDraftSave').click();await page.locator('#slSaveStatus').filter({hasText:'已保存'}).waitFor();
 assert.equal(await page.locator('#slViewResult').isVisible(),false);
 await page.locator('#slSubmit').click();await page.locator('.sl-review-total').waitFor({timeout:8000}).catch(async e=>{console.log('SLRES:',await page.locator('#slRes').textContent(),await page.locator('#slViewResult').count());throw e;});
 assert.ok((await page.locator('#slViewResult').textContent()).includes('返回作答'));
 await page.locator('#slViewResult').click();await page.locator('#slAns').waitFor();assert.ok((await page.locator('#slViewResult').textContent()).includes('查看批改'));
 await page.locator('#slViewResult').click();await page.locator('.sl-calibrate summary').click();await page.locator('#slCalibrateRun').click();
 await page.locator('.sl-calibrate-body').filter({hasText:'得分率'}).waitFor();await shot('6-calibrate');
 // 大作文助手：立意拆解 + 提纲点评；小题没有入口
 assert.equal(await page.locator('#slEssay').count(),0);
 await page.locator('#slBack').click();await open(3);
 await page.locator('#slEssay').click();await page.locator('#slEssayAnglesRun').click();await page.locator('#slEssayAngles').filter({hasText:'以人为本'}).waitFor();
 await page.locator('#slEssayOutline').fill('中心论点：服务要以居民需求为中心。\n分论点：简化流程。');await page.locator('#slEssayReview').click();
 await page.locator('#slEssayReviewBox').filter({hasText:'先补全中心论点'}).waitFor();
 await shot('4-essay');await page.locator('[data-essay-close]').click();
 assert.deepEqual(errors,[]);
 }finally{await browser?.close();server.kill();}
}
main().catch(e=>{console.error(e);process.exit(1);});
