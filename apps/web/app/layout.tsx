import type { Metadata, Viewport } from 'next';
import identity from '../../../packages/mascot/identity.json';
import './style.css';
import '../../../packages/mascot/theme.css';
import { Install } from '../components/Install';

export const metadata: Metadata = {
  title: `${identity.name} · ${identity.tagline}`,
  description: 'Organize suas finanças com importação de extratos e conversas claras.',
  appleWebApp: { capable:true, title:identity.name, statusBarStyle:'black-translucent' },
  icons: { apple:'/icons/180.png', icon:'/icons/192.png' },
};
export const viewport: Viewport = { themeColor:identity.palette.paper, colorScheme:'dark' };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="pt-BR"><body><a className="skip" href="#content">Pular para conteúdo</a>{children}<Install/></body></html>;
}
