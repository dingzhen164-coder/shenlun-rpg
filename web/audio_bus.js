/* 媒体音量总线：iOS忽略HTMLMediaElement.volume，改用Web Audio的GainNode。
   同源音乐/音效复用每个媒体节点的增益；无Web Audio时回退原音量。
   播放仍由原播放器控制，手势与回到前台时恢复AudioContext。 */
(() => {
 'use strict';
 let context;
 const channels=new WeakMap();
 const clamp=v=>Math.max(0,Math.min(1,Number(v)||0));
 function channel(audio){
  if(channels.has(audio))return channels.get(audio);
  const C=window.AudioContext||window.webkitAudioContext;
  if(!C)return null;
  try{
   context=context||new C();
   const source=context.createMediaElementSource(audio),gain=context.createGain();
   source.connect(gain);gain.connect(context.destination);
   const node={source,gain,value:1};channels.set(audio,node);return node;
  }catch(_){return null;}
 }
 function volume(audio,value){
  if(!audio)return;
  const v=clamp(value),node=channel(audio);
  if(node){node.value=v;node.gain.gain.setValueAtTime(v,context.currentTime);}
  else audio.volume=v;
 }
 function getVolume(audio){return channels.get(audio)?.value??audio.volume;}
 function resume(){if(context?.state==='suspended')context.resume().catch(()=>{});}
 document.addEventListener('pointerdown',resume,{capture:true});
 document.addEventListener('touchend',resume,{capture:true,passive:true});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)resume();});
 window.AudioBus={volume,getVolume,resume};
})();
