/* 3.4藏经阁·心法真实浏览器回归：看（原 skill 只读）→ 点修改（自动复制成我的版本）→ 保存即生效 → 刷新还在 →
   历史回滚 → 版本冲突提示 → 新建/改名/删除；电脑/平板不整页滚动、不横向溢出。
   服务只用临时自编资料与假HOME，不连接AI。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1]||'行测';
let logs='',browser,active,service;
// 每个尺寸各起一个新服务（临时假库），互不影响
function start(){service=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',subject,'--skillbook-fixture'],{env:process.env});service.stderr.on('data',x=>logs+=x);
 return new Promise((resolve,reject)=>{let s='';const timer=setTimeout(()=>reject(Error(logs||'服务启动超时')),20000);service.stdout.on('data',x=>{s+=x;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});service.on('exit',()=>{clearTimeout(timer);reject(Error(logs||'服务退出'));});});}
const out=path.resolve('ui-artifacts/skillbook');
async function fit(page,tag){assert.deepEqual(await page.evaluate(()=>{const e=[];if(document.documentElement.scrollHeight>innerHeight+2||document.documentElement.scrollWidth>innerWidth+2||scrollY)e.push('整页滚动或横向溢出');for(const s of ['.skb-side','.skb-main','.skb-body']){const r=document.querySelector(s)?.getBoundingClientRect();if(!r||r.bottom>innerHeight+2||r.right>innerWidth+2)e.push(s+'伸出屏幕');}return e;}),[],tag);}
(async()=>{try{
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 const sizes=process.argv.find(a=>a.startsWith('--sizes='))?.split('=')[1]?.split(',');
 for(const [label,viewport] of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]].filter(([l])=>!sizes||sizes.includes(l))){
  const base=await start();const page=await browser.newPage({viewport});active=page;const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept(d.type()==='prompt'?(d.message().includes('新的文件名')?'chapters/03.md':'chapters/02.md'):undefined));
  await page.goto(base);await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&!!DASH);
  await page.evaluate(()=>{try{localStorage.removeItem('skillbook-pos')}catch{};});
  await page.evaluate(()=>{LIB.tab='skillbook';go('skeleton');});await page.waitForSelector('.skb-root .skb-board');
  const label0=await page.evaluate(()=>W('skillbook'));assert(label0,'有风格词');
  assert.match(await page.locator('[data-libtab="skillbook"]').textContent(),new RegExp(label0));
  // 1 板块列表与原 skill（只读）
  const first=await page.locator('.skb-board.on').textContent();assert.match(first,/原 skill/);
  assert.match(await page.locator('.skb-banner').textContent(),/只读/);
  assert.match(await page.locator('.skb-meter').textContent(),/\d+ 个文件/);
  assert.equal(await page.locator('.skb-chip').count(),3,'SKILL.md + cheatsheet + chapters/01.md；scripts不算');
  assert.doesNotMatch(await page.locator('.skb-files').textContent(),/run\.md/);
  await fit(page,label+' 阅读');
  // 2 点修改：先复制成我的版本，再进入编辑
  await page.locator('[data-skb="edit"]').click();await page.waitForSelector('#skbText');
  assert.match(await page.inputValue('#skbText'),/自编入口/);
  await fit(page,label+' 修改');
  await page.fill('#skbText','# 我的入口\n新的识别法：先看问法');
  await page.keyboard.press('Control+s');
  await page.locator('.skb-note').filter({hasText:'已保存'}).waitFor();
  assert.match(await page.locator('.skb-board.on').textContent(),/我的版本/);
  assert.match(await page.locator('.skb-read').textContent(),/新的识别法/);
  // 3 保存即生效：解惑读取计划里就是新内容（接口层），原 skill 不变
  const view=await page.evaluate(()=>api('/api/skillbook'));const row=view.boards.find(b=>b.mode==='mine');assert(row,'有我的版本');
  assert.equal(row.items.filter(i=>i.kind==='method'&&i.read).length,3);
  // 4 刷新后还在原处
  await page.reload();await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&!!DASH);
  await page.evaluate(()=>{LIB.tab='skillbook';go('skeleton');});await page.waitForSelector('.skb-root .skb-board');
  assert.match(await page.locator('.skb-read').textContent(),/新的识别法/);
  // 5 历史与回滚
  await page.locator('[data-skb="history"]').click();await page.waitForSelector('.skb-ver');
  assert.equal(await page.locator('.skb-ver').count(),1);
  await page.locator('[data-skb="peek"]').click();assert.match(await page.locator('.skb-preview').textContent(),/自编入口/);
  await fit(page,label+' 历史');
  await page.locator('[data-skb="restore"]').click();await page.locator('.skb-note').filter({hasText:'已回滚'}).waitFor();
  assert.match(await page.locator('.skb-read').textContent(),/自编入口/);
  // 6 版本冲突：别处先改了，这里再保存会被拒绝且草稿还在
  await page.locator('[data-skb="edit"]').click();await page.waitForSelector('#skbText');await page.fill('#skbText','我的草稿不能丢');
  await page.evaluate(async()=>{const b=document.querySelector('.skb-board.on span').textContent;const f=await api('/api/skillbook/file',{board:b,path:'SKILL.md'});await api('/api/skillbook/save',{board:b,path:'SKILL.md',text:'别处改的',base:f.rev});});
  await page.locator('[data-skb="save"]').click();await page.locator('.skb-note').filter({hasText:'别处被改过'}).waitFor();
  assert.equal(await page.inputValue('#skbText'),'我的草稿不能丢');
  await page.locator('[data-skb="cancel"]').click();
  assert.match(await page.locator('.skb-read').textContent(),/别处改的/);
  // 7 新建文件、改名、删除
  await page.locator('[data-skb="newfile"]').click();await page.waitForSelector('#skbText');await page.fill('#skbText','# 第二章\n自编');await page.locator('[data-skb="save"]').click();
  await page.locator('.skb-chip',{hasText:'chapters/02.md'}).waitFor();
  await page.locator('[data-skb="rename"]').click();await page.locator('.skb-note').filter({hasText:'已改名'}).waitFor();
  assert.equal(await page.locator('.skb-chip',{hasText:'chapters/02.md'}).count(),0);await page.locator('.skb-chip',{hasText:'chapters/03.md'}).waitFor();
  await page.locator('[data-skb="delete"]').click();
  await page.locator('.skb-note').filter({hasText:'已删除'}).waitFor();assert.equal(await page.locator('.skb-chip',{hasText:'chapters/03.md'}).count(),0);
  // 7b 待审建议：勾选采纳（只采纳第一条），采纳前没改文件；另一条留着，再忽略掉
  const badge=await page.locator('.skb-board.on').textContent();assert.match(badge,/📝1/);
  assert.equal(await page.locator('.skb-prop .skb-edit').count(),2);
  assert.doesNotMatch((await page.evaluate(()=>api('/api/skillbook/file',{board:document.querySelector('.skb-board.on span').textContent,path:'cheatsheet.md'}))).text,/自编口诀二/);
  await page.locator('.skb-prop .skb-edit').nth(1).locator('input').uncheck();
  await page.locator('[data-skb="accept"]').click();await page.locator('.skb-note').filter({hasText:'已采纳：cheatsheet.md'}).waitFor();
  assert.match((await page.evaluate(()=>api('/api/skillbook/file',{board:document.querySelector('.skb-board.on span').textContent,path:'cheatsheet.md'}))).text,/自编口诀二/);
  assert.equal(await page.locator('.skb-prop').count(),1);assert.equal(await page.locator('.skb-prop .skb-edit.done').count(),1);
  await page.locator('[data-skb="dismiss"]').click();await page.locator('.skb-note').filter({hasText:'已忽略'}).waitFor();assert.equal(await page.locator('.skb-prop').count(),0);
  await page.locator('.skb-chip',{hasText:'变更记录.md'}).click();await page.locator('.skb-read').filter({hasText:/采纳「补一条自编口诀」/}).waitFor();
  // 7c 发布回原 skill：默认关闭 → 打开开关 → 预览 → 写回 → 撤回
  assert.equal(await page.locator('[data-skb="pub"]').count(),0);assert.equal(await page.locator('[data-skb-switch]').isChecked(),false);
  await page.locator('[data-skb-switch]').check();await page.locator('[data-skb="pub"]').waitFor();
  await page.locator('[data-skb="pub"]').click();await page.locator('.skb-pub').waitFor();assert.match(await page.locator('.skb-pub').textContent(),/覆盖（原文件已备份）/);
  await fit(page,label+' 发布预览');
  await page.locator('[data-skb="pubgo"]').click();await page.locator('.skb-note').filter({hasText:'已写回原 skill'}).waitFor();
  await page.locator('[data-skb="pub"]').click();await page.locator('[data-skb="pubrestore"]').waitFor();
  await page.locator('[data-skb="pubrestore"]').click();await page.locator('.skb-note').filter({hasText:'已撤回发布'}).waitFor();
  await page.locator('[data-skb="pubno"]').click().catch(()=>{});
  // 8 别的板块不受影响
  const others=await page.locator('.skb-board').evaluateAll(es=>es.filter(e=>!e.classList.contains('on')).map(e=>e.textContent));
  assert(others.length&&others.every(t=>!/我的版本/.test(t)));
  await fit(page,label+' 结束');
  assert.deepEqual(errors,[]);await page.close();service.kill();console.log(subject+' '+label+'：看/改/保存即生效/历史回滚/冲突/新建改名删除通过');
 }
}catch(e){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure-'+subject+'.png')}).catch(()=>{});}throw e;}finally{await browser?.close();service?.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
