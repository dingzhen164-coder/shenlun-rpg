/* 界面自动检查（省额度用）：程序先判，有问题才截图、才需要人 / AI 看图。
   两个仓库（fakao-rpg、shenlun-rpg）共用这一份；各自的 tests/ui_layout_server.py 负责起一个用临时库的服务，打印 “UI-READY 网址”。

   做什么：电脑 1280×860、平板 800×1280 × 亮色、暗色，依次点顶栏的每一个页面（#nav a[data-view]），每页检查：
     1. 页面脚本报错（pageerror、console.error）
     2. 整页横向溢出（出现左右滚动条）
     3. 有东西伸出屏幕左右边（不在可滚动 / 裁切的容器里）
     4. 按钮、链接、输入框互相压住（重叠面积超过较小那个的 30%）
     5. 页面空白（#view 里几乎没有字）
   输出：全部通过只打一行；有问题按“尺寸·明暗·页面：问题”逐条列出，并且只给出问题的那一页截图（存在 ui-artifacts/layout/）。

   用法：node tests/ui_layout_check.cjs [选项]
     --only=home,train      只查这几个页面（data-view 的值），改了哪里就查哪里
     --sizes=desktop        只查电脑（desktop / tablet）
     --themes=light         只查亮色（light / dark）
     --shots                每一页都截图（真要看外观时才用）
     --subject=行测          shenlun-rpg 用：传给 ui_layout_server.py，查哪一科
   退出码：有问题 1，全部通过 0。需要开发依赖 playwright（npm install --no-save playwright）；程序本身不依赖它。 */
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const fs = require('node:fs'), path = require('node:path');

const arg = (k, d) => { const a = process.argv.find((x) => x.startsWith('--' + k + '=')); return a ? a.split('=')[1] : d; };
const flag = (k) => process.argv.includes('--' + k);
const SIZES = { desktop: { width: 1280, height: 860 }, tablet: { width: 800, height: 1280 } };
const sizes = arg('sizes', 'desktop,tablet').split(',').filter((s) => SIZES[s]);
const themes = arg('themes', 'light,dark').split(',');
const only = arg('only', '') ? arg('only', '').split(',') : null;
const shotsAll = flag('shots');
const OUT = path.resolve('ui-artifacts', 'layout');

function startServer() {
  const py = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const extra = arg('subject', '') ? [arg('subject', '')] : [];
  const srv = spawn(py, ['tests/ui_layout_server.py', ...extra], { env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  let logs = '';
  srv.stderr.on('data', (b) => (logs += b));
  const ready = new Promise((resolve, reject) => {
    let t = '';
    const timer = setTimeout(() => reject(Error('服务 20 秒没起来\n' + logs)), 20000);
    srv.stdout.on('data', (b) => { t += b; const m = t.match(/UI-READY (http:\/\/\S+)/); if (m) { clearTimeout(timer); resolve(m[1].replace(/\/$/, '')); } });
    srv.on('exit', (c) => { clearTimeout(timer); reject(Error('服务退出 ' + c + '\n' + logs)); });
  });
  return { srv, ready };
}

// 在页面里跑的检查：返回问题列表（字符串）
function inspect() {
  const vw = window.innerWidth, out = [];
  const de = document.documentElement;
  if (de.scrollWidth > vw + 2) out.push(`整页横向溢出 ${de.scrollWidth - vw}px`);
  const visible = (el) => {   // 折叠起来的 <details> 里的东西浏览器照样算位置，但屏幕上看不到，不算
    if (el.checkVisibility && !el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true, contentVisibilityAuto: true })) return false;
    const d = el.closest('details:not([open])'); if (d && !el.closest('summary')) return false;
    const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) > 0.05; };
  const clipped = (el) => { for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
    const s = getComputedStyle(p); if (/(auto|scroll|hidden|clip)/.test(s.overflowX) || s.position === 'fixed') return true; } return false; };
  const name = (el) => (el.id ? '#' + el.id : el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/)[0] : ''))
    + (el.textContent ? '「' + el.textContent.trim().slice(0, 12) + '」' : '');
  const scope = [...document.querySelectorAll('header *, #view *')].slice(0, 4000);
  let sticking = 0;
  for (const el of scope) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    if ((r.right > vw + 2 || r.left < -2) && !clipped(el)) { if (sticking++ < 3) out.push(`伸出屏幕：${name(el)}（${Math.round(r.left)}–${Math.round(r.right)} / ${vw}）`); }
  }
  if (sticking > 3) out.push(`……还有 ${sticking - 3} 个元素伸出屏幕`);
  const ctrls = [...document.querySelectorAll('header button, header a, #view button, #view a, #view input, #view select, #view textarea')]
    .filter(visible).slice(0, 400).map((el) => [el, el.getBoundingClientRect()]);
  let overlaps = 0;
  for (let i = 0; i < ctrls.length; i++) for (let j = i + 1; j < ctrls.length; j++) {
    const [a, ra] = ctrls[i], [b, rb] = ctrls[j];
    if (a.contains(b) || b.contains(a)) continue;
    const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left), h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
    if (w <= 0 || h <= 0) continue;
    if (w * h > 0.3 * Math.min(ra.width * ra.height, rb.width * rb.height)) { if (overlaps++ < 3) out.push(`互相压住：${name(a)} 和 ${name(b)}`); }
  }
  if (overlaps > 3) out.push(`……还有 ${overlaps - 3} 处重叠`);
  const view = document.getElementById('view');
  if (view && view.innerText.trim().length < 5) out.push('页面几乎是空的');
  return out;
}

(async () => {
  const { srv, ready } = startServer();
  let browser, failed = 0, checked = 0;
  try {
    const base = await ready;
    browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
    for (const size of sizes) for (const theme of themes) {
      const page = await browser.newPage({ viewport: SIZES[size] });
      const errors = [];
      page.on('pageerror', (e) => errors.push('脚本报错：' + e.message.slice(0, 160)));
      page.on('console', (m) => { if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) errors.push('控制台报错：' + m.text().slice(0, 160)); });
      await page.addInitScript((t) => { try { localStorage.setItem('xrpg-theme', t); } catch (e) { /* 无痕模式 */ } }, theme);
      await page.goto(base + '/');
      await page.waitForTimeout(1500);
      await page.evaluate(() => document.querySelectorAll('.cer-ok').forEach((b) => b.click()));   // 首次进入的大典画面先关掉
      const listed = await page.$$eval('#nav a[data-view]', (as) => as.filter((a) => a.offsetParent !== null || true).map((a) => a.dataset.view));
      const views=only||[...new Set([...listed,"bank","tianji"])];
      for (const v of [...new Set(views)]) {
        if (only && !only.includes(v)) continue;
        errors.length = 0;
        await page.evaluate(v => go(v), v); // 地图/快捷键导航由ui_map_navigation实点验收；这里判页面布局。
        await page.waitForTimeout(1200);
        await page.evaluate(() => document.querySelectorAll('.cer-ok').forEach((b) => b.click()));
        const problems = [...errors, ...(await page.evaluate(inspect))];
        const tag = `${size}·${theme}·${v}`;
        checked++;
        if (problems.length || shotsAll) {
          fs.mkdirSync(OUT, { recursive: true });
          await page.screenshot({ path: path.join(OUT, tag.replace(/·/g, '-') + '.png') });
        }
        if (problems.length) {
          failed++;
          console.log(`✗ ${tag}`);
          for (const p of problems) console.log('    ' + p);
        }
      }
      await page.close();
    }
    console.log(failed ? `界面检查：${checked} 页里 ${failed} 页有问题（截图在 ${path.relative(process.cwd(), OUT)}）`
                       : `界面检查全部通过：${checked} 页（${sizes.join('/')} × ${themes.join('/')}）${shotsAll ? '，截图在 ' + path.relative(process.cwd(), OUT) : ''}`);
  } catch (e) {
    console.log('界面检查没跑完：' + e.message);
    failed = failed || 1;
  } finally {
    if (browser) await browser.close();
    srv.kill();
  }
  process.exit(failed ? 1 : 0);
})();
