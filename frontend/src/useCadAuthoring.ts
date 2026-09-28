import {useRef,useState} from 'react';
import {api,waitJob,type Model} from './api';
import {type CadDocument} from './cadDocument';

export function useCadAuthoring(model:Model|null,snapshot:()=>Model|null,onApply:(model:Model)=>void){
  const [proposal,setProposal]=useState<Model|null>(null),[pending,setPending]=useState(false),[error,setError]=useState(''),[original,setOriginal]=useState(false);
  const [past,setPast]=useState<Model[]>([]),[future,setFuture]=useState<Model[]>([]);
  const generation=useRef(0),job=useRef(''),running=useRef(false),cancelSignal=useRef<AbortController|null>(null);
  async function preview(document:CadDocument){
    if(running.current)return;
    running.current=true;const turn=++generation.current;setPending(true);setError('');setProposal(null);setOriginal(false);
    const controller=new AbortController();cancelSignal.current=controller;
    try{
      const queued=await api('/cad/preview','POST',{document});
      if(turn!==generation.current){await api(`/jobs/${queued.id}/cancel`,'POST');return;}
      job.current=queued.id;
      const result=await waitJob(queued.id,controller.signal);
      if(turn!==generation.current)return;
      const samePart=model?.state?.cad_document?.features[0]?.id===document.features[0].id;
      setProposal({file_id:result.cad_step,name:samePart?model!.name:'Untitled part.step',format:'step',result,editable:true,project:samePart?model!.project:undefined,state:{camera:samePart?snapshot()?.state?.camera:undefined,unit:'mm',dimensions:[],cad_document:result.cad_document,cad_job_id:queued.id}});
    }catch(e){if(turn===generation.current)setError(e instanceof Error?e.message:String(e));}
    finally{if(turn===generation.current){running.current=false;setPending(false);job.current='';}}
  }
  function cancel(){generation.current++;cancelSignal.current?.abort();if(job.current)api(`/jobs/${job.current}/cancel`,'POST').catch(()=>{});job.current='';running.current=false;setPending(false);setProposal(null);setError('');setOriginal(false);}
  function apply(){if(!proposal||running.current)return;const before=snapshot();setPast(items=>before?[...items,before].slice(-30):items);setFuture([]);onApply(proposal);setProposal(null);setOriginal(false);}
  function undo(){if(!past.length||pending||proposal)return;const before=snapshot();const target=past[past.length-1];setPast(past.slice(0,-1));if(before)setFuture([...future,before]);onApply(target);}
  function redo(){if(!future.length||pending||proposal)return;const before=snapshot();const target=future[future.length-1];setFuture(future.slice(0,-1));if(before)setPast([...past,before]);onApply(target);}
  function reset(){cancel();setPast([]);setFuture([]);}
  return {proposal,pending,error,original,setOriginal,preview,cancel,apply,undo,redo,reset,canUndo:past.length>0&&!pending&&!proposal,canRedo:future.length>0&&!pending&&!proposal};
}
