/* 参阅室（每日文章阅读页）：文章能滚动（手指拖动）、题头/工具条压缩、五步精读、存入摘编→档案室翻阅、名字叫“参阅室”。
   隔离假库，不连AI。电脑 1280×860、平板横屏 1280×800、平板竖屏 800×1280，明暗各一。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_article_server.py'],{env:{...process.env,PYTHONIOENCODING:'utf-8'}});let browser,logs='';service.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let s='';const t=setTimeout(()=>reject(Error(logs||'临时服务未启动')),20000);service.stdout.on('data',x=>{s+=x;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);resolve(m[1]);}});service.on('exit',c=>{clearTimeout(t);reject(Error('服务退出 '+c+'\n'+logs));});});
const SIZES=[['电脑',1280,860],['平板横屏',1280,800],['平板竖屏',800,1280]];let activePage,activeTag='';
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [name,width,height]of SIZES)for(const theme of ['light','dark']){
  const ctx=await browser.newContext({viewport:{width,height},hasTouch:name!=='电脑'}),page=await ctx.newPage(),errors=[];activePage=page;page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.goto(base);await page.evaluate(t=>{document.documentElement.dataset.theme=t;},theme);
  await page.evaluate(()=>go('tianji'));await page.locator('[data-open="abcd1234"]').waitFor();
  const tag=`${name}·${theme}`;activeTag=tag;
  // 名字：申论里叫“参阅室”，不再出现“天机台”
  assert.equal(await page.evaluate(()=>document.documentElement.innerHTML.includes('天机台')),false,tag+'：页面里不应出现“天机台”');
  assert.equal(await page.evaluate(()=>{const h=document.querySelector('.tj-head');return !!h&&getComputedStyle(h).display!=='none';}),false,tag+'：列表页也不再重复显示“每日文章”大标题块');
  await page.locator('[data-open="abcd1234"]').click();await page.locator('.nt-page').first().waitFor();
  // 阅读页：整页不溢出、文章区是真正的滚动容器
  const m=await page.evaluate(()=>{const r=s=>{const e=document.querySelector(s);if(!e)return null;const b=e.getBoundingClientRect();return {y:b.y,h:b.height,w:b.width};},p=document.querySelector('.nt-pages'),v=document.querySelector('#view');
   return {pages:r('.nt-pages'),sh:p.scrollHeight,ch:p.clientHeight,ov:getComputedStyle(p).overflowY,rhead:r('.ar-rhead'),bar:r('.nt-bar'),hud:r('#studyHud'),vh:innerHeight,vw:innerWidth,sw:document.documentElement.scrollWidth,tjhead:!!document.querySelector('.tj-head')&&getComputedStyle(document.querySelector('.tj-head')).display!=='none',viewOverflow:v.scrollHeight-v.clientHeight};});
  assert.ok(m.sh>m.ch+50,tag+'：文章应比可视区长');assert.ok(/auto|scroll/.test(m.ov),tag+'：.nt-pages 必须是滚动容器');
  assert.ok(m.sw<=m.vw+1,tag+'：横向溢出');assert.equal(m.tjhead,false,tag+'：阅读时不再显示“每日文章”大标题块');
  assert.ok(m.viewOverflow<=2,tag+'：整页内容不能被裁掉 '+m.viewOverflow);
  assert.ok(m.hud.h<=44,tag+'：顶部只留细条 '+m.hud.h);assert.ok(m.rhead.h<=60,tag+'：题头一行 '+m.rhead.h);
  assert.ok(m.pages.h>=m.vh*(name==='平板竖屏'?.42:.5),tag+'：文章区占比太小 '+Math.round(m.pages.h)+'/'+m.vh);
  // 滚动：脚本滚动 + 手指拖动（笔记本页面是 touch-action:none，靠脚本拖动）
  await page.evaluate(()=>{document.querySelector('.nt-pages').scrollTop=0;});
  if(name!=='电脑'){
   const box=await page.evaluate(()=>{const r=document.querySelector('.nt-pages').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height-60};});
   const cdp=await ctx.newCDPSession(page);await cdp.send('Input.synthesizeScrollGesture',{x:box.x,y:box.y,yDistance:-200,gestureSourceType:'touch'});
   await page.waitForFunction(()=>document.querySelector('.nt-pages').scrollTop>50,null,{timeout:4000}).catch(()=>{});
   assert.ok(await page.evaluate(()=>document.querySelector('.nt-pages').scrollTop)>50,tag+'：手指上滑文章应该滚动，不能卡住');
  }else{await page.mouse.move(m.pages.w/2,m.pages.y+100);await page.mouse.wheel(0,400);await page.waitForFunction(()=>document.querySelector('.nt-pages').scrollTop>100);}
  // 一键精读（五步）：新版显示五步，没有第六步；旧版显示提示
  const side=await page.locator('#arSide').innerText();
  for(const t of ['第1步 · 圈核心概念','第2步 · 拆行文骨架','第3步 · 挖万能对策','第4步 · 记黄金句式','第5步 · 做题型映射'])assert.ok(side.includes(t),tag+'：缺 '+t);
  assert.ok(!side.includes('第6步')&&!side.includes('模拟输出'),tag+'：第六步由用户自己做，不显示');assert.ok(!/分钟/.test(await page.locator('.ar-step > summary').allInnerTexts().then(a=>a.join(''))),tag+'：不显示建议用时');
  assert.equal(await page.locator('#arSide').evaluate(e=>e.innerHTML.includes('玉简')),false,tag+'：不再出现“玉简”');
  // 存入摘编 → 档案室「摘编」翻阅
  if(name==='电脑'&&theme==='light'){
   await page.locator('#arDigest').click();await page.locator('#arDigestGo').waitFor();
   await page.locator('#arDigestGo').click();await page.locator('.dg-root').waitFor();
   const dg=await page.locator('.dg-root').innerText();assert.ok(dg.includes('民生')&&dg.includes('治理')&&dg.includes('保留人工窗口'),'摘编按领域列出对策');
   await page.locator('[data-dg-mode="quote"]').click();assert.ok((await page.locator('#dgBody').innerText()).includes('不能只看系统上线了多少功能'),'摘编里能翻到黄金句式');
   await page.locator('[data-dg-mode="art"]').click();assert.ok((await page.locator('#dgBody').innerText()).includes('让科技服务走进基层'));
   assert.equal(await page.locator('.dg-root button:not([data-dg-mode]):not([data-dg-rm])').count(),0,'摘编只翻阅，没有别的写入按钮');
   assert.equal(await page.evaluate(()=>api('/api/cards').then(c=>JSON.stringify(c).includes('每日文章'))),false,'摘编不生成复习卡片');
  }
  // 旧版精读兼容
  await page.evaluate(()=>go('tianji'));await page.locator('.ar-read,[data-open]').first().waitFor();if(await page.locator('.ar-read').count()){await page.locator('#arBack').click();await page.locator('.ar-read').waitFor({state:'detached'});await page.waitForTimeout(300);}await page.locator('[data-open="beef0001"]').click();await page.locator('#arSide').waitFor();
  assert.ok((await page.locator('#arSide').innerText()).includes('旧版精读'),tag+'：旧版精读照常显示并提示重新精读');
  assert.deepEqual(errors,[],tag);await ctx.close();
 }
 console.log('参阅室阅读页：滚动/压缩布局/五步精读/摘编/改名 电脑与平板横竖屏明暗通过');
}catch(e){console.error('失败于：'+activeTag);if(activePage&&!activePage.isClosed())await activePage.screenshot({path:process.env.READER_FAIL||'ui-artifacts/reader-failure.png'}).catch(()=>{});throw e;}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
