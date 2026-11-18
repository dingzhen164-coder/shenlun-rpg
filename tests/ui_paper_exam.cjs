/* 4.2.0：宗门大比「自考」（无数字9点钟表计时+空格键打点+预设分值录分）与板块逐题用时自动求和回归；隔离假HOME，不连AI。 */
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

        // 2) 进入「自考」检查无数字 9:00 钟表、预设切换、做题顺序微调、空格键打点与录分闭环
        await p.locator('[data-cs-enter="self_exam"]').click();
        await p.locator('.pe-clock').waitFor();
        assert.equal(await p.locator('.pe-clock text').count(), 0, '钟表表盘不得包含任何数字刻度文字');
        assert.equal(await p.locator('#peDigitalWrap').isHidden(), true, '默认隐藏数字时间');
        assert.equal(await p.locator('#peHandHour').getAttribute('data-angle'), '270.00', '时针默认指向九点钟(270°)');
        assert.equal(await p.locator('#peHandMin').getAttribute('data-angle'), '0.00');
        assert.equal(await p.locator('#peHandSec').getAttribute('data-angle'), '0.00');

        // 切换到川黔省考常见（100题·100分）预设
        const selDone = p.waitForResponse(r => r.url().includes('/api/paper-exam/prefs') && r.request().method() === 'POST');
        await p.locator('#pePresetSel').selectOption('sc_gz_100');
        assert.equal((await selDone).status(), 200);

        // 开考前点上移按钮调整第 2 块与第 1 块顺序并持久化
        const firstTwoBefore = await p.locator('.pe-q-main b').evaluateAll(els => els.slice(0, 2).map(e => e.textContent));
        const reorderDone = p.waitForResponse(r => r.url().includes('/api/paper-exam/prefs') && r.request().method() === 'POST');
        await p.locator('[data-pe-move="1:-1"]').click();
        assert.equal((await reorderDone).status(), 200);
        const firstTwoAfter = await p.locator('.pe-q-main b').evaluateAll(els => els.slice(0, 2).map(e => e.textContent));
        assert.deepEqual(firstTwoAfter, [firstTwoBefore[1], firstTwoBefore[0]], '开考前应支持调整做题顺序');

        // 确保焦点不在次要按钮上，按空格键开始第 1 块计时，再按空格键打点切入第 2 块
        await p.locator('#peLapBtn').focus();
        await p.keyboard.press('Space');
        await p.waitForFunction(() => document.querySelectorAll('.pe-q-item.is-active').length === 1 && document.querySelector('.pe-q-item.is-active')?.getAttribute('data-pe-q') === '0');
        await p.waitForTimeout(220);
        await p.locator('#peLapBtn').focus();
        await p.keyboard.press('Space');
        await p.waitForFunction(() => document.querySelector('.pe-q-item.is-active')?.getAttribute('data-pe-q') === '1');
        assert.equal(await p.locator('[data-pe-q="0"].is-done').count(), 1, '第1块按空格后应标记已完成');

        // 点击「完成计时 · 去录分 →」，校验第 1 块用时已自动带入
        await p.locator('#peToScore').click();
        await p.locator('#peScoreRows').waitFor();
        const sec0Min = parseFloat(await p.locator('[data-pe-min="0"]').inputValue());
        assert(sec0Min > 0, '计时打点秒数应自动带入录分表用时列');

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
      console.log(size + '：自考无数字钟表/空格打点/预设算分/考情战绩联动/板块用时求和通过');
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
