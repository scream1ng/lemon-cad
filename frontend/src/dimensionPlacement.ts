export type Point2 = [number, number];
export function dimensionClick(hit:boolean, selected:number, pending:boolean, dragged:boolean){
  if(dragged)return 'none';
  if(pending&&(!hit||selected===2))return 'place';
  return hit?'select':'none';
}
export function offsetDimension(a:Point2,b:Point2,label:Point2){
  const dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
  const normal:Point2=length>1e-6?[-dy/length,dx/length]:[0,1];
  const offset=(label[0]-a[0])*normal[0]+(label[1]-a[1])*normal[1];
  return {a:[a[0]+normal[0]*offset,a[1]+normal[1]*offset] as Point2,b:[b[0]+normal[0]*offset,b[1]+normal[1]*offset] as Point2};
}

import * as THREE from 'three';
export type Placement={position:number[];matrix:number[];viewport:number[]};
export type Annotation={offset:number[];label:number[]};
export function anchorDimension(d:{p1:number[];p2:number[];type?:string},placement:Placement):Annotation{
  const matrix=new THREE.Matrix4().fromArray(placement.matrix),inverse=matrix.clone().invert();
  const a=new THREE.Vector3(...d.p1).applyMatrix4(matrix),b=new THREE.Vector3(...d.p2).applyMatrix4(matrix);
  const [w,h]=placement.viewport;
  const screen=(v:THREE.Vector3):Point2=>[(v.x+1)*w/2,(1-v.y)*h/2];
  const label:Point2=[placement.position[0]*w,placement.position[1]*h];
  const offset=offsetDimension(screen(a),screen(b),label);
  const world=(p:Point2,z:number)=>new THREE.Vector3(p[0]/w*2-1,1-p[1]/h*2,z).applyMatrix4(inverse);
  const displacement=world(offset.a,a.z).sub(new THREE.Vector3(...d.p1));
  const sa=screen(a),sb=screen(b),dx=sb[0]-sa[0],dy=sb[1]-sa[1];
  const t=((label[0]-sa[0])*dx+(label[1]-sa[1])*dy)/(dx*dx+dy*dy||1);
  const labelWorld=['dia','rad','angle'].includes(d.type||'')?world(label,(a.z+b.z)/2):new THREE.Vector3(...d.p1).lerp(new THREE.Vector3(...d.p2),t).add(displacement);
  return {offset:displacement.toArray(),label:labelWorld.toArray()};
}
