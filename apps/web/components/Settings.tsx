'use client';
import { useEffect, useState } from 'react';
import { auth, request, type Profile } from '../lib/client';

type Capacity={used:number;limit:number|null;remaining:number|null};
type Usage={period_end:string;messages:Capacity;import_sources:Capacity;agents:Capacity};

export function Settings({token,profile}:{token:string;profile:Profile}) {
  const [confirmation,setConfirmation]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [usage,setUsage]=useState<Usage>(),[usageError,setUsageError]=useState('');
  useEffect(()=>{
    let active=true;setUsage(undefined);setUsageError('');
    request<Usage>('/me/usage',token).then(value=>{if(active)setUsage(value);})
      .catch(()=>{if(active)setUsageError('Não foi possível consultar o consumo agora.');});
    return()=>{active=false;};
  },[token]);
  async function remove(event:React.FormEvent){event.preventDefault();if(confirmation!=='EXCLUIR')return;setBusy(true);setError('');
    try{await request('/me',token,{method:'DELETE',body:JSON.stringify({confirm:true})});await auth?.auth.signOut({scope:'local'});}
    catch(e){setError(e instanceof Error?e.message:'Não foi possível excluir. A solicitação pode estar pendente; tente novamente.');}
    finally{setBusy(false);}}
  return <section className="narrow stack"><h1>Sua conta.</h1><div className="panel"><h3>Plano {profile.plan.name}</h3><p>{profile.plan.agents} agente(s) ativo(s). {profile.plan.messages_per_month ?? 'Sem limite de'} mensagens por mês.</p><p>Cobrança e mudança de plano ainda não estão disponíveis.</p></div>
    <section className="panel" aria-label="Consumo do plano"><h2>Uso do seu plano</h2>
      {usage ? <><dl>{([['messages','Mensagens neste mês'],['import_sources','Fontes importadas'],['agents','Agentes ativos']] as const).map(([key,label])=>{
        const item=usage[key];return <div key={key}><dt>{label}</dt><dd>{item.used} usados · {item.limit==null?'sem limite contratual':`${item.remaining} restantes de ${item.limit}`}</dd></div>;
      })}</dl><p>Mensagens reiniciam em {usage.period_end.slice(0,10).split('-').reverse().join('/')} (UTC). Pedidos aceitos que falharam também contam; repetir o mesmo pedido não consome novamente.</p></> : <p role="status">{usageError || 'Consultando consumo…'}</p>}
    </section>
    <details className="panel"><summary>Excluir minha conta</summary><p>Esta ação remove seus registros, documentos, conversas e vetores. Não pode ser desfeita.</p>
      <form onSubmit={remove}><label>Digite EXCLUIR para confirmar<input autoComplete="off" value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></label>
        <button disabled={busy||confirmation!=='EXCLUIR'}>Excluir permanentemente</button></form></details>
    {error&&<p className="error" role="alert">{error}</p>}</section>;
}
