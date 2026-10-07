import type { MetadataRoute } from 'next';
import identity from '../../../packages/mascot/identity.json';
export const dynamic = 'force-static';
export default function manifest(): MetadataRoute.Manifest {
  return {name:identity.name,short_name:identity.name,description:identity.tagline,
    start_url:'/app/',scope:'/',display:'standalone',lang:'pt-BR',
    background_color:identity.palette.paper,theme_color:identity.palette.ink,
    icons:[192,512].map(size=>({src:`/icons/${size}.png`,sizes:`${size}x${size}`,type:'image/png',purpose:'any'})),
  };
}
