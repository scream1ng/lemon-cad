import {useState} from 'react';
import type {Sketch} from './cadDocument';

type Props={sketch:Sketch;disabled:boolean;onChange:(values:Partial<Sketch>)=>void};
export function PlanarSketch({sketch:s,disabled,onChange}:Props){
  const [first,setFirst]=useState<[number,number]|null>(null);
  const [span,setSpan]=useState(()=>Math.max(120,s.width*1.4,s.height*2,Math.abs(s.x||0)*2,Math.abs(s.y||0)*2,...(s.points||[]).flatMap(p=>p.map(v=>Math.abs(v)*2))));
  const [origin,setOrigin]=useState<[number,number]>(()=>s.frame?[(s.x||0)-10,(s.y||0)-10]:[0,0]);
  const x=s.x||0,y=s.y||0,scale=360/(Number.isFinite(span)&&span>=20&&span<=8000?span:120);
  const xy=(u:number,v:number)=>[30+(u-origin[0])*scale,210-(v-origin[1])*scale];
  const [cx,cy]=xy(x,y);
  const valid=[s.x??0,s.y??0,s.width,s.height,s.diameter,...(s.points||[]).flat()].every(Number.isFinite);
  function draw(event:React.PointerEvent<SVGSVGElement>){
    if(disabled)return;
    const svg=event.currentTarget,ctm=svg.getScreenCTM();if(!ctm)return;
    const p=new DOMPoint(event.clientX,event.clientY).matrixTransform(ctm.inverse());
    const u=Math.round((p.x-30)/scale+origin[0]),v=Math.round((210-p.y)/scale+origin[1]);
    if(Math.abs(u)>2000||Math.abs(v)>2000)return;
    if(s.profile==='circle')onChange({x:u,y:v});
    else if(s.profile==='polygon'){if((s.points?.length||0)<128)onChange({points:[...(s.points||[]),[u-x,v-y]],closed:false});}
    else if(!first)setFirst([u,v]);
    else {const width=Math.abs(u-first[0]),height=Math.abs(v-first[1]);if(width>0&&height>0){onChange({x:Math.min(first[0],u),y:Math.min(first[1],v),width,height});setFirst(null);}}
  }
  function fit(){
    const points=s.profile==='polygon'?(s.points||[]).map(([u,v])=>[u+x,v+y]):s.profile==='circle'?[[x-s.diameter/2,y-s.diameter/2],[x+s.diameter/2,y+s.diameter/2]]:[[x,y],[x+s.width,y+s.height]];
    if(!points.length||points.flat().some(v=>!Number.isFinite(v)))return;
    const low=[Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1]))],high=[Math.max(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1]))];
    setOrigin([low[0],low[1]]);setSpan(Math.max(20,(high[0]-low[0])*1.2,(high[1]-low[1])*2));
  }
  return <div className="planar-sketch">
    <svg viewBox="0 0 400 240" role="img" aria-label={`Sketch drawing area on ${s.frame?'selected face':s.plane||'XY'}. ${s.profile==='rectangle'?'Click two corners.':s.profile==='circle'?'Click to place centre.':'Click to add vertices, then close the profile.'} Coordinates can also be entered below.`} onPointerDown={draw}>
      <defs><pattern id="sketch-grid" width={10*scale} height={10*scale} patternUnits="userSpaceOnUse" x={xy(0,0)[0]} y={xy(0,0)[1]}><path d={`M ${10*scale} 0 H0 V${10*scale}`} fill="none" stroke="currentColor" strokeWidth=".5"/></pattern></defs>
      <rect width="400" height="240" fill="url(#sketch-grid)" className="sketch-grid"/>
      <path d={`M0 ${xy(0,0)[1]}H400M${xy(0,0)[0]} 240V0`} className="sketch-axis"/>
      <text x="380" y="228">{s.frame?'U':s.plane==='YZ'?'Y':'X'}</text><text x="12" y="16">{s.frame?'V':s.plane==='XY'?'Y':'Z'}</text>
      {valid&&(s.profile==='rectangle'?<rect className="sketch-profile" x={cx} y={cy-s.height*scale} width={s.width*scale} height={s.height*scale}/>:s.profile==='circle'?<circle className="sketch-profile" cx={cx} cy={cy} r={s.diameter*scale/2}/>:<path className="sketch-profile" d={(s.points||[]).map(([u,v],i)=>`${i?'L':'M'}${xy(u+x,v+y).join(' ')}`).join(' ')+(s.closed?' Z':'')} style={s.closed?undefined:{fill:'none'}}/>)}
      {(s.points||[]).filter(()=>valid&&s.profile==='polygon').map(([u,v],i)=><circle key={i} cx={xy(u+x,v+y)[0]} cy={xy(u+x,v+y)[1]} r="3" className="sketch-vertex"/>)}
      {first&&s.profile==='rectangle'&&<circle cx={xy(...first)[0]} cy={xy(...first)[1]} r="4" className="sketch-vertex"/>}
    </svg>
    <div className="sketch-controls"><span>{s.profile==='rectangle'?(first?'Choose opposite corner':'Click two corners'):s.profile==='circle'?'Click to place centre':s.closed?'Closed profile':'Click to add corners'}</span><button type="button" disabled={disabled} onClick={fit}>Fit sketch</button><label>View <input type="number" step="any" aria-label="Sketch view width" min="20" max="8000" required value={Number.isNaN(span)?'':span} disabled={disabled} onChange={e=>setSpan(e.target.valueAsNumber)}/> mm</label></div>
    {s.profile==='polygon'&&<><div className="sketch-point-actions"><button type="button" disabled={disabled||!s.points?.length} onClick={()=>onChange({points:s.points!.slice(0,-1),closed:false})}>Undo point</button><button type="button" disabled={disabled||(s.points?.length||0)<3||s.closed} onClick={()=>onChange({closed:true})}>Close profile</button><button type="button" disabled={disabled||(s.points?.length||0)>=128} onClick={()=>onChange({points:[...(s.points||[]),[0,0]],closed:false})}>Add point</button></div><div className="sketch-points">{(s.points||[]).map((point,i)=><div key={i}><span>{i+1}</span>{point.map((v,k)=><label key={k}><span>{k?'V':'U'}</span><input type="number" step="any" min="-2000" max="2000" required disabled={disabled} aria-label={`Point ${i+1} ${k?'V':'U'}`} value={Number.isNaN(v)?'':v} onChange={e=>{const points=s.points!.map(p=>[...p] as [number,number]);points[i][k]=e.target.valueAsNumber;onChange({points});}}/></label>)}</div>)}</div></>}
  </div>;
}
