import {useEffect,useState} from 'react';
import {Box,ChevronRight,Circle,CornerUpRight,EyeOff,History,Layers,Pencil,RotateCcw,Search} from 'lucide-react';
import {api,shareToken,type Model} from './api';
import {featureValue,type CadDocument} from './cadDocument';
import {featureTree,matchesFeature,type FeatureRow} from './featureTree';

type Props={model:Model|null;disabled:boolean;onEdit:(id:string)=>void;onPreview:(doc:CadDocument)=>void;onOpenRevision:(revision:string)=>void;onNew:()=>void};
export function CadHistory(p:Props){
  const [tab,setTab]=useState('features'),[query,setQuery]=useState(''),[versions,setVersions]=useState<any[]>([]),[error,setError]=useState(''),[loading,setLoading]=useState(false),[expanded,setExpanded]=useState<Set<string>>(()=>new Set());
  const doc=p.model?.state?.cad_document as CadDocument|undefined;
  useEffect(()=>{let live=true;setVersions([]);setError('');if(!p.model?.project)return;setLoading(true);api(`/projects/${p.model.project.id}/revisions${shareToken?`?share=${encodeURIComponent(shareToken)}`:''}`).then(r=>{if(live)setVersions(r);}).catch(e=>{if(live)setError(e.message);}).finally(()=>{if(live)setLoading(false);});return()=>{live=false;};},[p.model?.project?.id,p.model?.project?.revision_id]);
  function renderRow(row:FeatureRow,child:boolean,open:boolean){
    if(!doc)return null;
    const {feature:f,index:i,label,detail}=row;
    const inactive=f.suppressed||i>=doc.rollback;
    return <div key={f.id} className={'cad-feature'+(child?' cad-feature-child':'')+(inactive?' is-suppressed':'')}>
      {row.children.length?<button className="cad-feature-disclosure" disabled={!!query.trim()} title={query.trim()?'Clear search to collapse':undefined} aria-label={(open?'Collapse ':'Expand ')+label+' sketches'} aria-expanded={open} onClick={()=>setExpanded(current=>{const next=new Set(current);if(next.has(f.id))next.delete(f.id);else next.add(f.id);return next;})}><ChevronRight size={12}/></button>:<span className="cad-feature-indent"/>}
      <button disabled={p.disabled} className="cad-feature-main" title={`${label} · ${detail}${f.suppressed?' · Suppressed':i>=doc.rollback?' · Rolled back':''}`} onClick={()=>p.onEdit(f.id)}><span>{f.type==='sketch'?<Pencil size={14}/>:f.type==='hole'?<Circle size={14}/>:f.type==='fillet'?<CornerUpRight size={14}/>:<Box size={14}/>}</span><span>{label}</span><small>{featureValue(f)}</small></button>
      <span className="cad-feature-actions">{i>1&&<button className="cad-feature-action" disabled={p.disabled} aria-label={(f.suppressed?'Unsuppress ':'Suppress ')+label} title={f.suppressed?'Unsuppress':'Suppress'} onClick={()=>{const next=structuredClone(doc);next.features[i].suppressed=!f.suppressed;p.onPreview(next);}}><EyeOff size={13}/></button>}{i>=1&&i<doc.features.length-1&&<button className="cad-feature-action" disabled={p.disabled} aria-label={'Roll back after '+label} title="Roll back here" onClick={()=>p.onPreview({...doc,rollback:i+1})}><RotateCcw size={13}/></button>}</span>
    </div>;
  }
  return <div className="cad-history">
    <div className="cad-history-tabs" role="tablist" aria-label="Model history"><button role="tab" aria-selected={tab==='features'} onClick={()=>setTab('features')}>Features</button><button role="tab" aria-selected={tab==='versions'} onClick={()=>setTab('versions')}>Versions</button></div>
    {tab==='features'?<div className="cad-history-content"><label className="cad-search"><Search size={15}/><input aria-label="Search model history" placeholder="Find a feature…" value={query} onChange={e=>setQuery(e.target.value)}/></label>
      {!p.model?<div className="cad-history-empty"><Layers size={28}/><p>No part open.</p><button className="button" disabled={p.disabled} onClick={p.onNew}>New part</button></div>:<><div className="cad-history-root"><Box size={17}/><strong>{p.model.project?.name||p.model.name}</strong></div>
      {doc?featureTree(doc).filter(row=>matchesFeature(row,query)||row.children.some(child=>matchesFeature(child,query))).map(row=>{
        const open=expanded.has(row.feature.id)||!!query.trim();
        return <div key={row.feature.id}>{renderRow(row,false,open)}{open&&row.children.map(child=>renderRow(child,true,false))}</div>;
      }):<><div className="cad-import-row"><Box size={16}/><span>Imported {p.model.format.toUpperCase()} body</span></div><p className="muted">Source features are not included in imported geometry.</p></>}
      {doc&&doc.rollback<doc.features.length&&<button className="text-link" disabled={p.disabled} onClick={()=>p.onPreview({...doc,rollback:doc.features.length})}>Restore all features</button>}</>}
    </div>:<div className="cad-history-content">{error&&<p className="error-text" role="alert">{error}</p>}{loading&&<p role="status">Loading versions…</p>}{!p.model?.project&&<div className="cad-history-empty"><History size={28}/><p>Save a draft to keep versions.</p></div>}{versions.map((r,i)=><button key={r.id} className="cad-version" aria-current={p.model?.project?.revision_id===r.id?'true':undefined} disabled={p.disabled} onClick={()=>p.onOpenRevision(r.id)}><strong>{r.current?'Latest draft':`Version ${versions.length-i}`}{r.published&&<small>Published</small>}</strong><span>{new Date(r.created_at).toLocaleString()}</span></button>)}</div>}
  </div>;
}
