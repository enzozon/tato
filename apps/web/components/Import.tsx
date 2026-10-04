'use client';
import { useState } from 'react';
import { money, request, type Account } from '../lib/client';

type Preview = {count:number; start:string; end:string; credits_cents:number; debits_cents:number;
  receipt:string; warning:string; truncated:boolean;
  entries:{booked_on:string; description:string; amount_cents:number}[]};
export function Import({token, accounts, refresh}: {token:string; accounts:Account[]; refresh:()=>Promise<void>}) {
  const [preview, setPreview] = useState<Preview>(), [payload, setPayload] = useState<FormData>();
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  async function inspect(event:React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage(''); setPreview(undefined);
    const data = new FormData(event.currentTarget), file = data.get('file') as File;
    try {
      if (!file.size || file.size > 2 * 1024 * 1024) throw new Error('Escolha um arquivo de até 2 MiB.');
      const mapping = String(data.get('date_column') || '');
      if (mapping) data.set('mapping', JSON.stringify({date_column:mapping,
        description_column:data.get('description_column'), amount_column:data.get('amount_column')}));
      ['date_column','description_column','amount_column'].forEach(k=>data.delete(k));
      const result = await request<Preview>('/import/preview',token,{method:'POST',body:data});
      setPayload(data); setPreview(result);
    } catch(e) {setMessage(e instanceof Error ? e.message : 'Não foi possível ler o arquivo.');}
    finally {setBusy(false);}
  }
  async function confirm() {
    if (!payload || !preview) return; setBusy(true); setMessage('');
    try {
      payload.set('receipt',preview.receipt);
      const result = await request<{inserted:number; duplicates:number; warning?:string}>('/import/confirm',token,{method:'POST',body:payload});
      setMessage(`${result.inserted} lançamentos importados; ${result.duplicates} duplicados ignorados. ${result.warning || ''}`);
      setPreview(undefined); setPayload(undefined); await refresh();
    } catch(e) {setMessage(e instanceof Error ? e.message : 'Importação indisponível.');}
    finally {setBusy(false);}
  }
  return <section className="stack"><h2>Traga seus movimentos.</h2>
    <p className="muted">CSV, OFX ou PDF compatível. Contas PicPay e Banestes validadas; faturas e Sicoob ainda pendentes.</p>
    {!accounts.length ? <p>Adicione uma conta no resumo antes de importar.</p> : <form onSubmit={inspect} onChange={()=>{setPreview(undefined);setPayload(undefined);}}>
      <fieldset disabled={busy}><label>Conta de destino<select name="account_id">{accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
        <label>Formato<select name="kind"><option value="csv">CSV</option><option value="ofx">OFX</option><option value="pdf">PDF</option></select></label>
        <label>Extrato ou fatura<input name="file" type="file" accept=".csv,.ofx,.pdf" required /></label>
        <details><summary>Mapear colunas de CSV personalizado</summary><p>Deixe vazio para detectar um layout conhecido. Valores negativos representam despesas.</p>
          <label>Coluna da data<input name="date_column" /></label><label>Coluna da descrição<input name="description_column" /></label><label>Coluna do valor<input name="amount_column" /></label></details>
      </fieldset><button disabled={busy}>{busy ? 'Processando…' : 'Revisar prévia'}</button></form>}
    {preview && <section className="panel"><h3>Confira antes de salvar</h3><p>{preview.count} movimentos · {preview.start} a {preview.end}</p>
      <p>Entradas: {money(preview.credits_cents)} · Saídas: {money(preview.debits_cents)}</p>
      <div className="table-wrap"><table><thead><tr><th>Data</th><th>Descrição</th><th>Valor</th></tr></thead><tbody>{preview.entries.map((entry,i)=><tr key={i}><td>{entry.booked_on}</td><td>{entry.description}</td><td>{money(entry.amount_cents)}</td></tr>)}</tbody></table></div>
      {preview.truncated && <p>A tabela mostra somente parte do arquivo.</p>}<p className="notice">{preview.warning}</p>
      <button disabled={busy} onClick={confirm}>Confirmar importação</button></section>}
    {message && <p role="status" className="notice">{message}</p>}</section>;
}
