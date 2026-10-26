/* 语境词义批注：天机台与时政地图共用。mount(root,source)绑定阅读段落；
   选词后点“解释批注”，成功才加粗标红；再次点击读保存结果，无聊天输入。
   API数据/选词范围用Unicode码点，DOM范围仍用UTF-16；不改原资料。 */
(() => {
  'use strict';
  let cleanup=()=>{};
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function mount(root,source,options={}){
    cleanup();if(!root)return;
    let alive=true,notes={},chosen=null,loading=null,notesReady,loadError=null,reading={ranges:[]},readingReady=false;
    const managed=!!options.highlights;
    if(managed)root.dataset.highlightsReady='false';
    const controller=new AbortController(),opts={signal:controller.signal};
    const toolbar=document.createElement('button');toolbar.type='button';toolbar.className='wn-select';toolbar.textContent='解释批注';toolbar.hidden=true;
    const highlightTool=document.createElement('button');highlightTool.type='button';highlightTool.className='wn-highlight';highlightTool.hidden=true;
    const pop=document.createElement('aside');pop.className='wn-pop';pop.hidden=true;pop.setAttribute('role','dialog');pop.setAttribute('aria-label','词义批注');
    document.body.append(toolbar,pop);if(managed)document.body.append(highlightTool);
    const hideTools=()=>{toolbar.hidden=true;highlightTool.hidden=true;};
    const observer=new MutationObserver(()=>{if(!root.isConnected)close();});
    const close=()=>{alive=false;controller.abort();observer.disconnect();toolbar.remove();highlightTool.remove();bulk.remove();pop.remove();};
    cleanup=close;observer.observe(document.body,{childList:true,subtree:true});
    const blocks=()=>[...root.querySelectorAll('p,h2,h3,li')].filter(b=>!b.querySelector('p,h2,h3,li'));
    const blockOf=node=>{const el=node?.nodeType===3?node.parentElement:node;return el?.closest('p,h2,h3,li');};
    const norm=s=>[...s].filter(c=>!(/\s/.test(c))).join('');
    function spanFor(anchor){const base=anchor.block_offset||0;return [base+[...norm([...anchor.paragraph].slice(0,anchor.start).join(''))].length,base+[...norm([...anchor.paragraph].slice(0,anchor.end).join(''))].length];}
    function isMarked(anchor){const [a,b]=spanFor(anchor);return reading.ranges.some(([x,y])=>x<b&&y>a);}
    function placeTools(anchor){
      const rect={left:Math.max(12,Math.min(anchor.rect.left,innerWidth-(managed?252:124))),top:anchor.rect.top,bottom:anchor.rect.bottom};
      place(toolbar,rect);
      if(managed){highlightTool.textContent=isMarked(anchor)?'取消标红':'标为重点';place(highlightTool,{...rect,left:rect.left+120});highlightTool.disabled=!!loadError||!readingReady;}
    }
    function place(el,rect){
      const w=Math.min(el===pop?420:112,innerWidth-24);el.style.width=w+'px';el.hidden=false;
      const box=el.getBoundingClientRect(),room=innerHeight-rect.bottom-12;
      el.style.left=Math.max(12,Math.min(innerWidth-w-12,rect.left))+'px';
      el.style.top=Math.max(10,Math.min(innerHeight-box.height-12,room>=box.height?rect.bottom+8:rect.top-box.height-8))+'px';
    }
    function show(anchor,body){
      if(!alive||!root.isConnected)return;
      pop.innerHTML=`<header><strong>${esc(anchor.word)}</strong><button type="button" aria-label="关闭批注">×</button></header>${body}`;
      pop.querySelector('header button').onclick=()=>{pop.hidden=true;};
      place(pop,anchor.rect);
    }
    function showNote(anchor,note){
      const x=note.explanation,modern=note.version>=4;
      // 旧批注保留原记录，不在查看时偷偷调用API；仅展示概念，主动更新才重写。
      const concept=[x.meaning||x.plain].filter(Boolean);
      const research=note.research,sources=(research?.sources||[]).filter(s=>/^https:\/\//.test(s.url));
      show(anchor,`<section class="wn-core"><h4>通俗解释</h4>${concept.map(t=>`<p>${esc(t)}</p>`).join('')}</section><details class="wn-detail"><summary>背景与原因</summary><section><p>${esc(x.background||x.role||'旧批注尚未单独分析背景，可更新为精简解释。')}</p><h4>相近相反表述有什么不同</h4><p>${esc(x.compare||'旧批注未提供对比，可主动更新。')}</p>${sources.length?`<h4>联网参考 · 检索摘要</h4>${sources.map(s=>`<p><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a></p>`).join('')}`:research&&research.status!=='not_requested'?'<p class="wn-hint">本次未取得可核对的联网资料，以上依据原文与一般机制解释。</p>':''}</section></details>${modern?'':'<button type="button" class="wn-upgrade">更新为精简解释与相反表述对比（调用一次 API）</button>'}`);
      const upgrade=pop.querySelector('.wn-upgrade');if(upgrade)upgrade.onclick=()=>explain(anchor,true);
      if(managed&&isMarked(anchor)){const button=document.createElement('button');button.className='wn-unmark';button.textContent='取消标红（保留批注）';button.onclick=()=>changeHighlight(anchor,false);pop.append(button);}
      pop.querySelectorAll('details').forEach(el=>el.addEventListener('toggle',()=>{if(!pop.hidden)place(pop,anchor.rect);},{once:false}));
    }
    function textRange(block,start,end){
      const walk=document.createTreeWalker(block,NodeFilter.SHOW_TEXT);let node,offset=0,a=null,b=null;
      while((node=walk.nextNode())){const len=node.textContent.length;if(a===null&&start<=offset+len)a=[node,start-offset];if(end<=offset+len){b=[node,end-offset];break;}offset+=len;}
      if(!a||!b)return null;const r=document.createRange();r.setStart(...a);r.setEnd(...b);return r;
    }
    const HEADING_LIKE=/^(?:[一二三四五六七八九十百]+[、．.]|[（(](?:[一二三四五六七八九十百]+|\d+)[）)]|\d+[.．、]|《)/;
    function isHeadingBlock(block){const t=block.textContent.trim();return block.matches('.source-heading,h1,h2,h3,h4')||(t.length>0&&t.length<=64&&HEADING_LIKE.test(t)&&!/[。；！？]/.test(t));}
    // 研读：当前这一篇的红标记一键取消 / 恢复（不影响批注、消化清单、别的文章）
    const bulk=document.createElement('div');bulk.className='wn-bulk';bulk.hidden=true;
    const bulkButton=document.createElement('button');bulkButton.type='button';bulkButton.className='wn-bulk-btn';bulk.append(bulkButton);
    if(managed){if(options.bulkHost){bulk.classList.add('wn-bulk-inline');(options.bulkBefore?.parentElement===options.bulkHost?options.bulkBefore.before(bulk):options.bulkHost.append(bulk));}else root.insertAdjacentElement('beforebegin',bulk);}      // 有现成的工具行就放进去，不额外占正文上方的高度
    function syncBulk(){
      if(!managed||!readingReady&&!reading.ranges.length&&!reading.edited){bulk.hidden=true;return;}
      const has=reading.ranges.length>0;
      bulk.hidden=!has&&!reading.edited;
      bulkButton.dataset.mode=has?'clear':'restore';
      bulkButton.textContent=has?'🧹 一键取消红标记':'↺ 恢复红标记';
      bulkButton.title=has?'取消这一篇文章里全部红色重点；批注、消化清单和其他文章不受影响，之后可以恢复':'把这一篇的红色重点恢复成原来的样子';
    }
    bulkButton.addEventListener('click',async()=>{
      await notesReady;if(!alive||loadError)return;
      const clearing=reading.ranges.length>0;
      if(clearing&&!confirm('取消这一篇的全部红标记？\n批注和消化清单都不受影响，之后可以点“恢复红标记”找回。'))return;
      bulkButton.disabled=true;
      try{reading=await api('/api/politics/highlights',{...source,clear:clearing});if(!alive||!root.isConnected)return;await options.onChange?.(reading);paint();hideTools();pop.hidden=true;}
      catch(e){(parent.showError||alert)(e);}
      finally{bulkButton.disabled=false;}
    },opts);
    function paint(){paintBlocks();syncBulk();}
    function paintBlocks(){
      let blockOffset=0;
      for(const block of blocks()){
        const currentOffset=blockOffset;
        // 先去掉本组件旧标记；保留原文strong/mark及文本顺序。
        block.querySelectorAll('.wn-word').forEach(el=>el.replaceWith(...el.childNodes));block.normalize();
        if(managed){
          block.querySelectorAll('.source-emphasis,.wxj-key').forEach(el=>el.replaceWith(...el.childNodes));block.normalize();
          const chars=[...block.textContent],positions=[];let utf16=0;
          for(const c of chars){if(!(/\s/.test(c)))positions.push([utf16,utf16+c.length]);utf16+=c.length;}
          const heading=isHeadingBlock(block);     // 标题一律不加红：照常累计偏移，但不给标题套重点
          for(const [a,b] of heading?[]:[...reading.ranges].reverse()){
            const left=Math.max(a,blockOffset)-blockOffset,right=Math.min(b,blockOffset+positions.length)-blockOffset;
            if(left>=right)continue;
            const range=textRange(block,positions[left][0],positions[right-1][1]);if(!range)continue;
            const strong=document.createElement('strong');strong.className=root.matches('.wxj-news-body')?'wxj-key':'source-emphasis';strong.tabIndex=0;strong.setAttribute('role','button');strong.setAttribute('aria-label','查看重点解释');strong.append(range.extractContents());range.insertNode(strong);
          }
          blockOffset+=positions.length;
        }
        const paragraph=block.textContent,chosen=[];
        // 重叠选词优先显示最新批注；旧解释仍留存，避免新选词被旧范围遮住。
        for(const n of Object.values(notes).reverse())if(n.paragraph===paragraph&&(!managed||n.block_offset===undefined||n.block_offset===currentOffset)&&!chosen.some(x=>n.start<x.end&&n.end>x.start))chosen.push(n);
        const entries=chosen.sort((a,b)=>a.start-b.start);
        let lastEnd=-1;
        for(const n of entries){
          if(n.start<lastEnd||Array.from(paragraph).slice(n.start,n.end).join('')!==n.word)continue;
          const start=Array.from(paragraph).slice(0,n.start).join('').length,end=start+n.word.length,r=textRange(block,start,end);if(!r)continue;
          const mark=document.createElement('strong');mark.className='wn-word'+(managed?' wn-managed':'');mark.dataset.wnKey=n.key;mark.setAttribute('role','button');mark.tabIndex=0;mark.setAttribute('aria-label',n.word+'，查看解释批注');
          mark.append(r.extractContents());r.insertNode(mark);lastEnd=n.end;
        }
        // Range跨原重点边界时会留下空strong/mark，移除它们避免空白触控/键盘入口。
        block.querySelectorAll('.source-emphasis,.tj-key,.wxj-key').forEach(el=>{if(!el.textContent.trim())el.remove();});
      }
    }
    function anchorFor(block,start,end,rect){
      const paragraph=block.textContent;
      const block_offset=blocks().slice(0,blocks().indexOf(block)).reduce((n,b)=>n+[...norm(b.textContent)].length,0);
      return {paragraph,start:Array.from(paragraph.slice(0,start)).length,end:Array.from(paragraph.slice(0,end)).length,word:paragraph.slice(start,end),rect,...(managed?{block_offset}:{})};
    }
    async function refreshReading(){if(managed){reading=await api('/api/politics/highlights',source);if(alive)await options.onChange?.(reading);}}
    async function changeHighlight(anchor,enabled){
      hideTools();await notesReady;if(!alive||loadError)return;
      try{const {rect,...payload}=anchor;reading=await api('/api/politics/highlights',{...source,...payload,enabled});if(!alive||!root.isConnected)return;await options.onChange?.(reading);paint();pop.hidden=true;window.getSelection()?.removeAllRanges();}
      catch(e){show(anchor,`<p class="wn-hint">重点未能保存：${esc(e.message||e)}</p>`);}
    }
    async function explain(anchor,refresh=false){
      hideTools();
      await notesReady;
      if(!alive||!root.isConnected)return;
      if(loadError){
        show(anchor,`<p class="wn-hint">批注读取失败：${esc(loadError.message||loadError)}</p><button type="button" class="wn-retry">重新读取批注</button>`);
        pop.querySelector('.wn-retry').onclick=()=>{notesReady=loadNotes();explain(anchor);};return;
      }
      const cached=Object.values(notes).find(n=>n.paragraph===anchor.paragraph&&n.start===anchor.start&&n.end===anchor.end&&(!managed||n.block_offset===undefined||n.block_offset===anchor.block_offset));
      if(cached&&!refresh){showNote(anchor,cached);return;}
      if(loading)return;
      loading=anchor;show(anchor,'<p class="wn-hint" role="status">正在生成解释，成功后自动保存…</p>');
      try{
        const {rect,...payload}=anchor;
        const result=await api('/api/politics/explain',{...source,...payload,refresh});
        if(!alive||!root.isConnected)return;
        notes[result.note.key]=result.note;await refreshReading();if(!alive)return;paint();showNote(anchor,result.note);
        window.getSelection()?.removeAllRanges();
      }catch(e){
        show(anchor,`<p class="wn-hint">${esc(e.message||e)}</p><button type="button" class="wn-retry">重试</button>`);
        const retry=pop.querySelector('.wn-retry');if(retry)retry.onclick=()=>explain(anchor,refresh);
      }finally{loading=null;}
    }
    toolbar.addEventListener('pointerdown',e=>e.preventDefault(),opts);
    toolbar.addEventListener('click',()=>{if(chosen)explain(chosen);},opts);
    highlightTool.addEventListener('pointerdown',e=>e.preventDefault(),opts);
    highlightTool.addEventListener('click',()=>{if(chosen)changeHighlight(chosen,!isMarked(chosen));},opts);
    function selection(){
      if(!alive||!root.isConnected){close();return;}
      const s=window.getSelection();if(!s||s.isCollapsed||!s.rangeCount){hideTools();return;}
      const r=s.getRangeAt(0),block=blockOf(r.startContainer);
      if(!block||!root.contains(block)||block!==blockOf(r.endContainer)||s.toString().length>200){hideTools();return;}
      const prefix=r.cloneRange();prefix.selectNodeContents(block);prefix.setEnd(r.startContainer,r.startOffset);
      const start=prefix.toString().length,end=start+r.toString().length;
      if(!r.toString().trim())return;
      chosen=anchorFor(block,start,end,r.getBoundingClientRect());placeTools(chosen);
    }
    document.addEventListener('selectionchange',selection,opts);
    function clickWord(e){
      if(window.getSelection()?.toString().trim())return;
      // 已保存词句可能包住原文strong/mark，优先使用整条批注，避免点到内部重点重复请求。
      const el=e.target.closest('.wn-word')||e.target.closest('.source-emphasis,.tj-key,.wxj-key');if(!el||!root.contains(el))return;
      const block=blockOf(el);if(!block||el.textContent.length>200)return;
      e.preventDefault();
      const r=document.createRange();r.selectNodeContents(block);r.setEndBefore(el);const start=r.toString().length;
      explain(anchorFor(block,start,start+el.textContent.length,el.getBoundingClientRect()));
    }
    root.addEventListener('click',clickWord,opts);
    root.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.matches('.wn-word,.source-emphasis,.tj-key,.wxj-key')){e.preventDefault();e.target.click();}},opts);
    root.querySelectorAll('.source-emphasis,.tj-key').forEach(el=>{el.tabIndex=0;el.setAttribute('role','button');el.setAttribute('aria-label',el.textContent+'，解释批注');});
    document.addEventListener('pointerdown',e=>{if(!pop.contains(e.target)&&!e.target.closest('.wn-word,.source-emphasis,.tj-key,.wxj-key')&&e.target!==toolbar&&e.target!==highlightTool)pop.hidden=true;},opts);
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){pop.hidden=true;hideTools();}},opts);
    document.addEventListener('scroll',e=>{if(pop.contains(e.target))return;hideTools();pop.hidden=true;}, {...opts,capture:true});
    window.addEventListener('resize',()=>{hideTools();pop.hidden=true;},opts);
    async function loadNotes(){
      loadError=null;
      try{const result=await api('/api/politics/notes',source);if(alive&&root.isConnected){notes={...notes,...result.notes};await refreshReading();if(alive){paint();readingReady=true;if(managed)root.dataset.highlightsReady='true';}}}
      catch(e){loadError=e;}
    }
    notesReady=loadNotes();
  }
  window.WORD_NOTES={mount,close:()=>cleanup()};
})();
