import identity from './identity.json';

export type Mood = 'calmo' | 'atento' | 'alerta' | 'comemorando' | 'dormindo';
export function Mascot({ mood = 'calmo', size = 180 }: { mood?: Mood; size?: number }) {
  const curled = mood === 'alerta';
  return <svg width={size} height={size} viewBox="0 0 240 240" role="img"
    aria-label={`${identity.name}: ${mood}`} className={`mascot mood-${mood}`}>
    <ellipse cx="120" cy="204" rx="77" ry="9" fill="#173e3520" />
    <g className="breath" stroke="#173e35" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M55 169Q18 165 24 148L69 137" fill="#c87650" />
      <path d="M67 167L58 196H83L92 170M143 169L150 196H175L168 162" fill="#dda87b" />
      <path d="M47 153C35 49 156 31 187 114L190 168Q107 194 47 153Z" fill="#c87650" />
      <path d="M71 69Q57 117 84 173M99 57Q79 120 114 179M128 59Q105 121 147 176M154 72Q133 128 173 174" fill="none" opacity=".6" />
      {curled ? <><circle cx="128" cy="135" r="57" fill="#c87650" /><path d="M99 131q30-30 57 4q-9 41-44 23" fill="none" /></> : <>
        <path d="M157 104L151 62Q180 62 181 97M180 106L194 69Q214 86 203 117" fill="#dda87b" />
        <path d="M147 114Q181 87 208 117L228 149Q210 170 169 164Q142 160 147 114Z" fill="#f1c9a1" />
        {mood === 'dormindo' ? <path d="M176 128q9 8 16 0" fill="none" /> : <circle className="eye" cx="183" cy="129" r="4" fill="#173e35" />}
        <path d="M218 142l10 7-9 4Z" fill="#173e35" />
        <path d="M195 150q7 6 13 0" fill="none" />
      </>}
      {mood === 'comemorando' && <path d="M36 44v16M28 52h16M197 31v16M189 39h16" stroke="#c87650" />}
      {mood === 'atento' && <path d="M209 38v18m0 10v1" />}
    </g>
  </svg>;
}
