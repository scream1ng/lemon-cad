import {useEffect,useRef,useState} from 'react';
import {ArrowUp,Plus} from 'lucide-react';
import {api,type Model} from './api';

type Message={role:'user'|'assistant';content:string};
type Tool='drawing'|'costing'|'fixture';
type Props={model:Model|null;user:any;capabilities:string[];onTool:(tool:Tool,kind?:'weld'|'checking')=>void;onSignIn:()=>void;onPricing:()=>void;native?:boolean;locked?:boolean;onCadRequest?:(text:string)=>void};

export function WorkspaceChat(p:Props){
  const [service,setService]=useState<'fixture'|'costing'>('fixture'),[kind,setKind]=useState<'weld'|'checking'>('weld');
  const [messages,setMessages]=useState<Message[]>([]),[draft,setDraft]=useState(''),[sending,setSending]=useState(false),[error,setError]=useState(''),[ready,setReady]=useState(false),[toolsOpen,setToolsOpen]=useState(false);
  const version=useRef(0),bottom=useRef<HTMLDivElement>(null),toolsRoot=useRef<HTMLDivElement>(null),toolsTrigger=useRef<HTMLButtonElement>(null);
  useEffect(()=>{api('/engineering/chat/config').then(r=>setReady(r.available)).catch(()=>setReady(false));},[]);
  useEffect(()=>{version.current++;setMessages([]);setDraft('');setError('');setSending(false);},[p.model?.file_id]);
  useEffect(()=>{bottom.current?.scrollIntoView({block:'nearest'});},[messages,sending]);
  useEffect(()=>{if(!toolsOpen)return;toolsRoot.current?.scrollIntoView({block:'end'});toolsRoot.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus({preventScroll:true});const outside=(event:PointerEvent)=>{if(!toolsRoot.current?.contains(event.target as Node))setToolsOpen(false);};document.addEventListener('pointerdown',outside);return()=>document.removeEventListener('pointerdown',outside);},[toolsOpen]);
  function chooseTool(tool:Tool,selectedKind:'weld'|'checking'='weld'){setToolsOpen(false);toolsTrigger.current?.focus();if(tool==='costing')setService('costing');if(tool==='fixture'){setService('fixture');setKind(selectedKind);}p.onTool(tool,selectedKind);}
  async function send(){
    if(!draft.trim()||sending||p.locked)return;
    if(p.native&&p.onCadRequest){try{p.onCadRequest(draft.trim());setError('');}catch(e){setError(e instanceof Error?e.message:String(e));}return;}
    if(!p.user){p.onSignIn();return;}
    if(!p.capabilities.includes(service)){p.onPricing();return;}
    if(!ready)return;
    const next:Message[]=[...messages,{role:'user',content:draft.trim()}],turn=version.current;
    setMessages(next);setDraft('');setSending(true);setError('');
    try{const result=await api('/engineering/chat','POST',{messages:next,file_id:p.model?.file_id||null,service,kind});if(turn===version.current)setMessages([...next,{role:'assistant',content:result.content}]);}
    catch(e){if(turn===version.current){setMessages(messages);setDraft(next.at(-1)!.content);setError(e instanceof Error?e.message:String(e));}}
    finally{if(turn===version.current)setSending(false);}
  }
  return <div className={'workspace-chat'+(!messages.length?' is-empty':'')}>
    <div className="workspace-chat-body">{!messages.length&&<h2 className="workspace-chat-heading"><img src="/lemoncad-mark.svg" alt=""/>Ask Lemon</h2>}
      {messages.length>0&&<div className="workspace-chat-log" role="log" aria-label="Engineering conversation">{messages.map((message,i)=><article key={i}><strong>{message.role==='user'?'You':'LemonCAD'}</strong><p>{message.content}</p></article>)}{sending&&<p role="status">Thinking…</p>}<div ref={bottom}/></div>}
    </div>
    <form className="workspace-chat-composer" onSubmit={e=>{e.preventDefault();send();}}>
      <label className="sr-only" htmlFor="workspace-message">Ask Lemon</label>
      <textarea id="workspace-message" value={draft} onChange={e=>setDraft(e.target.value)} placeholder={p.native?"e.g. thickness 12 mm":"Ask about this part…"} disabled={p.locked} maxLength={8000} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send();}}}/>
      <div className="workspace-chat-compose-actions">
        <div className="workspace-tools" ref={toolsRoot} onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node))setToolsOpen(false);}} onKeyDown={event=>{
          if(event.key==='Escape'){event.preventDefault();event.stopPropagation();setToolsOpen(false);toolsTrigger.current?.focus();}
          if(!toolsOpen||!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;
          event.preventDefault();const items=Array.from(toolsRoot.current!.querySelectorAll<HTMLButtonElement>('[role="menuitem"]'));const current=items.indexOf(document.activeElement as HTMLButtonElement);const next=event.key==='Home'?0:event.key==='End'?items.length-1:(current+(event.key==='ArrowDown'?1:-1)+items.length)%items.length;items[next]?.focus();
        }}>
          <button className="workspace-tools-trigger" ref={toolsTrigger} type="button" aria-haspopup="menu" aria-expanded={toolsOpen} aria-controls="workspace-tools-menu" onClick={()=>setToolsOpen(!toolsOpen)} onKeyDown={event=>{if(!toolsOpen&&['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();setToolsOpen(true);}}}><Plus size={16}/>Tools</button>
          {toolsOpen&&<div className="workspace-tools-menu" id="workspace-tools-menu" role="menu" aria-label="Workflows">
            <button type="button" role="menuitem" onClick={()=>chooseTool('drawing')}><strong>Draft drawing</strong><small>Review sheets before PDF</small></button>
            <button type="button" role="menuitem" onClick={()=>chooseTool('costing')}><strong>Cost estimate</strong><small>Check shop assumptions</small></button>
            <button type="button" role="menuitem" onClick={()=>chooseTool('fixture','weld')}><strong>Weld fixture</strong><small>Plan datums and clamps</small></button>
            <button type="button" role="menuitem" onClick={()=>chooseTool('fixture','checking')}><strong>Checking fixture</strong><small>Plan inspection features</small></button>
          </div>}
        </div>
        <button className="button primary" type="submit" disabled={sending||!draft.trim()||(!ready&&!p.native)||p.locked} aria-label="Send message"><ArrowUp size={17}/></button>
      </div>
      {error&&<p role="alert" className="error-text">{error}</p>}
    </form>
    <p className="workspace-chat-status">{p.native?'Dimension commands · mm':!ready?'AI chat is not connected. Engineering tools are available.':!p.user?'Sign in to chat.':!p.capabilities.includes(service)?'Paid access needed to chat.':(service==='costing'?'Costing':'Fixture')+' chat sees file metadata, not CAD geometry.'}</p>
  </div>;
}
