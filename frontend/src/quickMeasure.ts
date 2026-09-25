import type {Dimension} from './api';
type Measurement=Omit<Dimension,'id'|'label'> & {label?:string};
export type MeasureFeature={type:string;center?:number[];axis?:number[];radius?:number;axial?:boolean;a?:number[];b?:number[];single?:Measurement};
const dot=(a:number[],b:number[])=>a.reduce((s,v,i)=>s+v*b[i],0);
const sub=(a:number[],b:number[])=>a.map((v,i)=>v-b[i]);
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
    if(Math.abs(dot(n,b.axis!))>1e-6)throw new Error('Select an edge perpendicular to the hole axis.');
    const shift=dot(sub(b.a!,c),n);
    if(!a.axial&&Math.abs(shift)>1e-5)throw new Error('Select a hole rim and edge in the same plane.');
    c=c.map((v,i)=>v+shift*n[i]);
    const t=dot(sub(c,b.a!),b.axis!);target=b.a!.map((v,i)=>v+t*b.axis![i]);radii=r;
    label='Centre to edge'+(t< -1e-5||t>Math.hypot(...sub(b.b!,b.a!))+1e-5?' (extended)':'');
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
  return {label,p1,p2,value_mm:Math.hypot(...sub(p1,p2)),method:label.toLowerCase(),entities:refs,relation,alternatives:['centre','clearance'],basis:'STEP geometry · nominal'};
}
