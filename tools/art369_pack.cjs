/* 试炼塔原生分块高清合成：prepare只生成构图参考，pack只缩小足尺寸原生块。
 * 开发工具依赖ImageMagick，不增加客户端依赖；输出含原生尺寸/哈希的来源清单。
 */
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),crypto=require('node:crypto');
const work=process.env.ART_PACK_WORK||'/workspace/art369-work',W=3840,H=2880,pad=16;
const run=args=>cp.execFileSync('convert',['-limit','thread','2',...args],{encoding:'utf8'});
const dimensions=file=>cp.execFileSync('identify',['-format','%w %h',file],{encoding:'utf8'}).trim().split(' ').map(Number);
const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const [command,input,...files]=process.argv.slice(2);
if(command==='prepare'){
 fs.mkdirSync(work,{recursive:true});run([input,'-resize',`${W}x${H}!`,path.join(work,'reference.png')]);
 const tiles=[];
 for(let row=0;row<2;row++)for(let col=0;col<4;col++){
  const index=row*4+col,x=Math.max(0,col*960-pad),y=Math.max(0,row*1440-pad),w=Math.min(W,(col+1)*960+pad)-x,h=Math.min(H,(row+1)*1440+pad)-y,ref=path.join(work,`ref-${index}.png`);
  run([path.join(work,'reference.png'),'-crop',`${w}x${h}+${x}+${y}`,'+repage',ref]);tiles.push({index,x,y,w,h,ref});
 }
 fs.writeFileSync(path.join(work,'spec.json'),JSON.stringify({base:input,baseNative:dimensions(input),target:[W,H],tiles},null,2));
 console.log(JSON.stringify(tiles));
}else if(command==='pack'){
 const spec=JSON.parse(fs.readFileSync(path.join(work,'spec.json'),'utf8'));if(files.length!==8)throw Error('需要8个原生块');
 const canvas=path.join(work,'canvas.png');run(['-size',`${W}x${H}`,'xc:black','-colorspace','sRGB','-type','TrueColor','-define','png:color-type=2',canvas]);
 for(const tile of spec.tiles){
  tile.path=files[tile.index];tile.native=dimensions(tile.path);tile.sha256=hash(tile.path);
  if(tile.native[0]<tile.w||tile.native[1]<tile.h)throw Error('原生尺寸不足：'+JSON.stringify(tile));
  const fit=path.join(work,`fit-${tile.index}.png`),tone=path.join(work,`tone-${tile.index}.png`),blend=path.join(work,`blend-${tile.index}.png`);
  run([tile.path,'-alpha','off','-resize',`${tile.w}x${tile.h}!`,fit]);
  run([fit,tile.ref,'(','-clone','0','-blur','0x24',')','(','-clone','1','-blur','0x24',')','-delete','1','-fx','u[0]+u[2]-u[1]',tone]);
  const factors=[];if(tile.x>0)factors.push('min(1,i/31)');if(tile.x+tile.w<W)factors.push('min(1,(w-1-i)/31)');if(tile.y>0)factors.push('min(1,j/31)');if(tile.y+tile.h<H)factors.push('min(1,(h-1-j)/31)');
  run([tone,'-alpha','off','-fx',`u*(${factors.join('*')||'1'})`,'-define','png:color-type=2',blend]);run([canvas,blend,'-geometry',`+${tile.x}+${tile.y}`,'-compose','Plus','-composite','-define','png:color-type=2',canvas]);
 }
 fs.mkdirSync(path.dirname(input),{recursive:true});run([canvas,'-quality','94','-define','webp:method=6',input]);
 spec.method='native-portrait-tiles';spec.interpolated_upscale=false;spec.grid=[4,2];spec.output=input;spec.sha256=hash(input);spec.bytes=fs.statSync(input).size;spec.actual=dimensions(input);
 fs.writeFileSync(input.replace(/\.webp$/,'.provenance.json'),JSON.stringify(spec,null,2)+'\n');console.log(JSON.stringify({actual:spec.actual,bytes:spec.bytes,sha256:spec.sha256}));
}else throw Error('prepare 原图 | pack 输出webp 8个原生块');
