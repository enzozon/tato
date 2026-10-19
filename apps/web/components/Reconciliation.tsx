'use client';
import { useEffect, useRef, useState } from 'react';
import { money, request, type Account, type TransactionEntry as Entry } from '../lib/client';

type Impact={kind:'transfer'|'card_payment';amount_cents:string;expense_reduction_cents:string;income_reduction_cents:string};
type Candidate={entry:Entry;impact:Impact};
type Pair={id?:string;debit:Entry;credit:Entry;impact:Impact};
type Candidates={source:Entry;candidates:Candidate[];truncated:boolean};

export function Reconciliation({entry,token,accounts,cancel,complete,busy,setBusy}:{entry:Entry;token:string;accounts:Account[];cancel:()=>void;complete:(message:string)=>Promise<void>;busy:boolean;setBusy:(value:boolean)=>void}){
  const [candidates,setCandidates]=useState<Candidates>(),[selected,setSelected]=useState<Pair>();
  const [loading,setLoading]=useState(true),[error,setError]=useState('');
  const generation=useRef(0);
  const region=useRef<HTMLElement>(null);
  useEffect(()=>{if(region.current?.getClientRects().length)region.current.focus();},[selected]);
  useEffect(()=>{
    const version=++generation.current,controller=new AbortController();
    setLoading(true);setError('');setSelected(undefined);setCandidates(undefined);
    const path=entry.reconciliation_id?`/reconciliations/${entry.reconciliation_id}`:`/reconciliations/candidates?debit_id=${entry.id}`;
    request<Pair|Candidates>(path,token,{signal:controller.signal}).then(data=>{
      if(version!==generation.current)return;
      if('candidates' in data)setCandidates(data);else setSelected(data);
    }).catch(e=>{if(!controller.signal.aborted&&version===generation.current)setError(e.message);})
      .finally(()=>{if(version===generation.current)setLoading(false);});
    return()=>{controller.abort();generation.current++;};
  },[entry.id,entry.reconciliation_id,token]);
  async function confirm(){
    if(!selected)return;
    const version=generation.current;setBusy(true);setError('');
    try{
      await request(selected.id?`/reconciliations/${selected.id}`:'/reconciliations',token,{
        method:selected.id?'DELETE':'POST',body:JSON.stringify({
          ...(selected.id?{}:{debit_id:selected.debit.id,credit_id:selected.credit.id}),
          debit_revision:selected.debit.revision,credit_revision:selected.credit.revision,confirm:true,
        }),
      });
      if(version===generation.current)await complete(selected.id?'Reconciliação desfeita.':'Reconciliação confirmada.');
    }catch(e){if(version===generation.current)setError(e instanceof Error?e.message:'Não foi possível confirmar.');}
    finally{setBusy(false);}
  }
  function movement(item:Entry){
    return <div><strong>{item.description}</strong><p>{accounts.find(a=>a.id===item.account_id)?.name||'Conta'} · {item.booked_on.split('-').reverse().join('/')}</p><strong>{money(item.amount_cents)}</strong></div>;
  }
  return <section ref={region} tabIndex={-1} aria-busy={loading||busy} className="notice stack reconciliation-panel" aria-label="Reconciliação de lançamentos">
    <h3>{entry.reconciliation_id?'Vínculo entre movimentos':'Revisar as duas pontas'}</h3>
    <p>Sugestões usam valor e data. Só confirme se os dois registros representam a mesma movimentação entre suas contas.</p>
    {loading&&<p role="status">Buscando os registros…</p>}
    {error&&<p role="alert" className="error">{error} Feche e recarregue a lista se o registro tiver mudado.</p>}
    {candidates&&!selected&&<>
      {movement(candidates.source)}
      {!candidates.candidates.length&&<p>Nenhuma entrada compatível em outra conta. Importe a outra ponta; compras do cartão não são pagamentos de fatura.</p>}
      {candidates.candidates.map(candidate=><article className="panel stack" key={candidate.entry.id}>{movement(candidate.entry)}
        <p>{candidate.impact.kind==='card_payment'?'Possível pagamento de fatura':'Possível transferência interna'}</p>
        <button disabled={busy} onClick={()=>setSelected({debit:candidates.source,credit:candidate.entry,impact:candidate.impact})}>Revisar este par</button>
      </article>)}
      {candidates.truncated&&<p>Lista limitada aos primeiros candidatos. Revise os lançamentos se a entrada esperada não aparecer.</p>}
    </>}
    {selected&&<>
      <div className="field-grid"><div><h4>Saída</h4>{movement(selected.debit)}</div><div><h4>Entrada</h4>{movement(selected.credit)}</div></div>
      <p>{selected.impact.kind==='card_payment'?'Pagamento de fatura':'Transferência interna'}. Valores, datas e saldos permanecem iguais.</p>
      <p>{selected.id?'Ao desfazer, voltam à classificação anterior:':'Deixarão de contar nestes registros:'} {money(selected.impact.expense_reduction_cents)} de despesas e {money(selected.impact.income_reduction_cents)} de receitas.</p>
      <p className="muted">O efeito segue a data de cada registro; podem ser meses diferentes. {selected.id?'Desfazer libera edição e exclusão e não move dinheiro no banco.':'As duas linhas ficarão vinculadas e só poderão ser editadas ou excluídas após desfazer.'}</p>
      <div className="row"><button disabled={busy} onClick={confirm}>{busy?'Confirmando…':selected.id?'Confirmar desfazer':'Confirmar reconciliação'}</button>
      {!selected.id&&<button className="secondary" disabled={busy} onClick={()=>setSelected(undefined)}>Voltar aos candidatos</button>}</div>
    </>}
    <button className="secondary" disabled={busy} onClick={cancel}>Fechar reconciliação</button>
  </section>;
}
