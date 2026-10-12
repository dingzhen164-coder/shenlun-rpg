/* 开发时生成Ink源与编译JSON；应用只带运行时，用户不需要Node/编译器。
   数据源rpg/data/narrative.json；INKJS_COMPILER指向inkjs@2.4.0的dist/ink-full.js。 */
const fs=require('node:fs'),path=require('node:path');
const {Compiler}=require(process.env.INKJS_COMPILER||'inkjs/full');
const base=path.resolve(__dirname,'..');
const definitions=JSON.parse(fs.readFileSync(path.join(base,'rpg/data/narrative.json'),'utf8'));
const out=path.join(base,'web/stories');fs.mkdirSync(out,{recursive:true});
for(const [world,definition] of Object.entries(definitions)){
  const lines=['// 原创剧情，生成自rpg/data/narrative.json；修改该源后重新编译。',
    'VAR learned = false','VAR tower = false','VAR boss = false','-> END'];
  for(const chapter of definition.chapters)for(const [id,node] of Object.entries(chapter.nodes)){
    lines.push(`=== ${id} ===`,...node.lines);
    for(const c of node.choices)lines.push(`+ ${c.when?`{${c.when}} `:''}[${c.text}] # choice:${c.id}`,`  -> ${c.target}`);
    if(!node.choices.length)lines.push('-> END');
  }
  const source=lines.join('\n')+'\n';
  const compiler=new Compiler(source);const story=compiler.Compile();
  if(compiler.errors?.length)throw Error(compiler.errors.join('\n'));
  fs.writeFileSync(path.join(out,world+'.ink'),source);
  fs.writeFileSync(path.join(out,world+'.json'),story.ToJson()+'\n');
}
console.log('Ink剧情编译通过');
