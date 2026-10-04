'use client';
import { useEffect, useRef, useState } from 'react';
import identity from '../../../../packages/mascot/identity.json';
import { Login } from '../../components/Login';
import { Overview } from '../../components/Overview';
import { auth, request, type Profile, type Summary } from '../../lib/client';

export default function AppPage() {
  const [token, setToken] = useState(''), [profile, setProfile] = useState<Profile>();
  const [data, setData] = useState<Summary>(), [error, setError] = useState('');
  const generation = useRef(0);
  async function refresh(current = token) {
    const version = generation.current;
    const p = await request<Profile>('/me', current);
    const d = await request<Summary>('/dashboard', current);
    if (version === generation.current) { setProfile(p); setData(d); }
  }
  useEffect(()=> {
    const subscription = auth?.auth.onAuthStateChange((_event, session)=>{
      generation.current++;
      setToken(session?.access_token || ''); setProfile(undefined); setData(undefined); setError('');
    }).data.subscription;
    return ()=>{ generation.current++; subscription?.unsubscribe(); };
  }, []);
  useEffect(()=>{if (token) refresh(token).catch(e=>setError(e.message));}, [token]);
  async function onboarding() {
    try { await request('/me/onboarding', token, {method:'POST',body:JSON.stringify({completed:true})}); await refresh(); }
    catch(e) { setError(e instanceof Error ? e.message : 'Não foi possível continuar.'); }
  }
  return <><header><a className="brand" href="/">{identity.name.toLowerCase()}.</a>
    {token && <nav><span>Plano {profile?.plan.name || '…'}</span><button className="secondary" onClick={()=>auth?.auth.signOut()}>Sair</button></nav>}</header>
    <main id="content">{!token ? <Login/> : <>
      {error && <p role="alert" className="error">{error} <button onClick={()=>refresh().then(()=>setError('')).catch(e=>setError(e.message))}>Tentar novamente</button></p>}
      {!profile && !error && <p role="status">Preparando seu espaço…</p>}
      {profile && !profile.onboarding_completed && <section className="panel"><h2>Você escolhe por onde começar.</h2><p>Cadastre uma conta, importe um extrato e revise a prévia. Não precisamos do seu CPF.</p><button onClick={onboarding}>Entendi, vamos lá</button></section>}
      {data && <Overview data={data} token={token} refresh={refresh}/>}</>}</main></>;
}
