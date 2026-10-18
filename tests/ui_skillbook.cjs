/* 3.4藏经阁·心法真实浏览器回归：书架 → 看 → 直接点修改（没有“我的版本”，第一次保存自动复制）→ 保存即生效 → 刷新还在 →
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
  await page.evaluate(()=>{LIB.tab='skillbook';go('skeleton');});await page.waitForSelector('.skb-root.shelf .skb-tome');
  const label0=await page.evaluate(()=>W('skillbook'));assert(label0,'有风格词');
  assert.match(await page.locator('[data-libtab="skillbook"]').textContent(),new RegExp(label0));
  // 0 书架：每个板块一本会浮动的古籍；整块铺满内容区（不再只占中间一列）
  const nBoards=await page.evaluate(async()=>(await api('/api/skillbook')).boards.length);
  assert.equal(await page.locator('.skb-tome').count(),nBoards,'一个板块一本书');
  if(subject==='行测')assert((await page.locator('.skb-tome').first().evaluate(e=>getComputedStyle(e).animationName)).includes('tome-float'),'有浮动动画');  // 申论是官场风格：档案盒不浮动
  const wide=await page.evaluate(()=>{const r=document.querySelector('#view .scene-panel').getBoundingClientRect();return r.width/innerWidth;});
  assert(wide>0.9,'藏经阁铺满宽度 '+wide);
  await page.locator('.skb-tome').first().click({force:true});await page.waitForSelector('.skb-root.detail .skb-chip');
  // 1 板块详情与原 skill（只读）
  const first=await page.locator('.skb-who').textContent();assert.doesNotMatch(first,/我的版本|原 skill/,'不再有版本标签');
  assert.match(await page.locator('.skb-banner').textContent(),/直接修改/);
  await page.locator('.skb-meter').filter({hasText:/个文件/}).waitFor();assert.match(await page.locator('.skb-meter').textContent(),/约 \d+ 字/);
  for(const gone of ['[data-skb="copy"]','[data-skb="pub"]','[data-skb-switch]'])assert.equal(await page.locator(gone).count(),0,gone+' 已取消');
  assert.equal(await page.locator('[data-skb="organize"]').count(),1,'生成学习版入口');assert.match(await page.locator('[data-skb="organize"]').textContent(),/学习版/);
  assert.equal(await page.locator('.skb-chip').count(),3,'SKILL.md + cheatsheet + chapters/01.md；scripts不算');
  assert.doesNotMatch(await page.locator('.skb-files').textContent(),/run\.md/);
  await fit(page,label+' 阅读');
  // 2 点修改：直接进入编辑（没有复制步骤）
  await page.locator('[data-skb="edit"]').click();await page.waitForSelector('#skbText');
  assert.match(await page.inputValue('#skbText'),/自编入口/);
  await fit(page,label+' 修改');
  await page.fill('#skbText','# 我的入口\n新的识别法：先看问法\n\n公式：$A \\rightarrow B$ 与 **加粗**\n\n| 信号 | 方法 |\n|---|---|\n| 除非 | $\\neg B \\rightarrow A$ |');
  await page.keyboard.press('Control+s');
  await page.locator('.skb-note').filter({hasText:'已保存'}).waitFor();
  assert.match(await page.locator('.skb-read').textContent(),/新的识别法/);
  const shown=await page.locator('.skb-read').textContent();assert.match(shown,/A → B/);assert.doesNotMatch(shown,/\$|rightarrow|\*\*/,'公式和加粗已渲染');
  assert.equal(await page.locator('.skb-read table th').count(),2,'表格已渲染');
  // 3 保存即生效：解惑读取计划里就是新内容（接口层），原 skill 不变
  const view=await page.evaluate(()=>api('/api/skillbook'));const row=view.boards.find(b=>b.mode==='mine');assert(row,'有我的版本');
  const pl=await page.evaluate(b=>api('/api/skillbook/plan',{board:b}),row.board);
  assert.equal(pl.items.filter(i=>i.kind==='method'&&i.read).length,3);
  // 4 刷新后还在原处
  await page.reload();await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&!!DASH);
  await page.evaluate(()=>{LIB.tab='skillbook';go('skeleton');});await page.waitForSelector('.skb-root.shelf .skb-tome');
  await page.locator('.skb-tome').first().click({force:true});await page.waitForSelector('.skb-read');
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
  await page.evaluate(async()=>{const b=document.querySelector('.skb-who b').textContent;const f=await api('/api/skillbook/file',{board:b,path:'SKILL.md'});await api('/api/skillbook/save',{board:b,path:'SKILL.md',text:'别处改的',base:f.rev});});
  await page.locator('[data-skb="save"]').click();await page.locator('.skb-note').filter({hasText:'别处被改过'}).waitFor();
  assert.equal(await page.inputValue('#skbText'),'我的草稿不能丢');
  await page.locator('[data-skb="cancel"]').click();
  assert.match(await page.locator('.skb-read').textContent(),/别处改的/);
  // 7 新建文件、改名、删除
  await page.locator('[data-skb="newfile"]').click();await page.waitForSelector('#skbText');await page.fill('#skbText','# 第二章\n自编');await page.locator('[data-skb="save"]').click();
  await page.locator('.skb-chip[title="chapters/02.md"]').waitFor();
  await page.locator('[data-skb="rename"]').click();await page.locator('.skb-note').filter({hasText:'已改名'}).waitFor();
  assert.equal(await page.locator('.skb-chip[title="chapters/02.md"]').count(),0);await page.locator('.skb-chip[title="chapters/03.md"]').waitFor();
  await page.locator('[data-skb="delete"]').click();
  await page.locator('.skb-note').filter({hasText:'已删除'}).waitFor();assert.equal(await page.locator('.skb-chip[title="chapters/03.md"]').count(),0);
  // 7b 待审建议：勾选采纳（只采纳第一条），采纳前没改文件；另一条留着，再忽略掉
  const badge=await page.locator('.skb-who').textContent();assert.match(badge,/📝1/);
  assert.equal(await page.locator('.skb-prop .skb-edit').count(),2);
  assert.doesNotMatch((await page.evaluate(()=>api('/api/skillbook/file',{board:document.querySelector('.skb-who b').textContent,path:'cheatsheet.md'}))).text,/自编口诀二/);
  await page.locator('.skb-prop .skb-edit').nth(1).locator('input').uncheck();
  await page.locator('[data-skb="accept"]').click();await page.locator('.skb-note').filter({hasText:'已采纳：cheatsheet.md'}).waitFor();
  assert.match((await page.evaluate(()=>api('/api/skillbook/file',{board:document.querySelector('.skb-who b').textContent,path:'cheatsheet.md'}))).text,/自编口诀二/);
  assert.equal(await page.locator('.skb-prop').count(),1);assert.equal(await page.locator('.skb-prop .skb-edit.done').count(),1);
  await page.locator('[data-skb="dismiss"]').click();await page.locator('.skb-note').filter({hasText:'已忽略'}).waitFor();assert.equal(await page.locator('.skb-prop').count(),0);
  await page.locator('.skb-chip[title="变更记录.md"]').click();await page.locator('.skb-read').filter({hasText:/采纳「补一条自编口诀」/}).waitFor();
  // 8 别的板块不受影响
  await fit(page,label+' 详情结束');
  await page.locator('[data-skb="shelf"]').click();await page.waitForSelector('.skb-root.shelf .skb-tome');
    const t0=Date.now();await page.evaluate(()=>{go('home')});await page.evaluate(()=>{LIB.tab='skillbook';go('skeleton');});await page.waitForSelector('.skb-tome');
  assert(Date.now()-t0<2500,'再次进入立即出书架');
  assert.deepEqual(errors,[]);await page.close();service.kill();console.log(subject+' '+label+'：看/改/保存即生效/历史回滚/冲突/新建改名删除通过');
 }
}catch(e){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure-'+subject+'.png')}).catch(()=>{});}throw e;}finally{await browser?.close();service?.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
