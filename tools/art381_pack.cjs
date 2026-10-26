/* 3.8.1场景原生分块队列：复用art369_pack的无放大合成，构图和原生块只留开发工作区。
 * prepare concepts.json | pack 场景名 tiles.json | status；不调用图像生成，不新增运行依赖。
 */
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),crypto=require('node:crypto');
const repo=path.resolve(__dirname,'..'),root=path.resolve(process.env.ART381_WORK||path.join(repo,'..','art381-work'));
const target=name=>path.join(repo,'web/assets/beauty/scenes/xingce/hd/381',name+'.webp');
const run=(args,name)=>cp.execFileSync(process.execPath,[path.join(__dirname,'art369_pack.cjs'),...args],{env:{...process.env,ART_PACK_WORK:path.join(root,name)},encoding:'utf8',maxBuffer:1024*1024});
const convert=(args,input)=>cp.execFileSync('convert',['-limit','thread','2',...args],{input,maxBuffer:64*1024*1024});
const dimensions=file=>cp.execFileSync('identify',['-format','%w %h',file],{encoding:'utf8'}).trim().split(' ').map(Number);
const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
function pack(name,files){
 const spec=JSON.parse(fs.readFileSync(path.join(root,name,'spec.json'),'utf8')),W=3840,H=2880;
 const sum=new Float32Array(W*H*3);
 for(const tile of spec.tiles){
  tile.path=files[tile.index];tile.native=dimensions(tile.path);tile.sha256=hash(tile.path);
  if(tile.native[0]<tile.w||tile.native[1]<tile.h)throw Error('原生块不足 '+name+':'+tile.index);
  const args=[tile.path,'-alpha','off','-resize',tile.w+'x'+tile.h+'!','-colorspace','sRGB'];
  const pixels=convert([...args,'-depth','8','rgb:-']),blur=convert([...args,'-blur','0x24','-depth','8','rgb:-']);
  const reference=convert([tile.ref,'-alpha','off','-colorspace','sRGB','-blur','0x24','-depth','8','rgb:-']);
  if(pixels.length!==tile.w*tile.h*3||blur.length!==pixels.length||reference.length!==pixels.length)throw Error('RGB长度不符');
  for(let y=0;y<tile.h;y++)for(let x=0;x<tile.w;x++){
   let a=1;if(tile.x>0)a*=Math.min(1,x/31);if(tile.x+tile.w<W)a*=Math.min(1,(tile.w-1-x)/31);if(tile.y>0)a*=Math.min(1,y/31);if(tile.y+tile.h<H)a*=Math.min(1,(tile.h-1-y)/31);
   const i=(y*tile.w+x)*3,j=((y+tile.y)*W+x+tile.x)*3;
   for(let c=0;c<3;c++)sum[j+c]+=Math.max(0,Math.min(255,pixels[i+c]+reference[i+c]-blur[i+c]))*a;
  }
 }
 const bytes=Buffer.alloc(sum.length);for(let i=0;i<sum.length;i++)bytes[i]=Math.max(0,Math.min(255,Math.round(sum[i])));
 const output=target(name);fs.mkdirSync(path.dirname(output),{recursive:true});convert(['-size',W+'x'+H,'-depth','8','rgb:-','-quality','94','-define','webp:method=6',output],bytes);
 const result={...spec,method:'native-portrait-tiles-rgb-low-frequency-alignment',interpolated_upscale:false,grid:[4,2],output,actual:dimensions(output),bytes:fs.statSync(output).size,sha256:hash(output)};
 fs.writeFileSync(output.replace(/\.webp$/,'.provenance.json'),JSON.stringify(result,null,2)+'\n');return {actual:result.actual,bytes:result.bytes,sha256:result.sha256};
}
const [command,arg,tilesFile]=process.argv.slice(2);
if(command==='prepare'){
 const scenes=JSON.parse(fs.readFileSync(arg,'utf8'));
 for(const [name,input]of Object.entries(scenes)){if(!/^(dwelling|bank|contest|skeleton|tianji|settings|selection)-(day|dusk|night|dawn)$/.test(name))throw Error('场景名无效');const spec=path.join(root,name,'spec.json');if(!fs.existsSync(spec))run(['prepare',input],name);}
 console.log(JSON.stringify({scenes:Object.keys(scenes).length,tiles:Object.keys(scenes).length*8,root}));
}else if(command==='pack'){
 if(!/^(dwelling|bank|contest|skeleton|tianji|settings|selection)-(day|dusk|night|dawn)$/.test(arg))throw Error('场景名无效');
 const entries=JSON.parse(fs.readFileSync(tilesFile,'utf8')),files=Array.from({length:8},(_,i)=>entries[arg+':'+i]);if(files.some(x=>!x))throw Error('原生块不全 '+arg);
 if(!fs.existsSync(target(arg)))console.log(JSON.stringify(pack(arg,files)));else console.log('已有成品 '+arg);
}else if(command==='status'){
 const folder=path.join(repo,'web/assets/beauty/scenes/xingce/hd/381');console.log(JSON.stringify(fs.existsSync(folder)?fs.readdirSync(folder).filter(n=>n.endsWith('.webp')):[]));
}else throw Error('prepare concepts.json | pack name tiles.json | status');
