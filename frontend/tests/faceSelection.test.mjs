import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {pickSketchFace} from '../src/picking.ts';

test('face selection uses visible surface triangles, never edges or geometry behind a face',()=>{
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute([
    0,0,5,10,0,5,0,10,5,
    0,0,0,10,0,0,0,10,0,
  ],3));
  const mesh=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({side:THREE.DoubleSide}));
  const ray=new THREE.Raycaster(new THREE.Vector3(2,2,20),new THREE.Vector3(0,0,-1));
  assert.deepEqual(pickSketchFace(ray,mesh,[11,22]),{id:11,point:[2,2,5]});
  ray.ray.origin.set(15,15,20);
  assert.equal(pickSketchFace(ray,mesh,[11,22]),undefined);
  ray.ray.origin.set(2,2,20);
  assert.equal(pickSketchFace(ray,mesh,[]),undefined);
  geometry.dispose();mesh.material.dispose();
});
