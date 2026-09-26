import {useEffect,useRef,useState} from 'react';
import {ChevronDown,Download,Share2} from 'lucide-react';

type Props={busy:boolean;onExport:(format:'png'|'pdf')=>void;onShare?:()=>void};

export function FileActions({busy,onExport,onShare}:Props){
  const [open,setOpen]=useState(false);
  const root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null);
  useEffect(()=>{
    if(!open)return;
    root.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus();
    const outside=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false);};
    document.addEventListener('pointerdown',outside);
    return()=>document.removeEventListener('pointerdown',outside);
  },[open]);
  function choose(action:()=>void){setOpen(false);trigger.current?.focus();action();}
  return <div className="file-actions" ref={root} onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node))setOpen(false);}} onKeyDown={event=>{
    if(event.key==='Escape'){event.preventDefault();event.stopPropagation();setOpen(false);trigger.current?.focus();}
    if(!open||!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;
    event.preventDefault();
    const items=Array.from(root.current!.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)'));
    const current=items.indexOf(document.activeElement as HTMLButtonElement);
    const next=event.key==='Home'?0:event.key==='End'?items.length-1:(current+(event.key==='ArrowDown'?1:-1)+items.length)%items.length;
    items[next]?.focus();
  }}>
    <button className="button" ref={trigger} aria-haspopup="menu" aria-expanded={open} aria-controls="cad-file-menu" disabled={busy} onClick={()=>setOpen(!open)} onKeyDown={event=>{if(!open&&['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();setOpen(true);}}}>File<ChevronDown size={14}/></button>
    {open&&<div className="file-menu" id="cad-file-menu" role="menu" aria-label="File actions">
      <button role="menuitem" onClick={()=>choose(()=>onExport('png'))}><Download size={15}/>Export PNG</button>
      <button role="menuitem" onClick={()=>choose(()=>onExport('pdf'))}><Download size={15}/>Export PDF</button>
      {onShare&&<button role="menuitem" onClick={()=>choose(onShare)}><Share2 size={15}/>Share folder</button>}
    </div>}
  </div>;
}
