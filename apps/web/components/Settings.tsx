'use client';
import { useEffect, useState } from 'react';
import { auth, request, type Profile } from '../lib/client';

type Capacity={used:number;limit:number|null;remaining:number|null};
type Usage={period_end:string;messages:Capacity;import_sources:Capacity;agents:Capacity};
type LLMUsage={period_start:string;period_end:string;attempts:number;input_tokens:number|null;output_tokens:number|null;
  unknown_input_attempts:number;unknown_output_attempts:number;elapsed_ms:number};

export function Settings({token,profile,owner}:{token:string;profile:Profile;owner:string}) {
  const [confirmation,setConfirmation]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [usage,setUsage]=useState<Usage>(),[usageError,setUsageError]=useState('');
  const [llmUsage,setLLMUsage]=useState<LLMUsage>(),[llmError,setLLMError]=useState('');
  useEffect(()=>{
    let active=true;setUsage(undefined);setUsageError('');
    setLLMUsage(undefined);setLLMError('');
    request<Usage>('/me/usage',token).then(value=>{if(active)setUsage(value);})
      .catch(()=>{if(active)setUsageError('Não foi possível consultar o consumo agora.');});
    request<LLMUsage>('/me/llm-usage',token).then(value=>{if(active)setLLMUsage(value);})
      .catch(()=>{if(active)setLLMError('Não foi possível consultar as medições da IA agora.');});
    return()=>{active=false;};
  },[token]);
  async function remove(event:React.FormEvent){event.preventDefault();if(confirmation!=='EXCLUIR')return;setBusy(true);setError('');
    try{
      await request('/me',token,{method:'DELETE',body:JSON.stringify({confirm:true})});
      const current=await auth?.auth.getSession();
      if(current?.data.session?.user.id===owner)await auth?.auth.signOut({scope:'local'});
    }
    catch(e){setError(e instanceof Error?e.message:'Não foi possível excluir. A solicitação pode estar pendente; tente novamente.');}
    finally{setBusy(false);}}
  return <section className="narrow stack"><h1>Sua conta.</h1><div className="panel"><h3>Plano {profile.plan.name}</h3><p>{profile.plan.agents} agente(s) ativo(s). {profile.plan.messages_per_month ?? 'Sem limite de'} mensagens por mês.</p><p>Cobrança e mudança de plano ainda não estão disponíveis.</p></div>
    <section className="panel" aria-label="Consumo do plano"><h2>Uso do seu plano</h2>
      {usage ? <><dl>{([['messages','Mensagens neste mês'],['import_sources','Fontes importadas'],['agents','Agentes ativos']] as const).map(([key,label])=>{
        const item=usage[key];return <div key={key}><dt>{label}</dt><dd>{item.used} usados · {item.limit==null?'sem limite contratual':`${item.remaining} restantes de ${item.limit}`}</dd></div>;
      })}</dl><p>Mensagens reiniciam em {usage.period_end.slice(0,10).split('-').reverse().join('/')} (UTC). Pedidos aceitos que falharam também contam; repetir o mesmo pedido não consome novamente.</p></> : <p role="status">{usageError || 'Consultando consumo…'}</p>}
    </section>
    <section className="panel" aria-label="Medições da IA"><h2>Medições da IA</h2>
      {llmUsage ? <><dl>
        <div><dt>Tentativas neste mês</dt><dd>{llmUsage.attempts}</dd></div>
        <div><dt>Tokens de entrada conhecidos</dt><dd>{llmUsage.input_tokens ?? 'não informado'}</dd></div>
        <div><dt>Tokens de saída conhecidos</dt><dd>{llmUsage.output_tokens ?? 'não informado'}</dd></div>
        <div><dt>Tempo acumulado das tentativas</dt><dd>{llmUsage.elapsed_ms} ms</dd></div>
      </dl><p>Tentativas sem contagem de tokens: {llmUsage.unknown_input_attempts} de entrada e {llmUsage.unknown_output_attempts} de saída.</p>
      <p>Período de {llmUsage.period_start.slice(0,10).split('-').reverse().join('/')} até {llmUsage.period_end.slice(0,10).split('-').reverse().join('/')} (fim exclusivo, UTC).</p></> : <p role="status">{llmError || 'Consultando medições…'}</p>}
      <p>São medições registradas pelo Tato, incluindo tentativas de fallback. Não representam saldo nem quota dos provedores.</p>
    </section>
    <details className="panel"><summary>Excluir minha conta</summary><p>Esta ação remove seus registros, documentos, conversas e vetores. Não pode ser desfeita.</p>
      <form onSubmit={remove}><label>Digite EXCLUIR para confirmar<input autoComplete="off" value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></label>
        <button disabled={busy||confirmation!=='EXCLUIR'}>Excluir permanentemente</button></form></details>
    {error&&<p className="error" role="alert">{error}</p>}</section>;
}
