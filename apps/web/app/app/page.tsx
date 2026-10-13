'use client';
import { useEffect, useRef, useState } from 'react';
import identity from '../../../../packages/mascot/identity.json';
import { Login } from '../../components/Login';
import { PasswordRecovery } from '../../components/PasswordRecovery';
import { Overview } from '../../components/Overview';
import { Chat } from '../../components/Chat';
import { Import } from '../../components/Import';
import { Agents } from '../../components/Agents';
import { Settings } from '../../components/Settings';
import { auth, recoveryIdentity, request, type Profile, type Summary } from '../../lib/client';

export default function AppPage() {
  const [token, setToken] = useState(''), [profile, setProfile] = useState<Profile>();
  const [data, setData] = useState<Summary>(), [error, setError] = useState('');
  const generation = useRef(0);
  const identityId = useRef('');
  const accessToken = useRef('');
  const recoveryOwner = useRef<string | null>(null);
  const [recovery, setRecovery] = useState<string | null>(null);
  const [owner, setOwner] = useState('');
  const [tab, setTab] = useState('Resumo');
  const [visited, setVisited] = useState(['Resumo']);
  async function refresh(current = token) {
    if (current !== accessToken.current || recoveryOwner.current !== null) return;
    const version = generation.current;
    try {
      const p = await request<Profile>('/me', current);
      const d = await request<Summary>('/dashboard', current);
      if (version === generation.current) { setProfile(p); setData(d); setError(''); }
    } catch(e) { if (version === generation.current) throw e; }
  }
  useEffect(()=> {
    const callbackUrl = window.location.href;
    let active = true;
    function clearCallback() {
      if (!active || window.location.href !== callbackUrl) return;
      const url = new URL(callbackUrl), fragment = new URLSearchParams(url.hash.slice(1));
      const keys = ['access_token','refresh_token','provider_token','provider_refresh_token',
        'code','error','error_code','error_description','expires_in','expires_at','token_type','type'];
      let changed = keys.some(key => fragment.has(key));
      for (const key of keys) if (url.searchParams.has(key)) { url.searchParams.delete(key); changed = true; }
      if (changed) window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}`);
    }
    auth?.auth.initialize().then(clearCallback, clearCallback);
    const captured = recoveryIdentity();
    if (captured || new URLSearchParams(window.location.search).get('recovery') === '1') {
      recoveryOwner.current = captured || ''; setRecovery(recoveryOwner.current);
      if (captured) window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
    }
    const subscription = auth?.auth.onAuthStateChange((event, session)=>{
      const nextToken = session?.access_token || '';
      const nextOwner = session?.user.id || '';
      if (event === 'PASSWORD_RECOVERY' && nextOwner) {
        recoveryOwner.current ||= nextOwner; setRecovery(recoveryOwner.current);
        window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
        generation.current++; setProfile(undefined); setData(undefined);
      }
      if (event === 'SIGNED_OUT') { recoveryOwner.current = null; setRecovery(null); }
      if (nextToken === accessToken.current && nextOwner === identityId.current) return;
      generation.current++;
      accessToken.current = nextToken;
      if (nextOwner !== identityId.current) {
        identityId.current = nextOwner; setOwner(nextOwner);
        setProfile(undefined); setData(undefined); setTab('Resumo'); setVisited(['Resumo']);
      }
      setToken(nextToken); setError('');
    }).data.subscription;
    return ()=>{ active = false; generation.current++; subscription?.unsubscribe(); };
  }, []);
  useEffect(()=>{let active=true;if (token && recovery === null) refresh(token).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};}, [token, recovery]);
  async function cancelRecovery() {
    const result = await auth?.auth.signOut({scope:'local'});
    if (result?.error) throw result.error;
    recoveryOwner.current = null; setRecovery(null);
    window.history.replaceState(null, '', '/app/');
  }
  async function onboarding() {
    const version = generation.current;
    try { await request('/me/onboarding', token, {method:'POST',body:JSON.stringify({completed:true})}); await refresh(); }
    catch(e) { if (version === generation.current) setError(e instanceof Error ? e.message : 'Não foi possível continuar.'); }
  }
  return <><header><a className="brand" href="/">{identity.name.toLowerCase()}.</a>
    {token && recovery === null && <nav><span>Plano {profile?.plan.name || '…'}</span><button className="secondary" onClick={()=>auth?.auth.signOut({scope:'local'})}>Sair</button></nav>}</header>
    <main id="content">{recovery !== null ? <PasswordRecovery key={recovery} owner={recovery} currentOwner={owner} cancel={cancelRecovery}/> : !token ? <Login/> : <>
      {error && <p role="alert" className="error">{error} <button onClick={()=>refresh().catch(e=>setError(e.message))}>Tentar novamente</button></p>}
      {!profile && !error && <p role="status">Preparando seu espaço…</p>}
      {profile && !profile.onboarding_completed && <section className="panel"><h2>Você escolhe por onde começar.</h2><p>Cadastre uma conta, importe um extrato e revise a prévia. Não precisamos do seu CPF.</p><button onClick={onboarding}>Entendi, vamos lá</button></section>}
      {data && <div key={owner}><nav className="tabs" aria-label="Seu espaço">{['Resumo','Conversa','Importar','Agentes','Conta'].map(name=><button className={tab===name?'':'secondary'} key={name} onClick={()=>{setTab(name);setVisited(t=>t.includes(name)?t:[...t,name]);}} aria-current={tab===name?'page':undefined}>{name}</button>)}</nav>
        <div hidden={tab!=='Resumo'}><Overview data={data} token={token} refresh={refresh}/></div>
        {visited.includes('Conversa') && <div hidden={tab!=='Conversa'}><Chat token={token} accounts={data.accounts} refresh={refresh}/></div>}
        {visited.includes('Importar') && <div hidden={tab!=='Importar'}><Import token={token} accounts={data.accounts} refresh={refresh}/></div>}
        {tab==='Agentes' && profile && <Agents token={token} accounts={data.accounts} limit={profile.plan.agents}/>}
        {tab==='Conta' && profile && <Settings token={token} profile={profile} owner={owner}/>}
      </div>}</>}</main></>;
}
