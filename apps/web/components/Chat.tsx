'use client';
import { useEffect, useRef, useState } from 'react';
import { Mascot, type Mood } from '../../../packages/mascot/Mascot';
import { apiUrl, money, request, type Account } from '../lib/client';
import { Import } from './Import';
import identity from '../../../packages/mascot/identity.json';

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

export function Chat({token, accounts, refresh, active=true}: {token:string; accounts:Account[]; refresh:()=>Promise<void>; active?:boolean}) {
  const [turns,setTurns]=useState<Turn[]>([]), [busy,setBusy]=useState(false), [error,setError]=useState('');
  const [attachment,setAttachment]=useState(false), [pending,setPending]=useState<Question>();
  const messages=useRef<HTMLDivElement>(null), input=useRef<HTMLTextAreaElement>(null);
  const importPanel=useRef<HTMLDivElement>(null);
  const followLatest=useRef(true);
  useEffect(()=>{let active=true; request<Turn[]>('/chat',token).then(t=>{if(active)setTurns(current=>[...t.filter(old=>!current.some(item=>item.request.request_id===old.request.request_id)),...current]);}).catch(()=>{if(active)setError('Histórico indisponível.');});return()=>{active=false;};},[token]);
  useEffect(()=>{const list=messages.current;if(active&&list&&followLatest.current)list.scrollTop=list.scrollHeight;},[turns,busy,active]);
  useEffect(()=>{const list=messages.current,panel=importPanel.current;if(active&&attachment&&list&&panel)list.scrollTop+=panel.getBoundingClientRect().top-list.getBoundingClientRect().top;},[attachment,active]);
  useEffect(()=>{if(attachment)importPanel.current?.focus({preventScroll:true});},[attachment]);
  async function send(question:Question) {
    followLatest.current=true;
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
    event.preventDefault();if(busy || pending)return;const form=event.currentTarget, data=new FormData(form);
    const question=String(data.get('question')).trim();if(!question)return;
    void send({request_id:crypto.randomUUID(),question,account_id:String(data.get('account_id'))||null});
    (form.elements.namedItem('question') as HTMLTextAreaElement).value='';
  }
  const mood=busy?'atento':turns.at(-1)?.response.mood || 'calmo';
  const suggestions=['Quanto gastei este mês?','O que é reserva de emergência?','Quero registrar um gasto'];
  return <section className="chat-space" aria-label="Conversa financeira">
    <div className="chat-thread" ref={messages} role="region" tabIndex={0} aria-label="Mensagens da conversa" onScroll={event=>{const list=event.currentTarget;if(active&&list.clientHeight)followLatest.current=list.scrollHeight-list.scrollTop-list.clientHeight<40;}}>
      {!turns.length && !pending && <div className="chat-welcome">
        <div className="chat-mascot-halo"><Mascot mood={mood} size={136}/></div><span className="eyebrow">Um pouco de clareza, uma conversa de cada vez</span><h2>{identity.messages.web_title}</h2>
        <p>{identity.messages.web_prompt}</p>
      </div>}
      <div className="conversation" aria-live="polite" aria-relevant="additions text">{turns.map(turn=><article key={turn.request.request_id}>
        <p className="question">{turn.request.question}</p>
        <div className="answer"><div className="chat-speaker"><Mascot mood={turn.response.mood} size={36}/><span>{identity.name}</span></div><p>{turn.response.message}</p>
          {turn.response.expense && <p><strong>{money(turn.response.expense.amount_cents)}</strong><br/><small>Consulta {turn.response.expense.source.tool} · {turn.response.expense.source.start} até {turn.response.expense.source.end} (fim exclusivo)</small></p>}
          {turn.response.draft && !turn.response.transaction_id && <div className="notice"><p>{turn.response.draft.description} · {turn.response.draft.booked_on} · {money(turn.response.draft.amount_cents)}</p><button disabled={busy} onClick={()=>confirm(turn)}>Confirmar lançamento</button></div>}
          {turn.response.sources?.map(source=><details key={source.chunk_id}><summary>Fonte: {source.section}</summary><p>{source.content}</p><small>Trecho {source.chunk_id}</small></details>)}
        </div></article>)}
        {pending && <p className="question">{pending.question}</p>}
        {busy && <div className="chat-thinking" role="status"><Mascot mood="atento" size={42}/><span>Conferindo seus registros…</span><span className="thinking-dots" aria-hidden="true"><i/><i/><i/></span></div>}
      </div>
      {attachment && <div className="chat-import" ref={importPanel} role="region" aria-label="Importação no chat" tabIndex={-1}><Import token={token} accounts={accounts} refresh={refresh}/></div>}
    </div>
    <div className="chat-bottom">
      {error && <p role="alert" className="error">{error} {pending && <button disabled={busy} onClick={()=>send(pending)}>Repetir pedido</button>}</p>}
      {!turns.length && !pending && <div className="chat-suggestions" aria-label="Sugestões de conversa">{suggestions.map(question=><button type="button" className="secondary" key={question} onClick={()=>{if(input.current){input.current.value=question;input.current.focus();}}}>{question}</button>)}</div>}
      <form className="chat-composer" onSubmit={submit} aria-busy={busy}>
        <label className="sr-only" htmlFor="chat-question">Sua mensagem</label>
        <textarea id="chat-question" ref={input} name="question" rows={2} maxLength={500} required placeholder={`Converse com ${identity.name}`} onKeyDown={event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();event.currentTarget.form?.requestSubmit();}}}/>
        <div className="chat-tools">
          <button type="button" className="secondary chat-attach" aria-expanded={attachment} onClick={()=>setAttachment(!attachment)} aria-label={attachment?'Fechar importação':'Importar um extrato no chat'} title={attachment?'Fechar importação':'Importar um extrato no chat'}><span aria-hidden="true">{attachment?'×':'+'}</span><span className="chat-attach-label">Extrato</span></button>
          <label className="chat-account"><span className="sr-only">Conta para consulta ou lançamento</span><select name="account_id"><option value="">Todas (somente consultas)</option>{accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
          <button className="chat-send" disabled={busy || !!pending} aria-label="Enviar mensagem" title="Enviar mensagem"><svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5m-6 6 6-6 6 6"/></svg></button>
        </div>
        {pending && !busy && <button type="button" className="secondary" onClick={()=>setPending(undefined)}>Descartar tentativa</button>}
      </form>
      <p className="chat-hint">Revise lançamentos antes de confirmar. Enter envia · Shift + Enter quebra a linha.</p>
    </div>
  </section>;
}
