import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {drawnProfile,planePoint,screenPoint,sketchFrame,validProfile} from '../src/sketchGeometry.ts';
import {appendSketch,appendExtrusion,newProfileDocument} from '../src/cadDocument.ts';

test('viewport picking stays on top, side and angled sketch planes through pan, zoom and resize',()=>{
  const frames=[sketchFrame({plane:'XY',offset:8}),sketchFrame({plane:'YZ',offset:13}),{origin:[4,5,6],u:[Math.SQRT1_2,Math.SQRT1_2,0],v:[0,0,1]}];
  for(const frame of frames)for(const [width,height,zoom] of [[1000,700,1],[420,600,2.4]]){
    const origin=new THREE.Vector3(...frame.origin),normal=new THREE.Vector3(...frame.u).cross(new THREE.Vector3(...frame.v));
    const camera=new THREE.OrthographicCamera(-100*width/height,100*width/height,100,-100,.1,1000);
    camera.position.copy(origin).addScaledVector(normal,300).addScaledVector(new THREE.Vector3(...frame.u),12);camera.up.fromArray(frame.v);camera.lookAt(origin.clone().addScaledVector(new THREE.Vector3(...frame.u),12));camera.zoom=zoom;camera.updateProjectionMatrix();camera.updateMatrixWorld();
    const view={matrix:new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).toArray(),width,height};
    const expected=[12.375,-8.125],actual=planePoint(frame,screenPoint(frame,expected,view),view);
    actual.forEach((v,i)=>assert.ok(Math.abs(v-expected[i])<1e-9));
  }
});

test('drawing works in either direction and rejects degenerate or oversized profiles',()=>{
  assert.deepEqual(drawnProfile('rectangle',[20,15],[0,3]),{profile:'rectangle',x:0,y:3,width:20,height:12,closed:true});
  assert.equal(drawnProfile('rectangle',[0,0],[0,5]),null);
  assert.equal(drawnProfile('rectangle',[-1500,0],[1500,5]),null);
  assert.equal(drawnProfile('circle',[0,0],[3,4]).diameter,10);
  assert.equal(drawnProfile('circle',[0,0],[0,0]),null);
  assert.equal(validProfile({profile:'polygon',width:1,height:1,diameter:1,points:[[0,0],[2,0],[0,2]],closed:false}),false);
  assert.equal(validProfile({profile:'rectangle',x:NaN,width:20,height:12,diameter:1}),false);
});

test('extrude explicitly uses the active sketch even when another sketch is last',()=>{
  const doc=appendSketch(appendSketch(newProfileDocument(),'rectangle'),'circle'),id=doc.features[2].id;
  const next=appendExtrusion(doc,'add',id);
  assert.equal(next.features.at(-1).sketch_id,id);
  assert.equal(doc.features.length,4);
  assert.throws(()=>appendExtrusion(doc,'add','missing'),/available sketch/);
});

import {planeEdge,rectangleSide,edgeGap,positionFromEdge,worldPoint} from '../src/sketchGeometry.ts';

test('rectangle edge gaps position without resizing on top, side and angled planes',()=>{
  for(const frame of [sketchFrame({plane:'XY',offset:10}),sketchFrame({plane:'YZ',offset:7}),{origin:[40,10,25],u:[1,0,0],v:[0,Math.SQRT1_2,Math.SQRT1_2]}]){
    const ref=(id,a,b)=>planeEdge({id,type:'line',points:[worldPoint(frame,a),worldPoint(frame,b)]},frame);
    const left=ref(1,[0,0],[0,50]),bottom=ref(2,[0,0],[80,0]),right=ref(3,[80,0],[80,50]),top=ref(4,[0,50],[80,50]);
    let s={profile:'rectangle',x:25,y:20,width:20,height:12};
    s={...s,...positionFromEdge(s,'left',left,8),...positionFromEdge(s,'bottom',bottom,6)};
    assert.ok(Math.abs(s.x-8)<1e-9);assert.ok(Math.abs(s.y-6)<1e-9);
    assert.equal(s.width,20);assert.equal(s.height,12);
    assert.ok(Math.abs(edgeGap(s,'left',left)-8)<1e-9);
    s={...s,...positionFromEdge(s,'right',right,8),...positionFromEdge(s,'top',top,6)};
    assert.equal(s.x,52);assert.equal(s.y,32);
    assert.equal(rectangleSide(s,'right')[0][0],72);
    assert.deepEqual(positionFromEdge(s,'right',right,0),{x:60});
    assert.deepEqual(positionFromEdge({...s,x:60},'right',right,8),{x:52});
    assert.equal(positionFromEdge(s,'left',bottom,5),null);
    for(const invalid of [-1,NaN,Infinity,2001])assert.equal(positionFromEdge(s,'left',left,invalid),null);
    assert.equal(positionFromEdge({...s,x:1999},'left',{...left,a:[1990,0],b:[1990,50]},20),null);
  }
});

test('edge references reject off-plane, curved, diagonal and degenerate geometry',()=>{
  const frame=sketchFrame({plane:'XY',offset:10});
  for(const edge of [{type:'line',points:[[0,0,0],[0,10,0]]},{type:'circle',points:[[0,0,10],[0,10,10]]},{type:'line',points:[[0,0,10],[10,10,10]]},{type:'line',points:[[0,0,10],[0,0,10]]},{type:'line',points:[[NaN,0,10],[0,10,10]]}])assert.equal(planeEdge({id:1,...edge},frame),null);
  assert.deepEqual(drawnProfile('rectangle',[.001,.002],[22.104,15.632]),{profile:'rectangle',x:.001,y:.002,width:22.103,height:15.63,closed:true});
});
