'use client';
import { useEffect, useRef, useState } from 'react';
import { Mascot, type Mood } from '../../../packages/mascot/Mascot';
import { apiUrl, money, request, type Account } from '../lib/client';
import { Import } from './Import';

type Reply = {turn_id:string; message:string; mood:Mood; transaction_id?:string;
  draft?:{description:string; booked_on:string; amount_cents:number; kind:string};
  expense?:{amount_cents:number; source:{start:string; end:string; tool:string}};
  sources:{chunk_id:string; section:string; content:string}[]};
type Question = {request_id:string; question:string; account_id:string|null};
type Turn = {request:Question; response:Reply};

async function stream(question:Question, token:string):Promise<Reply> {
  const response = await fetch(`${apiUrl}/chat/stream`, {method:'POST',cache:'no-store', credentials:'omit',
    headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify(question)});
  if (!response.ok || !response.body) throw new Error('Conversa indisponível. Confira sua sessão e quota.');
  const reader=response.body.getReader(), decoder=new TextDecoder(); let buffer='', reply:Reply|undefined;
  while (true) {
    const {done,value}=await reader.read(); if(done) break;
    buffer+=decoder.decode(value,{stream:true}); let boundary;
    while((boundary=buffer.indexOf('\n\n'))>=0) {
      const event=buffer.slice(0,boundary); buffer=buffer.slice(boundary+2);
      const data=event.split('\n').find(line=>line.startsWith('data: '))?.slice(6);
      if(event.startsWith('event: error')) throw new Error('Não foi possível concluir. Você pode repetir este pedido.');
      if(event.startsWith('event: reply') && data) reply=JSON.parse(data);
    }
  }
  if(!reply) throw new Error('A conexão foi interrompida. Repita o mesmo pedido.');
  return reply;
}

export function Chat({token, accounts, refresh}: {token:string; accounts:Account[]; refresh:()=>Promise<void>}) {
  const [turns,setTurns]=useState<Turn[]>([]), [busy,setBusy]=useState(false), [error,setError]=useState('');
  const [attachment,setAttachment]=useState(false), [pending,setPending]=useState<Question>();
  const bottom=useRef<HTMLDivElement>(null);
  useEffect(()=>{let active=true; request<Turn[]>('/chat',token).then(t=>{if(active)setTurns(current=>[...t.filter(old=>!current.some(item=>item.request.request_id===old.request.request_id)),...current]);}).catch(()=>{if(active)setError('Histórico indisponível.');});return()=>{active=false;};},[token]);
  useEffect(()=>{bottom.current?.scrollIntoView({block:'nearest'});},[turns]);
  async function send(question:Question) {
    setBusy(true);setError('');setPending(question);
    try {const reply=await stream(question,token);setTurns(t=>[...t.filter(x=>x.request.request_id!==question.request_id),{request:question,response:reply}]);setPending(undefined);}
    catch(e){setError(e instanceof Error?e.message:'Conversa indisponível.');}finally{setBusy(false);}
  }
  async function confirm(turn:Turn) {
    setBusy(true);setError('');
    try {const reply=await request<Reply>(`/chat/${turn.response.turn_id}/confirm`,token,{method:'POST',body:JSON.stringify({confirm:true})});
      setTurns(t=>t.map(x=>x.response.turn_id===reply.turn_id?{...x,response:reply}:x));await refresh();}
    catch(e){setError(e instanceof Error?e.message:'Não foi possível confirmar.');}finally{setBusy(false);}
  }
  function submit(event:React.FormEvent<HTMLFormElement>) {
    event.preventDefault();const form=event.currentTarget, data=new FormData(form);
    const question=String(data.get('question')).trim();if(!question)return;
    void send({request_id:crypto.randomUUID(),question,account_id:String(data.get('account_id'))||null});
    (form.elements.namedItem('question') as HTMLTextAreaElement).value='';
  }
  return <section className="stack"><div className="row"><Mascot mood={turns.at(-1)?.response.mood || 'calmo'} size={90}/><div><h2>Vamos conversar.</h2><p className="muted">Pergunte sobre despesas ou conte um novo gasto.</p></div></div>
    <button className="secondary" onClick={()=>setAttachment(!attachment)}>{attachment?'Fechar importação':'Importar um extrato no chat'}</button>
    {attachment && <Import token={token} accounts={accounts} refresh={refresh}/>}
    <div className="conversation" aria-live="polite">{turns.map(turn=><article key={turn.request.request_id}>
      <p className="question">{turn.request.question}</p><div className="answer"><p>{turn.response.message}</p>
        {turn.response.expense && <p><strong>{money(turn.response.expense.amount_cents)}</strong><br/><small>Consulta {turn.response.expense.source.tool} · {turn.response.expense.source.start} até {turn.response.expense.source.end} (fim exclusivo)</small></p>}
        {turn.response.draft && !turn.response.transaction_id && <div className="notice"><p>{turn.response.draft.description} · {turn.response.draft.booked_on} · {money(turn.response.draft.amount_cents)}</p><button disabled={busy} onClick={()=>confirm(turn)}>Confirmar lançamento</button></div>}
        {turn.response.sources?.map(source=><details key={source.chunk_id}><summary>Fonte: {source.section}</summary><p>{source.content}</p><small>Trecho {source.chunk_id}</small></details>)}
      </div></article>)}<div ref={bottom}/></div>
    {busy && <p role="status">Conferindo seus registros…</p>}
    {error && <p role="alert" className="error">{error} {pending && <button disabled={busy} onClick={()=>send(pending)}>Repetir pedido</button>}</p>}
    <form onSubmit={submit}><label>Conta para consulta ou lançamento<select name="account_id"><option value="">Todas (somente consultas)</option>{accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      <label>Sua mensagem<textarea name="question" rows={3} maxLength={500} required placeholder="Quanto gastei este mês?"/></label><button disabled={busy || !!pending}>Enviar mensagem</button>
      {pending && !busy && <button type="button" className="secondary" onClick={()=>setPending(undefined)}>Descartar tentativa</button>}</form></section>;
}
