/* 显示层重排只用自编题文，不读资料库。 */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx={window:{}};vm.runInNewContext(fs.readFileSync('web/wanxiang_text.js','utf8'),ctx);const t=ctx.window.WANXIANG_TEXT;
const lines=s=>Array.from(t.paragraphs(s));
assert.deepEqual(lines('支持主\n产区发展。'),['支持主产区发展。']);
assert.deepEqual(lines('根据自编资料判断：\nA.甲方\n乙方\nB.丙方\nC.丁方\nD.其他'),['根据自编资料判断：','A.甲方乙方','B.丙方','C.丁方','D.其他']);
assert.deepEqual(lines('自编问题？A.甲 B.乙 C.丙 D.丁'),['自编问题？','A.甲','B.乙','C.丙','D.丁']);
assert.deepEqual(lines('第一自然段。\n\n第二自然段。'),['第一自然段。','第二自然段。']);
assert.deepEqual(lines('增长3.5%，\n支持科技。'),['增长3.5%，支持科技。']);
assert.deepEqual(lines('①第一项\n续行。\n②第二项。'),['①第一项续行。','②第二项。']);
assert.equal(t.plain('Growth\nRate'),'Growth Rate');
assert(!t.html('<img src=x onerror=alert(1)>').includes('<img'));
console.log('WANXIANG-TEXT-OK：软换行、自然段、选项、序号、小数和HTML转义');
