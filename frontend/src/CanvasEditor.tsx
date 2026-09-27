import {useState,type ComponentProps,type ReactNode} from 'react';
import {ChevronDown,SlidersHorizontal,X} from 'lucide-react';
import {CadEditor} from './CadEditor';

type Props=ComponentProps<typeof CadEditor>&{onCut:()=>void;preview?:ReactNode};
export function CanvasEditor(p:Props){
  const [options,setOptions]=useState(false);
  return <section className={'cad-canvas-editor'+(p.viewportSketch?' is-sketch':'')} aria-label="Modeling controls" onKeyDown={e=>{if(e.key==='Escape'&&options){e.stopPropagation();setOptions(false);}}}>
    {p.viewportSketch&&<div className="cad-sketch-actions">
      <button type="button" className="button small" aria-expanded={options} onClick={()=>setOptions(!options)}><SlidersHorizontal size={15}/>Options<ChevronDown size={13}/></button>
      <button type="button" className="button primary small" disabled={p.pending||!p.drawn} onClick={p.onExtrude}>Extrude</button>
      <button type="button" className="button small" disabled={p.pending||!p.drawn} onClick={p.onCut}>Cut</button>
      <button type="button" className="icon-button" aria-label="Cancel sketch" onClick={p.onCancel}><X size={17}/></button>
    </div>}
    {(!p.viewportSketch||options)&&<CadEditor {...p}/>}{p.preview}
  </section>;
}
