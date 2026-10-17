'use client';
import { useEffect, useRef, useState } from 'react';
import { auth, request, requestResponse, type Profile } from '../lib/client';
import { Billing } from './Billing';

type Capacity={used:number;limit:number|null;remaining:number|null};
type Usage={period_end:string;messages:Capacity;import_sources:Capacity;agents:Capacity};
type LLMUsage={period_start:string;period_end:string;attempts:number;input_tokens:number|null;output_tokens:number|null;
  unknown_input_attempts:number;unknown_output_attempts:number;elapsed_ms:number};

export function Settings({token,profile,owner}:{token:string;profile:Profile;owner:string}) {
  const [confirmation,setConfirmation]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [usage,setUsage]=useState<Usage>(),[usageError,setUsageError]=useState('');
  const [llmUsage,setLLMUsage]=useState<LLMUsage>(),[llmError,setLLMError]=useState('');
  const [exporting,setExporting]=useState(false),[exportError,setExportError]=useState('');
  const exportController=useRef<AbortController|null>(null),identity=useRef({token,owner});
  identity.current={token,owner};
  useEffect(()=>{
    setExporting(false);setExportError('');
    const subscription=auth?.auth.onAuthStateChange((_event,session)=>{
      if(session?.access_token!==token||session?.user.id!==owner)exportController.current?.abort();
    }).data.subscription;
    return()=>{exportController.current?.abort();subscription?.unsubscribe();};
  },[token,owner]);
  function cancelExport(){exportController.current?.abort();exportController.current=null;setExporting(false);}
  async function downloadExport(){
    if(exportController.current&&!exportController.current.signal.aborted)return;
    const controller=new AbortController();exportController.current=controller;
    const current=()=>!controller.signal.aborted&&identity.current.token===token&&identity.current.owner===owner;
    setExporting(true);setExportError('');
    try{
      const response=await requestResponse('/me/export',token,{signal:controller.signal});
      if(response.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase()!=='application/json')throw new Error();
      // Preserva os bytes e os inteiros financeiros sem passar pelo Number do JavaScript.
      const blob=await response.blob();
      if(!current())return;
      const session=await auth?.auth.getSession();
      if(!current()||session?.error||session?.data.session?.access_token!==token||session.data.session.user.id!==owner)return;
      const url=URL.createObjectURL(blob),link=document.createElement('a');
      try{link.href=url;link.download='tato-dados.json';document.body.append(link);link.click();}
      finally{link.remove();setTimeout(()=>URL.revokeObjectURL(url),0);}
    }catch{if(current())setExportError('Não foi possível exportar seus dados. Aguarde e tente novamente.');}
    finally{if(exportController.current===controller){exportController.current=null;if(current())setExporting(false);}}
  }
  useEffect(()=>{
    let active=true;setUsage(undefined);setUsageError('');
    setLLMUsage(undefined);setLLMError('');
    request<Usage>('/me/usage',token).then(value=>{if(active)setUsage(value);})
      .catch(()=>{if(active)setUsageError('Não foi possível consultar o consumo agora.');});
    request<LLMUsage>('/me/llm-usage',token).then(value=>{if(active)setLLMUsage(value);})
      .catch(()=>{if(active)setLLMError('Não foi possível consultar as medições da IA agora.');});
    return()=>{active=false;};
  },[token]);
  async function remove(event:React.FormEvent){event.preventDefault();if(confirmation!=='EXCLUIR')return;cancelExport();setBusy(true);setError('');
    try{
      await request('/me',token,{method:'DELETE',body:JSON.stringify({confirm:true})});
      const current=await auth?.auth.getSession();
      if(current?.data.session?.user.id===owner)await auth?.auth.signOut({scope:'local'});
    }
    catch(e){setError(e instanceof Error?e.message:'Não foi possível excluir. A solicitação pode estar pendente; tente novamente.');}
    finally{setBusy(false);}}
  return <section className="narrow stack"><h1>Sua conta.</h1><div className="panel"><h3>Plano {profile.plan.name}</h3><p>{profile.plan.agents} agente(s) ativo(s). {profile.plan.messages_per_month ?? 'Sem limite de'} mensagens por mês.</p></div>
    <Billing token={token}/>
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
    <section className="panel" aria-label="Exportar dados"><h2>Uma cópia dos seus dados</h2>
      <p>O arquivo JSON contém dados pessoais e financeiros legíveis. Guarde-o em um local seguro e compartilhe apenas com quem você escolher.</p>
      <button disabled={exporting||busy} onClick={downloadExport}>Baixar meus dados</button>
      {exporting&&<><p role="status">Preparando sua exportação…</p><button className="secondary" onClick={cancelExport}>Cancelar exportação</button></>}
      {exportError&&<p className="error" role="alert">{exportError}</p>}
    </section>
    <details className="panel"><summary>Excluir minha conta</summary><p>Esta ação remove seus registros, documentos, conversas e vetores. Não pode ser desfeita.</p>
      <form onSubmit={remove}><label>Digite EXCLUIR para confirmar<input autoComplete="off" value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></label>
        <button disabled={busy||confirmation!=='EXCLUIR'}>Excluir permanentemente</button></form></details>
    {error&&<p className="error" role="alert">{error}</p>}</section>;
}
