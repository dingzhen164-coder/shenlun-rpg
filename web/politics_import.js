/* 将补充PDF加入指定考试地图；原文、题目与进度由后端增量保存。 */
(() => {
 'use strict';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let message='',lastChannel='sprint-study',manageNote='',manageOpen=false;
 function html(exams,selected){return `<details class="wx-import"><summary>导入时政 PDF</summary><p class="muted">月半、专题、冲刺资料和独立消化清单都从这里导入。期刊独立保存，冲刺资料归入选定考试；已有记录保留。</p><form data-politics-import><label>导入栏目<select name="channel"><option value="month">月半时政</option><option value="topic">专题时政</option><option value="sprint-study" selected>冲刺学习</option><option value="sprint-quiz">冲刺刷题</option><option value="digest">消化清单</option></select></label><label data-import-exam>加入地图<select name="exam">${exams.map(e=>`<option value="${e.id}" ${e.id===selected?'selected':''}>${esc(e.title)}</option>`).join('')}</select></label><label data-import-kind>材料类型<select name="kind"><option value="">自动识别</option>${['重大会议','讲话','指导','文件'].map(k=>`<option>${k}</option>`).join('')}</select></label><label class="wx-pdf-file">PDF 文件<input type="file" name="pdf" accept=".pdf,application/pdf" required></label><button class="btn" type="submit">导入资料</button></form><p class="small muted">支持可提取文字的PDF；扫描版请先做文字识别。消化清单不用选讲义，可一次选多份PDF：程序按每段的上下文自动到已导入的讲义、月半和专题里找出处，答案只取清单写明的答案或原文里唯一的匹配，找不到出处的段落不导入、不猜。无法确定题目对应材料时，保留为整份讲义配套练习。</p><p data-import-result role="status">${esc(message)}</p><details class="wx-manage" data-import-manage ${manageOpen?'open':''}><summary>管理已导入文件</summary><p class="small muted">勾选后可批量删除。删除前会先备份到「训练/时政回收」，学习进度和批注不动；重新导入同一份PDF会自动对上。</p><div data-manage-list role="group" aria-label="已导入的时政文件">正在读取…</div><div class="wx-manage-actions"><button type="button" class="ghost" data-manage-all>全选</button><button type="button" class="ghost" data-manage-none>清除选择</button><button type="button" class="btn wx-danger" data-manage-delete disabled>删除所选</button></div><p data-manage-result role="status">${esc(manageNote)}</p></details></details>`;}
 const exam=r=>r?`\n识别到${r.papers.length}套：${r.papers.map(p=>p.title+' '+p.questions+'题').join('；')}。${r.incomplete_count?`有${r.incomplete_count}道题选项不全（${r.incomplete.join('、')}${r.incomplete_count>r.incomplete.length?'…':''}），请对照原PDF。`:''}`:'';
 function bindManage(root,exam,onDone){
  const box=root.querySelector('[data-import-manage]');if(!box)return;
  const list=box.querySelector('[data-manage-list]'),del=box.querySelector('[data-manage-delete]'),note=box.querySelector('[data-manage-result]');
  const checked=()=>[...list.querySelectorAll('input[type=checkbox]:checked')];
  const sync=()=>{const n=checked().length;del.disabled=!n;del.textContent=n?`删除所选（${n}）`:'删除所选';};
  async function load(){
   list.textContent='正在读取…';
   try{const r=await api('/api/wanxiang/import/list',{});list.innerHTML=r.groups.length?r.groups.map(group=>`<fieldset class="wx-manage-group"><legend>${esc(group.title)}</legend>${group.items.map(i=>`<label class="wx-manage-item"><input type="checkbox" value="${esc(i.id)}"><span><b>${esc(i.label)}</b><small>${esc(i.detail)}</small></span></label>`).join('')}</fieldset>`).join(''):'<p class="muted">还没有导入过的时政文件。</p>';}
   catch(error){list.textContent='读取失败：'+error.message;}
   sync();
  }
  box.addEventListener('toggle',()=>{manageOpen=box.open;if(box.open)load();});
  list.onchange=sync;
  box.querySelector('[data-manage-all]').onclick=()=>{list.querySelectorAll('input[type=checkbox]').forEach(x=>x.checked=true);sync();};
  box.querySelector('[data-manage-none]').onclick=()=>{list.querySelectorAll('input[type=checkbox]').forEach(x=>x.checked=false);sync();};
  del.onclick=async()=>{
   const ids=checked().map(x=>x.value);if(!ids.length)return;
   if(!confirm(`删除所选的 ${ids.length} 项导入文件？\n删除前会先备份到「训练/时政回收」，学习进度和批注不动。`))return;
   del.disabled=true;
   try{const r=await api('/api/wanxiang/import/delete',{ids});manageNote=`已删除 ${r.deleted} 项，备份在「${r.recycle}」。`;manageOpen=true;await onDone(exam());const panel=root.querySelector('.wx-import');if(panel)panel.open=true;}
   catch(error){note.textContent='删除未完成：'+error.message;sync();}
  };
  if(box.open)load();
 }
 function bind(root,onDone){
  const form=root.querySelector('[data-politics-import]');if(!form)return;
  bindManage(root,()=>form.elements.exam.value,onDone);
  const channel=form.elements.channel;channel.value=lastChannel;
  const update=()=>{const periodic=['month','topic'].includes(channel.value),digest=channel.value==='digest';form.querySelector('[data-import-exam]').hidden=periodic||digest;form.querySelector('[data-import-kind]').hidden=periodic||digest;form.elements.pdf.multiple=digest;};channel.onchange=()=>{lastChannel=channel.value;update();};update();
  const read=file=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('无法读取文件'));reader.readAsDataURL(file);});
  form.onsubmit=async event=>{
   event.preventDefault();const picked=[...form.elements.pdf.files];if(!picked.length)return;
   const chosenChannel=channel.value,chosenExam=form.elements.exam.value,kind=form.elements.kind.value,digest=chosenChannel==='digest';
   const files=digest?picked:picked.slice(0,1);
   const output=root.querySelector('[data-import-result]'),button=form.querySelector('[type=submit]');
   if(files.some(f=>f.size>40*1024*1024)){output.textContent='请拆成40MB以内的PDF后再导入。';return;}
   button.disabled=true;const notes=[];
   try{
    for(const [index,file] of files.entries()){
     output.textContent=(files.length>1?`正在导入第${index+1}/${files.length}份：`:'')+'正在提取正文与题目，请稍候…';
     try{
      const result=await api('/api/wanxiang/import',{channel:chosenChannel,exam:chosenExam,kind,name:file.name,data:await read(file)});
      if(digest){
       const skipped=result.unmatched?`，${result.unmatched}段没在讲义原文里直接找到，已按前后文放进相邻资料并标为待补全${(result.lost||[]).length?'（如：'+result.lost.map(x=>'「'+x+'…」').join('、')+'）':''}`:'';
       const redone=result.redone?`；已按新的识别规则重新识别${result.moved?'，'+result.moved+'个核对记号已保留':''}`:'';
       notes.push(result.duplicate?`「${result.title}」已导入，未重复添加${skipped}`:`「${result.title}」识别到${result.rows}段${result.pdf_blanks}空，已分配到${result.targets}份资料：共${result.blanks}空，有明确答案或已匹配${result.ready}空，待补全${result.pending}空${skipped}${redone}`);
      }else if(result.channel==='month'||result.channel==='topic')notes.push(`已加入「${result.title}」：研读${result.news}条、消化${result.cloze}段、精卷${result.questions}题。`);
      else notes.push(result.duplicate?'这份PDF已导入，未重复添加。':`已加入 ${result.added} 份材料、${result.questions} 道题。${result.unanswered?`${result.unanswered} 道题未找到参考答案，暂不判分。`:''}${result.whole_document_questions?`${result.whole_document_questions} 道题保留为整份讲义配套练习。`:''}${exam(result.exam)}`);
     }catch(error){notes.push(`「${file.name}」未导入：${error.message}`);}
    }
    message=notes.join('\n');
    await onDone(chosenExam);const panel=root.querySelector('.wx-import');if(panel)panel.open=true;/* 先刷新目录再显示结果，避免提示已出现而目录还是旧的 */
    const live=root.querySelector('[data-import-result]');if(live)live.textContent=message;
   }catch(error){output.textContent='导入未完成：'+error.message;}finally{button.disabled=false;}
  };
 }
 window.POLITICS_IMPORT={html,bind};
})();
