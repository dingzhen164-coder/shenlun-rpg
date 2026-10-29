/* 旧内核兜底（web/legacy_css.js）：强制走改写路径，检查样式表里没有 color-mix/dvh、磨砂底板仍有底色、答题页铺满屏幕、页面无脚本报错。
   用法：node tests/ui_legacy_css.cjs [行测|申论] */
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const assert = require('node:assert/strict');
(async () => {
  const subject = process.argv[2] || '行测';
  const srv = spawn(process.env.PYTHON || 'python3', ['tests/ui_layout_server.py', subject], { env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  const base = await new Promise((res, rej) => { let t = ''; const timer = setTimeout(() => rej(Error('服务没起来')), 25000);
    srv.stdout.on('data', (b) => { t += b; const m = t.match(/UI-READY (\S+)/); if (m) { clearTimeout(timer); res(m[1]); } }); });
  const browser = await chromium.launch();
  try {
    for (const [w, h] of [[1280, 860], [800, 1280], [1280, 800]]) {
      const page = await browser.newPage({ viewport: { width: w, height: h } });
      const errors = [];
      page.on('pageerror', (e) => errors.push(e.message));
      await page.goto(base + '/?legacycss=1'); await page.waitForTimeout(1500);
      await page.evaluate(() => document.querySelectorAll('.cer-ok').forEach((b) => b.click()));
      const info = await page.evaluate(() => {
        const styles = [...document.querySelectorAll('style[data-legacy-from]')];
        const text = styles.map((s) => s.textContent).join('\n');
        return { legacy: document.documentElement.classList.contains('legacy-css'), n: styles.length, links: document.querySelectorAll('link[rel="stylesheet"]').length,
                 mix: /color-mix\(/.test(text), dvh: /\ddvh\b/.test(text) };
      });
      assert(info.legacy && info.n > 10, `${w}x${h} 没有走改写路径 ${JSON.stringify(info)}`);
      assert.equal(info.links, 0, '样式表应全部被换成内联');
      assert(!info.mix && !info.dvh, '改写后仍有 color-mix/dvh');
      for (const v of ['home', 'dwelling', 'contest']) {
        await page.evaluate((x) => go(x), v); await page.waitForTimeout(900);
        const bad = await page.evaluate(() => [...document.querySelectorAll('.ig-shell')].filter((e) => e.offsetParent !== null).filter((e) => getComputedStyle(e).backgroundColor === 'rgba(0, 0, 0, 0)').length);
        assert.equal(bad, 0, `${w}x${h} ${v}：磨砂底板没有底色`);
      }
      assert.deepEqual(errors, [], `${w}x${h} 脚本报错`);
      await page.close();
    }
    console.log('旧内核兜底：改写路径、无 color-mix/dvh、底板有底色、三尺寸无报错通过：' + subject);
  } finally { await browser.close(); srv.kill(); }
})().catch((e) => { console.error(e); process.exit(1); });
