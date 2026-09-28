import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {viewportFrustum} from '../src/viewportFit.ts';

test('fit contains the complete solid at mobile, tablet, desktop and ultrawide sizes',()=>{
 for(const [width,height] of [[300,550],[390,700],[768,650],[1280,720],[1920,1080],[3440,1440]]){
  for(const size of [[80,50,10],[10,20,180],[1000,5,12]]){
   const extent=Math.hypot(...size),f=viewportFrustum(extent,width,height);
   for(const direction of [[1,-1,.8],[0,-1,0],[0,0,1],[1,0,0]]){
    const camera=new THREE.OrthographicCamera(f.left,f.right,f.top,f.bottom,.01,extent*1000);
    camera.up.set(0,direction[2]===1?1:0,direction[2]===1?0:1);
    camera.position.fromArray(direction).normalize().multiplyScalar(extent*3);camera.lookAt(0,0,0);camera.updateMatrixWorld(true);
    for(const x of [-1,1])for(const y of [-1,1])for(const z of [-1,1]){
     const projected=new THREE.Vector3(x*size[0]/2,y*size[1]/2,z*size[2]/2).project(camera);
     assert.ok(Math.abs(projected.x)<1&&Math.abs(projected.y)<1,`clipped ${size} at ${width}×${height}`);
    }
   }
  }
 }
});

test('saved annotation labels stay visible when a desktop view becomes portrait',async()=>{
 const {visibleLabelCenter}=await import('../src/viewportFit.ts');
 for(const ratio of [1,2])for(const [x,y] of [[980,350],[-200,1200],[180,250]]){
  const width=366*ratio,height=500*ratio,labelWidth=110*ratio;
  const [cx,cy]=visibleLabelCenter([x*ratio,y*ratio],width,height,labelWidth,ratio);
  assert.ok(cx-labelWidth/2>=0&&cx+labelWidth/2<=width);
  assert.ok(cy-17*ratio>=0&&cy+7*ratio<=height);
 }
});
