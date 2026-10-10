/* 实际浏览器交互验证：隔离库中抓取、书写、撤销、保存、手账重开和PDF导出。
   npm install --no-save playwright && npx playwright install chromium
   node tests/ui_articles.cjs；截图输出 ui-artifacts/（不提交用户数据）。 */
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

async function main() {
  const out = path.resolve('ui-artifacts'); fs.mkdirSync(out, { recursive: true });
  const server = spawn(process.env.PYTHON || 'python', ['tests/ui_article_server.py'], { env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  let logs = ''; server.stderr.on('data', b => { logs += b.toString(); });
  let browser;
  try {
    const base = await new Promise((resolve, reject) => {
      let text = ''; const timeout = setTimeout(() => reject(new Error('测试服务未启动: ' + logs)), 20000);
      server.stdout.on('data', b => { text += b.toString(); const m = text.match(/UI-READY (http:\/\/\S+)/); if (m) { clearTimeout(timeout); resolve(m[1]); } });
      server.on('exit', code => { clearTimeout(timeout); reject(new Error('测试服务退出 ' + code + ': ' + logs)); });
    });
    browser = await chromium.launch({ headless: true });
    const errors = [];
    const context = await browser.newContext({ viewport: { width: 1280, height: 860 } });
    const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message));
    page.on('dialog', d => d.accept());
    await page.goto(base); await page.locator('#nav [data-view="tianji"]').click();
    await page.locator('[data-tab="article"]').click(); await page.locator('#arCrawl').click();
    await page.locator('[data-count="15"]').click(); assert.equal(await page.locator('#arFetchCount').inputValue(), '15');
    await page.locator('#arFetchCount').fill('2'); await page.locator('#arFetchRange').selectOption('6m');
    await page.locator('[data-fetch-cat="科技"]').check();
    for (const cb of await page.locator('[data-fetch-src]').all()) await cb.uncheck();
    await page.locator('[data-fetch-src="本地测试源"]').check();
    await page.screenshot({ path: path.join(out, 'fetch-desktop-light.png'), fullPage: true });
    const sent = page.waitForRequest(r => r.url().endsWith('/api/articles/crawl') && r.method() === 'POST');
    await page.locator('#arFetchStart').click(); const payload = (await sent).postDataJSON();
    assert.equal(payload.count, 2); assert.equal(payload.range, '6m'); assert.deepEqual(payload.categories, ['科技']); assert.deepEqual(payload.sources, ['本地测试源']);
    await page.waitForFunction(() => document.querySelector('.ar-log')?.textContent.includes('本次新增 2 / 2'), { timeout: 15000 });
    await page.locator('#arCrawl').click(); assert.equal(await page.locator('#arFetchCount').inputValue(), '2'); await page.locator('#arCrawl').click();
    await page.locator('[data-open="abcd1234"]').click(); await page.locator('.nt-ink').first().waitFor();
    const first = page.locator('.nt-ink').first(); const rect = await first.boundingBox();
    await page.mouse.move(rect.x + 70, rect.y + 150); await page.mouse.down(); await page.mouse.move(rect.x + 260, rect.y + 180, { steps: 12 }); await page.mouse.up();
    await page.evaluate(() => NOTES.save());
    async function book() { const r = await page.request.post(base + '/api/notes/get', { data: { id: 'article-abcd1234' } }); return r.json(); }
    assert.equal((await book()).pages[0].strokes.length, 1);
    await page.locator('[data-act="undo"]').click(); await page.evaluate(() => NOTES.save()); assert.equal((await book()).pages[0].strokes.length, 0);
    await page.locator('[data-act="redo"]').click(); await page.evaluate(() => NOTES.save()); assert.equal((await book()).pages[0].strokes.length, 1);
    await page.locator('[data-tool="hl"]').click();
    await first.evaluate(el => {
      const r = el.getBoundingClientRect();
      for (const [type,x] of [['pointerdown',100],['pointermove',180],['pointerup',210]]) el.dispatchEvent(new PointerEvent(type,{pointerType:'pen',pointerId:9,clientX:r.left+x,clientY:r.top+220,bubbles:true,button:0}));
    });
    await page.evaluate(() => NOTES.save()); const withPen = await book(); assert.equal(withPen.pages[0].strokes.length, 2); assert.equal(withPen.pages[0].strokes[1].t, 'hl');
    await first.evaluate(el => {
      const r = el.getBoundingClientRect();
      for (const [type,y] of [['pointerdown',300],['pointermove',280],['pointerup',280]]) el.dispatchEvent(new PointerEvent(type,{pointerType:'touch',pointerId:10,clientX:r.left+100,clientY:r.top+y,bubbles:true,button:0}));
    });
    await page.evaluate(() => NOTES.save()); assert.equal((await book()).pages[0].strokes.length, 2, '手指只翻页不能新增笔画');
    await page.locator('.ar-typed summary').click(); await page.locator('#ntArticleText').fill('从实际需要出发，让技术创新落到服务群众的具体行动中。');
    await page.locator('#arBack').click(); await page.locator('[data-open="abcd1234"]').click(); await page.locator('#ntArticleText').waitFor({state:'attached'});
    assert.equal(await page.locator('#ntArticleText').inputValue(), '从实际需要出发，让技术创新落到服务群众的具体行动中。');
    assert.equal((await book()).pages[0].strokes.length, 2);
    await page.locator('#arSideToggle').click(); assert.equal(await page.locator('#arSide').isVisible(), false); await page.locator('#arSideToggle').click();
    await page.locator('#ntFull').click(); assert.equal(await page.locator('html').evaluate(el=>el.classList.contains('nt-full')), true); await page.locator('#ntFull').click();
    const pdfResult = page.waitForResponse(r => r.url().endsWith('/api/notes/pdf') && r.request().method() === 'POST');
    await page.locator('#ntPdf').click(); const pdf = await (await pdfResult).json(); assert.ok(!pdf.error, pdf.error); assert.equal(pdf.pages, (await book()).pages.length + 1);
    const file = await page.request.get(base + pdf.url); assert.equal(file.status(), 200); const data = await file.body(); assert.ok(data.subarray(0,4).equals(Buffer.from('%PDF'))); fs.writeFileSync(path.join(out, 'article-notes.pdf'), data);
    await page.locator('.nt-pdf-toast [data-o="x"]').click();
    for (const [name, width, height] of [['desktop',1280,860],['tablet',800,1280]]) {
      await page.setViewportSize({width,height});
      for (const theme of ['light','dark']) {
        await page.evaluate(t => { localStorage.setItem('xrpg-theme',t); document.documentElement.dataset.theme=t; dispatchEvent(new Event('resize')); }, theme);
        await page.screenshot({path:path.join(out,`read-${name}-${theme}.png`),fullPage:true});
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1), '页面不能横向溢出');
        const canvases = await page.locator('.nt-page').first().evaluate(el=>({w:el.clientWidth,ink:el.querySelector('.nt-ink').style.width})); assert.ok(canvases.w>0);
      }
    }
    await page.locator('#arLedger').click(); await page.locator('[data-nb="article-abcd1234"]').waitFor();
    assert.equal((await book()).pages[0].strokes.length,2);
    await page.locator('[data-nb="article-abcd1234"]').click(); await page.locator('.nt-ink').first().waitFor();
    await page.screenshot({path:path.join(out,'ledger-tablet-dark.png'),fullPage:true});
    // 强制旧版本写入必须失败，新笔迹及正文仍在。
    const saved = await book(); const stale = await page.request.post(base+'/api/notes/save',{data:{...saved,revision:saved.revision-1,text:'过期内容'}});
    assert.ok((await stale.json()).error); assert.equal((await book()).text,saved.text);
    assert.deepEqual(errors, []); fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({passed:true,screenshots:7,checks:['合计抓取/条件记忆','钢笔/荧光笔','撤销重做','手指翻页不写字','自动保存/重开','精读收起/全屏','PDF导出','电脑平板明暗主题','公务手账接续','过期版本拒绝']},null,2));
    console.log('ARTICLE-UI-OK');
  } finally { if (browser) await browser.close(); server.kill(); }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
