/* 宗门大比试卷导入：行测PDF/已保存HTML/HTML+资源ZIP/完整ZIP。
   文件仅发给当前本机API；HTML先检查完整性，结果与文件绑定，不执行网页脚本。
   原120分钟导入计时由服务端按季去重；本模块不计算分数或奖励。 */
(() => {
 'use strict';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let files=null,preview=null,last='',filename='',generation=0;
 const enabled=()=>window.SUBJECT0==='行测';
 function html(){if(!enabled())return '';return `<details class="card cs-entry-section mock-paper-import" id="mockPaperImport" data-cs-fold="paper"><summary><span>01</span><b>试卷导入</b><small>PDF · HTML · 配套资源 ZIP</small></summary><div class="mi-body"><p class="small muted">选择粉笔模考PDF，或已保存的HTML；HTML的同名_files文件夹请压成ZIP选在配套资源。也可直接选择包含HTML和_files的完整ZIP。</p><div class="mi-fields"><label>试卷文件<input id="mhFile" type="file" accept=".pdf,.html,.htm,.zip,application/pdf,text/html,application/zip"></label><label>配套资源ZIP（HTML选填）<input id="mhAssets" type="file" accept=".zip,application/zip"></label><label>第几季<input id="mhSeason" type="number" min="1" max="9999" placeholder="默认从标题识别"></label></div><p id="mhFilename" class="small muted">${esc(filename)}</p><div class="row"><button type="button" id="mhPreview">检查HTML / ZIP</button><button type="button" class="primary" id="mhCommit">开始导入</button></div><div id="mhResult" role="status" aria-live="polite">${last}</div><details class="fold" data-cs-fold="stored"><summary>已有试卷与导入管理</summary><div id="mhPdfStatus" class="small muted">展开试卷导入后读取…</div></details></div></details>`;}
 async function fileData(file){if(file.size>32*1024*1024)throw Error('单个文件最多32MB');const bytes=new Uint8Array(await file.arrayBuffer());let bin='';for(let i=0;i<bytes.length;i+=32768)bin+=String.fromCharCode(...bytes.subarray(i,i+32768));return {name:file.name,data:btoa(bin)};}
 function scoreReport(r){return `${r.timed!=null?`<p>逐题用时 ${r.timed}/${r.total} 题</p>`:''}${r.reported_score!=null?`<p>HTML报告：${esc(r.reported_score)} 分</p>`:''}${r.saved_score!=null?`<p>已录成绩：${esc(r.saved_score)} 分（保持原记录）</p>`:''}${r.estimate?`<p><b>${r.estimate.ready?'参考估分 '+esc(r.estimate.score)+' 分':'尚不能完整估分'}</b></p><p class="small muted">${r.estimate.ready?'按当前参考分值与逐题对错计算，与报告分数独立。':esc(r.estimate.reason)} 成绩单可核对后保存；检查不会入库、录分或累计时长。</p>`:''}`;}
 function report(r){return `<p><b>${r.dry?'检查完成':'导入完成'} · 第 ${r.season} 季</b></p><p>识别 ${r.total} 题 · ${r.images} 张配图 · ${r.ready} 题${r.dry?'可导入':'已入库'} · ${r.dup} 题已存在</p><p class="small muted">${r.boards.map(([b,n])=>esc(b)+' '+n+'题').join(' · ')}</p>${r.missing_images?`<p class="bad">缺少 ${r.missing_images} 个图片资源。请补充同名_files资源ZIP后重新检查；未写入题库。</p><p class="small">${r.missing.map(esc).join('<br>')}</p>`:''}${r.blocked?`<p class="bad">${r.blocked} 题结构待核对：${r.problems.map(x=>x.num+'题 '+x.reasons.map(esc).join('、')).join('；')}</p>`:''}${scoreReport(r)}${r.review_preserved?'<p class="small muted">已有复盘及笔记已保留。</p>':''}${r.practice_minutes?`<p>已按原规则记入 ${r.practice_minutes} 分钟；同季重复导入不重复计时。</p>`:''}`;}
 function bind(){const host=document.getElementById('mockPaperImport');if(!host||host.dataset.bound)return;host.dataset.bound='1';const token=++generation;
  const show=text=>{last=text;if(host.isConnected)host.querySelector('#mhResult').innerHTML=text;};
  const read=async()=>{const file=host.querySelector('#mhFile').files[0],assets=host.querySelector('#mhAssets').files[0];if(!file&&!files)throw Error('先选择试卷文件');if(file){files=await fileData(file);if(assets)files.resources=await fileData(assets);filename=file.name+(assets?' ＋ '+assets.name:'');host.querySelector('#mhFilename').textContent=filename;}return {...files,season:Number(host.querySelector('#mhSeason').value)||undefined};};
  host.querySelectorAll('input').forEach(input=>input.addEventListener('change',()=>{preview=null;files=null;filename='';show('文件已变化，请重新检查。');}));
  async function run(commit){const buttons=[...host.querySelectorAll('#mhPreview,#mhCommit')];buttons.forEach(b=>b.disabled=true);try{
   const body=await read();if(generation!==token||!host.isConnected)return;
   if(body.name.toLowerCase().endsWith('.pdf')){
    if(!commit)throw Error('PDF使用原拆分流程，请点“开始导入”；HTML / ZIP先点检查。');
    show('PDF上传完成后开始拆分，请稍候…');const saved=await api('/api/import/upload_pdf',body);const r=await api('/api/import/split',{file:saved.file});show(`<p>第 ${r.season} 季PDF已导入：新增 ${r.ready} 题，待修 ${r.fix} 题，重复 ${r.dup} 题。</p>${scoreReport(r)}${r.practice_minutes?`<p>已记入 ${r.practice_minutes} 分钟。</p>`:''}`);if(r.events)handleEvents(r.events);await window.CONTEST?.importDone(r.season);return;
   }
   if(commit&&!preview)throw Error('请先检查HTML / ZIP，确认题目和图片完整后再导入');
   show(commit?'正在导入…':'正在检查题目与图片…');const r=await api('/api/import/html',{...body,commit,digest:commit?preview.digest:undefined});
   if(generation!==token||!host.isConnected)return;preview=r;show(report(r));if(commit){if(r.events)handleEvents(r.events);await window.CONTEST?.importDone(r.season);}
  }catch(e){show(`<p class="bad">${esc(e.message)}</p>`);}finally{buttons.forEach(b=>b.disabled=false);}}
  host.querySelector('#mhPreview').onclick=()=>run(false);host.querySelector('#mhCommit').onclick=()=>run(true);
  let loaded=false;
  async function action(button,fn){button.disabled=true;try{await fn();}catch(e){show(`<p class="bad">${esc(e.message)}</p>`);}finally{if(button.isConnected)button.disabled=false;}}
  async function refreshed(season){await window.CONTEST?.importDone(season);if(host.isConnected)await loadStored();}
  async function loadStored(){
   const d=await api('/api/import');if(!host.isConnected||generation!==token)return;
   const box=host.querySelector('#mhPdfStatus');
   box.innerHTML=`<p>${!d.splitter?'PDF拆分需先安装 xingce-mokao-split；HTML / ZIP无需该组件。':!d.pymupdf?'PDF缺少pymupdf组件。':'PDF拆分组件可用。'}</p>
    ${d.splitter&&!d.pymupdf?'<button type="button" id="mhInstall">安装PDF组件（联网）</button>':''}
    ${d.pdfs.filter(x=>!x.split).map(x=>`<div class="row"><span>${esc(x.file)}</span><button type="button" data-mi-pdf="${esc(x.file)}">拆分并导入</button></div>`).join('')}
    ${d.seasons.length?'<p>已有板块复盘：检查会自动核分，补导入保留笔记与原计时。</p>':''}
    ${d.seasons.map(x=>`<div class="import-sec"><div class="row"><span>第 ${x.season} 季 · 已入库 ${x.imported} 题</span><button type="button" data-mi-season="${x.season}" data-mi-preview>检查</button><button type="button" data-mi-season="${x.season}">补导入</button><button type="button" data-mi-delete="${x.season}" ${x.imported?'':'disabled'}>删除</button></div><div data-mi-result="${x.season}" role="status" aria-live="polite"></div></div>`).join('')}
    ${(d.recycled||[]).length?`<details class="fold"><summary>已删除的入库批次（可恢复）</summary><p>原试卷、复盘笔记、图片、成绩与学习记录保留。恢复不会覆盖同编号的新内容。</p>${d.recycled.map(x=>`<div class="row"><span>第 ${x.season} 季 · ${x.removed} 题${x.recovery?' · 上次删除未完成':''} <small>${esc(x.created)}</small></span><button type="button" data-mi-restore="${esc(x.token)}">恢复入库</button></div>`).join('')}</details>`:''}`;
   box.querySelectorAll('[data-mi-pdf]').forEach(b=>b.onclick=()=>action(b,async()=>{const r=await api('/api/import/split',{file:b.dataset.miPdf});show(`<p>第 ${r.season} 季PDF已导入，新增 ${r.ready} 题。</p>${scoreReport(r)}`);if(r.events)handleEvents(r.events);await refreshed(r.season);}));
   box.querySelectorAll('[data-mi-season]').forEach(b=>b.onclick=()=>action(b,async()=>{
    const dry=b.hasAttribute('data-mi-preview'),season=Number(b.dataset.miSeason),r=await api(dry?'/api/import/preview':'/api/import/commit',{kind:'season',season});
    const result=`<p>${dry?'检查完成':'补导入完成'} · 第 ${season} 季：可入库 ${r.ready} 题，待修 ${r.fix} 题，已存在 ${r.dup} 题。</p>${r.preview_error?`<p class="bad">入库检查提示：${esc(r.preview_error)}</p>`:''}${scoreReport(r)}`;
    if(dry){if(host.isConnected)box.querySelector('[data-mi-result="'+season+'"]').innerHTML=result;}
    else{show(result);if(r.events)handleEvents(r.events);await refreshed(season);}
   }));
   box.querySelectorAll('[data-mi-delete]').forEach(b=>b.onclick=()=>action(b,async()=>{
    const season=Number(b.dataset.miDelete),p=await api('/api/import/season/remove',{season});
    if(!confirm(`删除第 ${season} 季入库的 ${p.removed} 题？\n${p.scope}。\n移出的题目有回收副本，可恢复；不会清除原始资料。`))return;
    const r=await api('/api/import/season/remove',{season,commit:true,digest:p.digest});show(`<p>已删除第 ${season} 季入库的 ${r.removed} 题。原复盘与成绩保留，可在“已删除的入库批次”恢复。</p>`);await refreshed(season);
   }));
   box.querySelectorAll('[data-mi-restore]').forEach(b=>b.onclick=()=>action(b,async()=>{
    const r=await api('/api/import/season/restore',{token:b.dataset.miRestore});show(`<p>第 ${r.season} 季已恢复入库；学习历史与其他题目保持。</p>`);await refreshed(r.season);
   }));
   const install=box.querySelector('#mhInstall');if(install)install.onclick=()=>action(install,async()=>{const r=await api('/api/import/install_pymupdf',{});show(r.ok?'组件已安装，请重新打开录入页。':'组件安装未完成。');});
  }
  host.addEventListener('toggle',async()=>{if(!host.open||loaded)return;loaded=true;try{await loadStored();}catch(e){loaded=false;show(esc(e.message));}});

 }
 window.MOCK_IMPORT={html,bind};
})();
