/* 3.5藏经阁·心法·蒸馏真实浏览器回归（不连接AI：全部走“复制提示词 / 粘贴结果导入”这条路，和软件里的AI最后走同一个校验）：
   素材（贴逐字稿）→ 切分（定位、看全文、略过的文字）→ 拆卡 → 卡片预览 → 汇总 v1.0（待审建议，采纳后存版本）→ 再加素材更新到 v1.1（对比、回到旧版本）
   → 检验（程序判对错、做对率）→ 诊断错题（待审建议、采纳）；电脑/平板不整页滚动、不溢出；申论里没有蒸馏页签。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1]||'行测';
let logs='',browser,active,service;
function start(){service=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',subject,'--skillbook-fixture','--distill-fixture'],{env:process.env});service.stderr.on('data',x=>logs+=x);
 return new Promise((resolve,reject)=>{let s='';const timer=setTimeout(()=>reject(Error(logs||'服务启动超时')),20000);service.stdout.on('data',x=>{s+=x;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});service.on('exit',()=>{clearTimeout(timer);reject(Error(logs||'服务退出'));});});}
const out=path.resolve('ui-artifacts/distill');
const T="好，同学们大家好，今天我们先讲补全逻辑啊。呃，这个考点的特征是题干里有逻辑连词，比如如果、那么、只要、就、除非、否则、必须。\n所以看到逻辑连词，就把它连一连箭头，做做逆否。一会儿再给大家讲例题啊，先听免费系统课。\n\n好，我们来看这道2026年福建事业单位的题啊。结论是人工智能的艺术品本质是模仿，引词是因此。论据一，人工智能没有自我意识；论据二，审美需求对于创造性劳动是不可或缺的。\n所以这里缺一环：没有A就没有B，也就是只有A才B。C选项补上了这个逻辑，直接选C。A选项逻辑外挖坑，B选项题干没说将来。这道题选C。\n\n好，今天就到这里，大家下课。";
const SEG={segments:[{type:"考点",title:"补全逻辑",start:"好，同学们大家好，今天我们先讲补全逻辑啊",end:"做做逆否。"},{type:"闲聊",title:"预告",start:"一会儿再给大家讲例题啊",end:"先听免费系统课。"},{type:"例题",title:"2026福建事业单位",start:"好，我们来看这道2026年福建事业单位的题啊",end:"这道题选C。"},{type:"闲聊",title:"下课",start:"好，今天就到这里",end:"大家下课。"}]};
const POINT={name:"补全逻辑",one_line:"论据和结论之间缺一环，选项用逻辑连词补上",signals:{category:"表示条件关系的逻辑连词",examples:["如果","只要","除非"],test:"能不能改写成如果…那么…"},steps:["找结论","找论据","连箭头做逆否","选补上缺口的选项"],tips:["非补全逻辑的题里带逻辑连词的选项多是迷惑项"],quotes:["连一连箭头，做做逆否"],uncertain:[]};
const EXAMPLE={title:"2026福建事业单位",exam:"2026 福建事业单位",question:{complete:false,stem:"结论：人工智能艺术品本质是模仿",options:{C:"只有A才B"},answer:"C"},concepts:["补全逻辑"],steps:["找结论（引词因此）","找论据","发现缺没有A就没有B","选补上的C"],exclusions:[{option:"A",reason:"讨论方向超出论证",type:"逻辑外挖坑"},{option:"B",reason:"题干没说将来",type:"题干未提及"}],quotes:["这就是数学题"]};
const MINE="我的做法：看到指出相同类的选项，先找共同点，再看是不是论据和结论的共同点。这是我自己的总结，很简单。";
async function fit(page,tag){assert.deepEqual(await page.evaluate(()=>{const e=[];if(document.documentElement.scrollHeight>innerHeight+2||document.documentElement.scrollWidth>innerWidth+2||scrollY)e.push('整页滚动或横向溢出');for(const s of ['.skb-side','.skb-main','.skb-body']){const r=document.querySelector(s)?.getBoundingClientRect();if(!r||r.bottom>innerHeight+2||r.right>innerWidth+2)e.push(s+'伸出屏幕');}return e;}),[],tag);}
async function pasteImport(page,json,key){ // 点“复制提示词”→ 出现提示词包 → 粘贴回复 → 导入
 const box=page.locator('.dst-step').filter({has:page.locator(`[data-dst="pack"][data-key^="${key}"]`)}).first();
 await box.locator('[data-dst="pack"]').click();await box.locator('.dst-pack').first().waitFor();
 const text=await box.locator('.dst-pack').first().inputValue();
 await box.locator('.dst-paste').first().fill(typeof json==='string'?json:JSON.stringify(json));await box.locator('[data-dst="import"]').first().click();
 return text;}
(async()=>{try{
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 const sizes=process.argv.find(a=>a.startsWith('--sizes='))?.split('=')[1]?.split(',');
 for(const [label,viewport] of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]].filter(([l])=>!sizes||sizes.includes(l))){
  const base=await start();const page=await browser.newPage({viewport});active=page;const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.goto(base);await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&!!DASH);
  await page.evaluate(()=>{try{localStorage.removeItem('skillbook-pos')}catch{};LIB.tab='skillbook';go('skeleton');});await page.waitForSelector('.skb-root.shelf .skb-tome');
  await page.locator('.skb-tome').first().click({force:true});await page.waitForSelector('.skb-root.detail .skb-chip');
  if(subject==='申论'){assert.equal(await page.locator('[data-skb-tab]').count(),0,'申论没有蒸馏页签');await page.close();service.kill();console.log('申论：没有蒸馏页签 通过');continue;}
  assert.match(await page.locator('[data-skb-tab="distill"]').textContent(),/蒸馏/);
  await page.locator('[data-skb-tab="distill"]').click();await page.waitForSelector('.dst-root .dst-sub');
  // 1 添加素材：贴逐字稿
  await page.locator('[data-dst-f="title"]').fill('328课');await page.locator('[data-dst-f="text"]').fill(T);await page.locator('[data-dst="mat-add"]').click();
  await page.locator('.dst-mat').waitFor();assert.match(await page.locator('.skb-note').textContent(),/已添加素材/);
  // 2 切分：复制提示词包（含逐字稿和格式要求）→ 粘贴回复 → 导入
  const pack=await pasteImport(page,"好的，结果如下：\n```json\n"+JSON.stringify(SEG)+"\n```",'seg:');
  assert.match(pack,/补全逻辑/);assert.match(pack,/"segments"/);
  await page.locator('.dst-seg').first().waitFor();assert.equal(await page.locator('.dst-seg').count(),4);
  assert.equal(await page.locator('.dst-seg input[type=checkbox]:checked').count(),2,'闲聊默认不采用');
  await page.locator('.dst-seg').nth(2).locator('[data-dst="seg-text"]').click();assert.match(await page.locator('.dst-full').textContent(),/福建事业单位/);
  await page.locator('.dst-seg').nth(2).locator('[data-dst="seg-text"]').click();
  // 3 拆卡
  await pasteImport(page,{cards:[{segment:"s1",card:POINT},{segment:"s3",card:EXAMPLE}]},'card:');
  await page.locator('.skb-note').filter({hasText:'拆出 2 张卡'}).waitFor();
  await page.waitForFunction(()=>document.querySelectorAll('.dst-seg .tag.ok').length===2);
  await fit(page,label+' 素材');
  // 4 卡片：预览
  await page.locator('[data-dst-sub="cards"]').click();assert.equal(await page.locator('.dst-card').count(),2);
  await page.locator('[data-dst="card-open"]').first().click();await page.locator('.dst-md').waitFor();assert.match(await page.locator('.dst-md').textContent(),/识别信号/);
  assert.doesNotMatch(await page.locator('.dst-md').textContent(),/\$|\*\*/);
  await fit(page,label+' 卡片');
  // 5 汇总 v1.0：待审建议 → 采纳 → 版本
  await page.locator('[data-dst-sub="ver"]').click();await page.locator('[data-dst="build"]').click();const P1=page.locator('.skb-prop').filter({hasText:'生成蒸馏版 v1.0'});await P1.waitFor();
  assert.equal(await P1.locator('.skb-edit input:checked').count()>=5,true);
  await fit(page,label+' 待审建议');
  await P1.locator('[data-skb="accept"]').click();await page.locator('.skb-note').filter({hasText:'已存成版本 v1.0'}).waitFor();
  await page.locator('.dst-cur').filter({hasText:'当前版本 v1.0'}).waitFor();
  // 6 心法文件里能看到蒸馏版，阅读区渲染正常
  await page.locator('[data-skb-tab="files"]').click();await page.locator('.skb-chip[title="蒸馏/03-考点/补全逻辑.md"]').click();
  await page.locator('.skb-read').filter({hasText:'判别问法'}).waitFor();assert.match(await page.locator('.skb-read').textContent(),/已印证/);
  // 7 再加一份“自己的话”，拆卡并进已有考点，更新到 v1.1
  await page.locator('[data-skb-tab="distill"]').click();await page.locator('[data-dst-sub="mat"]').click();
  await page.locator('.dst-add summary').click();await page.locator('[data-dst-f="kind"]').selectOption('自述');await page.locator('[data-dst-f="whole"]').selectOption('考点');
  await page.locator('[data-dst-f="title"]').fill('我的总结');await page.locator('[data-dst-f="text"]').fill(MINE);await page.locator('[data-dst="mat-add"]').click();
  await page.locator('.dst-mat').nth(1).waitFor();
  await pasteImport(page,{cards:[{segment:"s1",card:{name:"指出相同",one_line:"找共同点",signals:{category:"共同点",examples:["相同"],test:""},steps:["找共同点","看是不是论据和结论的共同点"],quotes:["先找共同点"]}}]},'card:');
  await page.locator('.skb-note').filter({hasText:'拆出 1 张卡'}).waitFor();
  await page.locator('[data-dst-sub="ver"]').click();await page.locator('.dst-cur').filter({hasText:/有 1 张新卡/}).waitFor();
  await page.locator('[data-dst="build"]').click();const P2=page.locator('.skb-prop').filter({hasText:'更新到 v1.1'});await P2.waitFor();
  assert.match(await P2.textContent(),/整个文件更新|新建/);
  await P2.locator('[data-skb="accept"]').click();await page.locator('.skb-note').filter({hasText:'已存成版本 v1.1'}).waitFor();
  await page.locator('.dst-ver').filter({hasText:'v1.1'}).waitFor();
  await page.locator('.dst-ver').filter({hasText:'v1.1'}).locator('[data-dst="cmp"]').first().click();await page.locator('.dst-cmp').waitFor();assert.match(await page.locator('.dst-cmp').textContent(),/指出相同/);
  await fit(page,label+' 版本');
  // 8 检验：抽题 → 复制提示词（只有题干选项，没有答案）→ 粘贴全部选 A（题库答案全是 B）→ 程序判全错
  await page.locator('[data-dst-sub="test"]').click();await page.locator('[data-dst-n]').fill('5');await page.locator('[data-dst-n]').press('Tab');await page.locator('[data-dst="test-start"]').click();await page.locator('.dst-step').first().waitFor();
  const tp=await pasteImport(page,{answers:[1,2,3,4,5].map(n=>({n,answer:"A",why:"随便选的"}))},'test:');
  assert.match(tp,/补全逻辑/);assert.doesNotMatch(tp,/正确答案/);
  await page.locator('.skb-note').filter({hasText:'做完了：0 / 5'}).waitFor();
  await page.locator('[data-dst="res-open"]').first().click();await page.locator('.dst-cmp').filter({hasText:'0 / 5 题做对'}).waitFor();
  // 9 诊断错题 → 待审建议 → 采纳 → v1.2
  await pasteImport(page,{suggestions:[{concept:"补全逻辑",problem:"漏了方向",fix:"- 必要条件的箭头指向必须的一方"}]},'diag:');
  const P3=page.locator('.skb-prop').filter({hasText:'根据检验的错题补充心法'});await P3.waitFor();
  await P3.locator('[data-skb="accept"]').click();await page.locator('.skb-note').filter({hasText:'已存成版本 v1.2'}).waitFor();
  await page.locator('[data-dst-sub="ver"]').click();await page.locator('.dst-ver').filter({hasText:'v1.2'}).waitFor();
  // 10 回到 v1.0：文件换回去，指出相同考点不在了
  await page.locator('.dst-ver').filter({hasText:'v1.0'}).locator('[data-dst="restore"]').click();await page.locator('.skb-note').filter({hasText:'已回到 v1.0'}).waitFor();
  await page.locator('[data-skb-tab="files"]').click();await page.locator('.skb-chip').first().waitFor();
  assert.equal(await page.locator('.skb-chip[title="蒸馏/03-考点/指出相同.md"]').count(),0);
  await fit(page,label+' 结束');
  assert.deepEqual(errors,[]);await page.close();service.kill();console.log('行测 '+label+'：素材/切分/拆卡/汇总v1.0/更新v1.1/对比/检验/诊断/回滚 通过');
 }
}catch(e){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure-'+subject+'.png')}).catch(()=>{});}throw e;}finally{await browser?.close();service?.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
