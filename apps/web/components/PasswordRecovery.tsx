'use client';
import { useRef, useState } from 'react';
import { auth } from '../lib/client';
import { Mascot } from '../../../packages/mascot/Mascot';

export function PasswordRecovery({ owner, currentOwner, cancel }: { owner: string; currentOwner: string; cancel: () => Promise<void> }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [done, setDone] = useState(false);
  const [exitError, setExitError] = useState('');
  const identity = useRef(currentOwner);
  identity.current = currentOwner;
  const valid = !!owner && owner === currentOwner;
  async function update(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!auth || !valid || busy) return;
    const form = event.currentTarget, data = new FormData(form), password = String(data.get('password'));
    setError('');
    if (password !== data.get('confirmation')) { setError('As senhas precisam ser iguais.'); return; }
    setBusy(true);
    try {
      const session = await auth.auth.getSession();
      if (session.error || session.data.session?.user.id !== owner || identity.current !== owner) throw new Error();
      const result = await auth.auth.updateUser({ password });
      if (result.error || result.data.user?.id !== owner || identity.current !== owner) throw new Error();
      form.reset(); setDone(true);
    } catch { if (identity.current === owner) setError('Não foi possível atualizar a senha. Tente novamente ou solicite outro link.'); }
    finally { setBusy(false); }
  }
  async function leave() {
    setBusy(true); setError(''); setExitError('');
    try { await cancel(); }
    catch { setExitError('Não foi possível sair agora. Tente novamente.'); setBusy(false); }
  }
  return <section className="narrow panel auth-panel"><div className="auth-mascot"><Mascot mood={done?'comemorando':'atento'} size={80}/></div><span className="eyebrow">Seu espaço protegido</span><h1>Definir nova senha.</h1>
    {!valid ? <p role="alert">Link ausente, expirado ou de outra sessão. Solicite um novo link após sair.</p> : done ?
      <p role="status">Senha atualizada. Entre novamente com sua nova senha.</p> :
      <form onSubmit={update} aria-busy={busy}><label>Nova senha<input name="password" type="password" minLength={8} autoComplete="new-password" required disabled={busy}/></label>
        <label>Confirmar nova senha<input name="confirmation" type="password" minLength={8} autoComplete="new-password" required disabled={busy}/></label>
        <button disabled={busy}>Salvar nova senha</button></form>}
    {error && valid && <p role="alert" className="error">{error}</p>}
    {exitError && <p role="alert" className="error">{exitError}</p>}
    <button className="secondary" disabled={busy} onClick={leave}>{done ? 'Voltar ao login' : 'Cancelar e sair'}</button>
  </section>;
}
