/* 将补充PDF加入指定考试地图；原文、题目与进度由后端增量保存。 */
(() => {
 'use strict';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let message='',lastChannel='sprint-study';
 function html(exams,selected){return `<details class="wx-import"><summary>导入时政 PDF</summary><p class="muted">月半、专题和冲刺资料都从这里导入。期刊独立保存，冲刺资料归入选定考试；已有记录保留。</p><form data-politics-import><label>导入栏目<select name="channel"><option value="month">月半时政</option><option value="topic">专题时政</option><option value="sprint-study" selected>冲刺学习</option><option value="sprint-quiz">冲刺刷题</option></select></label><label data-import-exam>加入地图<select name="exam">${exams.map(e=>`<option value="${e.id}" ${e.id===selected?'selected':''}>${esc(e.title)}</option>`).join('')}</select></label><label data-import-kind>材料类型<select name="kind"><option value="">自动识别</option>${['重大会议','讲话','指导','文件'].map(k=>`<option>${k}</option>`).join('')}</select></label><label class="wx-pdf-file">PDF 文件<input type="file" name="pdf" accept=".pdf,application/pdf" required></label><button class="btn" type="submit">导入资料</button></form><p class="small muted">支持可提取文字的PDF；扫描版请先做文字识别。无法确定题目对应材料时，将保留为整份讲义的配套练习。</p><p data-import-result role="status">${esc(message)}</p></details>`;}
 function bind(root,onDone){
  const form=root.querySelector('[data-politics-import]');if(!form)return;
  const channel=form.elements.channel;channel.value=lastChannel;
  const update=()=>{const periodic=['month','topic'].includes(channel.value);form.querySelector('[data-import-exam]').hidden=periodic;form.querySelector('[data-import-kind]').hidden=periodic;};channel.onchange=()=>{lastChannel=channel.value;update();};update();
  form.onsubmit=async event=>{
   event.preventDefault();const file=form.elements.pdf.files[0];if(!file)return;
   const output=root.querySelector('[data-import-result]'),button=form.querySelector('[type=submit]');
   if(file.size>40*1024*1024){output.textContent='请拆成40MB以内的PDF后再导入。';return;}
   button.disabled=true;output.textContent='正在提取正文与题目，请稍候…';
   try{
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('无法读取文件'));reader.readAsDataURL(file);});
    const result=await api('/api/wanxiang/import',{channel:form.elements.channel.value,exam:form.elements.exam.value,kind:form.elements.kind.value,name:file.name,data});
    message=result.channel==='month'||result.channel==='topic'?`已加入「${result.title}」：研读${result.news}条、消化${result.cloze}段、精卷${result.questions}题。`:result.duplicate?'这份PDF已导入，未重复添加。':`已加入 ${result.added} 份材料、${result.questions} 道题。${result.unanswered?`${result.unanswered} 道题未找到参考答案，暂不判分。`:''}${result.whole_document_questions?`${result.whole_document_questions} 道题保留为整份讲义配套练习。`:''}`;
    await onDone(form.elements.exam.value);const panel=root.querySelector('.wx-import');if(panel)panel.open=true;
   }catch(error){output.textContent='导入未完成：'+error.message;}finally{button.disabled=false;}
  };
 }
 window.POLITICS_IMPORT={html,bind};
})();
