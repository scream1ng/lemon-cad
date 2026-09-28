import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {TrackballControls} from 'three/addons/controls/TrackballControls.js';
import {cylinderRims,pickCadFace,pickCadEntity} from '../src/picking.ts';

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
test('an opening split into two cylindrical faces remains selectable at its centre',()=>{
  const halves=[0,Math.PI].map(start=>new THREE.CylinderGeometry(6,6,6,32,1,true,start,Math.PI).toNonIndexed());
  const positions=halves.flatMap(g=>Array.from(g.getAttribute('position').array));
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  const first=halves[0].getAttribute('position').count/3;
  const ids=Array(first).fill(15).concat(Array(first).fill(16));
  const faces=[{id:15,type:'cylinder',cylinder_group:15},{id:16,type:'cylinder',cylinder_group:15}];
  const mesh=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({side:THREE.DoubleSide}));
  const camera=new THREE.OrthographicCamera(-20,20,20,-20,.1,1000);
  camera.position.set(0,100,0);camera.up.set(0,0,1);camera.lookAt(0,0,0);camera.updateMatrixWorld();
  const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(0,0),camera);
  assert.equal(pickCadFace(ray,mesh,ids,cylinderRims(geometry,ids,faces),camera,800,800,400,400)?.id,15);
});
test('a circular rim near a small hole picks the complete hole feature',()=>{
  const {geometry,ids,mesh,rims}=model();
  const camera=new THREE.OrthographicCamera(-300,300,300,-300,.1,1000);
  camera.position.set(0,100,0);camera.up.set(0,0,1);camera.lookAt(0,0,0);camera.updateMatrixWorld();
  const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(0,0),camera);
  const circle={id:7,type:'circle',points:Array.from({length:65},(_,i)=>[6*Math.cos(i*Math.PI/32),3,6*Math.sin(i*Math.PI/32)])};
  assert.equal(pickCadEntity(ray,mesh,ids,rims,[circle],camera,800,800,400,400)?.id,15);
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
test('edge under the cursor wins; visible surface wins beside an edge; Option picks the edge explicitly',()=>{
  const camera=new THREE.OrthographicCamera(-20,20,20,-20,.1,1000);camera.position.set(0,0,100);camera.lookAt(0,0,0);camera.updateMatrixWorld();
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(30,30),new THREE.MeshBasicMaterial());
  const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(0,0),camera);
  const edges=[{id:7,type:'line',points:[[0,-15,0],[0,15,0]]}];
  assert.equal(pickCadEntity(ray,mesh,[3,3],[],edges,camera,800,800,400,400)?.id,-7);
  const beside=new THREE.Raycaster();beside.setFromCamera(new THREE.Vector2(.02,0),camera);
  const args=[beside,mesh,[3,3],[],edges,camera,800,800,408,400];
  assert.equal(pickCadEntity(...args)?.id,3);
  assert.equal(pickCadEntity(...args,true)?.id,-7);
});

test('one hole pulls diameter; another feature selects distance; empty space places',async()=>{
  const {dimensionClick}=await import('../src/dimensionPlacement.ts');
  assert.equal(dimensionClick(true,0,false,false),'select');
  assert.equal(dimensionClick(true,1,true,false),'select');
  assert.equal(dimensionClick(false,1,true,false),'place');
  assert.equal(dimensionClick(false,2,true,false),'place');
  assert.equal(dimensionClick(true,2,true,false),'select');
  assert.equal(dimensionClick(false,2,true,true),'none');
  assert.equal(dimensionClick(false,0,false,false),'none');
});
test('a cursor-following dimension label sits directly above the pointer when space allows',async()=>{
  const {cursorLabelPosition}=await import('../src/dimensionPlacement.ts');
  assert.equal(cursorLabelPosition([.5,.5],800,600,120)[0],400);
  assert.equal(cursorLabelPosition([.25,.5],800,600,120)[0],200);
  for(const pointer of [[.5,.5],[.98,.5],[.5,.03],[.5,.97]]){
    const [cx,baseline]=cursorLabelPosition(pointer,800,600,120);
    const px=pointer[0]*800,py=pointer[1]*600;
    assert.ok(cx-60>=12&&cx+60<=788);
    assert.ok(baseline-17>=12&&baseline+7<=588);
    assert.ok(py<baseline-17-12||py>baseline+7+12,'label has a visible gap from the pointer');
  }
  assert.ok(cursorLabelPosition([.4,.38],358,420,90)[1]-17>=120,'mobile label clears the view controls');
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
  const {quickMeasure,withReferencePlane}=await import('../src/quickMeasure.ts');
  const features={'1':{type:'circle',center:[20,20,0],axis:[0,0,1],radius:6,axial:true},'2':{type:'circle',center:[60,20,0],axis:[0,0,1],radius:6,axial:true},'-3':{type:'line',a:[0,0,0],b:[0,80,0],axis:[0,1,0]}};
  assert.equal(quickMeasure(features,[1,2]).value_mm,40);
  assert.equal(quickMeasure(features,[1,2],'clearance').value_mm,28);
  assert.equal(quickMeasure(features,[1,-3]).value_mm,20);
  assert.deepEqual(quickMeasure(features,[1,-3]).reference_plane,{origin:[20,20,0],normal:[0,0,1]});
  const saved={...quickMeasure(features,[1,-3]),reference_plane:undefined};
  assert.deepEqual(withReferencePlane(saved,features).reference_plane,{origin:[20,20,0],normal:[0,0,1]},'older saved dimensions align when moved');
  assert.equal(withReferencePlane({...saved,p2:[20,20,10]},features).reference_plane,undefined,'axial measurements cannot lie in the hole face');
  assert.equal(quickMeasure(features,[-3,1],'clearance').value_mm,14);
  const endpoint=quickMeasure({...features,'-3':{...features['-3'],b:[0,10,0]}},[1,-3],'clearance');
  assert.deepEqual(endpoint.p2,[0,10,0],'dimension ends on the finite edge');
  assert.ok(Math.abs(endpoint.value_mm-(Math.hypot(20,10)-6))<1e-9);
  assert.equal(quickMeasure({},[1,2]),null,'older imports retain server fallback');
  const edges={'-4':{type:'line',a:[0,0,0],b:[160,0,0]},'-5':{type:'line',a:[0,60,5],b:[160,60,5]},'-6':{type:'line',a:[0,0,0],b:[0,60,0]}};
  assert.ok(Math.abs(quickMeasure(edges,[-4,-5]).value_mm-Math.hypot(60,5))<1e-9,'parallel edges measure instantly');
  assert.equal(quickMeasure(edges,[-4,-6]),null,'non-parallel edges use the server');
  const front=quickMeasure(edges,[-4,-5],'centre',[0,1,0]);
  assert.equal(front.value_mm,5,'edges at different depths measure the gap seen in the pick view');
  assert.deepEqual(front.reference_plane,{origin:[80,0,0],normal:[0,1,0]});
  assert.throws(()=>quickMeasure(edges,[-4,-5],'centre',[0,60,5]),/line up in this view/);
  assert.throws(()=>quickMeasure({...features,'2':{...features['2'],axis:[1,0,0]}},[1,2]),/not parallel/);
});
test('hole-to-surface defaults to wall clearance; hole-to-edge to centre',async()=>{
  const {defaultMeasureRelation}=await import('../src/quickMeasure.ts');
  const features={'15':{type:'circle'},'-7':{type:'circle'},'-8':{type:'line'},'16':{type:'circle'}};
  const faces=[{id:10,type:'plane'},{id:15,type:'cylinder'},{id:16,type:'cylinder'}];
  assert.equal(defaultMeasureRelation(features,faces,[15,10]),'clearance');
  assert.equal(defaultMeasureRelation(features,faces,[15,-8]),'centre');
  assert.equal(defaultMeasureRelation(features,faces,[15,16]),'centre');
  assert.equal(defaultMeasureRelation(features,faces,[-7,10]),'centre');
  assert.equal(defaultMeasureRelation(features,faces,[10,-8]),'centre');
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
test('hole-to-edge dimension offsets within its reference face',async()=>{
  const {anchorDimension}=await import('../src/dimensionPlacement.ts');
  const camera=new THREE.OrthographicCamera(-100,100,100,-100,.1,1000);
  camera.position.set(120,-120,90);camera.up.set(0,0,1);camera.lookAt(0,0,0);camera.updateMatrixWorld();
  const matrix=new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).toArray();
  const d={p1:[0,0,0],p2:[40,0,0],reference_plane:{origin:[0,0,0],normal:[0,0,1]}};
  const annotation=anchorDimension(d,{position:[.62,.7],viewport:[800,800],matrix});
  assert.ok(Math.abs(annotation.offset[0])<1e-7,'offset is perpendicular to the measured span');
  assert.ok(Math.abs(annotation.offset[2])<1e-7,'offset stays in the flange plane');
  assert.ok(Math.hypot(...annotation.offset)>1,'offset is visible');
  const label=new THREE.Vector3(...annotation.label).applyMatrix4(new THREE.Matrix4().fromArray(matrix));
  assert.ok(Math.abs(label.x-(.62*2-1))<1e-7&&Math.abs(label.y-(1-.7*2))<1e-7,'placed label stays where previewed');
});
test('surface dimensions hide when their measured span is edge-on',async()=>{
  const {visiblePlanarDimension}=await import('../src/dimensionPlacement.ts');
  assert.equal(visiblePlanarDimension([100,100],[102,101]),false);
  assert.equal(visiblePlanarDimension([100,100],[100,106]),true);
});
test('dimension text drops units and trailing zeros',async()=>{
  const {formatDimension}=await import('../src/dimensionPlacement.ts');
  assert.equal(formatDimension(40,undefined,'mm'),'40');
  assert.equal(formatDimension(40.5,undefined,'mm'),'40.5');
  assert.equal(formatDimension(40.126,undefined,'mm'),'40.13');
  assert.equal(formatDimension(6.1,'dia','mm'),'Ø6.1');
  assert.equal(formatDimension(3,'rad','mm'),'R3');
  assert.equal(formatDimension(90,'angle','in'),'90°');
  assert.equal(formatDimension(25.4,undefined,'in'),'1');
  assert.equal(formatDimension(6.1,'dia','in'),'Ø0.24');
});
test('hole callout arrow lands on the rim point facing the label',async()=>{
  const {calloutTip}=await import('../src/dimensionPlacement.ts');
  // Tilted hole projects as an ellipse 20 wide, 5 tall.
  const rim=Array.from({length:96},(_,k)=>{const t=k/96*Math.PI*2;return [100+20*Math.cos(t),100+5*Math.sin(t)];});
  const tip=calloutTip([100,100],[200,0],rim);
  assert.ok(Math.abs(((tip[0]-100)/20)**2+((tip[1]-100)/5)**2-1)<1e-9,'tip is on the ellipse');
  assert.ok(tip[0]>100&&tip[1]<100,'tip faces up-right toward the label');
});
test('overlapping labels slide apart along their own direction',async()=>{
  const {separateLabels}=await import('../src/dimensionPlacement.ts');
  const shifts=separateLabels([{x:0,y:0,width:40,height:20,dir:[0,-1]},{x:10,y:5,width:40,height:20,dir:[0,-1]},{x:200,y:0,width:40,height:20,dir:[1,0]}]);
  assert.deepEqual(shifts[0],[0,0]);
  assert.ok(shifts[1][0]===0&&5+shifts[1][1]+20<=0,'second label clears the first');
  assert.deepEqual(shifts[2],[0,0]);
});
