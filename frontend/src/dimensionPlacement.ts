export type Point2 = [number, number];
export function visiblePlanarDimension(a:Point2,b:Point2,scale=1){return Math.hypot(b[0]-a[0],b[1]-a[1])>=6*scale;}
export function dimensionClick(hit:boolean, selected:number, pending:boolean, dragged:boolean){
  if(dragged)return 'none';
  if(pending&&!hit)return 'place';
  return hit?'select':'none';
}
export function cursorLabelPosition(pointer:Point2,width:number,height:number,labelWidth:number,scale=1):Point2{
  const x=pointer[0]*width,y=pointer[1]*height,margin=12*scale;
  const center=Math.max(margin+labelWidth/2,Math.min(width-margin-labelWidth/2,x));
  const topInset=(width/scale<600?120:72)*scale,above=y-20*scale;
  const baseline=above-17*scale>=topInset?above:Math.max(y+55*scale,topInset+17*scale);
  return [center,Math.max(24*scale,Math.min(height-12*scale,baseline))];
}
export function offsetDimension(a:Point2,b:Point2,label:Point2){
  const dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
  const normal:Point2=length>1e-6?[-dy/length,dx/length]:[0,1];
  const offset=(label[0]-a[0])*normal[0]+(label[1]-a[1])*normal[1];
  return {a:[a[0]+normal[0]*offset,a[1]+normal[1]*offset] as Point2,b:[b[0]+normal[0]*offset,b[1]+normal[1]*offset] as Point2};
}
// Up to 2 decimals (3 in inches), trailing zeros dropped: 40, 40.5, Ø6.1, R3, 90°.
export function formatDimension(value_mm:number,type:string|undefined,unit:string){
  const inch=unit==='in'&&type!=='angle',value=Number((value_mm/(inch?25.4:1)).toFixed(inch?3:2));
  return `${type==='dia'?'Ø':type==='rad'?'R':''}${value||0}${type==='angle'?'°':''}`;
}
export function projectOntoLine(p:Point2,a:Point2,b:Point2):Point2{
  const dx=b[0]-a[0],dy=b[1]-a[1],t=((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy||1);
  return [a[0]+dx*t,a[1]+dy*t];
}
// Rim point (screen) whose direction from the centre best faces the label.
export function calloutTip(center:Point2,label:Point2,rim:Point2[]):Point2{
  const lx=label[0]-center[0],ly=label[1]-center[1];let best=rim[0],score=-Infinity;
  for(const p of rim){const dx=p[0]-center[0],dy=p[1]-center[1],s=(dx*lx+dy*ly)/(Math.hypot(dx,dy)||1);if(s>score){score=s;best=p;}}
  return best;
}
export type LabelBox={x:number;y:number;width:number;height:number;dir:Point2};
// Slide each later label along its own direction until it clears earlier ones. Returns the shifts.
export function separateLabels(boxes:LabelBox[],step=4,limit=60):Point2[]{
  const placed:LabelBox[]=[];
  return boxes.map(box=>{
    let shift:Point2=[0,0];
    const hits=(s:Point2)=>placed.some(o=>box.x+s[0]<o.x+o.width&&o.x<box.x+s[0]+box.width&&box.y+s[1]<o.y+o.height&&o.y<box.y+s[1]+box.height);
    for(let i=1;i<=limit&&hits(shift);i++)shift=[box.dir[0]*step*i,box.dir[1]*step*i];
    placed.push({...box,x:box.x+shift[0],y:box.y+shift[1]});
    return shift;
  });
}

import * as THREE from 'three';
export type Placement={position:number[];matrix:number[];viewport:number[]};
export type Annotation={offset:number[];label:number[]};
export function anchorDimension(d:{p1:number[];p2:number[];type?:string;reference_plane?:{origin:number[];normal:number[]}},placement:Placement):Annotation{
  const matrix=new THREE.Matrix4().fromArray(placement.matrix),inverse=matrix.clone().invert();
  const a=new THREE.Vector3(...d.p1).applyMatrix4(matrix),b=new THREE.Vector3(...d.p2).applyMatrix4(matrix);
  const [w,h]=placement.viewport;
  const screen=(v:THREE.Vector3):Point2=>[(v.x+1)*w/2,(1-v.y)*h/2];
  const label:Point2=[placement.position[0]*w,placement.position[1]*h];
  const offset=offsetDimension(screen(a),screen(b),label);
  const world=(p:Point2,z:number)=>new THREE.Vector3(p[0]/w*2-1,1-p[1]/h*2,z).applyMatrix4(inverse);
  let displacement=world(offset.a,a.z).sub(new THREE.Vector3(...d.p1));
  const sa=screen(a),sb=screen(b),dx=sb[0]-sa[0],dy=sb[1]-sa[1];
  if(d.reference_plane&&!['dia','rad','angle'].includes(d.type||'')){
    const origin=new THREE.Vector3(...d.p1);
    const inPlane=new THREE.Vector3(...d.reference_plane.normal).cross(new THREE.Vector3(...d.p2).sub(origin)).normalize();
    const projected=screen(origin.clone().add(inPlane).applyMatrix4(matrix));
    const ux=projected[0]-sa[0],uy=projected[1]-sa[1],det=dx*uy-dy*ux;
    if(inPlane.lengthSq()>.9&&Math.abs(det)>1e-3){
      const distance=(dx*(label[1]-sa[1])-dy*(label[0]-sa[0]))/det;
      displacement=inPlane.multiplyScalar(distance);
    }
  }
  const t=((label[0]-sa[0])*dx+(label[1]-sa[1])*dy)/(dx*dx+dy*dy||1);
  const labelWorld=d.reference_plane||['dia','rad','angle'].includes(d.type||'')?world(label,(a.z+b.z)/2):new THREE.Vector3(...d.p1).lerp(new THREE.Vector3(...d.p2),t).add(displacement);
  return {offset:displacement.toArray(),label:labelWorld.toArray()};
}
