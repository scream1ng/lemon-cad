export type Plane='XY'|'XZ'|'YZ'|'FACE';
export type SketchFrame={origin:[number,number,number];u:[number,number,number];v:[number,number,number]};
export type Sketch={id:string;type:'sketch';profile:'rectangle'|'circle'|'polygon';width:number;height:number;diameter:number;plane?:Plane;frame?:SketchFrame|null;offset?:number;x?:number;y?:number;points?:[number,number][];closed?:boolean;suppressed?:boolean};
export type Extrude={id:string;type:'extrude';depth:number;sketch_id?:string;operation?:'add'|'cut';direction?:1|-1;extent?:'depth'|'through_all';suppressed?:boolean};
export type Hole={id:string;type:'hole';diameter:number;x:number;y:number;suppressed?:boolean};
export type Fillet={id:string;type:'fillet';radius:number;scope:'outer_edges';suppressed?:boolean};
export type Feature=Sketch|Extrude|Hole|Fillet;
export type CadDocument={schema_version:1|2|3;kind:'part';units:'mm';features:Feature[];rollback:number};
export function newDocument():CadDocument{return {schema_version:1,kind:'part',units:'mm',rollback:2,features:[{id:crypto.randomUUID(),type:'sketch',profile:'rectangle',width:80,height:50,diameter:50},{id:crypto.randomUUID(),type:'extrude',depth:10}]};}
export function featureName(f:Feature){return f.type==='sketch'?(f.profile==='rectangle'?'Rectangle':f.profile==='circle'?'Circle':'Line profile')+' sketch':f.type==='extrude'?(f.operation==='cut'?'Extruded cut':'Extrusion'):f.type==='hole'?'Through-hole':'Outer edge fillet';}
export function featureValue(f:Feature){return f.type==='sketch'?(f.profile==='rectangle'?`${f.width} × ${f.height}`:f.profile==='circle'?`Ø${f.diameter}`:`${f.points?.length||0} points`):f.type==='extrude'?(f.extent==='through_all'?'Through all':`${f.depth} mm`):f.type==='hole'?`Ø${f.diameter}`:`R${f.radius}`;}
export function insertFeature(doc:CadDocument,kind:'hole'|'fillet'):CadDocument{
  if(doc.schema_version>=2)throw new Error('Use a circle sketch and Extruded cut for holes. General edge fillets are not available yet.');
  const next=structuredClone(doc),sketch=next.features[0] as Sketch;
  const f:Feature=kind==='hole'?{id:crypto.randomUUID(),type:'hole',diameter:10,x:sketch.profile==='rectangle'?sketch.width/2:0,y:sketch.profile==='rectangle'?sketch.height/2:0}:{id:crypto.randomUUID(),type:'fillet',radius:2,scope:'outer_edges'};
  const fillet=next.features.findIndex(f=>f.type==='fillet');
  if(kind==='fillet'&&fillet>=0)return next;
  next.features.splice(fillet<0?next.features.length:fillet,0,f);next.rollback=next.features.length;return next;
}
// A small, explicit command grammar. Unrecognized text never executes geometry.
export function requestDocument(text:string,doc:CadDocument):CadDocument|null{
  const match=text.trim().match(/^(?:set |change )?(thickness|extrude|width|height|hole(?: diameter)?|fillet(?: radius)?)\s*(?:to |of |[:=]\s*)?(\d+(?:\.\d+)?)\s*(mm)?[.!]?$/i);
  if(!match)return null;
  const value=Number(match[2]);if(!Number.isFinite(value)||value<=0.01||value>2000)throw new Error('Use a dimension greater than 0.01 and no more than 2000 mm.');
  let next=structuredClone(doc);const key=match[1].toLowerCase();
  if(key.startsWith('hole')){const holes=next.features.filter(f=>f.type==='hole');if(holes.length>1)throw new Error('Select a hole in History to edit it individually.');if(!holes.length)next=insertFeature(next,'hole');(next.features.find(f=>f.type==='hole') as Hole).diameter=value;}
  else if(key.startsWith('fillet')){next=insertFeature(next,'fillet');(next.features.find(f=>f.type==='fillet') as Fillet).radius=value;}
  else if(key==='width'||key==='height'){const sketch=next.features[0] as Sketch;if(sketch.profile!=='rectangle')throw new Error('Width and height apply to rectangle sketches. Edit the circle in History.');sketch[key]=value;}
  else (next.features[1] as Extrude).depth=value;
  next.rollback=next.features.length;return next;
}

export function upgradeDocument(doc:CadDocument):CadDocument{
  const next=structuredClone(doc);if(next.schema_version>=2)return next;
  next.schema_version=2;
  next.features=next.features.map(f=>f.type==='sketch'?{...f,plane:'XY',offset:0,x:0,y:0,points:[],closed:true}:f.type==='extrude'?{...f,sketch_id:next.features[0].id,operation:'add',direction:1,extent:'depth'}:f);
  return next;
}
export function newProfileDocument():CadDocument{return upgradeDocument(newDocument());}
export function appendSketch(doc:CadDocument,profile:Sketch['profile']='rectangle'):CadDocument{
  const next=upgradeDocument(doc);
  next.features.push({id:crypto.randomUUID(),type:'sketch',profile,width:80,height:50,diameter:6,plane:'XY',offset:0,x:0,y:0,points:[],closed:profile!=='polygon'});
  next.rollback=next.features.length;return next;
}
export function appendExtrusion(doc:CadDocument,operation:'add'|'cut'='add',sketchId?:string):CadDocument{
  const next=upgradeDocument(doc),sketch=next.features.filter(f=>f.type==='sketch'&&!f.suppressed&&(!sketchId||f.id===sketchId)).at(-1);
  if(!sketch)throw new Error('Select an available sketch to extrude.');
  next.features.push({id:crypto.randomUUID(),type:'extrude',sketch_id:sketch.id,operation,direction:sketch.type==='sketch'&&sketch.frame&&operation==='cut'?-1:1,extent:operation==='cut'?'through_all':'depth',depth:10});
  next.rollback=next.features.length;return next;
}

export function prepareSketchExtrusion(doc:CadDocument,sketchId:string,operation:'add'|'cut'){
  const document=structuredClone(doc),sketch=document.features.find(f=>f.id===sketchId&&f.type==='sketch') as Sketch|undefined;
  if(!sketch||sketch.suppressed)throw new Error('Select an available sketch to extrude.');
  const feature=document.features.find(f=>f.type==='extrude'&&f.sketch_id===sketchId) as Extrude|undefined;
  if(!feature){const next=appendExtrusion(document,operation,sketchId),id=next.features.at(-1)!.id;return {document:next,featureId:id,newExtrudeId:id};}
  if(document.features[1].id===feature.id&&operation==='cut')throw new Error('The base extrusion must add material. Create another sketch to cut the body.');
  if(feature.suppressed)throw new Error('Restore the suppressed extrusion in History before editing its sketch.');
  if((feature.operation??'add')!==operation)Object.assign(feature,{operation,extent:operation==='cut'?'through_all':'depth',direction:sketch.frame&&operation==='cut'?-1:1});
  return {document,featureId:feature.id,newExtrudeId:undefined};
}

export function appendFaceSketch(doc:CadDocument,frame:SketchFrame,point:number[],profile:Sketch['profile']='rectangle'):CadDocument{
  const next=appendSketch(doc,profile);next.schema_version=3;
  const sketch=next.features.at(-1) as Sketch;
  const local=(axis:number[])=>axis.reduce((sum,value,k)=>sum+value*(point[k]-frame.origin[k]),0);
  const coordinate=(axis:number[])=>Math.round((local(axis)-(profile==='rectangle'?5:0))*1000)/1000;
  Object.assign(sketch,{plane:'FACE',frame:structuredClone(frame),offset:0,width:10,height:10,x:coordinate(frame.u),y:coordinate(frame.v)});
  return next;
}
