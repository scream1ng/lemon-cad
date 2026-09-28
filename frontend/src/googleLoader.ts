let loading:Promise<void>|null=null;

export function loadGoogle(){
  if(window.google)return Promise.resolve();
  if(!loading)loading=new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='https://accounts.google.com/gsi/client';script.async=true;
    const timer=setTimeout(()=>fail('Google sign-in took too long to load. Try again or use email.'),12000);
    function fail(message:string){clearTimeout(timer);loading=null;script.remove();reject(new Error(message));}
    script.onload=()=>{clearTimeout(timer);if(window.google){loading=null;resolve();}else fail('Google sign-in could not start. Try again or use email.');};
    script.onerror=()=>fail('Google sign-in could not load. Try again or use email.');document.head.append(script);});
  return loading;
}
