import type { Metadata } from 'next';
import identity from '../../../packages/mascot/identity.json';
import './style.css';

export const metadata: Metadata = {
  title: `${identity.name} · ${identity.tagline}`,
  description: 'Organize suas finanças com importação de extratos e conversas claras.',
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="pt-BR"><body><a className="skip" href="#content">Pular para conteúdo</a>{children}</body></html>;
}
