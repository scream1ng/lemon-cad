import * as THREE from 'three';
import {pickEdge,type CadEdge} from './edgePicking.ts';

export function pickSketchFace(ray:THREE.Raycaster,mesh:THREE.Mesh,ids:number[]){
  const hit=ray.intersectObject(mesh)[0];
  return hit&&hit.faceIndex!=null&&ids[hit.faceIndex]?{id:ids[hit.faceIndex],point:hit.point.toArray()}:undefined;
}

// Normalize signed zero as well as tessellation noise at a closed cylinder seam.
const vertexKey=(p:THREE.Vector3)=>p.toArray().map(v=>Math.round(v*10000)).join(',');

export type Rim = {faceId:number; a:THREE.Vector3; b:THREE.Vector3};
// Cylinder boundary segments let users select a hole at its visible rim, even
// when the thin cylindrical wall occupies less than a pixel in a front view.
export function cylinderRims(geometry:THREE.BufferGeometry, ids:number[], faces:{id:number;type:string;cylinder_group?:number}[]):Rim[] {
  const cylinders=new Map(faces.filter(f=>f.type==='cylinder').map(f=>[f.id,f.cylinder_group||f.id]));
  const position=geometry.getAttribute('position'), edges=new Map<string,{rim:Rim;count:number}>();
  for(let triangle=0;triangle<ids.length;triangle++){
    const faceId=cylinders.get(ids[triangle]);if(!faceId)continue;
    const vertices=[0,1,2].map(k=>new THREE.Vector3().fromBufferAttribute(position,triangle*3+k));
    for(let k=0;k<3;k++){
      const a=vertices[k],b=vertices[(k+1)%3];
      const key=faceId+':'+[vertexKey(a),vertexKey(b)].sort().join('|');
      const edge=edges.get(key);if(edge)edge.count++;else edges.set(key,{rim:{faceId,a,b},count:1});
    }
  }
  return [...edges.values()].filter(e=>e.count===1).map(e=>e.rim);
}

export function pickCadFace(ray:THREE.Raycaster, mesh:THREE.Mesh, ids:number[], rims:Rim[], camera:THREE.Camera, width:number,height:number,x:number,y:number){
  mesh.updateMatrixWorld();camera.updateMatrixWorld();
  const direct=ray.intersectObject(mesh)[0];
  const opening=openingAt(ray,direct,rims,camera,width,height,x,y);
  let best:{id:number;point:number[]}|undefined;
  let distance=10, depth=Infinity;
  const visibilityRay=new THREE.Raycaster();
  for(const rim of rims){
    const a=rim.a.clone().project(camera),b=rim.b.clone().project(camera);
    if(a.z < -1 || a.z > 1 || b.z < -1 || b.z > 1)continue;
    const ax=(a.x+1)*width/2,ay=(1-a.y)*height/2,bx=(b.x+1)*width/2,by=(1-b.y)*height/2;
    const dx=bx-ax,dy=by-ay;
    const t=THREE.MathUtils.clamp(((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy||1),0,1);
    const d=Math.hypot(x-ax-t*dx,y-ay-t*dy);if(d>distance)continue;
    const point=rim.a.clone().lerp(rim.b,t),projected=point.clone().project(camera);
    visibilityRay.setFromCamera(new THREE.Vector2(projected.x,projected.y),camera);
    const obstruction=visibilityRay.intersectObject(mesh)[0];
    const rimDepth=point.distanceTo(visibilityRay.ray.origin);
    if(obstruction&&obstruction.distance<rimDepth-0.05)continue;
    if(Math.abs(d-distance)<0.001&&rimDepth>=depth)continue;
    distance=d;depth=rimDepth;best={id:rim.faceId,point:point.toArray()};
  }
  return best || opening || (direct?{id:ids[direct.faceIndex||0]||0,point:direct.point.toArray()}:undefined);
}

export function pickCadEntity(ray:THREE.Raycaster,mesh:THREE.Mesh,ids:number[],rims:Rim[],edges:CadEdge[],camera:THREE.Camera,width:number,height:number,x:number,y:number,preferEdge=false){
  const face=pickCadFace(ray,mesh,ids,rims,camera,width,height,x,y);
  if(preferEdge)return pickEdge(ray,mesh,edges,camera,width,height,x,y)||face;
  // A straight edge directly under the cursor beats the faces on either side of it.
  return pickEdge(ray,mesh,edges,camera,width,height,x,y,4,['line'])||face||pickEdge(ray,mesh,edges,camera,width,height,x,y);
}

type RimLoop={faceId:number;points:THREE.Vector3[];plane:THREE.Plane};
const loopCache=new WeakMap<Rim[],RimLoop[]>();
function rimLoops(rims:Rim[]){
  const cached=loopCache.get(rims);if(cached)return cached;
  const loops:RimLoop[]=[],unused=new Set(rims);
  const key=vertexKey;
  const adjacency=new Map<string,Rim[]>();
  for(const edge of rims)for(const point of [edge.a,edge.b]){
    const k=edge.faceId+':'+key(point);adjacency.set(k,[...(adjacency.get(k)||[]),edge]);
  }
  while(unused.size){
    const first=unused.values().next().value!;unused.delete(first);
    const points=[first.a,first.b];let current=first.b;
    while(key(current)!==key(first.a)){
      const next=(adjacency.get(first.faceId+':'+key(current))||[]).find(e=>unused.has(e));
      if(!next)break;unused.delete(next);current=key(next.a)===key(current)?next.b:next.a;points.push(current);
    }
    if(points.length<4||key(current)!==key(first.a))continue;
    points.pop();
    const plane=new THREE.Plane().setFromCoplanarPoints(points[0],points[Math.floor(points.length/3)],points[Math.floor(points.length*2/3)]);
    if(plane.normal.lengthSq()>.9&&points.every(p=>Math.abs(plane.distanceToPoint(p))<.02))loops.push({faceId:first.faceId,points,plane});
  }
  loopCache.set(rims,loops);return loops;
}

function openingAt(ray:THREE.Raycaster,direct:THREE.Intersection|undefined,rims:Rim[],camera:THREE.Camera,width:number,height:number,x:number,y:number){
  let closest=Infinity,result:{id:number;point:number[]}|undefined;
  for(const loop of rimLoops(rims)){
    const projected=loop.points.map(p=>p.clone().project(camera));
    if(projected.some(p=>p.z < -1||p.z > 1))continue;
    const polygon=projected.map(p=>[(p.x+1)*width/2,(1-p.y)*height/2]);
    let inside=false;
    for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){
      const [ax,ay]=polygon[i],[bx,by]=polygon[j];
      if((ay>y)!==(by>y)&&x<(bx-ax)*(y-ay)/(by-ay)+ax)inside=!inside;
    }
    if(!inside)continue;
    const point=ray.ray.intersectPlane(loop.plane,new THREE.Vector3());if(!point)continue;
    const distance=point.distanceTo(ray.ray.origin);
    if(distance>=closest||(direct&&direct.distance<distance-.05))continue;
    closest=distance;result={id:loop.faceId,point:point.toArray()};
  }
  return result;
}
