import test from 'node:test';
import assert from 'node:assert/strict';
import {loadGoogle} from '../src/googleLoader.ts';

test('stalled Google script fails and retry loads a fresh script',async()=>{
  const old={window:globalThis.window,document:globalThis.document,setTimeout:globalThis.setTimeout,clearTimeout:globalThis.clearTimeout};
  const scripts=[];let timeout;
  try{
    globalThis.window={};
    globalThis.document={createElement:()=>({remove(){this.removed=true;}}),head:{append(script){scripts.push(script);}}};
    globalThis.setTimeout=callback=>{timeout=callback;return 1;};
    globalThis.clearTimeout=()=>{};
    const stalled=loadGoogle();
    assert.equal(scripts.length,1);
    timeout();
    await assert.rejects(stalled,/too long/);
    assert.equal(scripts[0].removed,true);
    const retry=loadGoogle();
    assert.equal(scripts.length,2);
    window.google={};scripts[1].onload();
    await retry;
  }finally{
    Object.assign(globalThis,old);
  }
});
