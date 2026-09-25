import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {TrackballControls} from 'three/addons/controls/TrackballControls.js';
import {cylinderRims,pickCadFace} from '../src/picking.ts';

function model(){
  // Cylindrical hole wall viewed straight down its axis: almost no triangle
  // area is available for direct ray picking, but the rim must be selectable.
  const geometry=new THREE.CylinderGeometry(6,6,6,64,1,true).toNonIndexed();
  const ids=Array(geometry.getAttribute('position').count/3).fill(15);
  const mesh=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({side:THREE.DoubleSide}));
  const camera=new THREE.OrthographicCamera(-20,20,20,-20,.1,1000);
  camera.position.set(0,100,0);camera.up.set(0,0,1);camera.lookAt(0,0,0);camera.updateMatrixWorld();
  const rims=cylinderRims(geometry,ids,[{id:15,type:'cylinder'}]);
  return {geometry,ids,mesh,camera,rims};
}
test('front-facing hole rim snaps to the cylindrical CAD face within 10 pixels',()=>{
  const {ids,mesh,camera,rims}=model();
  const projected=new THREE.Vector3(6,3,0).project(camera);
  const x=(projected.x+1)*400+4,y=(1-projected.y)*400;
  const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(x/400-1,1-y/400),camera);
  const picked=pickCadFace(ray,mesh,ids,rims,camera,800,800,x,y);
  assert.equal(picked?.id,15);
  assert.ok(Math.abs(Math.hypot(picked.point[0],picked.point[2])-6)<.05);
});
test('empty canvas does not invent a hole measurement',()=>{
  const {ids,mesh,camera,rims}=model(),ray=new THREE.Raycaster();
  ray.setFromCamera(new THREE.Vector2(.95,.95),camera);
  assert.equal(pickCadFace(ray,mesh,ids,rims,camera,800,800,780,20),undefined);
});
test('hole rims behind an opaque face are not selectable',()=>{
  const {geometry,ids,camera}=model();
  const rims=cylinderRims(geometry,ids,[{id:15,type:'cylinder'}]);
  const occluder=new THREE.Mesh(new THREE.BoxGeometry(30,2,30),new THREE.MeshBasicMaterial());occluder.position.y=10;
  const projected=new THREE.Vector3(6,3,0).project(camera),x=(projected.x+1)*400,y=(1-projected.y)*400;
  const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(projected.x,projected.y),camera);
  const picked=pickCadFace(ray,occluder,Array(12).fill(2),rims,camera,800,800,x,y);
  assert.equal(picked?.id,2);
});
test('trackball makes a full vertical revolution, passing upside down',()=>{
  const camera=new THREE.OrthographicCamera(-20,20,20,-20,.1,1000);camera.position.set(0,-100,0);camera.up.set(0,0,1);
  const controls=new TrackballControls(camera);controls.staticMoving=true;controls.rotateSpeed=3;
  const start=camera.position.clone();let inverted=false;
  for(let i=0;i<16;i++){
    controls._movePrev.set(0,0);controls._moveCurr.set(0,Math.PI/24);controls.update();
    if(camera.up.z<-.9)inverted=true;
  }
  assert.ok(inverted,'camera should pass through an upside-down orientation');
  assert.ok(camera.position.distanceTo(start)<1e-7,'full revolution returns to the starting position');
});

test('clicking anywhere inside a hole opening selects its diameter, without hitting the wall',()=>{
  const {ids,mesh,camera,rims}=model();
  for(const [x,y] of [[400,400],[450,420],[365,350]]){
    const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(x/400-1,1-y/400),camera);
    assert.equal(ray.intersectObject(mesh).length,0,'test clicks go through the hole, not the wall');
    assert.equal(pickCadFace(ray,mesh,ids,rims,camera,800,800,x,y)?.id,15);
  }
});
test('a plate covering a hole opening prevents diameter selection through the plate',()=>{
  const {camera,rims}=model();
  const plate=new THREE.Mesh(new THREE.BoxGeometry(30,2,30),new THREE.MeshBasicMaterial());plate.position.y=10;
  const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(0,0),camera);
  assert.equal(pickCadFace(ray,plate,Array(12).fill(2),rims,camera,800,800,400,400)?.id,2);
});

test('actual straight STEP edge snaps independently of face IDs',async()=>{
  const {pickEdge}=await import('../src/edgePicking.ts');
  const camera=new THREE.OrthographicCamera(-20,20,20,-20,.1,1000);camera.position.set(0,0,100);camera.lookAt(0,0,0);camera.updateMatrixWorld();
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(30,30),new THREE.MeshBasicMaterial());
  const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(0,0),camera);
  const edges=[{id:7,type:'line',points:[[0,-15,0],[0,15,0]]}];
  assert.equal(pickEdge(ray,mesh,edges,camera,800,800,405,400)?.id,-7);
  assert.equal(pickEdge(ray,mesh,edges,camera,800,800,430,400),undefined);
});

test('one hole pulls diameter; another feature selects distance; empty space places',async()=>{
  const {dimensionClick}=await import('../src/dimensionPlacement.ts');
  assert.equal(dimensionClick(true,0,false,false),'select');
  assert.equal(dimensionClick(true,1,true,false),'select');
  assert.equal(dimensionClick(false,1,true,false),'place');
  assert.equal(dimensionClick(false,2,true,false),'place');
  assert.equal(dimensionClick(true,2,true,false),'place');
  assert.equal(dimensionClick(false,2,true,true),'none');
  assert.equal(dimensionClick(false,0,false,false),'none');
});
test('pulling a dimension offsets both extension lines without changing their span',async()=>{
  const {offsetDimension}=await import('../src/dimensionPlacement.ts');
  assert.deepEqual(offsetDimension([10,20],[90,20],[50,100]),{a:[10,100],b:[90,100]});
  assert.deepEqual(offsetDimension([10,20],[10,80],[100,50]),{a:[100,20],b:[100,80]});
  const result=offsetDimension([0,0],[30,40],[70,90]);
  assert.ok(Math.abs(Math.hypot(result.b[0]-result.a[0],result.b[1]-result.a[1])-50)<1e-9);
});

test('placed annotation rotates with model instead of rebuilding from a fixed screen label',async()=>{
  const {anchorDimension}=await import('../src/dimensionPlacement.ts');
  const camera=new THREE.OrthographicCamera(-100,100,100,-100,.1,1000);camera.position.set(0,0,100);camera.lookAt(0,0,0);camera.updateMatrixWorld();
  const d={p1:[-50,0,0],p2:[50,0,0]};
  const annotation=anchorDimension(d,{position:[.5,.7],viewport:[800,800],matrix:new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).toArray()});
  assert.ok(Math.abs(annotation.offset[0])<1e-8);assert.ok(Math.abs(annotation.offset[1]+40)<1e-8);
  const transform=new THREE.Matrix4().makeRotationZ(Math.PI/2);
  const offset=new THREE.Vector3(...annotation.offset).applyMatrix4(transform);
  assert.ok(Math.abs(offset.x-40)<1e-8);assert.ok(Math.abs(offset.y)<1e-8);
  const a=new THREE.Vector3(...d.p1).add(new THREE.Vector3(...annotation.offset)).applyMatrix4(transform);
  const b=new THREE.Vector3(...d.p2).add(new THREE.Vector3(...annotation.offset)).applyMatrix4(transform);
  assert.ok(Math.abs(a.distanceTo(b)-100)<1e-8);
});
test('instant analytical measurements distinguish hole pitch from wall clearance',async()=>{
  const {quickMeasure}=await import('../src/quickMeasure.ts');
  const features={'1':{type:'circle',center:[20,20,0],axis:[0,0,1],radius:6,axial:true},'2':{type:'circle',center:[60,20,0],axis:[0,0,1],radius:6,axial:true},'-3':{type:'line',a:[0,0,0],b:[0,80,0],axis:[0,1,0]}};
  assert.equal(quickMeasure(features,[1,2]).value_mm,40);
  assert.equal(quickMeasure(features,[1,2],'clearance').value_mm,28);
  assert.equal(quickMeasure(features,[1,-3]).value_mm,20);
  assert.equal(quickMeasure(features,[-3,1],'clearance').value_mm,14);
  assert.equal(quickMeasure({},[1,2]),null,'older imports retain server fallback');
  assert.throws(()=>quickMeasure({...features,'2':{...features['2'],axis:[1,0,0]}},[1,2]),/not parallel/);
});

test('an isometric placement keeps the text on the dimension line after changing views',async()=>{
  const {anchorDimension}=await import('../src/dimensionPlacement.ts');
  const camera=new THREE.OrthographicCamera(-100,100,100,-100,.1,1000);camera.position.set(150,-150,120);camera.up.set(0,0,1);camera.lookAt(0,0,0);camera.updateMatrixWorld();
  const d={p1:[-45,0,30],p2:[45,0,30]};
  const annotation=anchorDimension(d,{position:[.7,.8],viewport:[800,800],matrix:new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).toArray()});
  const a=new THREE.Vector3(...d.p1).add(new THREE.Vector3(...annotation.offset));
  const direction=new THREE.Vector3(...d.p2).sub(new THREE.Vector3(...d.p1));
  assert.ok(new THREE.Vector3(...annotation.label).sub(a).cross(direction).length()<1e-7);
});
