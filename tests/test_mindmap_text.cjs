/* 行内格式必须可读、保留字面转义，用户HTML/链接不能成为可执行节点。 */
const assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
const dom=new JSDOM('',{runScripts:'outside-only'}),w=dom.window;
w.eval(fs.readFileSync('web/mindmap_text.js','utf8'));
const f=w.MINDMAP_TEXT,read=s=>{const e=w.document.createElement('div');e.innerHTML=f.html(s);return e;};
let e=read('普通 **加粗**、__重点__、*斜体*、~~删除~~、`**原样**`：$A \\rightarrow B \\Leftrightarrow C$ → &rarr;');
assert.equal(e.querySelector('strong').textContent,'加粗');assert.equal(e.querySelectorAll('strong').length,2);
assert.equal(e.querySelector('em').textContent,'斜体');assert.equal(e.querySelector('del').textContent,'删除');
assert.equal(e.querySelector('code').textContent,'**原样**');assert(e.textContent.includes('A → B ⇔ C → →'));
e=read('\\*\\*字面星号\\*\\*、a_b_c、$未知\\unknown{甲}$');assert.equal(e.querySelector('strong,em'),null);assert(e.textContent.includes('未知\\unknown{甲}'));
e=read('***双重强调*** **外层 *内层***');assert.equal(e.querySelector('strong em').textContent,'双重强调');assert.equal(e.querySelectorAll('strong em')[1].textContent,'内层');
e=read('<img src="bad" onerror="alert(1)"> &lt;script&gt;bad&lt;/script&gt;');assert.equal(e.querySelector('img,script'),null);assert(e.textContent.includes('<img'));
const old={data:{richText:true,text:'<p><strong>保留重点</strong> &rarr; <span style="font-style:italic">条件</span></p><p><script>bad()</script><img src="bad">下一行</p>'}};
f.normalize(old);e=read(old.data.text);assert.equal(e.querySelector('strong').textContent,'保留重点');assert.equal(e.querySelector('em').textContent,'条件');assert(e.textContent.includes('→'));assert(e.textContent.includes('\n下一行'));assert(!e.textContent.includes('bad'));assert.equal(old.data.richText,undefined);
console.log('灵脉图行内格式：加粗/嵌套/箭头/公式/代码/转义/旧富文本/HTML隔离通过');
