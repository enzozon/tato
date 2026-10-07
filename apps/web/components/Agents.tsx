'use client';
import { useEffect, useState } from 'react';
import { cents, money, request, type Account } from '../lib/client';

const kinds = {subscription_watch:'Vigia de assinatura',anomaly:'Desvio de padrão',runway:'Fôlego',goal:'Meta'};
type Kind=keyof typeof kinds;
type Agent={kind:Kind; account_id:string; goal_id:string|null; enabled:boolean; email_enabled:boolean};
type Goal={id:string; description:string; target_cents:number};
type Insight={id:string; read_at:string|null; signal:{message:string; kind:Kind; as_of:string; facts:Record<string,number>}};
const labels:Record<string,string>={balance_cents:'Saldo registrado',target_cents:'Alvo',spent_cents:'Despesas',
  projected_expense_cents:'Projeção de despesas',remaining_days:'Dias restantes',history_total_cents:'Histórico',
  history_months:'Meses de histórico',mean_cents_floor:'Média (arredondada)',previous_cents:'Cobrança anterior',current_cents:'Cobrança atual'};

export function Agents({token,accounts,limit}:{token:string;accounts:Account[];limit:number}) {
  const [agents,setAgents]=useState<Agent[]>([]),[goals,setGoals]=useState<Goal[]>([]),[insights,setInsights]=useState<Insight[]>([]);
  const [kind,setKind]=useState<Kind>('runway'),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function load(){const [a,g,i]=await Promise.all([request<Agent[]>('/agents',token),request<Goal[]>('/goals',token),request<Insight[]>('/insights',token)]);setAgents(a);setGoals(g);setInsights(i);}
  useEffect(()=>{load().catch(()=>setError('Não foi possível carregar seus agentes.'));},[]);
  async function action(work:()=>Promise<unknown>){setBusy(true);setError('');try{await work();await load();}catch(e){setError(e instanceof Error?e.message:'Operação indisponível.');}finally{setBusy(false);}}
  function configure(event:React.FormEvent<HTMLFormElement>){event.preventDefault();const data=new FormData(event.currentTarget);
    void action(()=>request(`/agents/${kind}`,token,{method:'PUT',body:JSON.stringify({account_id:data.get('account_id'),goal_id:kind==='goal'?data.get('goal_id'):null,enabled:true,email_enabled:false})}));}
  function goal(event:React.FormEvent<HTMLFormElement>){event.preventDefault();const data=new FormData(event.currentTarget);
    void action(()=>request('/goals',token,{method:'POST',body:JSON.stringify({description:data.get('description'),target_cents:cents(String(data.get('target'))),due_on:null})}));}
  return <section className="stack"><h1>Um toque na hora certa.</h1><p className="muted">Seu plano permite {limit} agente(s) ativo(s). Os avisos consideram somente os movimentos registrados.</p>
    <div className="grid">{agents.map(a=><article className="panel" key={a.kind}><h3>{kinds[a.kind]}</h3><p>{a.enabled?'Ativo':'Pausado'}</p>
      <button disabled={busy} className="secondary" onClick={()=>action(()=>request(`/agents/${a.kind}`,token,{method:'PUT',body:JSON.stringify({account_id:a.account_id,goal_id:a.goal_id,enabled:!a.enabled,email_enabled:a.email_enabled})}))}>{a.enabled?'Pausar':'Ativar'}</button></article>)}</div>
    <details className="panel"><summary>Configurar um agente</summary>{!accounts.length?<p>Adicione uma conta primeiro.</p>:<form onSubmit={configure}>
      <label>Agente<select value={kind} onChange={e=>setKind(e.target.value as Kind)}>{Object.entries(kinds).map(([k,name])=><option key={k} value={k}>{name}</option>)}</select></label>
      <label>Conta<select name="account_id" required>{accounts.filter(a=>!['runway','goal'].includes(kind)||a.kind!=='credit_card').map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      {kind==='goal'&&<label>Meta<select name="goal_id" required><option value="">Selecione uma meta</option>{goals.map(g=><option key={g.id} value={g.id}>{g.description}</option>)}</select></label>}
      <p>Os avisos aparecem aqui. Notificações por e-mail ainda estão em preparação.</p><button disabled={busy}>Salvar agente</button></form>}</details>
    <details className="panel"><summary>Criar uma meta</summary><form onSubmit={goal}><label>Objetivo<input name="description" maxLength={500} required/></label><label>Valor desejado (R$)<input name="target" inputMode="decimal" required/></label><button disabled={busy}>Salvar meta</button></form></details>
    <h2>Seus avisos</h2>{!insights.length&&<p>Nenhum aviso por enquanto. Eles dependem de histórico suficiente e de uma execução dos agentes.</p>}
    {insights.map(i=><article className="panel" key={i.id}><span className="eyebrow">{kinds[i.signal.kind]} · {i.signal.as_of}</span><h3>{i.signal.message}</h3>
      <dl>{Object.entries(i.signal.facts).map(([key,value])=><div className="row" key={key}><dt>{labels[key]||key}</dt><dd>{key.includes('cents')?money(value):value}</dd></div>)}</dl>
      <small>Fonte: lançamentos registrados. Projeções são estimativas.</small><p>{i.read_at?'Lido':<button disabled={busy} className="secondary" onClick={()=>action(()=>request(`/insights/${i.id}/read`,token,{method:'POST'}))}>Marcar como lido</button>}</p></article>)}
    {error&&<p role="alert" className="error">{error}</p>}</section>;
}
