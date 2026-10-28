/* 真实灵脉图/配对文档格式回归：三尺寸明暗、SVG测量、只读不写文件、编辑保存与重新载入。 */
const assert=require('node:assert/strict'),fs=require('node:fs'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
const subject=process.argv.find(a=>a.startsWith('--subject='))?.split('=')[1];
const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py',...(subject?[subject]:[])],{env:process.env});let logs='',browser,page;
srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((ok,no)=>{let s='';const timer=setTimeout(()=>no(Error(logs)),20000);srv.stdout.on('data',b=>{s+=b;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);ok(m[1]);}});srv.on('exit',()=>{clearTimeout(timer);no(Error(logs));});});
(async()=>{try{
 const base=await ready;browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 for(const [name,width,height]of [['desktop',1280,860],['portrait',800,1280],['landscape',1280,800]])for(const theme of ['light','dark']){
  page=await browser.newPage({viewport:{width,height}});const errors=[],writes=[],unexpected=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/api/mindmap/save'))writes.push(r.postData());if(r.url().includes('never-fetch-format'))unexpected.push(r.url());});
  await page.addInitScript(theme=>{for(const key of ['xrpg-theme','srpg-theme'])localStorage.setItem(key,theme);let lib;Object.defineProperty(window,'simpleMindMap',{configurable:true,get:()=>lib,set:v=>{lib=v;const M=v.default||v,render=M.prototype.render;M.prototype.render=function(...a){if(this.opt?.el?.id==='lnCanvas')window.__mapFormat=this;return render.apply(this,a);};}});},theme);
  await page.goto(base);await page.locator('.portal-world').waitFor();await page.locator('#splash').waitFor({state:'hidden'});
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),theme,'实际主题必须匹配用例');
  const fixture=await page.evaluate(async caseName=>{
   const board=DASH.tree[0].board,name='自编格式阅读-'+caseName,data={root:{data:{text:'**自编知识** → 条件'},children:[
    {data:{text:'**重点** 与普通字 $A \\rightarrow B$'}},
    {data:{text:'<p><strong>旧重点</strong> &rarr; <em>旧条件</em></p>',richText:true}},
    {data:{text:'\\*\\*字面\\*\\* x < y <img src="never-fetch-format" onerror="alert(1)">'}},
    {data:{text:'普通 **'+'加粗的长知识条件'.repeat(12)+'**\n下一行 ↔ ⇒ ∴ ∀ ≠ ≤ ≥'}},
    {data:{text:'*斜体*、~~删除~~、`原样 **代码**`'}}]}};
   const list=await api('/api/mindmap');if(!list.boards.some(b=>b.board===board&&b.maps.some(m=>m.name===name)))await api('/api/mindmap/create',{board,name,data});
   const before=JSON.stringify((await api('/api/mindmap/get',{board,name,readonly:true})).data);await MINDMAP.open(board,name,false);return {board,name,before};
  },name+'-'+theme);
  await page.waitForFunction(()=>document.querySelector('#lnCanvas text')?.textContent.includes('自编知识'));
  await page.locator('[data-ln-mode="split"]').click();
  assert.equal(await page.locator('#lnMarkdown h1 strong').innerText(),'自编知识');assert.equal(await page.locator('#lnMarkdown li strong').first().innerText(),'重点');
  assert((await page.locator('#lnMarkdown').innerText()).includes('A → B'));assert.equal(await page.locator('#lnMarkdown img,#lnMarkdown script,#lnCanvas foreignObject').count(),0);
  const rendered=await page.evaluate(()=>{
   const nodes=[];const walk=n=>{nodes.push(n);n.children.forEach(walk);};walk(__mapFormat.renderer.root);
   return nodes.map(n=>({source:n.getData('text'),shown:n._textData.node.node.textContent,bold:[...n._textData.node.node.querySelectorAll('tspan[font-weight]')].map(t=>[t.textContent,getComputedStyle(t).fontWeight]),width:n._textData.width,measured:n._textData.node.bbox().width,nodeWidth:n.width}));
  });
  const emphasized=rendered.find(n=>n.source.startsWith('**重点**'));assert.equal(emphasized.shown,'重点 与普通字 A → B');assert(emphasized.bold.some(([s,w])=>s==='重点'&&Number(w)>=700));
  assert(rendered.some(n=>n.shown.startsWith('**字面** x < y')),'字面转义与比较符号必须保留');
  for(const n of rendered){assert(n.width>=n.measured-1,'格式字宽计入测量：'+JSON.stringify(n));assert(n.nodeWidth>=n.width,'节点不能裁掉加粗文字：'+JSON.stringify(n));}
  assert.deepEqual(unexpected,[]);assert.equal(writes.length,0);assert.equal(await page.evaluate(async f=>JSON.stringify((await api('/api/mindmap/get',{board:f.board,name:f.name,readonly:true})).data),fixture),fixture.before);
  if(name==='desktop'&&theme==='light'&&process.argv.includes('--shots')){fs.mkdirSync('ui-artifacts/mindmap-format',{recursive:true});await page.screenshot({path:'ui-artifacts/mindmap-format/'+(subject||'法考')+'.png'});}
  await page.locator('#lnBack').click();await page.evaluate(f=>MINDMAP.open(f.board,f.name,true),fixture);await page.locator('.ln-tools').waitFor();await page.waitForFunction(()=>!!document.querySelector('#lnCanvas tspan[font-weight]'));
  await page.evaluate(()=>{__mapFormat.execCommand('SET_NODE_TEXT',__mapFormat.renderer.root,'**编辑后重点** → 保留');});
  await page.waitForFunction(()=>document.querySelector('#lnSaved')?.textContent==='已保存');await page.locator('#lnBack').click();
  const saved=await page.evaluate(f=>api('/api/mindmap/get',{board:f.board,name:f.name,readonly:true}),fixture);assert.equal(saved.data.root.data.text,'**编辑后重点** → 保留');assert(saved.markdown.includes('**编辑后重点**'));assert(saved.markdown.includes('\\rightarrow'));
  await page.evaluate(f=>MINDMAP.open(f.board,f.name,false),fixture);await page.locator('#lnMarkdown h1 strong').waitFor();assert.equal(await page.locator('#lnMarkdown h1 strong').innerText(),'编辑后重点');
  if(name==='desktop'&&theme==='light'){
   await page.locator('#lnBack').click();await page.evaluate(f=>MINDMAP.open(f.board,f.name,true),fixture);await page.locator('#lnFile').waitFor({state:'attached'});
   await page.locator('#lnFile').setInputFiles({name:'自编格式导入.md',mimeType:'text/markdown',buffer:Buffer.from('# **导入标题**\n- **导入重点** $A \\rightarrow B$\n')});
   await page.waitForFunction(()=>document.querySelector('#lnCanvas text')?.textContent.includes('导入标题'));
   assert.equal(await page.locator('#lnCanvas tspan[font-weight]').first().textContent(),'导入标题');
   const imported=await page.evaluate(board=>api('/api/mindmap/get',{board,name:'自编格式导入',readonly:true}),fixture.board);assert.equal(imported.data.root.data.text,'**导入标题**');assert(imported.markdown.includes('**导入重点**'));
  }
  assert.deepEqual(errors,[]);await page.close();console.log((subject||'法考')+' '+name+'/'+theme+'：加粗/箭头/公式/旧富文本/SVG尺寸/只读/编辑重载通过');
 }
}catch(e){if(page&&!page.isClosed()){console.error('FORMAT-FAIL',await page.evaluate(()=>({theme:document.documentElement.dataset.theme,title:document.querySelector('#lnMarkdown h1')?.textContent,svg:[...document.querySelectorAll('#lnCanvas text')].map(e=>e.textContent)})));fs.mkdirSync('ui-artifacts/mindmap-format',{recursive:true});await page.screenshot({path:'ui-artifacts/mindmap-format/failure-'+(subject||'法考')+'.png'});}throw e;}finally{await browser?.close();srv.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
