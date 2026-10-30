/* 多老师真实HTTP：ZIP预览确认/自动分发/完整文档/复盘选择/头像与AI隔离，三尺寸。 */
const assert=require('node:assert/strict'),fs=require('node:fs'),{spawn,spawnSync}=require('node:child_process'),{chromium}=require('playwright');
const service=spawn('python3',['tests/ui_trial_server.py','--teachers-fixture'],{env:process.env});let logs='',browser,page;service.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let s='';const t=setTimeout(()=>no(Error(logs)),20000);service.stdout.on('data',b=>{s+=b;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(t);ok(m[1]);}});});
const docs={'大懒猫-言语.md':'# 猫专属标记\n完整言语原文。','句号-资料言语.md':'# 句号专属标记\n资料与言语的完整文档。','青菜白玉汤-判断.md':'# 青菜心法\n判断的完整文档。','未命名.md':'未知后缀不猜'};
const zipped=spawnSync('python3',['-c',"import io,json,sys,zipfile\nb=io.BytesIO()\nwith zipfile.ZipFile(b,'w') as z:\n for n,t in json.loads(sys.argv[1]).items():z.writestr(n,t)\nsys.stdout.buffer.write(b.getvalue())",JSON.stringify(docs)]);assert.equal(zipped.status,0,String(zipped.stderr));
(async()=>{try{const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [label,width,height]of [['desktop',1280,860],['portrait',800,1280],['landscape',1280,800]]){
  page=await browser.newPage({viewport:{width,height}});const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());await page.goto(base);await page.waitForFunction(()=>!!window.DASH_REF?.());await page.locator('#splash').waitFor({state:'hidden'});
  await page.evaluate(()=>{LIB.tab='skillbook';return go('skeleton');});await page.locator('[data-skb="teachers-import"]').waitFor();assert.equal(await page.locator('.skb-zj-card,.skb-tip').count(),0);
  await page.locator('#skbTeachersPick').setInputFiles({name:'多老师.zip',mimeType:'application/zip',buffer:zipped.stdout});await page.locator('.skb-note').filter({hasText:'已导入 3 份老师文档'}).waitFor();
  const all=await page.evaluate(()=>api('/api/skillbook'));for(const b of ['资料分析','逻辑填空','片段阅读'])assert(all.boards.find(x=>x.board===b).teachers.some(t=>t.name==='句号'));
  await page.locator('[data-skb-board="逻辑填空"]').click({force:true});await page.locator('[data-skb-teacher]').selectOption('大懒猫');await page.locator('.skb-read').filter({hasText:'猫专属标记'}).waitFor();assert(!((await page.locator('.skb-read').textContent()).includes('句号专属标记')));
  await page.locator('[data-skb-teacher]').selectOption('句号');await page.locator('.skb-read').filter({hasText:'资料与言语的完整文档'}).waitFor();
  const route=await page.request.post(base+'/api/skillbook/zongjue',{data:{}});assert.equal(route.status(),404,'旧总诀接口删除');
  await page.evaluate(async()=>{const b=await api('/api/bank'),run=b.active_runs.find(r=>r.board.startsWith('点:'));if(!run)throw Error('缺少自编复盘');await startTask({task:{type:'bank',board:run.board,target:run.board,title:'自编老师复盘'}});});await page.locator('#reviewSkillTeacher').waitFor();
  let aiCalls=0;page.on('request',r=>{if(r.url().endsWith('/api/session/action')&&r.postData()?.includes('exam_explain'))aiCalls++;});
  await page.locator('#reviewSkillTeacher').selectOption('大懒猫');await page.waitForFunction(()=>!T.busy&&T.mentor?.name==='大懒猫');assert.equal(aiCalls,0,'切换老师不自动调用解惑');
  await page.locator('[data-act^="exam_explain:"]').click();await page.waitForFunction(()=>!T.busy&&T.msgs.some(m=>m.text?.includes('猫专属讲解')));assert.equal(aiCalls,1);
  await page.locator('#reviewSkillTeacher').selectOption('句号');await page.waitForFunction(()=>!T.busy&&T.mentor?.name==='句号');
  const old=await page.evaluate(()=>T.msgs.find(m=>m.text?.includes('猫专属讲解'))?.mentor?.name);assert.equal(old,'大懒猫','切换老师不能把旧讲解冒认为新老师');
  await page.locator('[data-act^="exam_explain:"]').click();await page.waitForFunction(()=>!T.busy&&T.msgs.some(m=>m.text?.includes('句号专属讲解')));assert.equal(aiCalls,2);
  assert.equal(await page.evaluate(()=>T.mentor.avatar),'assets/teachers/full-stop.png');for(const asset of ['lazy-cat','jade-cabbage','full-stop']){const response=await page.request.get(base+'/assets/teachers/'+asset+'.png');assert.equal(response.status(),200);}
  const lay=await page.evaluate(()=>{const sel=document.querySelector('#reviewSkillTeacher'),row=sel.closest('.composer-row'),comp=document.querySelector('.composer'),corner=[...document.querySelectorAll('.beauty-audio,.page-settings-gear')].map(e=>e.getBoundingClientRect()).filter(r=>r.width>0);
   const sb=sel.getBoundingClientRect(),btns=[...(row?row.querySelectorAll('button'):[])].map(b=>b.getBoundingClientRect()),hit=btns.some(b=>corner.some(c=>b.left<c.right&&b.right>c.left&&b.top<c.bottom&&b.bottom>c.top));
   return {inRow:!!row,sameLine:btns.length>0&&Math.abs((sb.top+sb.bottom)/2-(btns[0].top+btns[0].bottom)/2)<btns[0].height,labelText:sel.closest('label').textContent.includes('心法老师'),opts:[...sel.options].every(o=>!o.textContent.includes('心法')),hit,rowH:comp.getBoundingClientRect().height};});
  assert(lay.inRow,'心法老师选择并进底部按钮行，不单独占一行');assert(lay.sameLine,'选择框与“求助”等按钮在同一行（'+label+'）');assert(!lay.labelText,'下拉框只显示老师名字，不再带“心法老师”文字');assert(!lay.hit,'底部按钮不被右下角音量/设置圆钮压住（'+label+'）');
  assert.equal(await page.locator('.review-teacher-avatar').count(),1,'复盘选择区直接显示老师Q版头像');await page.locator('.review-teacher-avatar').evaluate(img=>img.decode());assert(await page.locator('.review-teacher-avatar').isVisible());
  if(label==='desktop'){fs.mkdirSync('ui-artifacts/teachers',{recursive:true});await page.screenshot({path:'ui-artifacts/teachers/review-desktop.png'});}
  if(label==='desktop'){
   const catalog=JSON.parse(fs.readFileSync('rpg/data/teacher_avatars.json','utf8')),gallery=await browser.newPage({viewport:{width:1280,height:1000}});
   await gallery.setContent('<meta charset="utf-8"><style>body{background:#efece4;font:14px sans-serif;margin:12px}.grid{display:grid;grid-template-columns:repeat(8,1fr);gap:8px}figure{margin:0;text-align:center;background:#fff9;border-radius:12px;padding:6px}img{height:90px;width:90px;object-fit:contain}figcaption{line-height:22px}</style><div class="grid">'+Object.entries(catalog).map(([name,r])=>'<figure><img src="'+base+'/assets/teachers/'+r.file+'.png"><figcaption>'+name+'</figcaption></figure>').join('')+'</div>');
   await gallery.locator('img').evaluateAll(xs=>Promise.all(xs.map(im=>im.decode())));assert.equal(await gallery.locator('img').count(),58);await gallery.screenshot({path:'ui-artifacts/teachers/catalog.png',fullPage:true});await gallery.close();
  }
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));assert.deepEqual(errors,[]);await page.close();console.log(label+'：多老师ZIP/完整分发/阅读选择/复盘心法隔离/旧讲解署名/Q版头像通过');
 }
}finally{await browser?.close();service.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
