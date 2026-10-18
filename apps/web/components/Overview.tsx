'use client';
import { useState } from 'react';
import { cents, money, request, type Summary } from '../lib/client';
import { Mascot } from '../../../packages/mascot/Mascot';

export function Overview({ data, token, refresh }: { data: Summary; token: string; refresh: () => Promise<void> }) {
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [refreshFailed, setRefreshFailed] = useState(false);
  async function retryRefresh() {
    setBusy(true);
    try { await refresh(); setRefreshFailed(false); setError(''); }
    catch { setError('Conta criada. Não foi possível atualizar o resumo; repita somente a atualização.'); }
    finally { setBusy(false); }
  }
  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget, fields = new FormData(form);
    setBusy(true); setError(''); setRefreshFailed(false); let saved = false;
    try {
      await request('/accounts', token, {method:'POST', body:JSON.stringify({
        name: fields.get('name'), kind: fields.get('kind'), opening_date: fields.get('date'),
        opening_balance_cents: cents(String(fields.get('balance'))),
      })});
      saved = true; form.reset(); await refresh();
    } catch(e) {
      setRefreshFailed(saved);
      setError(saved ? 'Conta criada. Não foi possível atualizar o resumo; repita somente a atualização.' :
        e instanceof Error ? e.message : 'Não foi possível criar a conta.');
    }
    finally { setBusy(false); }
  }
  return <div className="stack"><div className="screen-heading"><div className="screen-header"><span className="eyebrow">Seu ponto de partida</span><h1>Uma visão tranquila.</h1>
    <p className="muted">Com base nos registros até {data.as_of.split('-').reverse().join('/')}.</p></div>
    <Mascot size={100} mood={!data.accounts.length?'dormindo':BigInt(data.projected_balance_cents??data.balance_cents)<0n?'alerta':'calmo'}/></div>
    <div className="grid metrics"><article className="panel metric-card"><span className="metric-label">Saldo das contas</span><h2 className="metric-value">{money(data.balance_cents)}</h2><small>Cartões não entram neste saldo.</small></article>
      <article className="panel metric-card"><span className="metric-label">Despesas do mês</span><h2 className="metric-value">{money(data.expense_cents)}</h2><small>Inclui despesas de cartão registradas.</small></article>
      <article className="panel metric-card"><span className="metric-label">Estimativa para o fim do mês</span><h2 className="metric-value">{data.projected_balance_cents==null?'Histórico insuficiente':money(data.projected_balance_cents)}</h2><small>Saldo menos projeção linear das despesas das contas. Sem novas receitas e sem cartões.</small></article>
      <article className="panel category-list"><h3>Principais categorias</h3>{data.categories.length ? data.categories.map(c=><p key={c.name}>{c.name} <strong>{money(c.amount_cents)}</strong></p>) : <p>Importe seus primeiros lançamentos.</p>}</article></div>
    <section className="account-list"><div className="section-heading"><h2>Suas contas</h2><span className="status-pill">{data.accounts.length} cadastrada(s)</span></div>{!data.accounts.length&&<p className="empty-state">Seu resumo começa com uma conta. Adicione abaixo e depois importe um extrato.</p>}{data.accounts.map(a=><div className="row panel account-row" key={a.id}><div><strong>{a.name}</strong><small>{a.kind==='credit_card'?'Cartão de crédito':a.kind==='savings'?'Poupança':a.kind==='cash'?'Dinheiro':'Conta corrente'}</small></div><span>{money(a.balance_cents)}</span></div>)}</section>
    <details className="panel" open={!data.accounts.length}><summary>Adicionar conta ou cartão</summary>
      <p>Informe o saldo imediatamente anterior ao primeiro dia de movimentações que vai importar.</p>
      <form onSubmit={create} aria-busy={busy}><label>Nome<input name="name" maxLength={80} required placeholder="Minha conta" /></label>
        <label>Tipo<select name="kind"><option value="checking">Conta corrente</option><option value="savings">Poupança</option><option value="credit_card">Cartão de crédito</option><option value="cash">Dinheiro</option></select></label>
        <label>Primeiro dia do período<input name="date" type="date" required /></label>
        <label>Saldo de abertura (R$)<input name="balance" inputMode="decimal" defaultValue="0,00" required /></label>
        <button disabled={busy}>{busy?'Salvando…':'Salvar conta'}</button></form>{error && <p className="error" role="alert">{error}</p>}
      {refreshFailed && <button className="secondary" disabled={busy} onClick={retryRefresh}>Atualizar resumo</button>}
    </details></div>;
}
