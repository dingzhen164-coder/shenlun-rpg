/* 验证全部主题/节点/条件的Ink文字、选择和跳转与服务器定义一致。 */
const fs=require('node:fs'),assert=require('node:assert/strict');
const {Story}=require('../web/vendor/inkjs/ink.js');
const definitions=JSON.parse(fs.readFileSync('rpg/data/narrative.json','utf8'));
let count=0;
for(const [world,def] of Object.entries(definitions)){
  const source=fs.readFileSync(`web/stories/${world}.json`,'utf8');
  for(const chapter of def.chapters)for(const [node,definition] of Object.entries(chapter.nodes))for(const learned of [false,true]){
    const s=new Story(source);s.variablesState.learned=learned;s.ChoosePathString(node);
    const lines=[];while(s.canContinue){const text=s.Continue().trim();if(text)lines.push(text);}
    assert.deepEqual(lines,definition.lines,`${world}/${node}`);
    const expected=definition.choices.filter(c=>!c.when||learned);
    assert.deepEqual(s.currentChoices.map(c=>c.text.trim()),expected.map(c=>c.text),`${world}/${node} choices`);
    for(const [i,c] of expected.entries()){
      const branch=new Story(source);branch.variablesState.learned=learned;branch.ChoosePathString(node);
      while(branch.canContinue)branch.Continue();branch.ChooseChoiceIndex(i);
      const result=[];while(branch.canContinue){const t=branch.Continue().trim();if(t)result.push(t);}
      assert.deepEqual(result,chapter.nodes[c.target].lines,`${world}/${node}/${c.id} target`);
    }
    count++;
  }
}
console.log(`Ink节点与条件检查通过：${count}组`);
