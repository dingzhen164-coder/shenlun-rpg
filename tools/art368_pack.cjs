/* 原生分块重绘的开发用合成工具：只负责裁切参考/降采样原生块/接缝色调与合成，不调用AI超分。
 * prepare只生成参考，不作为成品像素来源；pack逐块断言原生分辨率足够，最终细节来自生成块。
 */
const fs=require('node:fs'),path=require('node:path'),{execFileSync}=require('node:child_process'),crypto=require('node:crypto');
const ROOT=path.resolve(process.env.ART368_WORK||'../art368-work'),W=3840,H=2880,PAD=16;
const run=args=>execFileSync('magick',args[0]==='identify'?['identify','-limit','thread','2',...args.slice(1)]:['-limit','thread','2',...args],{encoding:'utf8',maxBuffer:1024*1024});
const identify=file=>run(['identify','-format','%w %h',file]).trim().split(/\s+/).map(Number);
function prepare(name,base){
 if(!/^(home|train)-[a-z]+-(day|dusk|night)$/.test(name))throw Error('名称不合法');
 const folder=path.join(ROOT,name);fs.mkdirSync(folder,{recursive:true});
 const full=path.join(folder,'reference-full.png');run([base,'-resize',W+'x'+H+'!',full]);
 const tiles=[];
 for(let row=0;row<2;row++)for(let col=0;col<4;col++){
  const index=row*4+col,x=Math.max(0,col*960-PAD),y=Math.max(0,row*1440-PAD),w=Math.min(W,(col+1)*960+PAD)-x,h=Math.min(H,(row+1)*1440+PAD)-y;
  const ref=path.join(folder,'ref-'+index+'.png');run([full,'-crop',`${w}x${h}+${x}+${y}`,'+repage',ref]);tiles.push({index,x,y,w,h,ref});
 }
 return {name,base,baseNative:identify(base),target:[W,H],grid:[4,2],overlap:PAD,tiles};
}
function pack(spec){
 if(spec.tiles.length!==8)throw Error('必须有8块');
 const folder=path.join(ROOT,spec.name),canvas=path.join(folder,'canvas.png');run(['-size',W+'x'+H,'xc:black','-colorspace','sRGB','-type','TrueColor','-define','png:color-type=2',canvas]);
 for(const tile of spec.tiles){
  const native=identify(tile.path);if(native[0]<tile.w||native[1]<tile.h)throw Error('原生块不足目标区域：'+JSON.stringify({name:spec.name,tile:tile.index,native,needed:[tile.w,tile.h]}));
  tile.native=native;tile.sha256=crypto.createHash('sha256').update(fs.readFileSync(tile.path)).digest('hex');
  const token=crypto.createHash('sha256').update(tile.sha256).update(fs.readFileSync(tile.ref)).update(tile.w+'x'+tile.h).digest('hex').slice(0,16);
  const resized=path.join(folder,'fit-'+tile.index+'-'+token+'.png'),corrected=path.join(folder,'tone-'+tile.index+'-'+token+'.png'),masked=path.join(folder,'blend-'+tile.index+'.png');
  if(!fs.existsSync(resized))run([tile.path,'-alpha','off','-resize',tile.w+'x'+tile.h+'!',resized]);
  // 仅用参考低频色调消除分块色差；新绘高频纹理保留，参考本身不作成品底层。
  if(!fs.existsSync(corrected))run([resized,tile.ref,'(','-clone','0','-blur','0x24',')','(','-clone','1','-blur','0x24',')','-delete','1','-fx','u[0]+u[2]-u[1]',corrected]);
  const factors=[];
  if(tile.x>0)factors.push('min(1,i/31)');if(tile.x+tile.w<W)factors.push('min(1,(w-1-i)/31)');
  if(tile.y>0)factors.push('min(1,j/31)');if(tile.y+tile.h<H)factors.push('min(1,(h-1-j)/31)');
  run([corrected,'-alpha','off','-fx','u*('+(factors.join('*')||'1')+')','-define','png:color-type=2',masked]);
  run([canvas,masked,'-geometry',`+${tile.x}+${tile.y}`,'-compose','Plus','-composite','-define','png:color-type=2',canvas]);
 }
 const output=path.join(folder,'final.webp');run([canvas,'-alpha','off','-define','webp:method=6','-quality','94',output]);
 const bytes=fs.statSync(output).size;if(bytes>12*1024*1024)throw Error('单图超过12MiB');
 const metadata={...spec,output,bytes,sha256:crypto.createHash('sha256').update(fs.readFileSync(output)).digest('hex'),actual:identify(output)};
 fs.writeFileSync(path.join(folder,'metadata.json'),JSON.stringify(metadata,null,2)+'\n');return metadata;
}
const [command,a,b]=process.argv.slice(2);
if(command==='prepare')console.log(JSON.stringify(prepare(a,b)));
else if(command==='pack')console.log(JSON.stringify(pack(JSON.parse(fs.readFileSync(a,'utf8')))));
else throw Error('prepare name base | pack spec.json');
