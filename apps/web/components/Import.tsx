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
      const columns = ['date_column','description_column','amount_column','id_column'] as const;
      const values = columns.map(key=>String(data.get(key) || '').trim());
      if (data.get('kind') === 'csv' && values.some(Boolean)) {
        if (values.slice(0,3).some(value=>!value)) throw new Error('Preencha as colunas de data, descrição e valor.');
        data.set('mapping', JSON.stringify({date_column:values[0],description_column:values[1],
          amount_column:values[2],id_column:values[3] || null,
          decimal_separator:data.get('decimal_separator'),debit_positive:data.get('debit_positive') === 'true'}));
      }
      [...columns,'decimal_separator','debit_positive'].forEach(key=>data.delete(key));
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
        <details><summary>Mapear colunas de CSV personalizado</summary><p>Preencha as três colunas principais para personalizar; deixe todas vazias para detectar um layout conhecido.</p>
          <label>Coluna da data<input name="date_column" maxLength={100} /></label><label>Coluna da descrição<input name="description_column" maxLength={100} /></label><label>Coluna do valor<input name="amount_column" maxLength={100} /></label>
          <label>Coluna do identificador (opcional)<input name="id_column" maxLength={100} /></label>
          <p>Use o identificador estável fornecido pelo banco para reconhecer movimentos repetidos.</p>
          <label>Separador decimal<select name="decimal_separator"><option value=",">Vírgula (12,34)</option><option value=".">Ponto (12.34)</option></select></label>
          <label>Sinal das despesas<select name="debit_positive"><option value="false">Negativo (-12,34)</option><option value="true">Positivo (12,34)</option></select></label>
          <p>Essas opções valem para CSV personalizado. Confira entradas e saídas na prévia.</p></details>
      </fieldset><button disabled={busy}>{busy ? 'Processando…' : 'Revisar prévia'}</button></form>}
    {preview && <section className="panel"><h3>Confira antes de salvar</h3><p>{preview.count} movimentos · {preview.start} a {preview.end}</p>
      <p>Entradas: {money(preview.credits_cents)} · Saídas: {money(preview.debits_cents)}</p>
      <div className="table-wrap"><table><thead><tr><th>Data</th><th>Descrição</th><th>Valor</th></tr></thead><tbody>{preview.entries.map((entry,i)=><tr key={i}><td>{entry.booked_on}</td><td>{entry.description}</td><td>{money(entry.amount_cents)}</td></tr>)}</tbody></table></div>
      {preview.truncated && <p>A tabela mostra somente parte do arquivo.</p>}<p className="notice">{preview.warning}</p>
      <button disabled={busy} onClick={confirm}>Confirmar importação</button></section>}
    {message && <p role="status" className="notice">{message}</p>}</section>;
}
