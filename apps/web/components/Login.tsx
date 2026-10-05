'use client';
import { useState } from 'react';
import { auth } from '../lib/client';

export function Login() {
  const [signup, setSignup] = useState(false), [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!auth) return;
    const fields = new FormData(event.currentTarget);
    setBusy(true); setMessage('');
    try {
      const credentials = {email: String(fields.get('email')), password: String(fields.get('password'))};
      const { error } = signup ? await auth.auth.signUp({...credentials, options:{emailRedirectTo:`${window.location.origin}/app/`}}) : await auth.auth.signInWithPassword(credentials);
      setMessage(error ? 'Não foi possível entrar. Confira seus dados e a confirmação do e-mail.' : signup ? 'Confira seu e-mail para confirmar o cadastro.' : 'Sessão iniciada.');
    } catch { setMessage('Não foi possível conectar. Confira sua conexão.'); }
    finally { setBusy(false); }
  }
  async function google() {
    if(!auth)return;setBusy(true);setMessage('');
    try {const {error}=await auth.auth.signInWithOAuth({provider:'google',options:{redirectTo:`${window.location.origin}/app/`}});
      if(error)setMessage('Login com Google indisponível neste momento.');
    }catch{setMessage('Não foi possível conectar ao Google.');}finally{setBusy(false);}
  }
  return <section className="narrow panel"><h1>{signup ? 'Vamos começar?' : 'Que bom te ver.'}</h1>
    <p className="muted">Entre para conversar sobre suas finanças.</p>
    {!auth && <p role="status" className="notice">Login ainda não configurado neste ambiente. O responsável precisa configurar o projeto Supabase.</p>}
    <form onSubmit={submit}><label>E-mail<input name="email" type="email" autoComplete="email" required /></label>
      <label>Senha<input name="password" type="password" minLength={8} autoComplete={signup ? 'new-password' : 'current-password'} required /></label>
      <button disabled={busy || !auth}>{busy ? 'Aguarde…' : signup ? 'Criar conta' : 'Entrar'}</button></form>
    {process.env.NEXT_PUBLIC_GOOGLE_AUTH_ENABLED==='true'&&<button disabled={busy||!auth} className="secondary" onClick={google}>Continuar com Google</button>}
    {message && <p role="status">{message}</p>}
    <button className="secondary" onClick={()=>setSignup(!signup)}>{signup ? 'Já tenho conta' : 'Criar conta gratuitamente'}</button>
  </section>;
}
