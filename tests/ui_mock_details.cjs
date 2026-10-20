/* 隔离自编整卷，电脑/平板：报告分/参考分分离、小数录入、原答题用时与旧资料兼容。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const law=!fs.existsSync('rpg/mock_score.py');let browser,srv,active;
const output=path.resolve('ui-artifacts/mock-details');
function service(){srv=spawn('python3',['tests/ui_layout_server.py',...(law?['--merge-fixture']:['行测','--score-fixture'])],{env:process.env});let log='';srv.stderr.on('data',b=>log+=b);return new Promise((ok,no)=>{let txt='';const timer=setTimeout(()=>no(Error(log)),20000);srv.stdout.on('data',b=>{txt+=b;const match=txt.match(/UI-READY (http:\/\/\S+)/);if(match){clearTimeout(timer);ok(match[1]);}});srv.on('exit',()=>{clearTimeout(timer);no(Error(log));});});}
async function bounds(p){assert.deepEqual(await p.evaluate(()=>{const bad=[];if(scrollY||document.documentElement.scrollWidth>innerWidth+2||document.documentElement.scrollHeight>innerHeight+2)bad.push('整页溢出');for(const e of document.querySelectorAll('.cs-pane:not([hidden]),.composer'))if(e.scrollWidth>e.clientWidth+2)bad.push('内容横向溢出');return bad;}),[]);}
(async()=>{try{browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});for(const [size,viewport]of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]]){
 const base=await service(),p=await browser.newPage({viewport});active=p;const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(base);await p.waitForFunction(()=>!!window.DASH_REF?.());await p.evaluate(()=>go('contest'));await p.locator('[data-cs-enter=entry]').click();await p.locator('[data-cs-fold=scores]>summary').click();
 if(law){assert.equal(await p.locator('#mkEstimate').count(),0);}else{
  assert.equal(await p.locator('#mkScore').inputValue(),'70.6');assert.equal(await p.locator('#mkScore').getAttribute('data-score-source'),'html');assert((await p.locator('#mkEstimate').textContent()).includes('99.15'));
  assert.equal(await p.evaluate(async()=>(await api('/api/mock')).seasons[0].score),null,'导入建议不自动录分');
  await p.locator('#mkUseEstimate').click();assert.equal(await p.locator('#mkScore').inputValue(),'99.15');assert(await p.locator('#mkScore').evaluate(e=>e.validity.valid));await p.locator('#mkUseReported').click();
 }
 const auto=p.locator('details').filter({has:p.locator('#rpFiles')}).last();await auto.locator(':scope>summary').click();const text=p.locator('#rpText');await text.evaluate(e=>e.closest('details').open=true);await text.fill('得分\n70\n.6');const scanned=p.waitForResponse(r=>r.url().endsWith('/api/mock/report/scan'));await p.locator('#rpScan').click();assert.equal((await(await scanned).json()).fields.score,'70.6');assert.equal(await p.locator('#mkScore').inputValue(),'70.6');
 for(const theme of ['light','dark']){await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);await bounds(p);}
 if(!law){
  await p.locator('#mkScore').fill('77.77');await p.evaluate(()=>CONTEST.importDone(39));assert.equal(await p.locator('#mkScore').inputValue(),'77.77');assert.equal(await p.locator('#mkScore').getAttribute('data-score-source'),'manual');
  await p.evaluate(()=>{if(window.CEREMONY)CEREMONY.contest=async()=>{};});await p.locator('#mkUseReported').click();const [saved]=await Promise.all([p.waitForResponse(r=>r.url().endsWith('/api/mock/save')),p.locator('[data-cs-save]').click()]);const record=(await saved.json()).summary.seasons[0];assert.equal(record.score,70.6);assert.equal(record.score_source,'html');
  await p.locator('#mkScore').waitFor({state:'attached'});assert.equal(await p.locator('#mkScore').inputValue(),'70.6');
  if(process.argv.includes('--shots')&&size==='tablet'){fs.mkdirSync(output,{recursive:true});await p.evaluate(()=>document.documentElement.dataset.theme='light');await p.screenshot({path:path.join(output,'tablet-scores.png')});}
  await p.evaluate(()=>startTask({task:{type:'mock_review',season:39,board:'政治理论'}}));await p.locator('.train').filter({hasText:'原答题用时：1:25'}).waitFor();const content=await p.locator('.train').innerText();assert(content.indexOf('正确答案')<content.indexOf('原答题用时'));assert(!content.includes('还没写复盘解析'));
  for(const theme of ['light','dark']){await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);await bounds(p);}
 }
 assert.deepEqual(errors,[]);await p.close();srv.kill();console.log((law?'法考':'行测')+' '+size+'：小数识别、成绩精度与边界'+(law?'（不启用行测参考表）':'、核分/保存/草稿、原用时顺序')+'通过');
 }}catch(e){if(active&&!active.isClosed()){fs.mkdirSync(output,{recursive:true});await active.screenshot({path:path.join(output,'failure'+(law?'-law':'')+'.png')}).catch(()=>{});}throw e;}finally{srv?.kill();await browser?.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
