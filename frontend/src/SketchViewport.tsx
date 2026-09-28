import {useEffect,useRef,useState} from 'react';
import type {Sketch} from './cadDocument';
import type {ViewerHandle} from './Viewer';
import {drawnProfile,planePoint,profilePoints,screenPoint,sketchFrame,rectangleSide,edgeGap,positionFromEdge,type RectangleSide,type PlaneEdge,type SketchTool,type SketchView,type UV} from './sketchGeometry';
type Size='width'|'height'|'diameter';
type Gap={side:RectangleSide;edge:PlaneEdge;label:UV};
type Props={sketch:Sketch;drawn:boolean;tool:SketchTool;viewer:React.RefObject<ViewerHandle|null>;onPatch:(patch:Partial<Sketch>,drawn?:boolean)=>void;onTool:(tool:SketchTool)=>void};
export function SketchViewport(p:Props){
  const host=useRef<HTMLDivElement>(null),[view,setView]=useState<SketchView|null>(null),[first,setFirst]=useState<UV|null>(null),[hover,setHover]=useState<UV|null>(null);
  const [placing,setPlacing]=useState<Size|'gap'|null>(null),[editing,setEditing]=useState<string|null>(null),[value,setValue]=useState(''),[error,setError]=useState('');
  const [side,setSide]=useState<RectangleSide|null>(null),[edge,setEdge]=useState<PlaneEdge|null>(null),[hoverEdge,setHoverEdge]=useState<PlaneEdge|null>(null),[gaps,setGaps]=useState<Gap[]>([]);
  const [positions,setPositions]=useState<Partial<Record<Size,UV>>>({});
  const inputRef=useRef<HTMLInputElement>(null);
  useEffect(()=>{if(editing){inputRef.current?.focus();inputRef.current?.select();}},[editing]);
  const pan=useRef<UV|null>(null),s=p.sketch,frame=sketchFrame(s);
  function clearSelection(){setSide(null);setEdge(null);setHoverEdge(null);setPlacing(null);setError('');}
  useEffect(()=>{let id=0,last='';function update(){const next=p.viewer.current?.sketchView();if(next){const key=JSON.stringify(next);if(key!==last){last=key;setView(next);}}id=requestAnimationFrame(update);}update();return()=>cancelAnimationFrame(id);},[p.viewer]);
  useEffect(()=>{setFirst(null);setHover(null);setEditing(null);clearSelection();},[p.tool,s.id]);
  useEffect(()=>{setGaps([]);setPositions({});setEditing(null);setFirst(null);setHover(null);clearSelection();},[s.profile,s.plane,s.offset,JSON.stringify(s.frame)]);
  useEffect(()=>{host.current?.focus();},[p.tool]);
  if(!view)return null;
  const project=(uv:UV)=>screenPoint(frame,uv,view),x=s.x||0,y=s.y||0;
  const ghost=first&&hover?drawnProfile(p.tool,first,hover):null;
  const shape=ghost?{...s,...ghost}:s;
  const points=(p.drawn||ghost||s.profile==='polygon')?profilePoints(shape).filter(pt=>pt.every(Number.isFinite)):[];
  const screen=points.map(project),closed=!!ghost||(p.drawn&&s.profile!=='polygon')||!!s.closed;
  const path=screen.map((pt,i)=>`${i?'L':'M'}${pt.join(' ')}`).join(' ')+(closed&&screen.length?' Z':'');
  const line=(a:UV,b:UV)=>`M${project(a).join(' ')}L${project(b).join(' ')}`;
  const sidePath=(which:RectangleSide)=>line(...rectangleSide(s,which));
  const hint=error|| (editing?'Enter a distance':placing?'Click to place dimension':p.tool==='dimension'?(s.profile==='polygon'?'Use Options to edit point coordinates':edge?'Select a parallel rectangle side':side?'Select a parallel model edge, or click away for size':'Select a rectangle side or straight model edge'):p.tool==='rectangle'?(first?'Opposite corner':'First corner'):p.tool==='circle'?(first?'Set radius':'Circle centre'):p.tool==='line'?(s.points?.length?'Next point · click first point to close':'First point'):s.profile==='polygon'?(s.closed?'Closed profile · ready to extrude':'Open profile · use Line to continue'):'Select a dimension to edit');
  function cursor(e:React.PointerEvent):UV{const r=host.current!.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top];}
  function point(e:React.PointerEvent):UV|null{const uv=planePoint(frame,cursor(e),view!);return uv?uv.map(n=>Math.round(n*1000)/1000) as UV:null;}
  function edit(key:string,n:number){setEditing(key);setValue(String(Number(n.toFixed(3))));clearSelection();}
  function selectSide(which:RectangleSide){
    if(placing||editing)return;
    setError('');
    if(edge&&edgeGap(s,which,edge)===null){setError('Choose a side parallel to the model edge.');return;}
    setSide(which);if(edge)setPlacing('gap');
  }
  function down(e:React.PointerEvent){
    host.current?.focus();
    if(e.button===1||e.button===2){e.preventDefault();pan.current=[e.clientX,e.clientY];e.currentTarget.setPointerCapture(e.pointerId);return;}
    if(e.button!==0||editing)return;
    const uv=point(e);if(!uv)return;
    if(placing){
      if(placing==='gap'&&side&&edge){const next={side,edge,label:uv},index=gaps.length;setGaps(old=>[...old,next]);edit('gap:'+index,Math.abs(edgeGap(s,side,edge)!));}
      else if(placing!=='gap'){setPositions(old=>({...old,[placing]:uv}));edit(placing,s[placing]);}
      return;
    }
    if(p.tool==='dimension'&&p.drawn){
      const [cx,cy]=cursor(e),hit=p.viewer.current?.pickSketchEdge(cx,cy,frame);
      if(hit){
        if(side&&edgeGap(s,side,hit)===null){setError('Choose an edge parallel to the rectangle side.');return;}
        setEdge(hit);setError('');if(side)setPlacing('gap');
      }else if(side&&!edge){const size=side==='left'||side==='right'?'height':'width';setPositions(old=>({...old,[size]:uv}));edit(size,s[size]);}
      else setError('Select a visible straight edge on this sketch plane.');
      return;
    }
    if(p.tool==='rectangle'||p.tool==='circle'){
      if(!first)setFirst(uv);
      else {const patch=drawnProfile(p.tool,first,uv);if(patch){p.onPatch(patch,true);setGaps([]);setFirst(null);p.onTool('select');}}
    }else if(p.tool==='line'){
      const pts=s.profile==='polygon'&&!p.drawn?(s.points||[]):[];
      const start=pts[0]&&project([pts[0][0]+x,pts[0][1]+y]),mouse=project(uv);
      if(start&&pts.length>=3&&Math.hypot(start[0]-mouse[0],start[1]-mouse[1])<12){p.onPatch({closed:true},true);p.onTool('select');}
      else if(pts.length<128)p.onPatch({profile:'polygon',x:0,y:0,points:[...pts.map(pt=>[pt[0]+x,pt[1]+y] as UV),uv],closed:false},false);
    }
  }
  function commit(e:React.FormEvent){
    e.preventDefault();if(!editing)return;
    const n=Number(value),gap=editing.startsWith('gap:')?gaps[Number(editing.slice(4))]:null;
    if(!value.trim()||!Number.isFinite(n)||n>2000||(gap?n<0:n<=.01)){setError(gap?'Use a distance from 0 to 2000 mm.':'Use a size above 0.01 and up to 2000 mm.');return;}
    const patch=gap?positionFromEdge(s,gap.side,gap.edge,n):{[editing]:n};
    if(!patch){setError('This position is outside the sketch limits.');return;}
    p.onPatch(patch,true);setEditing(null);setError('');host.current?.focus();
  }
  const definitions:{key:string;name:string;a:UV;b:UV;label:UV;axis:0|1;value:number;gap?:boolean}[]=s.profile==='rectangle'?[{key:'width',name:'Width',a:[x,y],b:[x+s.width,y],label:[x+s.width/2,y],axis:0,value:s.width},{key:'height',name:'Height',a:[x+s.width,y],b:[x+s.width,y+s.height],label:[x+s.width,y+s.height/2],axis:1,value:s.height}]:s.profile==='circle'?[{key:'diameter',name:'Diameter',a:[x-s.diameter/2,y],b:[x+s.diameter/2,y],label:[x+s.diameter/2,y+s.diameter/2],axis:0,value:s.diameter}]:[];
  const dimensions=definitions.map(d=>{const base=project(d.label),label=positions[d.key as Size]?project(positions[d.key as Size]!):[base[0]+(d.key==='height'?44:0),base[1]+(d.key==='width'?34:d.key==='diameter'?-30:0)] as UV;return {...d,a:project(d.a),b:project(d.b),label};});
  if(s.profile==='rectangle')gaps.forEach((g,i)=>{const a=rectangleSide(s,g.side)[0],b=[...a] as UV;b[g.edge.axis]=g.edge.a[g.edge.axis];dimensions.push({key:'gap:'+i,name:`${g.side} edge gap`,a:project(a),b:project(b),label:project(g.label),axis:g.edge.axis,value:Math.abs(edgeGap(s,g.side,g.edge)!),gap:true});});
  const input=dimensions.find(d=>d.key===editing),origin=project([0,0]);
  const inputLeft=input?Math.max(8,Math.min(view.width-228,input.label[0]-65)):0,inputTop=input?Math.max(64,Math.min(view.height-180,input.label[1]-24)):0;
  return <div ref={host} className="viewport-sketch" tabIndex={0} role="application" aria-label="Sketch on model face. Draw directly on the part. Right drag to pan, scroll to zoom." onContextMenu={e=>e.preventDefault()} onWheel={e=>{if(!(e.target as HTMLElement).closest('input,form'))p.viewer.current?.zoomSketch(Math.exp(-e.deltaY*.001));}} onPointerDown={down} onPointerUp={e=>{pan.current=null;if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);}} onPointerCancel={()=>{pan.current=null;}} onPointerMove={e=>{if(pan.current){p.viewer.current?.panSketch(e.clientX-pan.current[0],e.clientY-pan.current[1]);pan.current=[e.clientX,e.clientY];return;}setHover(point(e));if(p.tool==='dimension'&&!placing&&!editing){const [cx,cy]=cursor(e);setHoverEdge(p.viewer.current?.pickSketchEdge(cx,cy,frame)??null);}}} onKeyDown={e=>{if((e.target as HTMLElement).matches('input'))return;if(e.key==='Escape'){e.preventDefault();e.stopPropagation();setFirst(null);setEditing(null);clearSelection();p.onTool('select');}if(e.key==='Backspace'&&p.tool==='line'){e.preventDefault();p.onPatch({points:s.points?.slice(0,-1),closed:false},false);}}}>
    <svg className="sketch-viewport-svg" width={view.width} height={view.height}>
      <path className="viewport-sketch-origin" d={`M${origin[0]-5} ${origin[1]}h26 M${origin[0]} ${origin[1]+5}v-26`}/><text className="sketch-axis-label" x={origin[0]+24} y={origin[1]+4}>U</text><text className="sketch-axis-label" x={origin[0]-4} y={origin[1]-26}>V</text>
      <path className="viewport-sketch-profile" d={path} style={{fill:closed?'#66855b14':'none'}}/>
      {first&&<circle cx={project(first)[0]} cy={project(first)[1]} r="4" className="viewport-sketch-point"/>}
      {p.tool==='line'&&screen.length>0&&hover&&!p.drawn&&<path className="viewport-sketch-ghost" d={`M${screen.at(-1)!.join(' ')}L${project(hover).join(' ')}`}/>}
      {s.profile==='polygon'&&screen.map((pt,i)=><circle key={i} cx={pt[0]} cy={pt[1]} r={i===0?5:3} className="viewport-sketch-point"/>)}
      {p.drawn&&dimensions.map(d=><path key={d.key} className={'sketch-size-line'+(d.gap?' sketch-gap-line':'')} d={d.key==='diameter'?`M${d.a.join(' ')}L${d.b.join(' ')}L${d.label.join(' ')}`:d.axis===0?`M${d.a.join(' ')}V${d.label[1]}H${d.b[0]}V${d.b[1]}`:`M${d.a.join(' ')}H${d.label[0]}V${d.b[1]}H${d.b[0]}`}/>)}
      {p.drawn&&p.tool==='dimension'&&!placing&&!editing&&s.profile==='rectangle'&&(['left','right','bottom','top'] as const).map(which=><path key={which} className="sketch-dimension-hit" d={sidePath(which)} onPointerDown={e=>{if(e.button!==0)return;e.stopPropagation();if(side&&!edge){down(e);return;}selectSide(which);}}/>)}
      {p.drawn&&p.tool==='dimension'&&!placing&&!editing&&s.profile==='circle'&&<path className="sketch-dimension-hit" d={path} onPointerDown={e=>{if(e.button!==0)return;e.stopPropagation();setPlacing('diameter');}}/>}
      {side&&<path className="sketch-reference-edge" d={sidePath(side)}/>}
      {(edge||hoverEdge)&&<path className="sketch-reference-edge" d={line((edge||hoverEdge)!.a,(edge||hoverEdge)!.b)}/>}
      {placing&&hover&&<text x={project(hover)[0]+12} y={project(hover)[1]-12} className="sketch-place-label">{placing==='gap'?'Edge gap':placing==='diameter'?'Ø '+Number(s.diameter.toFixed(2)):Number(s[placing].toFixed(2))} mm</text>}
    </svg>
    {p.drawn&&dimensions.map(d=><button key={d.key} className={'sketch-size-label'+(d.gap?' sketch-gap-label':'')} aria-label={`Edit sketch ${d.name.toLowerCase()}`} title={d.gap?'Position once · no persistent edge link':undefined} style={{left:Math.max(44,Math.min(view.width-44,d.label[0])),top:Math.max(80,Math.min(view.height-68,d.label[1]))}} onPointerDown={e=>e.stopPropagation()} onClick={()=>edit(d.key,d.value)}>{d.key==='diameter'?'Ø':''}{Number(d.value.toFixed(2))}<small> mm</small></button>)}
    {input&&<form className="sketch-size-input" style={{left:inputLeft,top:inputTop}} onPointerDown={e=>e.stopPropagation()} onSubmit={commit}><label>{input.name}<input ref={inputRef} autoFocus aria-label={`Sketch ${input.name.toLowerCase()}`} type="number" step="any" value={value} onFocus={e=>e.currentTarget.select()} onChange={e=>setValue(e.target.value)} onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();setEditing(null);setError('');host.current?.focus();}}}/></label><button type="submit" className="button primary small">Set</button><button type="button" className="icon-button" aria-label="Cancel dimension edit" onClick={()=>{setEditing(null);setError('');}}>×</button>{input.gap&&<small>Position once · no edge link</small>}{error&&<span role="alert">{error}</span>}</form>}
    <div className="sketch-mode-hint" role="status"><strong>Sketch</strong><span>{hint}</span><small>Right drag to pan · scroll to zoom</small></div>
  </div>;
}
