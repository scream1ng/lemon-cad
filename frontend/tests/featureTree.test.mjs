import test from 'node:test';
import assert from 'node:assert/strict';
import {newDocument,appendSketch,appendExtrusion} from '../src/cadDocument.ts';
import {featureTree,matchesFeature} from '../src/featureTree.ts';

test('history collapses consumed sketches without changing the saved document',()=>{
  const doc=appendExtrusion(appendSketch(newDocument(),'circle'),'cut');
  const before=structuredClone(doc),rows=featureTree(doc);
  assert.deepEqual(rows.map(r=>r.label),['Extrude1','Cut1']);
  assert.deepEqual(rows.map(r=>r.children[0].label),['Sketch1','Sketch2']);
  assert.deepEqual(rows.map(r=>r.index),[1,3]);
  assert.deepEqual(doc,before);
  assert.ok(matchesFeature(rows[1].children[0],'circle'));
  assert.ok(matchesFeature(rows[1].children[0],'  sketch2  '));
});

test('unused sketches remain visible and shared sketches are accessible under each operation',()=>{
  const doc=appendExtrusion(appendExtrusion(appendSketch(newDocument(),'circle'),'cut'),'cut');
  const rows=featureTree(doc);
  assert.equal(rows[1].children[0].feature.id,rows[2].children[0].feature.id);
  const unused=featureTree(appendSketch(doc,'polygon'));
  assert.equal(unused.at(-1).label,'Sketch3');
  assert.equal(unused.at(-1).children.length,0);
});

test('legacy documents, suppression and rollback retain original feature indices',()=>{
  const doc=newDocument();
  assert.equal(featureTree(doc)[0].children[0].label,'Sketch1');
  const extended=appendExtrusion(appendSketch(doc),'cut');
  extended.features[3].suppressed=true;extended.rollback=2;
  const row=featureTree(extended)[1];
  assert.equal(row.index,3);assert.equal(row.children[0].index,2);
  assert.equal(row.feature.suppressed,true);
});
