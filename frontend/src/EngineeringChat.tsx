import {useEffect,useRef,useState,type ReactNode} from 'react';
import {ArrowLeft,ArrowUp,Box,Plus,Wrench,Ruler,Calculator,MessageSquare} from 'lucide-react';
import {api,type Model} from './api';

type Message={role:'user'|'assistant';content:string};
type Props={model:Model|null;user:any;capabilities:string[];service:string;kind:string;onService:(service:string,kind:string)=>void;onOpen:()=>void;onSignIn:()=>void;onPricing:()=>void;onViewer:()=>void;details:ReactNode;detailsOnly?:boolean};
export function EngineeringChat(p:Props){
  const [messages,setMessages]=useState<Message[]>([]),[draft,setDraft]=useState(''),[sending,setSending]=useState(false),[error,setError]=useState(''),[ready,setReady]=useState(false),[tab,setTab]=useState('model');
  const bottom=useRef<HTMLDivElement>(null),version=useRef(0);
  useEffect(()=>{api('/engineering/chat/config').then(r=>setReady(r.available)).catch(()=>setReady(false));},[]);
  useEffect(()=>{version.current++;setMessages([]);setError('');setSending(false);},[p.model?.file_id]);
  useEffect(()=>{bottom.current?.scrollIntoView({block:'nearest'});},[messages,sending]);
  const enabled=ready&&p.user&&p.capabilities.includes(p.service);
  async function send(){
    if(!draft.trim()||sending)return;if(!p.user){p.onSignIn();return;}if(!enabled)return;
    const next:Message[]=[...messages,{role:'user',content:draft.trim()}],turn=version.current;
    setMessages(next);setDraft('');setSending(true);setError('');
    try{const result=await api('/engineering/chat','POST',{messages:next,file_id:p.model?.file_id||null,service:p.service,kind:p.kind});if(turn===version.current)setMessages([...next,{role:'assistant',content:result.content}]);}
    catch(e){if(turn===version.current){setMessages(messages);setDraft(next.at(-1)!.content);setError(e instanceof Error?e.message:String(e));}}
    finally{if(turn===version.current)setSending(false);}
  }
  const starters=[{id:'weld',service:'fixture',icon:<Wrench size={16}/>,title:'Weld fixture',prompt:'Help me plan a weld fixture for this part. Ask about datums, clamp access and production quantity first.'},{id:'checking',service:'fixture',icon:<Ruler size={16}/>,title:'Checking fixture',prompt:'Help me plan a checking fixture. Ask which features and tolerances need inspection.'},{id:'costing',service:'costing',icon:<Calculator size={16}/>,title:'Cost estimate',prompt:'Help me estimate manufacturing cost. Ask about material, process, quantity and shop rates.'}];
  if(p.detailsOnly)return <section className="engineering-details workspace-result" aria-label="Engineering tool">{p.details}</section>;
  return <section className="engineering-assistant" aria-label="Engineering assistant"><div className="assistant-tabs"><button className={tab==='model'?'button selected':'button'} onClick={()=>setTab('model')}>Chat</button><button className={tab==='tools'?'button selected':'button'} onClick={()=>setTab('tools')}>{p.service==='costing'?'Estimate':'Fixture brief'}</button><button className="button small" onClick={p.onViewer} aria-label="Close Engineering"><ArrowLeft size={16}/></button></div>
    <aside className="engineering-chat" hidden={tab!=='model'}><div className="chat-heading"><span><MessageSquare size={16}/>Engineering</span><button title="New conversation" aria-label="New conversation" onClick={()=>{version.current++;setMessages([]);setDraft('');setSending(false);setError('');}}><Plus size={18}/></button></div>
      <div className="chat-scroll">{!messages.length?<div className="chat-welcome"><div className="eyebrow">YOUR NEXT STEP</div><h1>What are we making?</h1><p>Explore a fixture or work through a cost estimate with your part beside you.</p><div className="chat-starters">{starters.map(s=><button key={s.id} aria-pressed={p.service===s.service&&(s.id==='costing'||p.kind===s.id)} onClick={()=>{p.onService(s.service,s.id==='costing'?'weld':s.id);setDraft(s.prompt);}}>{s.icon}{s.title}</button>)}</div><p className="chat-scope">AI helps plan and explain. Generated CAD and verified fixture designs are not available in chat yet.</p></div>:messages.map((m,i)=><article key={i} className={`chat-message ${m.role}`}><strong>{m.role==='user'?'You':'LemonCAD'}</strong><p>{m.content}</p></article>)}{sending&&<p className="muted" role="status">Thinking…</p>}<div ref={bottom}/></div>
      <form className="chat-composer" onSubmit={e=>{e.preventDefault();send();}}>{p.model&&<div className="chat-attachment"><Box size={15}/><span>{p.model.name}</span></div>}<label className="sr-only" htmlFor="engineering-message">Message Engineering</label><textarea id="engineering-message" maxLength={8000} value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Describe what you need, or choose a starting point…" onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send();}}}/><div className="composer-actions"><button type="button" className="text-link" onClick={p.onOpen}><Plus size={16}/>Attach part</button><button type="submit" className="button primary" disabled={sending||!draft.trim()||!!p.user&&!enabled} aria-label="Send engineering message"><ArrowUp size={17}/></button></div>{error&&<p role="alert" className="error-text">{error}</p>}<p className="chat-availability">{!ready?'AI chat is not connected yet. You can prepare your prompt and use the tools.':!p.user?'Sign in to chat.':!p.capabilities.includes(p.service)?'A paid engineering entitlement is needed to send messages.':'Messages and attached part metadata are sent to Claude. Completed exchanges are saved to your account history.'}</p></form>
      <button className="chat-pricing text-link" onClick={p.onPricing}>Plans & credits</button>
    </aside>{tab==='tools'&&<div className="engineering-details">{p.details}</div>}
  </section>;
}
