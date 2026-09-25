import {useLayoutEffect,useRef,useId,type ReactNode,type ButtonHTMLAttributes} from 'react';

export function CadToolbar({className,label,vertical=false,children}:{className:string;label:string;vertical?:boolean;children:ReactNode}){
  const ref=useRef<HTMLDivElement>(null);
  function controls(){return Array.from(ref.current!.querySelectorAll<HTMLElement>('button:not(:disabled),select:not(:disabled)'));}
  useLayoutEffect(()=>{const items=controls(),active=items.find(item=>item===document.activeElement)||items.find(item=>item.tabIndex===0)||items[0];items.forEach(item=>item.tabIndex=item===active?0:-1);});
  return <div ref={ref} className={className} role="toolbar" aria-label={label} aria-orientation={vertical?'vertical':'horizontal'} onFocus={e=>controls().forEach(item=>item.tabIndex=item===e.target?0:-1)} onKeyDown={e=>{
    if((e.target as HTMLElement).tagName==='SELECT')return;
    const keys=vertical?['ArrowUp','ArrowDown']:['ArrowLeft','ArrowRight'];
    if(![...keys,'Home','End'].includes(e.key))return;
    const items=controls();if(!items.length)return;e.preventDefault();
    const index=items.indexOf(e.target as HTMLElement),next=e.key==='Home'?0:e.key==='End'?items.length-1:(index+(e.key===keys[0]?-1:1)+items.length)%items.length;
    items[next].focus();
  }}>{children}</div>;
}

export function CadTool({label,children,...props}:ButtonHTMLAttributes<HTMLButtonElement>&{label:string}){
  const id=useId();
  return <span className="cad-tool"><button {...props} aria-label={label} aria-describedby={id}>{children}</button><span id={id} className="cad-tooltip" role="tooltip">{label}</span></span>;
}
