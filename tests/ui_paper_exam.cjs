/* 4.2.0：宗门大比「自考」（9点挂钟计时+空格键打点+预设分值录分）与板块逐题用时自动求和回归；隔离假HOME，不连AI。 */
const {chromium} = require('playwright'), {spawn} = require('node:child_process'), assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const service = spawn('python3', ['tests/ui_layout_server.py', '行测', '--merge-fixture', '--score-fixture'], {env: process.env});
let browser, active, logs = '';
service.stderr.on('data', x => logs += x);
const out = path.resolve('ui-artifacts/paper-exam');
const ready = new Promise((resolve, reject) => {
  let s = '';
  const t = setTimeout(() => reject(Error(logs || '临时服务未启动')), 20000);
  service.stdout.on('data', x => {
    s += x;
    const m = s.match(/UI-READY (http:\/\/\S+)/);
    if (m) { clearTimeout(t); resolve(m[1]); }
  });
  service.on('exit', c => { clearTimeout(t); reject(Error(c + ' ' + logs)); });
});

async function fits(p) {
  assert.deepEqual(await p.evaluate(() => {
    const bad = [], d = document.querySelector('.cs-dialog'), pane = d.querySelector('.cs-pane:not([hidden])'), r = d.getBoundingClientRect();
    if (document.documentElement.scrollWidth > innerWidth + 2 || document.documentElement.scrollHeight > innerHeight + 2 || scrollY) bad.push('整页溢出');
    if (d.open) {
      if (Math.abs(r.width - document.querySelector('#view').clientWidth) > 3) bad.push('卷宗未全宽');
      if (r.left < 0 || r.right > innerWidth + 1 || r.bottom > innerHeight + 1) bad.push('卷宗越界');
      if (pane.scrollWidth > pane.clientWidth + 2) bad.push('卷宗横向溢出');
      for (const e of d.querySelectorAll('.th-dialog-head,.cs-foot')) {
        const a = e.getBoundingClientRect();
        if (a.top < r.top || a.bottom > r.bottom + 1) bad.push('固定区域越界');
      }
    }
    return bad;
  }), []);
}

(async () => {
  try {
    const base = await ready;
    browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined});
    for (const [size, viewport] of [['desktop', {width: 1280, height: 860}], ['tablet-portrait', {width: 800, height: 1280}], ['tablet-landscape', {width: 1280, height: 800}]]) {
      const p = await browser.newPage({viewport});
      active = p;
      p.setDefaultTimeout(12000);
      const errors = [];
      p.on('pageerror', e => errors.push(e.message));
      await p.goto(base);
      await p.waitForFunction(() => !!window.DASH_REF?.());
      await p.evaluate(() => go('contest'));
      await p.locator('.contest-scene').waitFor();

      // 5 个入口齐全：考情 / 复盘 / 战绩 / 自考 / 录入
      assert.deepEqual(
        await p.locator('[data-cs-enter]').evaluateAll(els => els.map(e => e.getAttribute('data-cs-enter'))),
        ['overview', 'review', 'trends', 'self_exam', 'entry']
      );

      // 明暗两套主题下「自考」计时与录分两步均无溢出
      for (const theme of ['light', 'dark']) {
        await p.evaluate(t => { document.documentElement.dataset.theme = t; }, theme);
        await p.locator('[data-cs-enter="self_exam"]').click();
        await fits(p);
        assert.deepEqual((await p.locator('.pe-clock text').allTextContents()).map(Number).sort((a, b) => a - b),
          [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
        assert.equal(await p.locator('.pe-clock-ticks line').count(), 60);
        const clock = await p.locator('.pe-clock').boundingBox();
        const left = await p.locator('.pe-clock-box').boundingBox();
        const right = await p.locator('.pe-queue-box').boundingBox();
        assert(clock.width >= 320 && left.width > right.width && right.x >= left.x + left.width - 1,
          '电脑、平板横竖屏并排，钟面放大、钟表区比右侧宽');
        const pause = await p.locator('#pePauseBtn').boundingBox();
        const pane = await p.locator('.cs-pane:not([hidden])').boundingBox();
        assert(pause.y + pause.height <= pane.y + pane.height + 1, '无需滚动即可看到钟面和计时操作');
        if (theme === 'light') {
          await p.locator('#peLapBtn').click();
          await p.waitForFunction(() => Number(document.getElementById('peHandSec').dataset.angle) > 0.5);
          const queue = p.locator('.pe-queue-list');
          if (size !== 'tablet-portrait') assert(await queue.evaluate(q => q.scrollHeight > q.clientHeight));
          await queue.locator('[data-pe-jump]').last().click();
          assert(await queue.evaluate(q => {
            const row = q.querySelector('.is-active').getBoundingClientRect();
            const box = q.getBoundingClientRect();
            return row.top >= box.top - 1 && row.bottom <= box.bottom + 1;
          }), '跳到队尾后，当前板块在独立队列中可见');
          await p.locator('#pePauseBtn').click();
          assert.equal(await p.locator('#pePauseBtn').textContent(), '继续');
          await p.locator('#peResetBtn').click();
          assert.equal(await p.locator('#peHandSec').getAttribute('data-angle'), '0.00');
        }
        await p.locator('[data-pe-step="score"]').click();
        await fits(p);
        await p.locator('[data-pe-step="timer"]').click();
        await fits(p);
        await p.keyboard.press('Escape');
        await p.locator('.cs-dialog').waitFor({state: 'hidden'});
      }
      await p.evaluate(() => { document.documentElement.dataset.theme = 'light'; });

      if (size === 'desktop') {
        const beforeMock = await p.evaluate(() => api('/api/mock'));
        const beforeCount = beforeMock.overall.count;

        // 1) 验证宗门大比「复盘」卡片对有逐题秒数的第 39 季自动按板块求和显示用时
        await p.locator('[data-cs-enter="review"]').click();
        await p.locator('#rvPick').selectOption('39');
        const rvTilesText = await p.locator('.rv-grid').textContent();
        assert(rvTilesText.includes('1.4分'), '复盘板块应显示逐题求和用时（85秒≈1.4分）');
        await p.locator('[data-cs-close]').click();

        // 2) 进入「自考」检查9:00 挂钟、预设切换、做题顺序微调、空格键打点与录分闭环
        await p.locator('[data-cs-enter="self_exam"]').click();
        await p.locator('.pe-clock').waitFor();
        assert.equal(await p.locator('#peDigitalWrap').isHidden(), true, '默认隐藏数字时间');
        assert.equal(await p.locator('#peHandHour').getAttribute('data-angle'), '270.00', '时针默认指向九点钟(270°)');
        assert.equal(await p.locator('#peHandMin').getAttribute('data-angle'), '0.00');
        assert.equal(await p.locator('#peHandSec').getAttribute('data-angle'), '0.00');

        // 切换到川黔省考常见（100题·100分）预设
        const selDone = p.waitForResponse(r => r.url().includes('/api/paper-exam/prefs') && r.request().method() === 'POST');
        await p.locator('#pePresetSel').selectOption('sc_gz_100');
        assert.equal((await selDone).status(), 200);

        // 两个言语板块可以各自移动、打点和录分。
        const names = () => p.locator('.pe-q-main b').allTextContents();
        const before = await names();
        const reading = before.indexOf('片段阅读');
        assert.equal(before[reading - 1], '逻辑填空');
        const reorderDone = p.waitForResponse(r => r.url().includes('/api/paper-exam/prefs') && r.request().method() === 'POST');
        await p.locator(`[data-pe-move="${reading}:-1"]`).click();
        assert.equal((await reorderDone).status(), 200);
        const readingIdx = reading - 1;
        await p.waitForFunction(i => document.querySelector(`[data-pe-q="${i}"] .pe-q-main b`)?.textContent === '片段阅读', readingIdx);
        assert.deepEqual((await names()).slice(readingIdx, readingIdx + 2), ['片段阅读', '逻辑填空']);

        await p.locator('#peLapBtn').focus();
        await p.keyboard.press('Space');
        await p.locator(`[data-pe-jump="${readingIdx}"]`).click();
        // 推进这一板块的单调时钟 30 分 30 秒，其他页面定时器仍按真实时间运行。
        await p.evaluate(() => {
          const now = performance.now.bind(performance);
          performance.now = () => now() + 1830000;
        });
        await p.waitForFunction(() => {
          const angle = id => Number(document.getElementById(id).dataset.angle);
          return Math.abs(angle('peHandHour') - 285.25) < 0.05 &&
            Math.abs(angle('peHandMin') - 183) < 0.5 && Math.abs(angle('peHandSec') - 180) < 30;
        });
        await p.locator('#peLapBtn').focus();
        await p.keyboard.press('Space');
        await p.locator(`[data-pe-q="${reading}"].is-active`).waitFor();
        assert.equal(await p.locator(`[data-pe-q="${readingIdx}"].is-done`).count(), 1);
        await p.locator('#peLapBtn').focus();
        await p.keyboard.press('Space');
        await p.locator('#peToScore').click();
        await p.locator('#peScoreRows').waitFor();
        assert(parseFloat(await p.locator(`[data-pe-min="${readingIdx}"]`).inputValue()) >= 30.5);
        assert(parseFloat(await p.locator(`[data-pe-min="${reading}"]`).inputValue()) > 0);
        await p.locator(`[data-pe-ok="${readingIdx}"]`).fill('12');
        await p.locator(`[data-pe-ok="${reading}"]`).fill('9');
        assert.equal(await p.locator(`[data-pe-sec-score="${readingIdx}"]`).textContent(), '12');
        assert.equal(await p.locator(`[data-pe-sec-score="${reading}"]`).textContent(), '9');

        // 录入试卷名与对错题数，校验实时算分并保存计入宗门大比
        await p.evaluate(() => { if (window.CEREMONY) CEREMONY.contest = async () => {}; });
        await p.locator('#peName').fill('2025四川省考行测纸质卷');
        await p.locator('[data-pe-ok="0"]').fill('10');
        await p.locator('[data-pe-ok="1"]').fill('8');
        await p.locator('[data-pe-min="1"]').fill('12.5');
        const sumText = await p.locator('#peSumScore').textContent();
        assert(sumText.includes('分') && !sumText.includes('汇总 0 分'), '实时汇总分数应随对题数立即计算');

        const saveResp = p.waitForResponse(r => r.url().includes('/api/paper-exam/save') && r.request().method() === 'POST');
        await p.locator('#peSaveExam').click();
        assert.equal((await saveResp).status(), 200);
        await p.waitForFunction(() => document.querySelector('.pe-history')?.textContent.includes('2025四川省考行测纸质卷'));
        await fits(p);

        // 修改历史卷时禁用当前方案的计时，并保留手工修订的用时。
        await p.locator('[data-pe-edit]').first().click();
        assert(await p.locator('[data-pe-step="timer"]').isDisabled());
        await p.locator(`[data-pe-min="${readingIdx}"]`).fill('18.75');
        await p.locator('[data-pe-step="score"]').click();
        assert.equal(await p.locator(`[data-pe-min="${readingIdx}"]`).inputValue(), '18.75');
        await p.locator('#peCancelEdit').click();

        // 3) 校验已计入「考情」与「战绩」，但不污染「复盘」下拉框
        await p.locator('[data-cs-close]').click();
        await p.locator('[data-cs-enter="overview"]').click();
        assert((await p.locator('.contest-hero').innerText()).includes(`共 ${beforeCount + 1} 份试卷`), '考情总卷数应增加1');
        await p.locator('[data-cs-close]').click();

        await p.locator('[data-cs-enter="trends"]').click();
        const trendsTable = await p.locator('[data-cs-pane="trends"] .mk-table').innerText();
        assert(trendsTable.includes('2025四川省考行测纸质卷') && trendsTable.includes('自考') && trendsTable.includes('分'), '战绩历次大比应显示自考卷与汇总用时');
        await p.locator('[data-cs-close]').click();

        await p.locator('[data-cs-enter="review"]').click();
        const rvOptions = await p.locator('#rvPick option').allTextContents();
        assert(!rvOptions.some(t => t.includes('2025四川省考行测纸质卷')), '纸质自考无需逐题复盘，不应出现在逐题复盘下拉列表');
        await p.locator('[data-cs-close]').click();
      }

      assert.deepEqual(errors, []);
      await p.close();
      console.log(size + '：自考挂钟/空格打点/预设算分/考情战绩联动/板块用时求和通过');
    }
  } catch (e) {
    if (active && !active.isClosed()) {
      fs.mkdirSync(out, {recursive: true});
      await active.screenshot({path: path.join(out, 'failure.png')}).catch(() => {});
    }
    throw e;
  } finally {
    await browser?.close();
    service.kill();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
