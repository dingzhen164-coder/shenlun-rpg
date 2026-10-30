/* 套卷模考补充（2026-10-30）：草稿工具栏放进顶栏中间且按钮只有笔头、顶栏字号放大/缩小、选完答案自动跳下一题（可关、最后一题不跳）、
   删除套卷（整份删除，列表和大比记录都没有了）。隔离假HOME，自编130题，不连AI；电脑、平板横竖屏。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_exam_server.py'],{env:process.env});let logs='',browser,active;service.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let s='';const t=setTimeout(()=>reject(Error(logs||'考试服务未启动')),20000);service.stdout.on('data',x=>{s+=x;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);resolve(m[1]);}});service.on('exit',c=>{clearTimeout(t);reject(Error('服务退出 '+c+'\n'+logs));});});
const pos=p=>p.locator('[data-er-pos]').textContent();
async function openRoom(page){await page.evaluate(()=>go('bank'));await page.locator('.trial-hall').waitFor();if(await page.locator('dialog[open]').count())await page.keyboard.press('Escape');await page.locator('[data-th-enter=exam]').click();await page.locator('.er-paper').first().waitFor();}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,viewport]of [['desktop',{width:1280,height:860}],['tablet-landscape',{width:1280,height:800}],['tablet',{width:800,height:1280}]]){
  const page=await browser.newPage({viewport});active=page;page.setDefaultTimeout(10000);const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.evaluate(()=>{try{localStorage.removeItem('er.autoNext');localStorage.removeItem('chatLayout');}catch(_){}});await page.evaluate(()=>api('/api/exam/discard',{season:1001}));   // 上一个尺寸暂存的作答不带过来
  await openRoom(page);
  assert.equal(await page.locator('[data-er-start="1001"]').count(),1);
  await page.locator('[data-er-start="1001"]').click();await page.locator('dialog.er-run[open]').waitFor();
  // 草稿按钮：只有笔头图标，没有“草稿”二字
  const penText=(await page.locator('[data-er-pen]').innerText()).trim();assert.equal(penText,'',label+'：草稿按钮不显示文字');assert.equal(await page.locator('[data-er-pen] svg').count(),1);
  // 字号放大/缩小：初始110%＝原大小，放大后题干字号变大，缩小回去
  assert.equal(await page.locator('.er-bar .reading-size-tools output').textContent(),'110%');
  const fs=()=>page.locator('.er-question').evaluate(e=>parseFloat(getComputedStyle(e).fontSize));
  const base0=await fs();await page.locator('.er-bar [data-reading-size="10"]').click();const big=await fs();assert.ok(big>base0+0.5,label+'：放大后字号应变大 '+base0+'→'+big);
  await page.locator('.er-bar [data-reading-size="-10"]').click();assert.ok(Math.abs(await fs()-base0)<.2,label+'：缩小回到原大小');
  // 草稿工具栏：停在顶栏中间的空位，不盖住题目、也不盖住计时/答题卡
  await page.locator('[data-er-pen]').click();await page.locator('.draw-layer.on .draw-bar').waitFor();await page.waitForTimeout(700);
  const g=await page.evaluate(()=>{const r=s=>document.querySelector(s).getBoundingClientRect(),b=r('.draw-bar'),h=r('.er-bar'),c=r('[data-er-clock]'),k=r('[data-er-card]'),q=r('.er-body');
   return {bt:b.top,bb:b.bottom,bl:b.left,br:b.right,ht:h.top,hb:h.bottom,cl:c.left,kl:k.left,qt:q.top};});
  assert.ok(g.bt>=g.ht-1&&g.bb<=g.hb+2,label+'：草稿工具栏应在顶栏那一行里 '+JSON.stringify(g));
  assert.ok(g.br<=g.cl-4,label+'：不能盖住右边的计时 '+JSON.stringify(g));assert.ok(g.bb<=g.qt+2,label+'：不盖住题目');
  // 模拟字体晚加载使计时变宽（云端字体慢）：工具栏要自己重新避开，不能压住计时
  await page.evaluate(()=>{const c=document.querySelector('[data-er-clock]');c.style.paddingLeft='70px';});await page.waitForTimeout(400);
  const g2=await page.evaluate(()=>({br:document.querySelector('.draw-bar').getBoundingClientRect().right,cl:document.querySelector('[data-er-clock]').getBoundingClientRect().left}));
  assert.ok(g2.br<=g2.cl+1,label+'：计时变宽后工具栏仍压住计时 '+JSON.stringify(g2));
  await page.keyboard.press('Escape');await page.locator('.draw-layer.on').waitFor({state:'detached'}).catch(()=>{});
  // 选完答案自动跳下一题
  assert.ok((await pos(page)).includes('第 1/'),label);
  await page.locator('[data-er-choice="A"]').click();await page.waitForFunction(()=>document.querySelector('[data-er-pos]').textContent.includes('第 2/'));
  // 回头改选：选完同样自动跳到下一题
  await page.locator('[data-er-prev]').click();assert.ok((await pos(page)).includes('第 1/'));
  await page.locator('[data-er-choice="B"]').click();await page.waitForFunction(()=>document.querySelector('[data-er-pos]').textContent.includes('第 2/'));
  // 取消选择（再点同一个）不跳
  await page.locator('[data-er-prev]').click();await page.locator('[data-er-choice="B"]').click();await page.waitForTimeout(600);assert.ok((await pos(page)).includes('第 1/'),label+'：取消选择不应跳题');
  // 关掉开关后不再自动跳
  await page.locator('[data-er-card]').click();await page.locator('.er-sheet [data-er-auto]').uncheck();await page.locator('[data-er-sheet-close]').click();
  await page.locator('[data-er-choice="C"]').click();await page.waitForTimeout(600);assert.ok((await pos(page)).includes('第 1/'),label+'：关掉后不自动跳');
  await page.locator('[data-er-card]').click();await page.locator('.er-sheet [data-er-auto]').check();await page.locator('[data-er-sheet-close]').click();
  // 最后一题不跳
  await page.locator('[data-er-card]').click();await page.locator('.er-sheet .er-cell').last().click();await page.waitForFunction(()=>/第 130\/130/.test(document.querySelector('[data-er-pos]').textContent));
  await page.locator('[data-er-choice="A"]').click();await page.waitForTimeout(600);assert.ok(/第 130\/130/.test(await pos(page)),label+'：最后一题选完不跳');
  // 暂存离开，回到列表后删除整份套卷
  await page.locator('[data-er-leave]').click();await page.locator('.er-paper').first().waitFor();
  const before=await page.evaluate(()=>api('/api/exam/list',{}));assert.ok(before.papers.some(p=>p.season===1001&&p.deletable),label+'：导入的套卷可删除');
  if(label==='tablet'){          // 最后一个尺寸才删（同一个临时库，删了后面就没有卷子了）
   assert.equal(await page.locator('[data-er-delete="1001"]').count(),1,'每份导入的套卷有“删除”按钮');
   await page.locator('[data-er-delete="1001"]').click();await page.waitForFunction(()=>!document.querySelector('[data-er-start="1001"]'));
   const after=await page.evaluate(()=>api('/api/exam/list',{}));assert.ok(!after.papers.some(p=>p.season===1001),'删除后列表里没有这份卷');
   const mocks=await page.evaluate(()=>api('/api/mock'));assert.ok(!(mocks.seasons||[]).some(s=>s.season===1001),'宗门大比里这一季的记录也没有了');
   assert.ok(await page.locator('.er-ok').count()>=1,'删除后有提示');
  }
  assert.deepEqual(errors,[],label);await page.close();console.log(label+'：草稿工具栏在顶栏/字号放大缩小/自动跳下一题/删除套卷通过');
 }
}catch(e){if(active&&!active.isClosed())await active.screenshot({path:'ui-artifacts/exam-extras-failure.png'}).catch(()=>{});throw e;}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
