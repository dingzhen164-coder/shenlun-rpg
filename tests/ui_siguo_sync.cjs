/* 行测·思过崖手动同步与配图显示（2026-11）：
   1. 自动识别库内 gk-skill，点击「↻ 同步错题与词录」后同步错题集（含 assets 配图）与词录汇总；
   2. 数量关系石碑更新为 1 题，点进后题干 Markdown 配图与解析 Obsidian 配图均真实加载（naturalWidth > 0）；
   3. 电脑与平板竖屏、明暗主题无横向溢出、无脚本报错。 */
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');

const service = spawn(process.env.PYTHON || 'python3', ['tests/ui_layout_server.py', '行测', '--siguo-sync-fixture'], { env: process.env });
let logs = '';
service.stderr.on('data', (b) => { logs += b; });
const ready = new Promise((ok, no) => {
  let o = '';
  const t = setTimeout(() => no(Error(logs)), 20000);
  service.stdout.on('data', (b) => {
    o += b;
    const m = o.match(/UI-READY (http:\/\/\S+)/);
    if (m) { clearTimeout(t); ok(m[1]); }
  });
  service.on('exit', () => { clearTimeout(t); no(Error(logs)); });
});

(async () => {
  let browser;
  try {
    const base = await ready;
    browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
    for (const [size, viewport] of [['desktop', { width: 1280, height: 860 }], ['portrait', { width: 800, height: 1280 }]]) {
      for (const theme of ['light', 'dark']) {
        const page = await browser.newPage({ viewport });
        const errors = [];
        page.on('pageerror', (e) => errors.push(String(e)));
        await page.addInitScript((t) => {
          try { localStorage.setItem('theme', t); localStorage.removeItem('sg-pos-v1'); } catch (_) {}
        }, theme);
        await page.goto(base);
        await page.waitForFunction(() => typeof go === 'function' && typeof DASH !== 'undefined' && DASH);
        await page.evaluate(() => go('tianji'));
        await page.waitForSelector('[data-sgsync]');
        await page.click('[data-sgsync]');
        await page.waitForFunction(() => {
          const el = document.querySelector('[data-sgboard="数量关系"] .sg-count');
          return el && el.textContent.includes('1 题');
        });
        await page.click('[data-sgboard="数量关系"]');
        await page.waitForSelector('.sg-stem img.md-img');
        const stemImg = await page.evaluate(async () => {
          const img = document.querySelector('.sg-stem img.md-img');
          if (!img.complete) await new Promise((r) => { img.onload = r; img.onerror = r; });
          return { src: img.getAttribute('src'), w: img.naturalWidth, h: img.naturalHeight };
        });
        assert.match(stemImg.src || '', /^\/vault-file\?p=/);
        assert(stemImg.w > 0 && stemImg.h > 0, '题干配图应真实加载');
        await page.click('[data-sgpick="B"]');
        await page.waitForSelector('.sg-sec img.md-img');
        const secImg = await page.evaluate(async () => {
          const img = document.querySelector('.sg-sec img.md-img');
          if (!img.complete) await new Promise((r) => { img.onload = r; img.onerror = r; });
          return { w: img.naturalWidth, h: img.naturalHeight };
        });
        assert(secImg.w > 0 && secImg.h > 0, '解析配图（Obsidian 格式）应真实加载');
        const wb = await page.evaluate(() => api('/api/wordbook', { kind: '成语' }));
        assert(wb.groups && wb.groups.length === 1 && wb.groups[0].words.includes('自编甲'), '词录应同步到成语组');
        const sw = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
        assert(sw, `${size}/${theme} 不应有横向溢出`);
        assert.deepEqual(errors, []);
        await page.close();
        console.log(`思过崖同步与配图 ${size}/${theme}：通过`);
      }
    }
  } finally {
    await browser?.close();
    service.kill();
  }
})().catch((e) => { console.error(e); process.exit(1); });
