/* 万象峰题面重排：只在显示层消除PDF软换行，保留自然段、编号与选项。源题/答案不变。 */
(() => {
 'use strict';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function paragraphs(value){
  let text=String(value??'').replace(/\r\n?/g,'\n');
  const options=[...text.matchAll(/([A-D])[.．、)）](?!\d)/g)];
  if(options.some(x=>x[1]==='A')&&options.some(x=>x[1]==='B'))text=text.replace(/([A-D])[.．、)）](?!\d)/g,'\n$1.');
  const out=[];let current='';
  const flush=()=>{if(current.trim())out.push(current.trim());current='';};
  for(const row of text.split('\n')){
   const line=row.trim();if(!line){flush();continue;}
   if(/^(?:[A-D][.．、)）]|[①-⑳]|[（(][一二三四五六七八九十\d]+[)）]|[一二三四五六七八九十]+[、．])/.test(line)||/^\s{2,}\S/.test(row))flush();
   if(current&&/[A-Za-z0-9]$/.test(current)&&/^[A-Za-z]/.test(line))current+=' ';
   current+=line;
  }
  flush();return out;
 }
 const html=value=>paragraphs(value).map(s=>`<div class="wx-reflow-line">${esc(s)}</div>`).join('');
 window.WANXIANG_TEXT={paragraphs,html,plain:value=>paragraphs(value).join('\n')};
})();
