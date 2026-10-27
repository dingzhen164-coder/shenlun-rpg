/* 3.7.3真实HTTP浏览器：自编资料/隔离临时库/假AI；电脑和平板横竖屏。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs');
const server=spawn('python3',['tests/ui_layout_server.py','行测','--politics-fixture','--wanxiang373-fixture'],{env:process.env});let browser,page,logs='',train='';server.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let text='';const timer=setTimeout(()=>no(Error(logs)),20000);server.stdout.on('data',b=>{text+=b;const f=text.match(/UI-POLITICS (.+)/);if(f)train=f[1];const m=text.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});server.on('exit',()=>{clearTimeout(timer);no(Error(logs));});});
async function enter(){await page.evaluate(()=>{STUDY_REGIONS.select('chang');return go('train');});await page.locator('[data-wx-branch=politics]').click();await page.locator('[data-wx-exam]').first().click();const f=page.frameLocator('.wx-atlas-frame');await f.locator('#nav [data-go=sprint]').click();await f.locator('.sprint-workspace').waitFor();return f;}
async function select(f,word,selector='.original p'){await f.locator(selector).first().evaluate((p,word)=>{const at=p.textContent.indexOf(word),walk=document.createTreeWalker(p,NodeFilter.SHOW_TEXT);let node,offset=0,a,b;while(node=walk.nextNode()){const n=node.textContent.length;if(!a&&at<offset+n)a=[node,at-offset];if(at+word.length<=offset+n){b=[node,at+word.length-offset];break;}offset+=n;}const r=document.createRange();r.setStart(...a);r.setEnd(...b);getSelection().removeAllRanges();getSelection().addRange(r);document.dispatchEvent(new Event('selectionchange'));},word);await f.locator('.wn-highlight:not([hidden])').waitFor();}
async function columns(f,right){const geometry=await f.locator('.sprint-workspace').evaluate((el,right)=>{const a=el.querySelector('.sprint-index').getBoundingClientRect(),b=el.querySelector(right).getBoundingClientRect();return {ratio:a.width/el.clientWidth,separate:a.right<b.left,overflow:document.documentElement.scrollWidth>innerWidth+2,top:b.top,height:innerHeight,paper:getComputedStyle(el.querySelector(right)).backgroundColor};},right);assert(geometry.separate&&geometry.ratio<.24,'目录始终在左侧且足够窄：'+JSON.stringify(geometry));assert(!geometry.overflow);const alpha=geometry.paper.match(/\/\s*([\d.]+)/)?.[1]||1;assert(Number(alpha)>=.88,'文字区域须保留足够底色对比度：'+geometry.paper);}
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});fs.mkdirSync('ui-artifacts/wanxiang373',{recursive:true});
 const combinations=[['desktop',1280,860],['tablet',800,1280],['landscape',1280,800]];
 for(const [size,width,height]of combinations)for(const theme of ['light','dark']){
  page=await browser.newPage({viewport:{width,height},hasTouch:true,reducedMotion:'reduce'});page.setDefaultTimeout(12000);const errors=[];let explainCalls=0;page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/api/politics/explain'))explainCalls++;});
  await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
  if(size==='desktop'&&theme==='light'){
   await page.locator('.npc-drawer-toggle').waitFor();
   for(const id of ['chang','yan','li','shu','zi']){await page.evaluate(id=>{STUDY_REGIONS.select(id);return go('train');},id);await page.locator('.npc-drawer-toggle').waitFor();}
   for(const view of ['bank','contest','skeleton','tianji','dwelling','settings']){await page.evaluate(v=>go(v),view);await page.locator('.npc-encounters').waitFor({state:'detached'});}
   await page.evaluate(()=>{STUDY_REGIONS.select('chang');return go('train');});await page.locator('[data-wx-branch=politics]').click();await page.locator('.wx-import>summary').click();await page.locator('[name=channel]').selectOption('digest');assert.equal(await page.locator('[name=target],[data-digest-target]').count(),0,'消化清单不再选择配套讲义');await page.locator('[name=pdf]').setInputFiles(train+'/自编消化清单.pdf');await page.locator('[data-politics-import] [type=submit]').click();await page.locator('[data-import-result]').filter({hasText:'共8空'}).waitFor();assert.match(await page.locator('[data-import-result]').textContent(),/1段没在讲义原文里直接找到，已按前后文放进相邻资料/);

  }
  let f=await enter();await page.locator('.npc-encounters').waitFor({state:'detached'});await columns(f,'.sprint-welcome');assert.equal(await f.locator('.sprint-group').count(),4);
  await f.locator('.sprint-index.hx381-shell').waitFor();const frost=await f.locator('.sprint-index').evaluate(e=>{const s=getComputedStyle(e);return{bg:s.backgroundColor,blur:s.backdropFilter||s.webkitBackdropFilter,border:s.borderTopWidth,edge:s.borderTopColor};});assert.notEqual(frost.bg,'rgba(0, 0, 0, 0)','目录必须有轻透底板');assert.match(frost.blur,/blur\(/,'目录保留背景虚化');assert.equal(frost.border,'1px');assert.notEqual(frost.edge,'rgba(0, 0, 0, 0)','目录保留细边线');
  await f.locator('[data-material=m1]').click();await f.locator('.original[data-highlights-ready=true]').waitFor();await columns(f,'.sprint-document-body');
  { // 所有标题不加红：标题块不渲染标红且用正文墨色；正文标红保持。目录条目下显示字数而不是“未学·N题”。
   await f.locator('[data-material=m3]').click();await f.locator('.original[data-highlights-ready=true]').waitFor();
   const h=await f.locator('.original').evaluate(host=>{const q=host.querySelector('p .source-emphasis');return{heads:[...host.querySelectorAll('.source-heading')].map(e=>({text:e.textContent,emph:e.querySelectorAll('.source-emphasis').length,color:getComputedStyle(e).color})),bodyEmph:host.querySelectorAll('p .source-emphasis').length,bodyColor:q?getComputedStyle(q).color:'',ink:getComputedStyle(host).color};});
   assert.equal(h.heads.length,2);for(const x of h.heads){assert.equal(x.emph,0,'标题不加红：'+x.text);assert.equal(x.color,h.ink,'标题使用正文墨色：'+x.text);assert.notEqual(x.color,h.bodyColor);}assert.ok(h.bodyEmph>=1,'正文标红保持');
   assert.match(await f.locator('.sprint-index [data-material=m3] small').textContent(),/^共计\d+字$/);assert.equal(await f.locator('.sprint-index [data-material=m3] small').textContent().then(t=>/题|未学/.test(t)),false);
   await f.locator('[data-material=m1]').click();await f.locator('.original[data-highlights-ready=true]').waitFor();
  }
  if(size==='desktop'&&theme==='light'){
   { // 一键取消这一篇的红标记（再恢复）：不改批注、不动消化清单的空
    const bulk=f.locator('.wn-bulk-btn');assert.equal((await bulk.textContent()).includes('一键取消红标记'),true);
    page.once('dialog',d=>d.accept());await bulk.click();await f.locator('.source-emphasis').waitFor({state:'detached'});
    assert.equal(await bulk.isVisible(),false,'取消后没有红标记，按钮隐藏，也没有“恢复红标记”');assert.equal(explainCalls,0);
    await select(f,'主产区');await f.locator('.wn-highlight').click();await f.locator('.source-emphasis').waitFor();assert.equal(await f.locator('.source-emphasis').count(),1,'取消后自己重新标红');
    assert.equal((await bulk.textContent()).includes('一键取消红标记'),true);
   }
   assert.equal(await f.locator('.source-emphasis').count(),1);await select(f,'主产区');assert.equal(await f.locator('.wn-highlight').textContent(),'取消标红');await f.locator('.wn-highlight').click();await f.locator('.source-emphasis').waitFor({state:'detached'});assert.equal(explainCalls,0);
   await f.locator('[data-tab=understand]').click();await f.locator('[data-digest-blank]').first().waitFor();assert.equal(await f.locator('[data-digest-blank]').count(),1,'取消标红不移除PDF空位');assert.equal(await f.locator('.digest-pending').count(),1,'找不到出处的清单段落也保留，标为待补全');assert.equal(await f.locator('.sprint-digest-meta,.sprint-digest-source,[data-digest-filter]').count(),0,'清单页不再显示配套/统计/来源行');await f.locator('[data-tab=original]').click();await f.locator('.original[data-highlights-ready=true]').waitFor();await select(f,'主产区');await f.locator('.wn-highlight').click();await f.locator('.source-emphasis').waitFor();
   await f.locator('.source-emphasis').click();await f.locator('.wn-pop section').first().waitFor();assert.equal(explainCalls,1);await f.locator('.wn-unmark').click();await f.locator('.source-emphasis').waitFor({state:'detached'});await f.locator('.wn-word').click();await f.locator('.wn-pop section').first().waitFor();assert.equal(explainCalls,1,'取消标红后批注仍读取缓存');await f.locator('.wn-pop header button').click();await select(f,'主产区');await f.locator('.wn-highlight').click();await f.locator('.source-emphasis').waitFor();
  }
  if(size==='desktop'&&theme==='light'){await f.locator('.sprint-index [data-material=m2]').click();await f.locator('.original[data-highlights-ready=true]').waitFor();await select(f,'甲方','.original p:last-child');await f.locator('.wn-select').click();await f.locator('.wn-pop section').first().waitFor();assert.equal(await f.locator('.original p').first().locator('.wn-word').count(),0,'重复段落的批注不能串位');assert.equal(await f.locator('.original p').last().locator('.wn-word').count(),1);await f.locator('.wn-pop header button').click();await f.locator('.sprint-index [data-material=m1]').click();await f.locator('.original[data-highlights-ready=true]').waitFor();}
  await f.locator('[data-tab=understand]').click();await f.locator('[data-digest-blank]').first().waitFor();assert.equal(await f.locator('[data-digest-blank]').count(),1);assert.equal(await f.locator('.digest-pending').count(),1);await f.locator('[data-digest-blank]').click();await f.locator('.sprint-blank:not(:disabled)').waitFor();assert.equal(await f.locator('.sprint-blank:not(:disabled)').evaluate(el=>getComputedStyle(el).whiteSpace),'normal');
  { // 重置所有的空：核对过的空回到“没核对”，可以再复习一遍
   const reset=f.locator('[data-digest-reset]');await reset.waitFor();
   assert.equal(await reset.isEnabled(),true,'核对过一个空后，重置按钮可点');assert.match(await reset.textContent(),/已核对 1 个/);
   page.once('dialog',d=>d.accept());await reset.click();await f.locator('.sprint-blank.hidden-answer').waitFor();assert.equal(await f.locator('[data-digest-reset]').isDisabled(),true,'没有核对过的空时重置按钮置灰');
   assert.equal(await f.locator('.sprint-blank.remember,.sprint-blank.forgot').count(),0,'重置后空位都盖回去');assert.equal(await f.locator('[data-digest-blank]').count(),1,'PDF里的空还在');
   await f.locator('[data-digest-blank]').click();await f.locator('.sprint-blank:not(:disabled)').waitFor();
  }
  if(theme==='light'&&size!=='landscape')await page.screenshot({path:`ui-artifacts/wanxiang373/${size}-cloze.png`});
  await f.locator('.atlas-reading-tools [data-go=sprint]').click();await f.locator('#nav [data-go=practice]').click();
  if(size==='desktop'&&theme==='light'){await f.locator('.sprint-practice-empty').waitFor();assert.equal(await f.locator('.question').count(),0);
   await page.evaluate(async data=>api('/api/wanxiang/import',{channel:'sprint-quiz',name:'自编补充.pdf',data}),fs.readFileSync(train+'/自编补充.pdf').toString('base64'));
   f=await enter();await f.locator('#nav [data-go=practice]').click();
  }
  await f.locator('.question').waitFor();assert.equal(await f.locator('.question').getAttribute('id'),'q2','只显示导入题（题号2），内置第1题不混入');assert((await f.locator('.question .chip').textContent()).includes('第1题'),'卡片显示套卷内题号');assert.equal(await f.locator('.wx-reflow-line').count(),5,'题干与四个选项分别自动折行');
  if(size==='desktop'&&theme==='light'){await f.locator('#atlasSearch').click();await f.locator('#search').fill('本段支持谁');await f.locator('[data-question-link="1"]').click();await f.locator('#q1').waitFor();assert.equal(await f.locator('[data-tab=questions][aria-selected=true]').count(),1,'搜索内置题进入讲义精卷，不跳到只含导入题的刷题区');await f.locator('.atlas-reading-tools [data-go=sprint]').click();}
  await f.locator('#nav [data-go=month]').click();await f.locator('[data-open="month|2026-10-上"]').click();await f.locator('.wxj-news-body[data-highlights-ready=true]').waitFor();
  await f.locator('[data-mode=cloze]').click();assert.deepEqual(await f.locator('.wxj-b[data-digest-blank]').allTextContents(),['主产区'],'期刊兼容原PDF的消化清单');
  await f.locator('[data-mode=quiz]').click();assert.equal(await f.locator('.wxj-q-stem .wx-reflow-line').count(),1,'期刊题干没有PDF硬换行');assert.equal(await f.locator('.wxj-opt').first().textContent(),'A自编甲方选项的续行');
  const overflow=await f.locator('body').evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);assert(!overflow);assert.deepEqual(errors,[]);await page.close();console.log(size+'/'+theme+'：双栏、重点/消化、取消复用、题面重排与题源隔离通过');
 }
}catch(e){if(page&&!page.isClosed())console.error('导入诊断',await page.locator('[data-import-result]').allTextContents());if(page&&!page.isClosed())await page.screenshot({path:'ui-artifacts/wanxiang373/failure.png'}).catch(()=>{});throw e;}finally{await browser?.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
