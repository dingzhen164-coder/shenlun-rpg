/* 自编HTML/资源ZIP的真实UI/API导入：不连接AI、不读真实资料；电脑和平板明暗。 */
const {chromium}=require('playwright'),{spawn,execFileSync}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const law=!fs.existsSync('rpg/html_mock.py');
const data=law?null:JSON.parse(execFileSync('python3',['-c','import json;from tests.test_html_mock import body;print(json.dumps(body()))'],{env:process.env,encoding:'utf8'}));
const srv=spawn('python3',['tests/ui_layout_server.py',...(subject?[subject]:[]),...(law?['--merge-fixture']:[])],{env:process.env});let browser,active,log='';srv.stderr.on('data',b=>log+=b);
const ready=new Promise((ok,no)=>{let text='';const t=setTimeout(()=>no(Error(log)),20000);srv.stdout.on('data',b=>{text+=b;const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});srv.on('exit',()=>{clearTimeout(t);no(Error(log));});});
const out=path.resolve('ui-artifacts/mock-html');
(async()=>{try{const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});for(const [size,viewport]of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]]){
 const p=await browser.newPage({viewport});active=p;const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(base);await p.waitForFunction(()=>!!window.DASH_REF?.());await p.evaluate(()=>go('contest'));await p.locator('[data-cs-enter=entry]').click();
 if(law){assert.equal(await p.locator('#mockPaperImport').count(),0);assert.equal(await p.locator('[data-cs-fold=scores]').evaluate(e=>e.open),false);await p.locator('[data-cs-fold=scores]>summary').click();await p.locator('#mkScore').fill('76');}
 else{
  assert.equal(await p.locator('#mockPaperImport').evaluate(e=>e.open),false);await p.locator('#mockPaperImport>summary').click();
  await p.locator('#mhFile').setInputFiles({name:data.name,mimeType:'text/html',buffer:Buffer.from(data.data,'base64')});
  // 单HTML发现缺图，预览不得创建复盘或授予导入时长。
  const first=p.waitForResponse(r=>r.url().endsWith('/api/import/html'));await p.locator('#mhPreview').click();const missing=await(await first).json();assert.equal(missing.missing_images,1);
  await p.locator('#mhResult').filter({hasText:'缺少 1'}).waitFor();
  await p.locator('#mhAssets').setInputFiles({name:data.resources.name,mimeType:'application/zip',buffer:Buffer.from(data.resources.data,'base64')});
  const checked=p.waitForResponse(r=>r.url().endsWith('/api/import/html'));await p.locator('#mhPreview').click();const r=await(await checked).json();assert.equal(r.missing_images,0);assert.equal(r.total,10);
  await p.locator('#mhResult').filter({hasText:'检查完成'}).waitFor();const saved=p.waitForResponse(r=>r.url().endsWith('/api/import/html'));await p.locator('#mhCommit').click();const committed=await(await saved).json();assert.equal(committed.ready,size==='desktop'?10:0);
  await p.locator('#mhResult').filter({hasText:'导入完成'}).waitFor();await p.locator('#mkSeason').waitFor({state:'attached'});assert.equal(await p.locator('#mkSeason').inputValue(),'39');assert.equal(await p.locator('[data-cs-fold=scores]').evaluate(e=>e.open),false);
  const minutes=await p.evaluate(async()=>(await api('/api/dashboard')).minutes.today);assert.equal(minutes,120,'同季重复导入不能重复累计');
  // 录分草稿在折叠、离开卷宗和导入重绘后保留。
  await p.locator('[data-cs-fold=scores]>summary').click();await p.locator('#mkScore').fill('77.7');await p.locator('[data-cs-fold=scores]>summary').click();await p.locator('[data-cs-fold=scores]>summary').click();assert.equal(await p.locator('#mkScore').inputValue(),'77.7');
  await p.evaluate(()=>CONTEST.importDone(39));assert.equal(await p.locator('#mkScore').inputValue(),'77.7');
  await p.evaluate(()=>{document.querySelector('#mockPaperImport').open=false;document.querySelector('[data-cs-fold=scores]').open=false;});
 }
 for(const theme of ['light','dark']){await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);assert.deepEqual(await p.evaluate(()=>{const bad=[];if(scrollY||document.documentElement.scrollWidth>innerWidth+2||document.documentElement.scrollHeight>innerHeight+2)bad.push('整页溢出');const pane=document.querySelector('#cs-pane-entry');if(pane.scrollWidth>pane.clientWidth+2)bad.push('录入横向溢出');return bad;}),[]);}
 if(process.argv.includes('--shots')&&!law){fs.mkdirSync(out,{recursive:true});await p.evaluate(()=>document.documentElement.dataset.theme='light');await p.screenshot({path:path.join(out,size+'-entry.png')});}
 await p.locator('[data-cs-close]').click();await p.locator('[data-cs-enter=entry]').click();if(!law){await p.locator('[data-cs-fold=scores]>summary').click();assert.equal(await p.locator('#mkScore').inputValue(),'77.7');}
 assert.deepEqual(errors,[]);await p.close();console.log((law?'法考':'行测')+' '+size+'：录入折叠、HTML/资源检查、真实导入、重复幂等/120分钟、草稿及边界通过');
 }}catch(e){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure'+(law?'-law':'')+'.png')}).catch(()=>{});}throw e;}finally{await browser?.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
