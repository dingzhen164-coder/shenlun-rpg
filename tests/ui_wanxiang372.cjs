/* 3.7.2：独立期刊、统一导入、冲刺三栏/四类目录、正文占比；隔离假库、假AI。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs');
const srv=spawn('python3',['tests/ui_layout_server.py','行测','--politics-fixture'],{env:process.env});let browser,page,logs='',train='';
srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let s='';const t=setTimeout(()=>no(Error(logs)),20000);srv.stdout.on('data',b=>{s+=b;const f=s.match(/UI-POLITICS (.+)/);if(f)train=f[1];const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});srv.on('exit',()=>{clearTimeout(t);no(Error(logs));});});
async function fit(f,selector){const data=await f.locator(selector).evaluate(el=>{const r=el.getBoundingClientRect();return {overflow:document.documentElement.scrollWidth>innerWidth+2,bodyTop:r.top,ratio:(innerHeight-r.top)/innerHeight};});assert(!data.overflow,'正文无横向溢出');assert(data.ratio>.72,'正文保留至少72%可用高度：'+JSON.stringify(data));}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 fs.mkdirSync('ui-artifacts/wanxiang372',{recursive:true});
 for(const [size,width,height]of [['desktop',1280,860],['tablet',800,1280],['tablet-landscape',1280,800]])for(const theme of ['light','dark']){
  page=await browser.newPage({viewport:{width,height},hasTouch:true,reducedMotion:'reduce'});page.setDefaultTimeout(12000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.evaluate(t=>{document.documentElement.dataset.theme=t;STUDY_REGIONS.select('chang');return go('train');},theme);
  await page.locator('[data-wx-branch=politics]').click();await page.locator('[data-wx-exam]').first().click();let f=page.frameLocator('.wx-atlas-frame');
  await f.locator('.wxj-cover').first().waitFor();assert.deepEqual(await f.locator('#nav button').allTextContents(),['月半时政','专题时政','冲刺学习','冲刺刷题']);assert.equal(await f.locator('input[type=file],[data-import]').count(),0);
  await f.locator('[data-open="month|2026-10-上"]').click();await f.locator('.wxj-news-body').waitFor();await fit(f,'.wxj-news-body');assert.equal(await f.locator('.atlas-toolbar').isVisible(),false,'期刊正文不叠加两层导航刘海');
  await f.locator('#wxjRead').click();await f.locator('[data-mode=cloze]').click();const blank=f.locator('.wxj-b[data-b]').first(),wasRemembered=(await blank.getAttribute('class')).split(' ').includes('ok');await blank.click();await f.locator('.wxj-b.'+(wasRemembered?'no':'ok')+'[data-b]').first().waitFor();
  await f.locator('#wxjBack').click();await f.locator('#nav [data-go=topic]').click();await f.locator('[data-open="topic|old-topic"]').click();await f.locator('.wxj-news-body').waitFor();await fit(f,'.wxj-news-body');
  if(theme==='light')await page.screenshot({path:`ui-artifacts/wanxiang372/${size}-topic.png`});
  await f.locator('#wxjBack').click();await f.locator('#nav [data-go=sprint]').click();assert.equal(await f.locator('.sprint-group').count(),4);assert.deepEqual(await f.locator('.sprint-group summary').evaluateAll(es=>es.map(e=>e.childNodes[0].textContent)),['重大会议','讲话','指导','文件']);
  await f.locator('[data-material=m1]').click();await f.locator('.original').waitFor();assert.deepEqual(await f.locator('.tabs button').allTextContents(),['研读','消化','精卷']);await fit(f,'.original');
  await f.locator('[data-tab=understand]').click();await f.locator('.digest-card details summary').first().click();await f.locator('[data-digest][data-value=remember]').first().click();await f.locator('[data-digest][data-value=remember][aria-pressed=true]').waitFor();
  await f.locator('.atlas-reading-tools [data-go=sprint]').click();await f.locator('#nav [data-go=practice]').click();await f.locator('.question').waitFor();assert.equal(await f.locator('.tabs').count(),0,'冲刺刷题不套研读三栏');
  const old=await page.evaluate(()=>api('/api/tianji/get',{kind:'month',id:'2026-10-上'}));assert.deepEqual(old.progress.read,[],'新阅读不回写旧天机台');assert.deepEqual(old.progress.cloze,{});
  await f.locator('#atlasBack').click();await page.locator('.wx-import>summary').click();assert.deepEqual(await page.locator('select[name=channel] option').evaluateAll(es=>es.map(e=>e.value)),['month','topic','sprint-study','sprint-quiz']);
  await page.locator('[name=channel]').selectOption('month');assert.equal(await page.locator('[data-import-exam]').isVisible(),false);await page.locator('[name=channel]').selectOption('sprint-study');assert(await page.locator('[data-import-exam]').isVisible());
  if(size==='desktop'&&theme==='light'){await page.locator('[name=exam]').selectOption('2026-12-shengkao');await page.locator('[name=pdf]').setInputFiles(train+'/自编补充.pdf');await page.locator('[data-politics-import] [type=submit]').click();await page.locator('[data-import-result]').filter({hasText:'已加入 1 份材料、1 道题'}).waitFor();}
  assert.deepEqual(errors,[]);await page.close();console.log(size+'/'+theme+'：四栏目、独立期刊/消化进度、四类冲刺目录、统一导入及正文占比通过');
 }
}catch(e){if(page&&!page.isClosed())await page.screenshot({path:'ui-artifacts/wanxiang372/failure.png'}).catch(()=>{});throw e;}finally{await browser?.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
