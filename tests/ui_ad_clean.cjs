/* 藏经阁「清除」（行测）：输入广告文字 → 查找 → 勾选 → 清除 → 撤销；加入广告词库；块不用 .card。隔离假库，不连AI；电脑、平板横竖屏 + 明暗。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_exam_server.py','--ads'],{env:process.env});let logs='',browser,active;service.stderr.on('data',x=>logs+=x);
const ready=new Promise((resolve,reject)=>{let s='';const t=setTimeout(()=>reject(Error(logs||'服务未启动')),20000);service.stdout.on('data',x=>{s+=x;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);resolve(m[1]);}});service.on('exit',c=>{clearTimeout(t);reject(Error('服务退出 '+c+'\n'+logs));});});
const AD='一手最全公考资源加微信 biguo368';
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,viewport,theme]of [['desktop',{width:1280,height:860},'light'],['tablet-landscape',{width:1280,height:800},'dark'],['tablet',{width:800,height:1280},'light']]){
  const page=await browser.newPage({viewport});active=page;page.setDefaultTimeout(10000);const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.evaluate(t=>{document.documentElement.dataset.theme=t;},theme);
  await page.evaluate(()=>{LIB.tab='adclean';return go('skeleton');});await page.locator('.ac-root').waitFor();
  assert.equal(await page.locator('[data-libtab="adclean"]').count(),1,label+'：行测档案室有“清除”页签');
  assert.equal(await page.locator('.ac-root .card').count(),0,label+'：清除页的块不用 .card');
  // 查找：忽略空白
  await page.locator('#acText').fill('一手最全公考资源加微信biguo368');await page.locator('#acFind').click();await page.locator('.ac-hit').first().waitFor();
  assert.equal(await page.locator('.ac-hit').count(),2,label+'：两处广告');
  assert.ok((await page.locator('.ac-summary').innerText()).includes('找到 2 处'));
  assert.equal(await page.locator('.ac-tag.ac-warn').count(),1,label+'：夹在句中的那处提示请核对');
  assert.equal(await page.locator('.ac-ctx mark').count(),2,label+'：命中处高亮');
  const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2&&[...document.querySelectorAll('.ac-root button,.ac-root input')].every(e=>{const r=e.getBoundingClientRect();return !r.width||(r.right<=innerWidth+1&&r.left>=-1);}));
  assert.ok(fits,label+'：不横向溢出');
  if(label==='tablet'){          // 最后一个尺寸才真清（同一个临时库，清了后面就查不到了）
   // 只清一处 → 撤销 → 全清；然后加入词库
   await page.locator('.ac-hit input').nth(1).uncheck();assert.equal(await page.locator('[data-ac-count]').textContent(),'1');
   await page.locator('[data-ac-clean]').click();await page.locator('.ac-summary').filter({hasText:'找到 1 处'}).waitFor();
   await page.locator('[data-ac-undo]').click();await page.locator('.ac-search').waitFor();
   await page.locator('#acText').fill(AD);await page.locator('#acFind').click();await page.locator('.ac-hit').first().waitFor();assert.equal(await page.locator('.ac-hit').count(),2,'撤销后两处都回来了');
   await page.locator('[data-ac-clean]').click();await page.locator('.ac-note').waitFor();
   assert.ok((await page.locator('.ac-note').innerText()).includes('没有找到'),'清完之后查不到了');
   assert.ok(await page.locator('[data-ac-undo]').count()===1,'清除后可以撤销');
   await page.locator('#acText').fill(AD);await page.locator('#acFind').click();
   await page.locator('.ac-note').waitFor();
   await page.getByText('＋ 以后导入自动清除这段文字').click();await page.locator('.ac-words li').waitFor();
   assert.ok((await page.locator('.ac-words').innerText()).includes('biguo368'),'词库里有这一条');
   const words=await page.evaluate(()=>api('/api/adclean/status',{}));assert.equal(words.words.length,1);
  }
  assert.deepEqual(errors,[],label);await page.close();console.log(label+'：清除页签 查找/勾选/清除/撤销/词库 通过');
 }
}catch(e){if(active&&!active.isClosed())await active.screenshot({path:'ui-artifacts/ad-clean-failure.png'}).catch(()=>{});throw e;}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
