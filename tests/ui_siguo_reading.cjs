/* 思过崖（2026-11-11 用户需求）：①题目字号按钮只放大题目标题/题干/选项，解析不变，题干默认 18 号字；
   ②左侧目录点下面的题、作答、再做一次都不跳回顶部，下一题走出可见范围时只挪一点，重进板块直接显示上次那题；目录无横向滚动条。
   电脑与平板横竖屏下检查。 */
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
const service=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','行测','--siguo-fixture'],{env:process.env});let logs='';service.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let o='';const t=setTimeout(()=>no(Error(logs)),20000);service.stdout.on('data',b=>{o+=b;const m=o.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});service.on('exit',()=>{clearTimeout(t);no(Error(logs));});});
(async()=>{let browser;try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,viewport] of [['desktop',{width:1280,height:860}],['portrait',{width:800,height:1280}],['landscape',{width:1280,height:800}]]){
  const page=await browser.newPage({viewport});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{try{if(!sessionStorage.getItem('sgReadingInit')){sessionStorage.setItem('sgReadingInit','1');localStorage.removeItem('sg-pos-v1');localStorage.removeItem('chatLayout');}}catch(_){}});
  await page.goto(base);await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&DASH);
  await page.evaluate(()=>go('tianji'));await page.waitForSelector('.sg-stele');
  assert.equal(await page.locator('#studyHud .reading-size-tools').count(),0,'石碑场景不显示题目字号按钮');
  await page.click('[data-sgboard="定义判断"]');await page.waitForSelector('.sg-q:nth-child(30)');
  await page.waitForSelector('#studyHud .reading-size-tools');
  const size=()=>page.evaluate(()=>({stem:parseFloat(getComputedStyle(document.querySelector('.sg-stem')).fontSize),title:parseFloat(getComputedStyle(document.querySelector('.sg-qtitle')).fontSize),
    opt:parseFloat(getComputedStyle(document.querySelector('.sg-opt')).fontSize),list:parseFloat(getComputedStyle(document.querySelector('.sg-q span')).fontSize),
    out:document.querySelector('#studyHud .reading-size-tools output').textContent}));
  const s0=await size();assert.equal(s0.stem,18,'题干默认 18 号字（不再被解析的 14 号盖掉）');assert.equal(s0.title,20);assert.equal(s0.opt,16);assert.equal(s0.out,'110%');
  const listBox=await page.evaluate(()=>{const l=document.querySelector('.sg-list');return {sw:l.scrollWidth,cw:l.clientWidth,row:getComputedStyle(l).flexDirection==='row'};});
  if(!listBox.row)assert(listBox.sw<=listBox.cw,'竖排目录没有横向滚动条');
  // 点下面的题：目录不跳回顶部
  const scrollKey=listBox.row?'scrollLeft':'scrollTop';
  await page.evaluate(k=>{const l=document.querySelector('.sg-list');l[k]=l[k==='scrollTop'?'scrollHeight':'scrollWidth'];},scrollKey);
  const before=await page.evaluate(k=>document.querySelector('.sg-list')[k],scrollKey);assert(before>200,'目录可以往下翻');
  // 点一个完全看得见的靠后的题（竖屏目录是横排，最右边那几个可能只露半截）
  const pick=await page.evaluate(()=>{const l=document.querySelector('.sg-list').getBoundingClientRect();const qs=[...document.querySelectorAll('.sg-q')];
    for(let i=qs.length-2;i>=0;i--){const r=qs[i].getBoundingClientRect();if(r.top>=l.top&&r.bottom<=l.bottom&&r.left>=l.left&&r.right<=l.right)return i+1;}return 0;});
  assert(pick>20,'翻到后面的题 '+pick);
  await page.click(`.sg-q:nth-child(${pick})`);await page.waitForSelector(`.sg-q:nth-child(${pick}).on`);
  const after=await page.evaluate(k=>document.querySelector('.sg-list')[k],scrollKey);assert(Math.abs(after-before)<2,`点题后目录停在原位 ${before}→${after}`);
  // 作答、再做一次：目录仍不动
  await page.click('[data-sgpick="B"]');await page.waitForSelector('.sg-verdict.bad');
  assert(Math.abs(await page.evaluate(k=>document.querySelector('.sg-list')[k],scrollKey)-before)<2,'作答后目录不动');
  // 解析不跟着放大，题目跟着放大
  const secBefore=await page.evaluate(()=>parseFloat(getComputedStyle(document.querySelector('.sg-sec .sg-md')).fontSize));
  await page.click('#studyHud [data-reading-size="10"]');await page.click('#studyHud [data-reading-size="10"]');
  await page.waitForTimeout(600);   // 按钮字号有过渡动画，等它走完再量
  const s1=await size();assert.equal(s1.out,'130%');assert(Math.abs(s1.stem-18*13/11)<0.6&&Math.abs(s1.opt-16*13/11)<0.6&&s1.title>s0.title,'题目跟着放大 '+JSON.stringify(s1));
  assert.equal(s1.list,s0.list,'左侧目录字号不变');
  assert.equal(await page.evaluate(()=>parseFloat(getComputedStyle(document.querySelector('.sg-sec .sg-md')).fontSize)),secBefore,'解析字号不变');
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('chatLayout')).fs),130,'与答题页共用同一个字号偏好');
  await page.click('[data-sgredo]');await page.waitForSelector('.sg-opt:not([disabled])');
  assert(Math.abs(await page.evaluate(k=>document.querySelector('.sg-list')[k],scrollKey)-before)<2,'再做一次后目录不动');
  // 回顶部后点“下一题”一路走到看不见的题：只挪到刚好露出来，不跳回顶部
  await page.evaluate(k=>{document.querySelector('.sg-list')[k]=0;},scrollKey);
  await page.click('.sg-q:nth-child(1)');
  for(let i=2;i<=12;i++){await page.click('.sg-acts .primary');await page.waitForSelector(`.sg-q:nth-child(${i}).on`);}
  const vis=await page.evaluate(()=>{const l=document.querySelector('.sg-list').getBoundingClientRect(),r=document.querySelector('.sg-q.on').getBoundingClientRect();return r.top>=l.top-1&&r.bottom<=l.bottom+1&&r.left>=l.left-1&&r.right<=l.right+1;});
  assert(vis,'当前题始终露在目录可见范围里');
  // 离开再进：直接显示上次那题，并且在目录里看得见
  await page.click('[data-sgback]');await page.waitForSelector('.sg-stele');
  assert.equal(await page.locator('#studyHud .reading-size-tools').count(),0,'回到石碑场景字号按钮拿掉');
  await page.click('[data-sgboard="定义判断"]');await page.waitForSelector('.sg-q:nth-child(12).on');
  const vis2=await page.evaluate(()=>{const l=document.querySelector('.sg-list').getBoundingClientRect(),r=document.querySelector('.sg-q.on').getBoundingClientRect();return r.top>=l.top-1&&r.bottom<=l.bottom+1&&r.left>=l.left-1&&r.right<=l.right+1;});
  assert(vis2,'重进板块时上次那题在目录里看得见');
  // 刷新后字号保持
  await page.reload();await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&DASH);await page.evaluate(()=>go('tianji'));await page.waitForSelector('.sg-stele');
  await page.click('[data-sgboard="定义判断"]');await page.waitForSelector('#studyHud .reading-size-tools');
  assert.equal((await size()).out,'130%');assert(Math.abs((await size()).stem-18*13/11)<0.6,'刷新后题目字号保持');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'无横向溢出');
  assert.deepEqual(errors,[]);await page.close();console.log(`思过崖字号与目录位置 ${label}：通过`);
 }
}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exit(1);});
