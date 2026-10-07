'use client';
import { useState } from 'react';
import { auth, request, type Profile } from '../lib/client';

export function Settings({token,profile}:{token:string;profile:Profile}) {
  const [confirmation,setConfirmation]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function remove(event:React.FormEvent){event.preventDefault();if(confirmation!=='EXCLUIR')return;setBusy(true);setError('');
    try{await request('/me',token,{method:'DELETE',body:JSON.stringify({confirm:true})});await auth?.auth.signOut({scope:'local'});}
    catch(e){setError(e instanceof Error?e.message:'Não foi possível excluir. A solicitação pode estar pendente; tente novamente.');}
    finally{setBusy(false);}}
  return <section className="narrow stack"><h1>Sua conta.</h1><div className="panel"><h3>Plano {profile.plan.name}</h3><p>{profile.plan.agents} agente(s) ativo(s). {profile.plan.messages_per_month ?? 'Sem limite de'} mensagens por mês.</p><p>Cobrança e mudança de plano ainda não estão disponíveis.</p></div>
    <details className="panel"><summary>Excluir minha conta</summary><p>Esta ação remove seus registros, documentos, conversas e vetores. Não pode ser desfeita.</p>
      <form onSubmit={remove}><label>Digite EXCLUIR para confirmar<input autoComplete="off" value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></label>
        <button disabled={busy||confirmation!=='EXCLUIR'}>Excluir permanentemente</button></form></details>
    {error&&<p className="error" role="alert">{error}</p>}</section>;
}
