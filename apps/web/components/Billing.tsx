'use client';
import { useEffect, useRef, useState } from 'react';
import { request } from '../lib/client';

type Status = { enabled: boolean; mode: 'test'; can_checkout: boolean; can_portal: boolean; pending_request_id: string | null };
type Checkout = { request_id: string; status: 'pending' | 'paid' | 'canceled'; checkout_url: string | null };

function destination(value: string, portal: boolean): string {
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.hostname !== (portal ? 'billing.stripe.com' : 'checkout.stripe.com') ||
      url.port || url.username || url.password || value.split('/')[2]?.includes('@') ||
      /[\u0000-\u0020\u007f\\]/.test(value) ||
      !(portal ? url.pathname === '/p/session' || url.pathname.startsWith('/p/session/') : url.pathname.startsWith('/c/pay/'))) {
    throw new Error('Destino de cobrança de teste inválido.');
  }
  return url.href;
}

export function Billing({ token }: { token: string }) {
  const [status, setStatus] = useState<Status>(), [error, setError] = useState('');
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  const generation = useRef(0), checkoutId = useRef<string | null>(null), portalId = useRef<string | null>(null);
  useEffect(() => {
    const version = ++generation.current;
    setStatus(undefined); setError(''); setBusy(false); setMessage('');
    request<Status>('/billing/status', token).then(value => {
      if (version !== generation.current) return;
      if (value.pending_request_id) checkoutId.current = value.pending_request_id;
      setStatus(value);
    }).catch(() => { if (version === generation.current) setError('Não foi possível consultar a cobrança de teste.'); });
    return () => { generation.current++; };
  }, [token]);

  async function open(portal: boolean) {
    const allowed = portal ? status?.can_portal : status?.can_checkout;
    if (busy || status?.enabled !== true || status.mode !== 'test' || allowed !== true) return;
    const version = generation.current, id = portal ? portalId : checkoutId;
    id.current ||= crypto.randomUUID();
    setBusy(true); setError(''); setMessage('');
    try {
      if (portal) {
        const result = await request<{ portal_url: string }>('/billing/stripe/portal', token,
          { method: 'POST', body: JSON.stringify({ request_id: id.current }) });
        if (version === generation.current) window.location.assign(destination(result.portal_url, true));
      } else {
        const result = await request<Checkout>('/billing/stripe/checkout', token,
          { method: 'POST', body: JSON.stringify({ request_id: id.current }) });
        if (version !== generation.current) return;
        if (result.checkout_url) window.location.assign(destination(result.checkout_url, false));
        else {
          setMessage(result.status === 'canceled' ? 'Checkout cancelado. Consulte novamente o estado da conta.' :
            'Checkout recebido. O plano depende da validação pelo serviço; o retorno do navegador não ativa o Pro.');
          const current = await request<Status>('/billing/status', token);
          if (version === generation.current) {
            if (current.pending_request_id) checkoutId.current = current.pending_request_id;
            else if (result.status === 'canceled' && current.pending_request_id === null) checkoutId.current = null;
            setStatus(current);
          }
        }
      }
    } catch {
      if (version === generation.current) setError('Não foi possível abrir a cobrança de teste. Tente novamente com o mesmo pedido.');
    } finally { if (version === generation.current) setBusy(false); }
  }

  const enabled = status?.enabled === true && status.mode === 'test';
  return <section className="panel stack" aria-label="Cobrança de teste"><h2>Cobrança de teste</h2>
    <p>Simulação: Pro por R$ 39/mês em modo de teste, sem cobrança real.</p>
    {!status && !error && <p role="status">Consultando disponibilidade…</p>}
    {status && !enabled && <p>Cobrança de teste desativada neste ambiente.</p>}
    {status?.pending_request_id && <p>Há um checkout pendente. Repetir mantém o mesmo pedido.</p>}
    <button disabled={busy || !enabled || status?.can_checkout !== true} onClick={() => open(false)}>Simular assinatura Pro</button>
    <button className="secondary" disabled={busy || !enabled || status?.can_portal !== true} onClick={() => open(true)}>Gerenciar assinatura de teste</button>
    {busy && <p role="status">Preparando ambiente de teste…</p>}
    {message && <p role="status">{message}</p>}{error && <p role="alert" className="error">{error}</p>}
  </section>;
}
