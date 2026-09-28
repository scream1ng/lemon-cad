import {featureName,featureValue,type CadDocument,type Feature} from './cadDocument.ts';

export type FeatureRow={feature:Feature;index:number;label:string;detail:string;children:FeatureRow[]};
export function featureTree(doc:CadDocument):FeatureRow[]{
  const counts:Record<string,number>={};
  const rows=doc.features.map((feature,index)=>{
    const kind=feature.type==='sketch'?'Sketch':feature.type==='extrude'?(feature.operation==='cut'?'Cut':'Extrude'):feature.type==='hole'?'Hole':'Fillet';
    const label=`${kind}${counts[kind]=(counts[kind]||0)+1}`;
    const plane=feature.type==='sketch'?(feature.frame?' · Fixed face plane':` · ${feature.plane||'XY'} · offset ${feature.offset||0} mm`):'';
    return {feature,index,label,detail:`${featureName(feature)} · ${featureValue(feature)}${plane}`,children:[]} as FeatureRow;
  });
  const consumed=new Set<string>();
  for(const row of rows){
    if(row.feature.type!=='extrude')continue;
    const sketchId=row.feature.sketch_id;
    const source=doc.schema_version===1?rows[0]:rows.find(r=>r.feature.id===sketchId);
    if(source&&source.index<row.index&&source.feature.type==='sketch'){
      row.children.push(source);consumed.add(source.feature.id);
    }
  }
  return rows.filter(row=>!consumed.has(row.feature.id));
}
export function matchesFeature(row:FeatureRow,query:string){return `${row.label} ${row.detail}`.toLowerCase().includes(query.trim().toLowerCase());}
