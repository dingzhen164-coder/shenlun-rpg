/* 灵脉图共用行内格式：Markdown/常用公式转安全文字片段，文档与SVG使用同一结果。
 * 只处理显示；节点仍保存原始Markdown，使用原SVG节点测量，不开启foreignObject富文本插件。
 */
(() => {
  'use strict';
  const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const symbols={rightarrow:'→',longrightarrow:'⟶',to:'→',Rightarrow:'⇒',Longrightarrow:'⟹',implies:'⇒',leftarrow:'←',Leftarrow:'⇐',leftrightarrow:'↔',longleftrightarrow:'↔',Leftrightarrow:'⇔',iff:'⇔',uparrow:'↑',downarrow:'↓',neg:'¬',lnot:'¬',land:'∧',wedge:'∧',lor:'∨',vee:'∨',forall:'∀',exists:'∃',in:'∈',notin:'∉',subset:'⊂',subseteq:'⊆',cup:'∪',cap:'∩',neq:'≠',ne:'≠',leq:'≤',le:'≤',geq:'≥',ge:'≥',equiv:'≡',approx:'≈',times:'×',div:'÷',cdot:'·',pm:'±',infty:'∞',therefore:'∴',because:'∵',alpha:'α',beta:'β',gamma:'γ',delta:'δ',pi:'π',ldots:'…',dots:'…',quad:' ',qquad:'  '};
  const math=s=>s.replace(/\\(?:text|mathrm)\{([^{}]*)\}/g,'$1').replace(/\\([A-Za-z]+)\b/g,(all,name)=>symbols[name]??all);
  const entity=s=>s.replace(/&(?:#\d+|#x[\da-f]+|[a-z][a-z\d]+);/gi,m=>{const e=document.createElement('textarea');e.innerHTML=m;return e.value;});
  const literal=s=>s.replace(/[\\`*_~$]/g,'\\$&');
  // template内容不会挂到页面；只取文字及允许的格式，不复制标签、属性或资源。
  function fromHtml(source){
    const template=document.createElement('template');template.innerHTML=String(source);
    const visit=(node,active={})=>{
      if(node.nodeType===3)return literal(node.textContent);
      if(node.nodeType!==1&&node.nodeType!==11)return '';
      const tag=node.nodeName.toLowerCase();
      if(['script','style','iframe','object','embed','svg','math'].includes(tag))return '';
      if(tag==='br')return '\n';
      const b=['b','strong'].includes(tag)||/^(bold|[6-9]00)$/.test(node.style?.fontWeight||''),i=['i','em'].includes(tag)||node.style?.fontStyle==='italic',del=['s','strike','del'].includes(tag)||node.style?.textDecoration.includes('line-through');
      const next={b:active.b||b,i:active.i||i,del:active.del||del};
      let body=[...node.childNodes].map(c=>visit(c,next)).join('');
      if(tag==='code')return '`'+node.textContent.replace(/`/g,'\\`')+'`';
      if(del&&!active.del)body='~~'+body+'~~';
      if(i&&!active.i)body='*'+body+'*';
      if(b&&!active.b)body='**'+body+'**';
      return body+(['p','div','li'].includes(tag)?'\n':'');
    };
    return visit(template.content).trim();
  }
  function runs(source){
    const out=[];
    const add=(text,style,decode=true)=>{if(!text)return;text=decode?entity(text):text;const last=out[out.length-1];if(last&&['b','i','code','del'].every(k=>!!last[k]===!!style[k]))last.text+=text;else out.push({text,...style});};
    function parse(s,style={},depth=0){
      if(depth>12){add(s,style);return;}
      let p=0,plain='';const flush=()=>{add(plain,style);plain='';};
      while(p<s.length){
        if(s[p]==='\\'&&/[\\`*_~$<>\[\]#]/.test(s[p+1]||'')){plain+=s[p+1];p+=2;continue;}
        if(s[p]==='`'){
          const marker=s.slice(p).match(/^`+/)[0],end=s.indexOf(marker,p+marker.length);
          if(end>=0){flush();add(s.slice(p+marker.length,end),{...style,code:true},false);p=end+marker.length;continue;}
        }
        if(s[p]==='$'){
          const marker=s[p+1]==='$'?'$$':'$',end=s.indexOf(marker,p+marker.length);
          if(end>p+marker.length){flush();add(math(s.slice(p+marker.length,end)),style);p=end+marker.length;continue;}
        }
        const marker=['***','___','**','__','~~','*','_'].find(m=>s.startsWith(m,p));
        if(marker&&!/\s/.test(s[p+marker.length]||' ')&&!(marker.includes('_')&&/\w/.test(s[p-1]||''))){
          let end=s.indexOf(marker,p+marker.length);
          while(end>=0){
            if(s[end-1]==='\\'||/\s/.test(s[end-1])){end=s.indexOf(marker,end+marker.length);continue;}
            const count=s.slice(end).match(new RegExp('^'+(marker[0]==='*'?'\\*':marker[0])+'+'))[0].length;
            if(marker.length===1&&count===2){end=s.indexOf(marker,end+count);continue;}
            if(marker.length===2&&count===3)end++;
            else if(marker.length===1&&count===3)end+=2;
            break;
          }
          if(end>=0){flush();const next={...style};if(marker==='~~')next.del=true;else{if(marker.length>=2)next.b=true;if(marker.length!==2)next.i=true;}parse(s.slice(p+marker.length,end),next,depth+1);p=end+marker.length;continue;}
        }
        plain+=s[p++];
      }
      flush();
    }
    parse(String(source??'').replace(/\r\n?/g,'\n'));return out;
  }
  function html(source){return runs(source).map(r=>{let s=esc(r.text);if(r.code)s='<code>'+s+'</code>';if(r.del)s='<del>'+s+'</del>';if(r.i)s='<em>'+s+'</em>';if(r.b)s='<strong>'+s+'</strong>';return s;}).join('');}
  function normalize(node){
    if(!node?.data)return node;
    if(node.data.richText){node.data.text=fromHtml(node.data.text||'');delete node.data.richText;}
    (node.children||[]).forEach(normalize);return node;
  }
  function installNode(node){
    if(node.__inlineText)return null;node.__inlineText=true;
    const original=node.createTextNode;
    node.createTextNode=function(specify){
      const source=typeof specify==='string'?specify:this.getData('text'),parts=runs(source),text=parts.map(r=>r.text).join('');
      const result=original.call(this,text);
      if(!parts.some(r=>r.b||r.i||r.code||r.del))return result;
      let offset=0;
      const indexed=parts.map(r=>{const start=offset;offset+=r.text.length;return {...r,start,end:offset};});offset=0;
      for(const line of result.node.node.querySelectorAll('text')){
        const length=line.textContent==='\uFEFF'?0:line.textContent.length,end=offset+length;
        if(length){const spans=indexed.filter(r=>r.end>offset&&r.start<end).map(r=>{const span=document.createElementNS('http://www.w3.org/2000/svg','tspan');span.textContent=r.text.slice(Math.max(0,offset-r.start),Math.min(r.text.length,end-r.start));if(r.b)span.setAttribute('font-weight',String(Math.max(700,Number(this.getStyle('fontWeight',false))||400)));if(r.i)span.setAttribute('font-style','italic');if(r.code)span.setAttribute('font-family','ui-monospace, Consolas, monospace');if(r.del)span.setAttribute('text-decoration','line-through');return span;});line.replaceChildren(...spans);}
        offset=end+(text[end]==='\n'?1:0);
      }
      // 放到实际SVG上下文测量，避免离屏测量的斜体/CJK字形与画布里的实际宽度不同。
      const svg=this.mindMap.el.querySelector('svg');
      if(svg?.isConnected)svg.appendChild(result.node.node);
      const box=result.node.bbox();
      if(svg?.isConnected)result.node.node.remove();
      result.width=Math.ceil(box.width*1.03)+2;result.height=Math.ceil(box.height);result.node.attr('data-width',result.width);result.node.attr('data-height',result.height);return result;
    };
    return null;
  }
  window.MINDMAP_TEXT={runs,html,fromHtml,normalize,installNode};
})();
