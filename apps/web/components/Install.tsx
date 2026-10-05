'use client';
import { useEffect, useState } from 'react';
type InstallEvent = Event & { prompt:()=>Promise<void>; userChoice:Promise<{outcome:string}> };
export function Install() {
  const [event,setEvent]=useState<InstallEvent>(),[message,setMessage]=useState('');
  useEffect(()=>{
    if(process.env.NODE_ENV==='production' && 'serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(()=>setMessage('O modo offline não está disponível neste navegador.'));
    }
    const handler=(e:Event)=>{e.preventDefault();setEvent(e as InstallEvent);};
    window.addEventListener('beforeinstallprompt',handler);
    return()=>window.removeEventListener('beforeinstallprompt',handler);
  },[]);
  async function install(){if(!event)return;await event.prompt();await event.userChoice;setEvent(undefined);}
  return <aside className="install"><details><summary>Usar como aplicativo</summary><p>No iPhone, abra no Safari e use Compartilhar → Adicionar à Tela de Início. No Android, procure Instalar aplicativo no menu do navegador.</p>{event&&<button onClick={install}>Instalar aplicativo</button>}{message&&<p role="status">{message}</p>}</details></aside>;
}
