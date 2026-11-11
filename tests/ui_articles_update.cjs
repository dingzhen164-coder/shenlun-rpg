/* 参阅室（2026-11-11 用户需求）：新排版（段间空、行距大）、精读栏自己编辑并写回 .md、手写精读存入摘编、
   批注不再闪“待保存/已保存”且停笔 3 秒只存改动的页、翻页立刻存；精读栏横屏可拖宽度并记住、竖屏是抽屉；
   旧内核（强制兜底 + 不认 :has）下文章区照样定高、手指能滑、大标题卡隐藏。隔离假库，不连 AI。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_article_server.py'],{env:{...process.env,PYTHONIOENCODING:'utf-8'}});let logs='';service.stderr.on('data',x=>logs+=x);
const ready=new Promise((ok,no)=>{let s='';const t=setTimeout(()=>no(Error(logs)),20000);service.stdout.on('data',x=>{s+=x;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});service.on('exit',c=>{clearTimeout(t);no(Error('exit '+c+logs));});});
async function openArticle(page,base,query=''){await page.goto(base+query);await page.waitForFunction(()=>typeof go==='function');await page.evaluate(()=>go('tianji'));await page.locator('[data-open="abcd1234"]').click();await page.locator('.nt-page').first().waitFor();await page.waitForTimeout(500);}
(async()=>{let browser;try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 // ---- 电脑：排版、编辑精读、存盘方式、拖宽度 ----
 {const ctx=await browser.newContext({viewport:{width:1280,height:860}}),page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await openArticle(page,base);
  const book=await page.evaluate(()=>api('/api/notes/get',{id:'article-abcd1234'}));
  assert.equal(book.article.layout,3,'新排版');assert.ok(book.pages[0].article_lines.includes(''),'段与段之间空半行');assert.ok(book.pages.every(p=>p.article_top>0));
  // 存盘：写一笔后不显示状态字；3 秒内不存，之后只送改动的页
  const saves=[];page.on('request',r=>{if(r.url().endsWith('/api/notes/save'))saves.push(JSON.parse(r.postData()||'{}'));});
  const c=await page.locator('.nt-ink').first().boundingBox();
  await page.mouse.move(c.x+c.width*.3,c.y+c.height*.4);await page.mouse.down();await page.mouse.move(c.x+c.width*.4,c.y+c.height*.42,{steps:6});await page.mouse.up();
  assert.equal(await page.locator('#ntSaveStatus').isVisible(),false,'写字时不显示待保存');
  await page.waitForTimeout(1800);assert.equal(saves.length,0,'停笔不到 3 秒不存');
  await page.waitForFunction(()=>true);await page.waitForTimeout(1800);
  assert.equal(saves.length,1,'停笔 3 秒后存一次');assert.ok(saves[0].page_patch&&!saves[0].pages,'只送改动的页');assert.deepEqual(Object.keys(saves[0].page_patch),['0']);
  assert.equal(await page.locator('#ntSaveStatus').isVisible(),false,'存完也不显示已保存');
  // 翻页立刻存：在第一页写一笔，马上滚到第二页
  await page.mouse.move(c.x+c.width*.3,c.y+c.height*.5);await page.mouse.down();await page.mouse.move(c.x+c.width*.35,c.y+c.height*.52,{steps:5});await page.mouse.up();
  await page.evaluate(()=>{const b=document.querySelector('.nt-pages'),p=b.querySelectorAll('.nt-page')[1];b.scrollTop=p.offsetTop-b.offsetTop+10;});
  await page.waitForFunction(n=>window.__saves===undefined,null).catch(()=>{});await page.waitForTimeout(700);
  assert.equal(saves.length,2,'翻页立刻存');
  const after=await page.evaluate(()=>api('/api/notes/get',{id:'article-abcd1234'}));assert.equal(after.pages[0].strokes.length,2,'两笔都存上了');assert.deepEqual(after.pages[0].article_lines,book.pages[0].article_lines,'原文行不被网页改动');
  // 编辑精读：AI 精读转成文字放进编辑框，改了保存写回 .md
  await page.locator('#arEdit').click();const draft=await page.locator('#arJdText').inputValue();assert.match(draft,/第三步 · 挖万能对策/);assert.match(draft,/打通部门数据/);
  await page.locator('#arJdText').fill('## 第三步 · 挖万能对策\n- 自编对策：上门代办\n\n## 第四步 · 记黄金句式（金句）\n- 自编金句：群众少跑腿\n');
  await page.locator('#arJdSave').click();await page.locator('.ar-jd-md').waitFor();
  assert.match(await page.locator('.ar-jd-md').innerText(),/上门代办/);
  const got=await page.evaluate(()=>api('/api/articles/get',{id:'abcd1234'}));assert.match(got.jd_md,/上门代办/,'写回文章 .md 的“## 精读”段');
  await page.locator('#arDigest').click();await page.locator('#arDigestGo').waitFor();
  const dg=await page.evaluate(()=>api('/api/articles/digest').then(d=>d.items.find(x=>x.id==='abcd1234')));
  assert.deepEqual(dg.countermeasures.map(x=>x.direction),['自编对策：上门代办']);assert.deepEqual(dg.quotes.map(x=>x.text),['自编金句：群众少跑腿']);
  // 精读栏宽度：默认 30%，拖动后记住
  const w0=await page.evaluate(()=>{const c=document.querySelector('.ar-cols').getBoundingClientRect(),s=document.querySelector('#arSide').getBoundingClientRect();return s.width/c.width;});
  assert.ok(Math.abs(w0-0.3)<0.03,'精读栏默认约 30% '+w0.toFixed(2));
  const sp=await page.locator('#arSplit').boundingBox();await page.mouse.move(sp.x+sp.width/2,sp.y+sp.height/2);await page.mouse.down();await page.mouse.move(sp.x-150,sp.y+sp.height/2,{steps:6});await page.mouse.up();
  const w1=await page.evaluate(()=>{const c=document.querySelector('.ar-cols').getBoundingClientRect(),s=document.querySelector('#arSide').getBoundingClientRect();return s.width/c.width;});assert.ok(w1>w0+0.08,'拖宽了');
  await openArticle(page,base);
  const w2=await page.evaluate(()=>{const c=document.querySelector('.ar-cols').getBoundingClientRect(),s=document.querySelector('#arSide').getBoundingClientRect();return s.width/c.width;});assert.ok(Math.abs(w2-w1)<0.03,'重进后宽度记住');
  assert.match(await page.locator('.ar-jd-md').innerText(),/上门代办/,'重进显示自己写的精读');
  // 更多菜单里的项目
  await page.locator('.ar-more > summary').click();for(const id of ['#arCat','#arStar','#arLedger','#arPdf','#arDel'])assert.ok(await page.locator('.ar-more-list '+id).isVisible(),'更多里有 '+id);
  assert.deepEqual(errors,[]);await ctx.close();console.log('参阅室 电脑：新排版/存盘只送改动页且不闪状态/翻页即存/编辑精读写回md/手写精读存摘编/精读栏拖宽记住 通过');}
 // ---- 平板竖屏：精读栏是抽屉；旧内核 + 不认 :has 时仍定高、手指能滑 ----
 for(const [label,query] of [['平板竖屏',''],['平板竖屏·旧内核',"/?legacycss=1&nohas=1"]]){
  const ctx=await browser.newContext({viewport:{width:800,height:1280},hasTouch:true}),page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await openArticle(page,base,query);
  if(query)assert.ok(await page.evaluate(()=>document.documentElement.classList.contains('legacy-has')),'走了 :has 替身');
  const m=await page.evaluate(()=>{const p=document.querySelector('.nt-pages'),r=p.getBoundingClientRect(),h=document.querySelector('.tj-head');return {top:r.top,h:r.height,sh:p.scrollHeight,ch:p.clientHeight,vh:innerHeight,tj:!!h&&getComputedStyle(h).display!=='none',bars:document.querySelectorAll('.ar-rhead').length,barH:document.querySelector('.nt-bar').getBoundingClientRect().height};});
  assert.equal(m.tj,false,label+'：大标题卡隐藏');assert.equal(m.bars,0,label+'：题头不单独占一行');assert.ok(m.barH<=50,label+'：工具栏一行 '+m.barH);
  assert.ok(m.sh>m.ch+50&&m.h>=m.vh*.74,label+'：文章区定高并占大部分 '+Math.round(m.h)+'/'+m.vh);
  assert.equal(await page.locator('#arSide').isVisible(),false,label+'：竖屏精读栏默认收起');
  await page.locator('#arSideToggle').click();await page.locator('#arSide').waitFor();
  const d=await page.evaluate(()=>{const s=document.querySelector('#arSide').getBoundingClientRect(),p=document.querySelector('.nt-pages').getBoundingClientRect();return {sw:s.width,pw:p.width,right:s.right,vw:innerWidth};});
  assert.ok(d.pw>=d.vw*.9,label+'：抽屉盖在文章上，不挤文章');assert.ok(d.right<=d.vw+1,label+'：抽屉在屏幕内');
  await page.locator('#arSideToggle').click();
  // 手指滑文章（CDP 触摸手势）
  const box=await page.evaluate(()=>{const r=document.querySelector('.nt-pages').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height-80};});
  const cdp=await ctx.newCDPSession(page);await cdp.send('Input.synthesizeScrollGesture',{x:box.x,y:box.y,yDistance:-300,gestureSourceType:'touch'});
  await page.waitForFunction(()=>document.querySelector('.nt-pages').scrollTop>50,null,{timeout:4000}).catch(()=>{});
  assert.ok(await page.evaluate(()=>document.querySelector('.nt-pages').scrollTop)>50,label+'：手指滑得动文章');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),label+'：无横向溢出');
  assert.deepEqual(errors,[]);await ctx.close();console.log(`参阅室 ${label}：抽屉精读栏/工具栏一行/定高/手指滑动 通过`);
 }
}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exit(1);});
