'use client';
import { useState } from 'react';
import { cents, money, request, type Summary } from '../lib/client';

export function Overview({ data, token, refresh }: { data: Summary; token: string; refresh: () => Promise<void> }) {
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget, fields = new FormData(form);
    setBusy(true); setError('');
    try {
      await request('/accounts', token, {method:'POST', body:JSON.stringify({
        name: fields.get('name'), kind: fields.get('kind'), opening_date: fields.get('date'),
        opening_balance_cents: cents(String(fields.get('balance'))),
      })});
      await refresh(); form.reset();
    } catch(e) { setError(e instanceof Error ? e.message : 'Não foi possível criar a conta.'); }
    finally { setBusy(false); }
  }
  return <div className="stack"><div><span className="eyebrow">Seu ponto de partida</span><h1>Uma visão tranquila.</h1>
    <p className="muted">Com base nos registros até {data.as_of.split('-').reverse().join('/')}.</p></div>
    <div className="grid"><article className="panel"><span>Saldo das contas</span><h2>{money(data.balance_cents)}</h2><small>Cartões não entram neste saldo.</small></article>
      <article className="panel"><span>Despesas do mês</span><h2>{money(data.expense_cents)}</h2><small>Inclui despesas de cartão registradas.</small></article>
      <article className="panel"><h3>Principais categorias</h3>{data.categories.length ? data.categories.map(c=><p key={c.name}>{c.name} <strong>{money(c.amount_cents)}</strong></p>) : <p>Importe seus primeiros lançamentos.</p>}</article></div>
    <section><h2>Suas contas</h2>{data.accounts.map(a=><div className="row panel" key={a.id}><strong>{a.name}</strong><span>{money(a.balance_cents)}</span></div>)}</section>
    <details className="panel" open={!data.accounts.length}><summary>Adicionar conta ou cartão</summary>
      <p>Informe o saldo imediatamente anterior ao primeiro dia de movimentações que vai importar.</p>
      <form onSubmit={create}><label>Nome<input name="name" maxLength={80} required placeholder="Minha conta" /></label>
        <label>Tipo<select name="kind"><option value="checking">Conta corrente</option><option value="savings">Poupança</option><option value="credit_card">Cartão de crédito</option><option value="cash">Dinheiro</option></select></label>
        <label>Primeiro dia do período<input name="date" type="date" required /></label>
        <label>Saldo de abertura (R$)<input name="balance" inputMode="decimal" defaultValue="0,00" required /></label>
        <button disabled={busy}>Salvar conta</button></form>{error && <p className="error" role="alert">{error}</p>}
    </details></div>;
}
