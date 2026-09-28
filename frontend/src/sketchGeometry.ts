import * as THREE from 'three';
import type {Sketch,SketchFrame} from './cadDocument';
import type {CadEdge} from './edgePicking';
export type UV=[number,number];
export type SketchTool='select'|'rectangle'|'circle'|'line'|'dimension';
export type SketchView={matrix:number[];width:number;height:number};
export function sketchFrame(s:Sketch):SketchFrame{
  if(s.frame)return s.frame;
  const o=s.offset||0;
  return s.plane==='XZ'?{origin:[0,o,0],u:[1,0,0],v:[0,0,1]}:s.plane==='YZ'?{origin:[o,0,0],u:[0,1,0],v:[0,0,1]}:{origin:[0,0,o],u:[1,0,0],v:[0,1,0]};
}
export function worldPoint(frame:SketchFrame,p:UV){return frame.origin.map((n,k)=>n+p[0]*frame.u[k]+p[1]*frame.v[k]);}
export function screenPoint(frame:SketchFrame,p:UV,view:SketchView):UV{
  const v=new THREE.Vector3(...worldPoint(frame,p)).applyMatrix4(new THREE.Matrix4().fromArray(view.matrix));
  return [(v.x+1)*view.width/2,(1-v.y)*view.height/2];
}
export function planePoint(frame:SketchFrame,p:UV,view:SketchView):UV|null{
  const inverse=new THREE.Matrix4().fromArray(view.matrix).invert(),x=p[0]/view.width*2-1,y=1-p[1]/view.height*2;
  const a=new THREE.Vector3(x,y,-1).applyMatrix4(inverse),b=new THREE.Vector3(x,y,1).applyMatrix4(inverse);
  const u=new THREE.Vector3(...frame.u),v=new THREE.Vector3(...frame.v),origin=new THREE.Vector3(...frame.origin),normal=u.clone().cross(v);
  const hit=new THREE.Ray(a,b.sub(a).normalize()).intersectPlane(new THREE.Plane().setFromNormalAndCoplanarPoint(normal,origin),new THREE.Vector3());
  if(!hit)return null;hit.sub(origin);const point:UV=[hit.dot(u),hit.dot(v)];
  return point.every(n=>Number.isFinite(n)&&Math.abs(n)<=2000)?point:null;
}
export function drawnProfile(tool:SketchTool,a:UV,b:UV):Partial<Sketch>|null{
  if(tool==='rectangle'){
    const width=Number(Math.abs(b[0]-a[0]).toFixed(3)),height=Number(Math.abs(b[1]-a[1]).toFixed(3));
    return width>.01&&height>.01&&width<=2000&&height<=2000?{profile:'rectangle',x:Math.min(a[0],b[0]),y:Math.min(a[1],b[1]),width,height,closed:true}:null;
  }
  const diameter=2*Math.hypot(b[0]-a[0],b[1]-a[1]);
  return tool==='circle'&&diameter>.01&&diameter<=2000?{profile:'circle',x:a[0],y:a[1],diameter,closed:true}:null;
}
export type RectangleSide='left'|'right'|'bottom'|'top';
export type PlaneEdge={id:number;a:UV;b:UV;axis:0|1};
export function planeEdge(edge:CadEdge,frame:SketchFrame):PlaneEdge|null{
  if(edge.type!=='line'||edge.points.length<2)return null;
  const u=new THREE.Vector3(...frame.u),v=new THREE.Vector3(...frame.v),normal=u.clone().cross(v);
  const points=edge.points.map(p=>new THREE.Vector3(...p).sub(new THREE.Vector3(...frame.origin)));
  if(points.some(p=>!Number.isFinite(p.length())||Math.abs(p.dot(normal))>.001))return null;
  const a:UV=[points[0].dot(u),points[0].dot(v)],b:UV=[points.at(-1)!.dot(u),points.at(-1)!.dot(v)];
  const dx=Math.abs(a[0]-b[0]),dy=Math.abs(a[1]-b[1]);
  if(Math.max(dx,dy)<1e-6||Math.min(dx,dy)>.002)return null;
  return {id:edge.id,a,b,axis:dx<dy?0:1};
}
export function rectangleSide(s:Sketch,side:RectangleSide):[UV,UV]{
  const x=s.x??0,y=s.y??0;
  if(side==='left'||side==='right'){const u=x+(side==='right'?s.width:0);return [[u,y],[u,y+s.height]];}
  const v=y+(side==='top'?s.height:0);return [[x,v],[x+s.width,v]];
}
export function edgeGap(s:Sketch,side:RectangleSide,edge:PlaneEdge){
  const axis=side==='left'||side==='right'?0:1;
  return axis===edge.axis?rectangleSide(s,side)[0][axis]-edge.a[axis]:null;
}
export function positionFromEdge(s:Sketch,side:RectangleSide,edge:PlaneEdge,distance:number):Partial<Sketch>|null{
  const gap=edgeGap(s,side,edge);
  if(gap===null||!Number.isFinite(distance)||distance<0||distance>2000)return null;
  const sign=Math.abs(gap)<1e-6?(side==='right'||side==='top'?-1:1):Math.sign(gap);
  const key=edge.axis===0?'x':'y',value=Number(((s[key]??0)+sign*distance-gap).toFixed(6));
  return Number.isFinite(value)&&Math.abs(value)<=2000?{[key]:value}:null;
}
export function profilePoints(s:Sketch):UV[]{
  const x=s.x||0,y=s.y||0;
  if(s.profile==='polygon')return (s.points||[]).map(p=>[p[0]+x,p[1]+y]);
  if(s.profile==='circle')return Array.from({length:96},(_,i)=>[x+Math.cos(i*Math.PI/48)*s.diameter/2,y+Math.sin(i*Math.PI/48)*s.diameter/2]);
  return [[x,y],[x+s.width,y],[x+s.width,y+s.height],[x,y+s.height]];
}
export function validProfile(s:Sketch){
  if(![s.x??0,s.y??0,s.width,s.height,s.diameter].every(Number.isFinite))return false;
  if(s.profile==='rectangle')return s.width>.01&&s.height>.01&&s.width<=2000&&s.height<=2000;
  if(s.profile==='circle')return s.diameter>.01&&s.diameter<=2000;
  const pts=s.points||[];
  return !!s.closed&&pts.length>=3&&pts.flat().every(n=>Number.isFinite(n)&&Math.abs(n)<=2000);
}
