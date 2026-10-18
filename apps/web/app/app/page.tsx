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
import { Mascot } from '../../../../packages/mascot/Mascot';

const navigation = [
  ['Conversa','M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2v-9.5A8.5 8.5 0 0 1 10.5 4H21Z'],
  ['Resumo','M4 20V10m8 10V4m8 16v-7'],
  ['Importar','M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4'],
  ['Agentes','M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4'],
  ['Conta','M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM4 21v-3a8 8 0 0 1 16 0v3'],
] as const;

export default function AppPage() {
  const [token, setToken] = useState(''), [profile, setProfile] = useState<Profile>();
  const [data, setData] = useState<Summary>(), [error, setError] = useState('');
  const generation = useRef(0);
  const identityId = useRef('');
  const accessToken = useRef('');
  const menuButton = useRef<HTMLButtonElement>(null);
  const recoveryOwner = useRef<string | null>(null);
  const closingRecovery = useRef(false);
  const [recovery, setRecovery] = useState<string | null>(null);
  const [owner, setOwner] = useState('');
  const [tab, setTab] = useState('Conversa'), [menuOpen, setMenuOpen] = useState(false);
  const [visited, setVisited] = useState(['Conversa']);
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
      if (event === 'SIGNED_OUT' && !closingRecovery.current) { recoveryOwner.current = null; setRecovery(null); }
      if (nextToken === accessToken.current && nextOwner === identityId.current) return;
      generation.current++;
      accessToken.current = nextToken;
      if (nextOwner !== identityId.current) {
        identityId.current = nextOwner; setOwner(nextOwner);
        setProfile(undefined); setData(undefined); setTab('Conversa'); setVisited(['Conversa']); setMenuOpen(false);
      }
      setToken(nextToken); setError('');
    }).data.subscription;
    return ()=>{ active = false; generation.current++; subscription?.unsubscribe(); };
  }, []);
  useEffect(()=>{let active=true;if (token && recovery === null) refresh(token).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};}, [token, recovery]);
  async function cancelRecovery() {
    closingRecovery.current = true;
    try {
      const result = await auth?.auth.signOut({scope:'local'});
      if (result?.error) throw result.error;
      recoveryOwner.current = null; setRecovery(null);
      window.history.replaceState(null, '', '/app/');
    } finally { closingRecovery.current = false; }
  }
  async function onboarding() {
    const version = generation.current;
    try { await request('/me/onboarding', token, {method:'POST',body:JSON.stringify({completed:true})}); await refresh(); }
    catch(e) { if (version === generation.current) setError(e instanceof Error ? e.message : 'Não foi possível continuar.'); }
  }
  const signedIn=!!token && recovery === null;
  return <div className={signedIn?`app-layout ${tab==='Conversa'?'chat-active':''}`:'auth-layout'}><header className={signedIn?'app-header':''}><a className="brand" href="/"><span aria-hidden="true"><Mascot size={38}/></span><span>{identity.name.toLowerCase()}.</span></a>
    {signedIn && data && <button ref={menuButton} className="secondary app-menu" aria-controls="app-navigation" aria-expanded={menuOpen} onClick={()=>setMenuOpen(!menuOpen)}>Menu</button>}
    {token && recovery === null && <nav aria-label="Sessão"><span className="status-pill">Plano {profile?.plan.name || '…'}</span><button className="secondary" onClick={()=>auth?.auth.signOut({scope:'local'})}>Sair</button></nav>}</header>
    <main id="content" className={signedIn?'app-main':''}>{recovery !== null ? <PasswordRecovery key={recovery} owner={recovery} currentOwner={owner} cancel={cancelRecovery}/> : !token ? <Login/> : <>
      {error && <p role="alert" className="error">{error} <button onClick={()=>refresh().catch(e=>setError(e.message))}>Tentar novamente</button></p>}
      {!profile && !error && <div className="empty-state" role="status"><Mascot mood="atento" size={80}/><p>Preparando seu espaço…</p></div>}
      {profile && !profile.onboarding_completed && <section className="panel onboarding-panel"><div className="onboarding-mascot"><Mascot scene size={92}/></div><span className="eyebrow">Seu primeiro passo</span><h2>Você escolhe por onde começar.</h2><p>Cadastre uma conta, importe um extrato e revise a prévia. Não precisamos do seu CPF.</p><button onClick={onboarding}>Entendi, vamos lá</button></section>}
      {data && <div className="app-workspace" key={owner}><nav id="app-navigation" onKeyDown={event=>{if(event.key==='Escape'&&menuOpen){setMenuOpen(false);menuButton.current?.focus();}}} className={`app-navigation ${menuOpen?'is-open':''}`} aria-label="Seu espaço">{navigation.map(([name,path])=><button className={tab===name?'':'secondary'} key={name} onClick={()=>{setTab(name);setVisited(t=>t.includes(name)?t:[...t,name]);setMenuOpen(false);if(menuOpen)menuButton.current?.focus();}} aria-current={tab===name?'page':undefined}><svg className="nav-icon" aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={path}/></svg><span className="nav-label">{name}</span></button>)}</nav>
        <div className={tab==='Conversa'?'app-view is-chat':'app-view'}>
          <div hidden={tab!=='Resumo'}><Overview data={data} token={token} refresh={refresh}/></div>
          {visited.includes('Conversa') && <div hidden={tab!=='Conversa'}><Chat token={token} accounts={data.accounts} refresh={refresh} active={tab==='Conversa'}/></div>}
          {visited.includes('Importar') && <div hidden={tab!=='Importar'}><Import token={token} accounts={data.accounts} refresh={refresh}/></div>}
          {tab==='Agentes' && profile && <Agents token={token} accounts={data.accounts} limit={profile.plan.agents}/>}
          {tab==='Conta' && profile && <Settings token={token} profile={profile} owner={owner}/>}
        </div>
      </div>}</>}</main></div>;
}
