'use client';
import { useEffect, useRef, useState } from 'react';
import { centsString, money, request, type Account, type TransactionEntry as Entry } from '../lib/client';
import { Reconciliation } from './Reconciliation';

type Page = {items:Entry[];next_cursor:string|null};
const kinds:Record<string,string>={income:'Receita',expense:'Despesa',transfer:'Transferência'};
function editableMoney(value:string){
  const number=BigInt(value),absolute=number<0n?-number:number;
  return `${number<0n?'-':''}${absolute/100n},${String(absolute%100n).padStart(2,'0')}`;
}

export function Transactions({token,accounts,refresh}:{token:string;accounts:Account[];refresh:()=>Promise<void>}){
  const [filters,setFilters]=useState(''),[cursors,setCursors]=useState<(string|null)[]>([null]);
  const [data,setData]=useState<Page>(),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [loading,setLoading]=useState(false),[busy,setBusy]=useState(false),[reload,setReload]=useState(0);
  const [editing,setEditing]=useState<Entry>(),[deleting,setDeleting]=useState<Entry>();
  const [reconciling,setReconciling]=useState<Entry>();
  const reconcileTrigger=useRef<HTMLButtonElement|null>(null),heading=useRef<HTMLHeadingElement>(null);
  const generation=useRef(0);
  const cursor=cursors[cursors.length-1];
  useEffect(()=>{
    const version=++generation.current,controller=new AbortController();
    setLoading(true);setError('');setData(undefined);setEditing(undefined);setDeleting(undefined);setReconciling(undefined);
    const query=new URLSearchParams(filters);if(cursor)query.set('cursor',cursor);
    request<Page>(`/transactions?${query}`,token,{signal:controller.signal}).then(result=>{
      if(version===generation.current)setData(result);
    }).catch(e=>{if(!controller.signal.aborted&&version===generation.current)setError(e.message);})
      .finally(()=>{if(version===generation.current)setLoading(false);});
    return()=>{controller.abort();generation.current++;};
  },[token,filters,cursor,reload]);
  function filter(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();const fields=new FormData(event.currentTarget),query=new URLSearchParams();
    for(const name of ['account_id','start','end','kind']){const value=String(fields.get(name)||'');if(value)query.set(name,value);}
    setCursors([null]);setFilters(query.toString());setReload(value=>value+1);setNotice('');
  }
  async function save(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();if(!editing)return;
    const fields=new FormData(event.currentTarget),version=generation.current;
    setBusy(true);setError('');setNotice('');
    try{
      await request(`/transactions/${editing.id}`,token,{method:'PUT',body:JSON.stringify({
        revision:editing.revision,booked_on:fields.get('date'),description:fields.get('description'),
        amount_cents:centsString(String(fields.get('amount'))),kind:fields.get('kind'),
        category:String(fields.get('category')||'').trim()||null,
      })});
      if(version!==generation.current)return;
      setEditing(undefined);setNotice('Lançamento corrigido.');setReload(value=>value+1);
      try{await refresh();}catch{setNotice('Lançamento corrigido. Atualize o Resumo para conferir os totais.');}
    }catch(e){if(version===generation.current)setError(e instanceof Error?e.message:'Não foi possível salvar.');}
    finally{setBusy(false);}
  }
  async function remove(){
    if(!deleting)return;
    const version=generation.current;setBusy(true);setError('');setNotice('');
    try{
      await request(`/transactions/${deleting.id}`,token,{method:'DELETE',body:JSON.stringify({revision:deleting.revision,confirm:true})});
      if(version!==generation.current)return;
      setDeleting(undefined);setNotice('Lançamento excluído.');setReload(value=>value+1);
      try{await refresh();}catch{setNotice('Lançamento excluído. Atualize o Resumo para conferir os totais.');}
    }catch(e){if(version===generation.current)setError(e instanceof Error?e.message:'Não foi possível excluir.');}
    finally{setBusy(false);}
  }
  async function reconciled(message:string){
    setReconciling(undefined);setNotice(message);setReload(value=>value+1);heading.current?.focus();
    try{await refresh();}catch{setNotice(`${message} Atualize o Resumo para conferir os totais.`);}
  }
  return <section className="stack"><div className="screen-header"><span className="eyebrow">Cada movimento conta</span><h2 ref={heading} tabIndex={-1}>Seus lançamentos.</h2><p>Confira a origem e corrija seus registros. Valores negativos representam saídas.</p></div>
    <form className="panel" onSubmit={filter}><fieldset disabled={busy} className="field-grid">
      <label>Conta<select name="account_id"><option value="">Todas as contas</option>{accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      <label>Tipo<select name="kind"><option value="">Todos os tipos</option>{Object.entries(kinds).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>De<input type="date" name="start"/></label><label>Até<input type="date" name="end"/></label>
      <button type="submit">Filtrar lançamentos</button>
    </fieldset></form>
    {error&&<div role="alert" className="error">{error} <button className="secondary" disabled={busy} onClick={()=>setReload(value=>value+1)}>Recarregar lançamentos</button></div>}
    {notice&&<p role="status" className="notice">{notice}</p>}
    {loading&&<p role="status">Carregando lançamentos…</p>}
    {data&&!data.items.length&&<p className="empty-state">Nenhum lançamento neste filtro. Importe um extrato ou registre uma movimentação na Conversa.</p>}
    {data&&<ul className="transaction-list stack" aria-label="Lançamentos">{data.items.map(item=><li className="panel" key={item.id}>
      <div className="section-heading"><div><strong>{item.description}</strong><p className="muted">{item.booked_on.split('-').reverse().join('/')} · {accounts.find(a=>a.id===item.account_id)?.name||'Conta'} · {kinds[item.kind]}</p></div><strong>{money(item.amount_cents)}</strong></div>
      <p>{item.category||'Sem categoria'}{item.reconciliation_id?' · Vinculado':''}</p><div className="row">{!item.reconciliation_id&&<><button className="secondary" disabled={busy} onClick={()=>{setEditing(item);setDeleting(undefined);setReconciling(undefined);setError('');setNotice('');}}>Editar lançamento</button>
      <button className="secondary" disabled={busy} onClick={()=>{setDeleting(item);setEditing(undefined);setReconciling(undefined);setError('');setNotice('');}}>Excluir lançamento</button></>}
      {(item.reconciliation_id||(BigInt(item.amount_cents)<0n&&accounts.find(a=>a.id===item.account_id)?.kind!=='credit_card'))&&<button className="secondary" disabled={busy} onClick={event=>{reconcileTrigger.current=event.currentTarget;setReconciling(item);setEditing(undefined);setDeleting(undefined);setError('');setNotice('');}}>{item.reconciliation_id?'Ver vínculo':'Reconciliar saída'}</button>}</div>
      {reconciling?.id===item.id&&<Reconciliation key={item.id} entry={item} token={token} accounts={accounts} busy={busy} setBusy={setBusy} complete={reconciled} cancel={()=>{setReconciling(undefined);reconcileTrigger.current?.focus();}}/>}
      {deleting?.id===item.id&&<div className="notice"><h3>Excluir este lançamento?</h3><p>Ele sairá dos saldos e relatórios. A mesma identidade de origem não será importada novamente. Arquivos diferentes sem ID bancário ainda podem sobrepor registros; revise os períodos. Esta ação não tem desfazer.</p><div className="row"><span className="danger-zone"><button disabled={busy} onClick={remove}>{busy?'Excluindo…':'Confirmar exclusão'}</button></span><button className="secondary" disabled={busy} onClick={()=>setDeleting(undefined)}>Cancelar exclusão</button></div></div>}
      {editing?.id===item.id&&<form onSubmit={save} className="stack"><fieldset disabled={busy} className="stack">
        <legend>Corrigir lançamento</legend>
        <label>Descrição<input name="description" defaultValue={item.description} maxLength={5000} required/></label>
        <div className="field-grid"><label>Data<input type="date" name="date" defaultValue={item.booked_on} required/></label>
        <label>Valor em reais<input name="amount" inputMode="decimal" defaultValue={editableMoney(item.amount_cents)} required/></label></div>
        <label>Natureza<select name="kind" defaultValue={item.kind}>{Object.entries(kinds).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
        <label>Categoria<input name="category" defaultValue={item.category||''} maxLength={80}/></label>
        <p className="muted">A correção altera saldos e relatórios. Receita é positiva; despesa é negativa. Transferência sai dos totais de consumo, mas não cria a outra ponta. A conta e a identidade de importação são preservadas.</p>
        <div className="row"><button type="submit">{busy?'Salvando…':'Confirmar correção'}</button><button type="button" className="secondary" onClick={()=>setEditing(undefined)}>Cancelar edição</button></div>
      </fieldset></form>}
    </li>)}</ul>}
    {data&&<nav className="row" aria-label="Páginas de lançamentos"><button className="secondary" disabled={busy||loading||cursors.length===1} onClick={()=>setCursors(values=>values.slice(0,-1))}>Página anterior</button><button className="secondary" disabled={busy||loading||!data.next_cursor} onClick={()=>setCursors(values=>[...values,data.next_cursor])}>Próxima página</button></nav>}
  </section>;
}
