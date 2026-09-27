import test from 'node:test';
import assert from 'node:assert/strict';
import {newDocument,insertFeature,requestDocument} from '../src/cadDocument.ts';

test('commands change only requested dimensions and leave the base document intact',()=>{
 const base=newDocument();
 const deeper=requestDocument('set thickness to 16 mm',base);
 assert.equal(deeper.features[1].depth,16);assert.equal(base.features[1].depth,10);
 const drilled=requestDocument('hole diameter 12 mm',deeper);
 assert.equal(drilled.features[2].diameter,12);assert.equal(drilled.features[2].x,40);
 const rounded=requestDocument('fillet radius 2 mm',drilled);
 const another=insertFeature(rounded,'hole');
 assert.deepEqual(another.features.map(f=>f.type),['sketch','extrude','hole','hole','fillet']);
 assert.equal(another.rollback,5);assert.equal(rounded.features.length,4);
 assert.throws(()=>requestDocument('hole 20 mm',another),/individually/);
});
test('unknown, unsafe, ambiguous-unit and nonfinite commands do not execute',()=>{
 const doc=newDocument();
 for(const text of ['delete everything','thickness 2 in','hole -5','hole NaN','run code','thickness 12 mm and width 10 mm'])assert.equal(requestDocument(text,doc),null);
 assert.throws(()=>requestDocument('hole 0 mm',doc));
 assert.throws(()=>requestDocument('extrude 5000 mm',doc));
 doc.features[0].profile='circle';assert.throws(()=>requestDocument('width 20 mm',doc),/rectangle/);
});

test('v2 migration preserves IDs, legacy features, and the old revision',async()=>{
 const {upgradeDocument,appendSketch,appendExtrusion}=await import('../src/cadDocument.ts');
 const old=insertFeature(insertFeature(newDocument(),'hole'),'fillet');
 const before=structuredClone(old),modern=upgradeDocument(old);
 assert.equal(modern.schema_version,2);assert.deepEqual(old,before);
 assert.deepEqual(modern.features.map(f=>f.id),old.features.map(f=>f.id));
 assert.equal(modern.features[1].sketch_id,old.features[0].id);
 const withSketch=appendSketch(old,'polygon');
 assert.equal(withSketch.features.at(-1).closed,false);
 const withCut=appendExtrusion(withSketch,'cut');
 assert.equal(withCut.features.at(-1).sketch_id,withSketch.features.at(-1).id);
 assert.equal(withCut.features.at(-1).extent,'through_all');
 assert.equal(withCut.rollback,withCut.features.length);
 assert.equal(withSketch.features.length,5);assert.deepEqual(old,before);
});

test('face sketches upgrade without mutating history and choose safe default directions',async()=>{
 const {appendFaceSketch,appendExtrusion,appendSketch}=await import('../src/cadDocument.ts');
 const base=newDocument(),before=structuredClone(base);
 const r=Math.SQRT1_2,frame={origin:[1,2,3],u:[0,1,0],v:[-r,0,r]};
 const doc=appendFaceSketch(base,frame,[1,12,3]);
 const sketch=doc.features.at(-1);
 assert.equal(doc.schema_version,3);assert.equal(sketch.plane,'FACE');
 assert.equal(sketch.x,5);assert.equal(sketch.y,-5);
 assert.deepEqual(base,before);assert.notEqual(sketch.frame,frame);
 assert.equal(appendExtrusion(doc,'add').features.at(-1).direction,1);
 assert.equal(appendExtrusion(doc,'cut').features.at(-1).direction,-1);
 assert.equal(appendSketch(doc).schema_version,3);
 const circle=appendFaceSketch(base,frame,[1,12,3],'circle').features.at(-1);
 assert.equal(circle.x,10);assert.equal(circle.y,0);
 const clicked=appendFaceSketch(base,frame,[1,12.12345678,3],'circle').features.at(-1);
 assert.equal(clicked.x,10.123);assert.deepEqual(clicked.frame,frame);
});

import {prepareSketchExtrusion,appendFaceSketch,newProfileDocument} from '../src/cadDocument.ts';

test('sketch Cut changes its existing extrusion and Extrude restores an additive operation',()=>{
  const frame={origin:[0,0,10],u:[1,0,0],v:[0,1,0]};
  const source=appendFaceSketch(newProfileDocument(),frame,[10,10,10]);
  const sketchId=source.features.at(-1).id;
  const first=prepareSketchExtrusion(source,sketchId,'add');
  assert.equal(first.newExtrudeId,first.featureId);
  const cut=prepareSketchExtrusion(first.document,sketchId,'cut');
  assert.equal(cut.document.features.length,first.document.features.length);
  assert.equal(cut.featureId,first.featureId);
  assert.equal(cut.newExtrudeId,undefined);
  assert.equal(cut.document.features.at(-1).operation,'cut');
  assert.equal(cut.document.features.at(-1).direction,-1);
  assert.equal(cut.document.features.at(-1).extent,'through_all');
  assert.equal(first.document.features.at(-1).operation,'add');
  const add=prepareSketchExtrusion(cut.document,sketchId,'add');
  assert.equal(add.document.features.at(-1).operation,'add');
  assert.equal(add.document.features.at(-1).extent,'depth');
  assert.equal(add.document.features.at(-1).direction,1);
  assert.throws(()=>prepareSketchExtrusion(source,source.features[0].id,'cut'),/base extrusion/);
});
