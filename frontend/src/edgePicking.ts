import * as THREE from 'three';
export type CadEdge={id:number;type:string;points:number[][]};
export function pickEdge(ray:THREE.Raycaster,mesh:THREE.Mesh,edges:CadEdge[],camera:THREE.Camera,width:number,height:number,x:number,y:number,limit=9,types=['line','circle']){
  let best:{id:number;point:number[];distance:number}|undefined;
  for(const edge of edges){
    if(!types.includes(edge.type))continue;
    for(let i=1;i<edge.points.length;i++){
      const a=new THREE.Vector3(...edge.points[i-1]),b=new THREE.Vector3(...edge.points[i]);
      const pa=a.clone().project(camera),pb=b.clone().project(camera);
      if(pa.z < -1||pa.z > 1||pb.z < -1||pb.z > 1)continue;
      const ax=(pa.x+1)*width/2,ay=(1-pa.y)*height/2,bx=(pb.x+1)*width/2,by=(1-pb.y)*height/2;
      const dx=bx-ax,dy=by-ay,t=Math.max(0,Math.min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy||1)));
      const distance=Math.hypot(x-ax-t*dx,y-ay-t*dy);if(distance>limit||best&&distance>=best.distance)continue;
      const p=a.lerp(b,t), projected=p.clone().project(camera), probe=new THREE.Raycaster();
      probe.setFromCamera(new THREE.Vector2(projected.x,projected.y),camera);
      const hit=probe.intersectObject(mesh)[0];
      if(hit&&hit.distance+Math.max(.03,p.distanceTo(probe.ray.origin)*1e-5)<p.distanceTo(probe.ray.origin))continue;
      best={id:-edge.id,point:p.toArray(),distance};
    }
  }
  return best;
}
