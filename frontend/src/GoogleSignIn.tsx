import {useEffect,useRef,useState} from 'react';
import {api} from './api';
import {loadGoogle} from './googleLoader';

declare global{interface Window{google?:{accounts:{id:{initialize:(options:Record<string,unknown>)=>void;renderButton:(element:HTMLElement,options:Record<string,unknown>)=>void}}}}}
export function GoogleSignIn({onSuccess,link=false}:{onSuccess:()=>Promise<void>;link?:boolean}){
  const host=useRef<HTMLDivElement>(null),callback=useRef(onSuccess);callback.current=onSuccess;
  const [status,setStatus]=useState('Loading Google sign-in…'),[error,setError]=useState(''),[retry,setRetry]=useState(0);
  useEffect(()=>{let cancelled=false;setError('');setStatus('Loading Google sign-in…');
    (async()=>{const options=await api('/auth/options','GET',undefined,AbortSignal.timeout(12000));if(cancelled)return;if(!options.google_client_id){setStatus('Google sign-in is being set up. Email sign-in is available below.');return;}
      const [,{nonce}]=await Promise.all([loadGoogle(),api('/google/nonce','GET',undefined,AbortSignal.timeout(12000))]);if(cancelled)return;
      window.google!.accounts.id.initialize({client_id:options.google_client_id,nonce,auto_select:false,callback:async({credential}:{credential:string})=>{if(cancelled)return;setError('');setStatus(link?'Connecting Google…':'Signing in…');try{await api('/google/sign-in','POST',{credential,nonce});await callback.current();}catch(e){if(!cancelled){setError(e instanceof Error?e.message:String(e));setStatus('');}}}});
      if(host.current){host.current.replaceChildren();window.google!.accounts.id.renderButton(host.current,{theme:'outline',size:'large',width:Math.min(360,host.current.clientWidth||300),text:'continue_with',shape:'rectangular'});}setStatus('');
    })().catch(e=>{if(!cancelled){setError(e instanceof Error&&e.name==='TimeoutError'?'Google sign-in took too long. Try again or use email.':e instanceof Error?e.message:String(e));setStatus('');}});
    return()=>{cancelled=true;host.current?.replaceChildren();};
  },[retry,link]);
  return <div className="google-sign-in"><div ref={host}/>{status&&<p className="muted" role="status">{status}</p>}{error&&<><p className="error-text" role="alert">{error}</p><button type="button" className="text-link" onClick={()=>setRetry(v=>v+1)}>Try Google again</button></>}</div>;
}
