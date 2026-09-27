import {useEffect,useRef} from 'react';
import {Check,Eye,LoaderCircle,X} from 'lucide-react';
import {featureName,type CadDocument,type Feature,type Sketch} from './cadDocument';
import {PlanarSketch} from './PlanarSketch';

type Props={document:CadDocument;featureId:string;pending:boolean;ready:boolean;error:string;onPreview:(doc:CadDocument)=>void;onApply:()=>void;onCancel:()=>void;onChange:(doc:CadDocument)=>void;viewportSketch?:boolean;drawn?:boolean;onExtrude?:()=>void;onBack?:()=>void};
export function CadEditor(p:Props){
  const doc=p.document;
  const form=useRef<HTMLFormElement>(null);
  useEffect(()=>{form.current?.querySelector<HTMLElement>('input,select')?.focus();},[]);
  const feature=doc.features.find(f=>f.id===p.featureId)!;
  const modern=doc.schema_version>=2;
  function patch(values:Partial<Feature>){p.onChange({...doc,features:doc.features.map(f=>f.id===feature.id?{...f,...values} as Feature:f)});}
  function number(label:string,key:string,value:number,signed=false){return <label>{label}<div className="cad-number"><input type="number" step="any" min={signed||key==='x'||key==='y'?-2000:0.011} max="2000" required value={Number.isNaN(value)?'':value} disabled={p.pending} onChange={e=>patch({[key]:e.target.valueAsNumber})}/><span>mm</span></div></label>;}
  const source=feature.type==='extrude'?doc.features.find(f=>f.id===feature.sketch_id) as Sketch|undefined:undefined;
  return <form ref={form} className="cad-editor" onSubmit={e=>{e.preventDefault();if(p.viewportSketch)p.onExtrude?.();else p.onPreview(doc);}}>
    <div className="cad-editor-heading"><h2>{p.viewportSketch?'Sketch':featureName(feature)}</h2><button type="button" className="icon-button" aria-label="Cancel edit" onClick={p.onCancel}><X size={18}/></button></div>
    {feature.type==='sketch'&&<>
      {modern&&<div className="form-grid"><label>Plane<select value={feature.plane} disabled={p.pending} onChange={e=>patch({plane:e.target.value as Sketch['plane'],frame:e.target.value==='FACE'?feature.frame:undefined,offset:0})}>{(feature.frame?['FACE','XY','XZ','YZ']:['XY','XZ','YZ']).map(v=><option key={v} value={v}>{v==='FACE'?'Selected face':v}</option>)}</select></label>{!feature.frame&&number('Plane offset','offset',feature.offset??0,true)}</div>}
      {feature.frame&&<p className="cad-face-note">Fixed face plane · stays here if the source face moves.</p>}
      <label>Profile<select value={feature.profile} disabled={p.pending} onChange={e=>patch({profile:e.target.value as Sketch['profile'],closed:e.target.value!=='polygon'||(feature.points?.length||0)>=3})}><option value="rectangle">Rectangle</option><option value="circle">Circle</option>{modern&&<option value="polygon">Closed line profile</option>}</select></label>
      {p.viewportSketch?null:modern?<PlanarSketch key={feature.profile} sketch={feature} disabled={p.pending} onChange={patch}/>:<div className="cad-profile-preview"><svg viewBox="0 0 160 100">{feature.profile==='rectangle'?<rect x="25" y="20" width="110" height="60"/>:<circle cx="80" cy="50" r="34"/>}</svg><span>XY plane · fixed origin</span></div>}
      {p.viewportSketch&&feature.profile==='polygon'&&<details><summary>Point coordinates</summary>{(feature.points||[]).map((point,i)=><div className="form-grid" key={i}>{point.map((v,k)=><label key={k}>Point {i+1} {k?'V':'U'}<input type="number" step="any" min="-2000" max="2000" required value={Number.isNaN(v)?'':v} onChange={e=>{const points=feature.points!.map(pt=>[...pt] as [number,number]);points[i][k]=e.target.valueAsNumber;patch({points});}}/></label>)}</div>)}</details>}
      {modern&&<div className="form-grid">{number(feature.profile==='circle'?'Centre U':'Origin U','x',feature.x??0,true)}{number(feature.profile==='circle'?'Centre V':'Origin V','y',feature.y??0,true)}</div>}
      {feature.profile==='rectangle'?<div className="form-grid">{number('Width','width',feature.width)}{number('Height','height',feature.height)}</div>:feature.profile==='circle'?number('Diameter','diameter',feature.diameter):null}
      <p className="muted">{p.viewportSketch?'Draw on the face. Select a dimension to resize.':modern?(doc.features[0].id===feature.id?`Base extrusion: ${(doc.features[1] as {depth:number}).depth} mm. Edit its depth in History.`:doc.features.some(f=>f.type==='extrude'&&f.sketch_id===feature.id)?'Edits rebuild the extrusions that use this sketch.':'U / V follow the labelled plane axes. Use Extrude or Cut after applying a sketch.'):`Dimensioned profile. Extrusion: ${(doc.features[1] as {depth:number}).depth} mm.`}</p>
    </>}
    {feature.type==='extrude'&&<>
      {modern&&<><label>Source sketch<select value={feature.sketch_id} disabled={p.pending} onChange={e=>patch({sketch_id:e.target.value})}>{doc.features.slice(0,doc.features.findIndex(f=>f.id===feature.id)).filter(f=>f.type==='sketch').map((f,i)=><option key={f.id} value={f.id} disabled={f.suppressed}>{i+1}. {featureName(f)} · {(f as Sketch).frame?'Face plane':(f as Sketch).plane}{f.suppressed?' (suppressed)':''}</option>)}</select></label><label>Operation<select value={feature.operation} disabled={p.pending||doc.features[1].id===feature.id} onChange={e=>patch({operation:e.target.value as 'add'|'cut',extent:'depth',direction:source?.frame&&e.target.value==='cut'?-1:1})}><option value="add">Join to body</option><option value="cut">Remove material</option></select></label><label>Direction<select value={feature.direction} disabled={p.pending} onChange={e=>patch({direction:Number(e.target.value) as 1|-1})}><option value="1">{source?.frame?'Outward from face':'+'+(source?.plane==='XZ'?'Y':source?.plane==='YZ'?'X':'Z')}</option><option value="-1">{source?.frame?'Into the face':'−'+(source?.plane==='XZ'?'Y':source?.plane==='YZ'?'X':'Z')}</option></select></label>{feature.operation==='cut'&&<label>Extent<select value={feature.extent} disabled={p.pending} onChange={e=>patch({extent:e.target.value as 'depth'|'through_all'})}><option value="depth">Depth</option><option value="through_all">Through all in this direction</option></select></label>}</>}
      {feature.extent!=='through_all'&&number('Depth','depth',feature.depth)}<p className="muted">{modern?(feature.operation==='cut'?'The cut must intersect the body.':'Additional extrusions must join the body.'):'From the sketch plane along +Z.'}</p>
    </>}
    {feature.type==='hole'&&<>{number('Diameter','diameter',feature.diameter)}<div className="form-grid">{number('Centre X','x',feature.x)}{number('Centre Y','y',feature.y)}</div><p className="muted">Through all · normal to XY.<br/>{(doc.features[0] as Sketch).profile==='rectangle'?'Origin is the lower-left corner.':'Origin is the circle centre.'}</p></>}
    {feature.type==='fillet'&&<>{number('Radius','radius',feature.radius)}<p className="muted">{(doc.features[0] as Sketch).profile==='rectangle'?'Four outside vertical corners.':'Top and bottom outside rims.'} Hole edges stay unchanged.</p></>}
    {p.onBack&&<button type="button" className="button" onClick={p.onBack}>Back to sketch</button>}
    <p className="cad-editor-note">{p.viewportSketch?'One closed profile · mm':'Rebuilds downstream features. Applying geometry clears measurements.'}</p>
    {p.error&&<p className="error-text" role="alert">{p.error}</p>}
    <div className="cad-editor-actions">{p.viewportSketch?<button className="button primary" disabled={p.pending||!p.drawn}>Extrude</button>:p.ready?<button type="button" className="button primary" onClick={p.onApply}><Check size={16}/>Apply</button>:<button className="button primary" disabled={p.pending}>{p.pending?<LoaderCircle className="spin" size={16}/>:<Eye size={16}/>} {p.pending?'Building…':'Preview'}</button>}<button type="button" className="button" onClick={p.onCancel}>Cancel</button></div>
  </form>;
}
