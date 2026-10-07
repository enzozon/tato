'use client';
import { useEffect, useRef, useState } from 'react';
import identity from '../../../../packages/mascot/identity.json';
import { Login } from '../../components/Login';
import { Overview } from '../../components/Overview';
import { Chat } from '../../components/Chat';
import { Import } from '../../components/Import';
import { Agents } from '../../components/Agents';
import { Settings } from '../../components/Settings';
import { auth, request, type Profile, type Summary } from '../../lib/client';

export default function AppPage() {
  const [token, setToken] = useState(''), [profile, setProfile] = useState<Profile>();
  const [data, setData] = useState<Summary>(), [error, setError] = useState('');
  const generation = useRef(0);
  const identityId = useRef('');
  const accessToken = useRef('');
  const [owner, setOwner] = useState('');
  const [tab, setTab] = useState('Resumo');
  const [visited, setVisited] = useState(['Resumo']);
  async function refresh(current = token) {
    if (current !== accessToken.current) return;
    const version = generation.current;
    try {
      const p = await request<Profile>('/me', current);
      const d = await request<Summary>('/dashboard', current);
      if (version === generation.current) { setProfile(p); setData(d); setError(''); }
    } catch(e) { if (version === generation.current) throw e; }
  }
  useEffect(()=> {
    const subscription = auth?.auth.onAuthStateChange((_event, session)=>{
      const nextToken = session?.access_token || '';
      const nextOwner = session?.user.id || '';
      if (nextToken === accessToken.current && nextOwner === identityId.current) return;
      generation.current++;
      accessToken.current = nextToken;
      if (nextOwner !== identityId.current) {
        identityId.current = nextOwner; setOwner(nextOwner);
        setProfile(undefined); setData(undefined); setTab('Resumo'); setVisited(['Resumo']);
      }
      setToken(nextToken); setError('');
    }).data.subscription;
    return ()=>{ generation.current++; subscription?.unsubscribe(); };
  }, []);
  useEffect(()=>{let active=true;if (token) refresh(token).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};}, [token]);
  async function onboarding() {
    const version = generation.current;
    try { await request('/me/onboarding', token, {method:'POST',body:JSON.stringify({completed:true})}); await refresh(); }
    catch(e) { if (version === generation.current) setError(e instanceof Error ? e.message : 'Não foi possível continuar.'); }
  }
  return <><header><a className="brand" href="/">{identity.name.toLowerCase()}.</a>
    {token && <nav><span>Plano {profile?.plan.name || '…'}</span><button className="secondary" onClick={()=>auth?.auth.signOut({scope:'local'})}>Sair</button></nav>}</header>
    <main id="content">{!token ? <Login/> : <>
      {error && <p role="alert" className="error">{error} <button onClick={()=>refresh().catch(e=>setError(e.message))}>Tentar novamente</button></p>}
      {!profile && !error && <p role="status">Preparando seu espaço…</p>}
      {profile && !profile.onboarding_completed && <section className="panel"><h2>Você escolhe por onde começar.</h2><p>Cadastre uma conta, importe um extrato e revise a prévia. Não precisamos do seu CPF.</p><button onClick={onboarding}>Entendi, vamos lá</button></section>}
      {data && <div key={owner}><nav className="tabs" aria-label="Seu espaço">{['Resumo','Conversa','Importar','Agentes','Conta'].map(name=><button className={tab===name?'':'secondary'} key={name} onClick={()=>{setTab(name);setVisited(t=>t.includes(name)?t:[...t,name]);}} aria-current={tab===name?'page':undefined}>{name}</button>)}</nav>
        <div hidden={tab!=='Resumo'}><Overview data={data} token={token} refresh={refresh}/></div>
        {visited.includes('Conversa') && <div hidden={tab!=='Conversa'}><Chat token={token} accounts={data.accounts} refresh={refresh}/></div>}
        {visited.includes('Importar') && <div hidden={tab!=='Importar'}><Import token={token} accounts={data.accounts} refresh={refresh}/></div>}
        {tab==='Agentes' && profile && <Agents token={token} accounts={data.accounts} limit={profile.plan.agents}/>}
        {tab==='Conta' && profile && <Settings token={token} profile={profile}/>}
      </div>}</>}</main></>;
}
