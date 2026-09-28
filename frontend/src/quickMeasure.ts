import type {Dimension} from './api';
type Measurement=Omit<Dimension,'id'|'label'> & {label?:string};
export type MeasureFeature={type:string;center?:number[];axis?:number[];radius?:number;axial?:boolean;a?:number[];b?:number[];single?:Measurement};
const dot=(a:number[],b:number[])=>a.reduce((s,v,i)=>s+v*b[i],0);
const sub=(a:number[],b:number[])=>a.map((v,i)=>v-b[i]);
export function defaultMeasureRelation(features:Record<string,MeasureFeature>,faces:{id:number;type:string}[],selection:number[]){
  if(selection.length!==2)return 'centre';
  const circle=selection.find(id=>features[String(id)]?.type==='circle');
  if(circle===undefined)return 'centre';
  const other=selection.find(id=>id!==circle)!;
  const cylinder=circle>0&&faces.some(f=>f.id===circle&&f.type==='cylinder');
  return features[String(other)]?.type==='line'||cylinder&&other>0&&faces.some(f=>f.id===other&&f.type==='plane')?'clearance':'centre';
}
export function withReferencePlane(d:Dimension,features:Record<string,MeasureFeature>):Dimension{
  if(d.reference_plane||d.entities?.length!==2||['dia','rad','angle'].includes(d.type||''))return d;
  const circle=d.entities.map(e=>features[String(e.kind==='edge'?-e.id:e.id)]).find(f=>f?.type==='circle'&&f.axis);
  if(!circle)return d;
  const span=sub(d.p2,d.p1),length=Math.hypot(...span);
  return length>1e-6&&Math.abs(dot(span,circle.axis!))<length*1e-5?{...d,reference_plane:{origin:d.p1,normal:circle.axis!}}:d;
}
export function quickMeasure(features:Record<string,MeasureFeature>,selection:number[],relation='centre'):Measurement|null{
  const refs=selection.map(id=>({kind:id<0?'edge':'face',id:Math.abs(id)}));
  const found=selection.map(id=>features[String(id)]);
  if(found.some(f=>!f))return null;
  if(found.length===1)return found[0].single?{...found[0].single,entities:refs}:null;
  if(found[1].type==='circle'&&found[0].type!=='circle')found.reverse();
  const [a,b]=found;
  if(a.type!=='circle'||!['circle','line'].includes(b.type))return null;
  let c=a.center!.slice();const n=a.axis!,r=a.radius!;let target:number[],radii:number,label:string;
  if(b.type==='line'){
    const edge=sub(b.b!,b.a!),length=Math.hypot(...edge);if(length<=1e-6)throw new Error('Select a nonzero edge.');
    const axis=edge.map(v=>v/length);
    if(Math.abs(dot(n,axis))>1e-6)throw new Error('Select an edge perpendicular to the hole axis.');
    const shift=dot(sub(b.a!,c),n);
    if(!a.axial&&Math.abs(shift)>1e-5)throw new Error('Select a hole rim and edge in the same plane.');
    c=c.map((v,i)=>v+shift*n[i]);
    const t=Math.max(0,Math.min(length,dot(sub(c,b.a!),axis)));target=b.a!.map((v,i)=>v+t*axis[i]);radii=r;
    label='Centre to edge';
  }else{
    if(Math.abs(Math.abs(dot(n,b.axis!))-1)>1e-6)throw new Error('Hole axes are not parallel. Select coplanar circular rims.');
    const shift=dot(sub(b.center!,c),n);
    if(!a.axial&&!b.axial&&Math.abs(shift)>1e-5)throw new Error('Select two hole rims in the same plane.');
    c=c.map((v,i)=>v+shift*n[i]);target=b.center!.slice();radii=r+b.radius!;label='Centre to centre';
  }
  const distance=Math.hypot(...sub(c,target));let p1=c.slice(),p2=target.slice();
  if(relation==='clearance'){
    if(distance<radii+1e-6)throw new Error('These features overlap or touch; a positive wall clearance is not available.');
    const direction=sub(target,c).map(v=>v/distance);p1=c.map((v,i)=>v+direction[i]*r);
    if(b.type==='circle')p2=target.map((v,i)=>v-direction[i]*b.radius!);
    label='Nearest wall clearance';
  }
  return {label,p1,p2,value_mm:Math.hypot(...sub(p1,p2)),method:label.toLowerCase(),entities:refs,relation,alternatives:['centre','clearance'],reference_plane:{origin:c,normal:n},basis:'STEP geometry · nominal'};
}
