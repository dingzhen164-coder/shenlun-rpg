/* 3.5.3 藏经阁·心法真实浏览器回归：书架（最前一本「总诀」+ 每个板块一本，初始为空）→ 看 → 直接修改保存即生效 → 刷新还在 → 历史回滚 → 版本冲突 →
   新建/改名/删除 → 导入 .skill 到空板块、再覆盖导入（旧内容进历史）→ 心法总诀（四份文件、复制、下载）；
   已取消的功能（生成学习版、蒸馏页签、待审建议）不再出现；电脑/平板不整页滚动、不横向溢出。
   服务只用临时自编资料与假HOME，不连接AI。 */
const {chromium}=require('playwright'),{spawn,spawnSync}=require('node:child_process');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1]||'行测';
let logs='',browser,active,service;
function start(){service=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',subject,'--skillbook-fixture'],{env:process.env});service.stderr.on('data',x=>logs+=x);
 return new Promise((resolve,reject)=>{let s='';const timer=setTimeout(()=>reject(Error(logs||'服务启动超时')),20000);service.stdout.on('data',x=>{s+=x;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});service.on('exit',()=>{clearTimeout(timer);reject(Error(logs||'服务退出'));});});}
const out=path.resolve('ui-artifacts/skillbook');
// 自编的 .skill 包（外面套一层文件夹；含 references/ 资料和不该导入的 yaml）
function makeSkill(file,entry){fs.mkdirSync(path.dirname(file),{recursive:true});
 const code=`import zipfile,sys\nz=zipfile.ZipFile(sys.argv[1],'w')\nz.writestr('pkg/SKILL.md',sys.argv[2])\nz.writestr('pkg/心法/00-总流程.md','# 总流程\\n1. 先判断方向')\nz.writestr('pkg/references/逐题表.md','# 逐题表\\n仅供查阅')\nz.writestr('pkg/agents/openai.yaml','x: 1')\nz.close()`;
 const r=spawnSync(process.env.PYTHON||'python3',['-c',code,file,entry]);assert.equal(r.status,0,String(r.stderr));}
async function fit(page,tag){assert.deepEqual(await page.evaluate(()=>{const e=[];if(document.documentElement.scrollHeight>innerHeight+2||document.documentElement.scrollWidth>innerWidth+2||scrollY)e.push('整页滚动或横向溢出');for(const s of ['.skb-side','.skb-main','.skb-body']){const r=document.querySelector(s)?.getBoundingClientRect();if(!r||r.bottom>innerHeight+2||r.right>innerWidth+2)e.push(s+'伸出屏幕');}return e;}),[],tag);}
(async()=>{try{
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 const sizes=process.argv.find(a=>a.startsWith('--sizes='))?.split('=')[1]?.split(',');
 for(const [label,viewport] of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]].filter(([l])=>!sizes||sizes.includes(l))){
  const base=await start();const page=await browser.newPage({viewport,acceptDownloads:true});active=page;const errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('dialog',d=>d.accept(d.type()==='prompt'?(d.message().includes('新的文件名')?'chapters/03.md':'chapters/02.md'):undefined));
  await page.goto(base);await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&!!DASH);
  await page.evaluate(()=>{try{localStorage.removeItem('skillbook-pos')}catch{};});
  await page.evaluate(()=>{LIB.tab='skillbook';go('skeleton');});await page.waitForSelector('.skb-root.shelf .skb-tome');
  const label0=await page.evaluate(()=>W('skillbook'));assert(label0,'有风格词');
  assert.match(await page.locator('[data-libtab="skillbook"]').textContent(),new RegExp(label0));
  // 0 书架：每个板块一本古籍（初始为空，只有预置的那一本有内容）；最前面是「总诀」入口
  const view=await page.evaluate(async()=>(await api('/api/skillbook')).boards);
  assert.equal(await page.locator('.skb-tome').count(),view.length,'一个板块一本书');
  assert.equal(view.filter(b=>b.n_files>0).length,1,'只有预置的一个板块有内容，其余为空');
  assert.equal(await page.locator('.skb-tome.none').count(),view.length-1,'空板块的书是灰的');
  assert.match(await page.locator('.skb-zj-card').textContent(),/总诀/);
  if(subject==='行测')assert((await page.locator('.skb-tome').first().evaluate(e=>getComputedStyle(e).animationName)).includes('tome-float'),'有浮动动画');
  const wide=await page.evaluate(()=>{const r=document.querySelector('#view .scene-panel').getBoundingClientRect();return r.width/innerWidth;});
  assert(wide>0.9,'藏经阁铺满宽度 '+wide);
  // 1 有内容的板块：看、改、保存即生效
  const full=view.find(b=>b.n_files>0).board;
  await page.locator(`[data-skb-board="${full}"]`).click({force:true});await page.waitForSelector('.skb-root.detail .skb-chip');
  assert.doesNotMatch(await page.locator('.skb-who').textContent(),/我的版本|原 skill|📝/);
  await page.locator('.skb-meter').filter({hasText:/个文件/}).waitFor();assert.match(await page.locator('.skb-meter').textContent(),/约 \d+ 字/);
  assert.equal(await page.locator('.skb-chip').count(),3,'SKILL.md + cheatsheet + chapters/01.md');
  for(const gone of ['[data-skb="organize"]','[data-skb="template"]','[data-skb-tab]','.skb-prop','.skb-propbar','[data-skb="accept"]','#dstRoot'])assert.equal(await page.locator(gone).count(),0,gone+' 已取消');
  assert.equal(await page.locator('[data-skb="import"]').count(),1,'导入入口');
  await fit(page,label+' 阅读');
  await page.locator('[data-skb="edit"]').click();await page.waitForSelector('#skbText');
  assert.match(await page.inputValue('#skbText'),/自编入口/);await fit(page,label+' 修改');
  await page.fill('#skbText','# 我的入口\n新的识别法：先看问法\n\n公式：$A \\rightarrow B$ 与 **加粗**\n\n| 信号 | 方法 |\n|---|---|\n| 除非 | $\\neg B \\rightarrow A$ |');
  await page.keyboard.press('Control+s');await page.locator('.skb-note').filter({hasText:'已保存'}).waitFor();
  const shown=await page.locator('.skb-read').textContent();assert.match(shown,/新的识别法/);assert.match(shown,/A → B/);assert.doesNotMatch(shown,/\$|rightarrow|\*\*/,'公式和加粗已渲染');
  assert.equal(await page.locator('.skb-read table th').count(),2,'表格已渲染');
  const pl=await page.evaluate(b=>api('/api/skillbook/plan',{board:b}),full);assert.equal(pl.items.filter(i=>i.kind==='method'&&i.read).length,3);
  // 2 刷新后还在原处
  await page.reload();await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&!!DASH);
  await page.evaluate(()=>{LIB.tab='skillbook';go('skeleton');});await page.waitForSelector('.skb-root.shelf .skb-tome');
  await page.locator(`[data-skb-board="${full}"]`).click({force:true});await page.waitForSelector('.skb-read');
  assert.match(await page.locator('.skb-read').textContent(),/新的识别法/);
  // 3 历史与回滚
  await page.locator('[data-skb="history"]').click();await page.waitForSelector('.skb-ver');
  assert.equal(await page.locator('.skb-ver').count(),1);
  await page.locator('[data-skb="peek"]').click();assert.match(await page.locator('.skb-preview').textContent(),/自编入口/);await fit(page,label+' 历史');
  await page.locator('[data-skb="restore"]').click();await page.locator('.skb-note').filter({hasText:'已回滚'}).waitFor();
  assert.match(await page.locator('.skb-read').textContent(),/自编入口/);
  // 4 版本冲突：别处先改了，这里再保存会被拒绝且草稿还在
  await page.locator('[data-skb="edit"]').click();await page.waitForSelector('#skbText');await page.fill('#skbText','我的草稿不能丢');
  await page.evaluate(async()=>{const b=document.querySelector('.skb-who b').textContent;const f=await api('/api/skillbook/file',{board:b,path:'SKILL.md'});await api('/api/skillbook/save',{board:b,path:'SKILL.md',text:'别处改的',base:f.rev});});
  await page.locator('[data-skb="save"]').click();await page.locator('.skb-note').filter({hasText:'别处被改过'}).waitFor();
  assert.equal(await page.inputValue('#skbText'),'我的草稿不能丢');
  await page.locator('[data-skb="cancel"]').click();assert.match(await page.locator('.skb-read').textContent(),/别处改的/);
  // 5 新建文件、改名、删除
  await page.locator('[data-skb="newfile"]').click();await page.waitForSelector('#skbText');await page.fill('#skbText','# 第二章\n自编');await page.locator('[data-skb="save"]').click();
  await page.locator('.skb-chip[title="chapters/02.md"]').waitFor();
  await page.locator('[data-skb="rename"]').click();await page.locator('.skb-note').filter({hasText:'已改名'}).waitFor();
  await page.locator('.skb-chip[title="chapters/03.md"]').waitFor();
  await page.locator('[data-skb="delete"]').click();await page.locator('.skb-note').filter({hasText:'已删除'}).waitFor();assert.equal(await page.locator('.skb-chip[title="chapters/03.md"]').count(),0);
  // 6 导入：再导入同一个板块 → 同名覆盖（旧内容进历史），其余文件不动
  const skill=path.join(out,'tmp','a.skill');makeSkill(skill,'# 导入的入口\n导入的内容');
  await page.setInputFiles('#skbPick',skill);
  await page.locator('.skb-note').filter({hasText:/已导入：新增 2 个、覆盖 1 个/}).waitFor();
  assert.match(await page.locator('.skb-note').textContent(),/跳过 1 个/);
  assert.match(await page.locator('.skb-read').textContent(),/导入的内容/);
  assert.equal(await page.locator('.skb-chip[title="cheatsheet.md"]').count(),1,'原有的其他文件还在');
  assert.match(await page.locator('.skb-chip[title="references/逐题表.md"]').textContent(),/仅查阅/);
  assert.match(await page.locator('.skb-meter').textContent(),/references \/ 学习版 里的 1 个文件只供查阅或阅读/);
  await page.locator('[data-skb="history"]').click();await page.waitForSelector('.skb-ver');assert((await page.locator('.skb-ver').count())>=1);await page.locator('[data-skb="back"]').click();
  await fit(page,label+' 导入后');
  // 7 空板块：提示导入或新建；导入后下一次解惑就读到
  await page.locator('[data-skb="shelf"]').click();await page.waitForSelector('.skb-root.shelf .skb-tome');
  const empty=view.find(b=>b.n_files===0).board;
  await page.locator(`[data-skb-board="${empty}"]`).click({force:true});await page.waitForSelector('.skb-root.detail');
  assert.match(await page.locator('.skb-banner').textContent(),/还是空的/);
  assert.equal(await page.locator('[data-skb="import"]').count(),1);assert.equal(await page.locator('[data-skb="newfile"]').count(),1);
  assert.equal(await page.locator('[data-skb="edit"]').count(),0,'空板块没有“修改”');
  await fit(page,label+' 空板块');
  await page.setInputFiles('#skbPick',skill);await page.locator('.skb-note').filter({hasText:/已导入：新增 3 个、覆盖 0 个/}).waitFor();
  assert.equal(await page.locator('.skb-chip').count(),3);
  const after=await page.evaluate(()=>api('/api/skillbook'));assert.equal(after.boards.filter(b=>b.n_files>0).length,2);
  // 8 心法总诀：四份文件、复制、下载
  await page.locator('[data-skb="shelf"]').click();await page.waitForSelector('.skb-root.shelf .skb-zj-card');
  await page.locator('.skb-zj-card').click();await page.waitForSelector('.skb-zj-text');
  assert.equal(await page.locator('[data-skb-zj]').count(),5,'五份文件');
  assert.match(await page.locator('.skb-zj-text').textContent(),/提取|例题/);
  await page.locator('[data-skb-zj="使用流程.md"]').click();await page.waitForFunction(()=>/导入 skill/.test(document.querySelector('.skb-zj-text')?.textContent||''));
  await page.locator('[data-skb-zj="配置-空白模板.md"]').click();await page.waitForFunction(()=>/固定清单/.test(document.querySelector('.skb-zj-text')?.textContent||''));
  await fit(page,label+' 总诀');
  await page.locator('[data-skb="zj-copy"]').click();await page.locator('.skb-note').filter({hasText:/已复制|复制失败/}).waitFor();
  const [dl]=await Promise.all([page.waitForEvent('download'),page.locator('a.skb-dl').click()]);
  assert.match(decodeURIComponent(dl.url()),/\/zongjue-file\?f=配置-空白模板\.md/);   // 文件名由服务端 Content-Disposition 给（无头浏览器不一定显示中文名，这里只核对地址和内容）
  const txt=fs.readFileSync(await dl.path(),'utf8');assert.match(txt,/固定清单/);
  await page.locator('[data-skb="shelf"]').click();await page.waitForSelector('.skb-root.shelf .skb-tome');
  const t0=Date.now();await page.evaluate(()=>{go('home')});await page.evaluate(()=>{LIB.tab='skillbook';go('skeleton');});await page.waitForSelector('.skb-tome');
  assert(Date.now()-t0<2500,'再次进入立即出书架');
  assert.deepEqual(errors,[]);await page.close();service.kill();console.log(subject+' '+label+'：空板块/看/改/历史/冲突/新建改名删除/导入/总诀 通过');
 }
}catch(e){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure-'+subject+'.png')}).catch(()=>{});}throw e;}finally{await browser?.close();service?.kill();}})().catch(e=>{console.error(e);process.exit(1);});
