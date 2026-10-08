// Graphiques sobres d'Insights, en SVG/HTML sans bibliothèque : barres horizontales fines à bouts
// arrondis, barre V/N/D empilée avec interstices, courbe de précision par partie. Le texte reste en
// couleur de texte : la couleur ne porte que la marque, jamais seule l'information (chiffre écrit
// à côté, survol par `title`).

const WIN = '#81b64c' // accent de l'app
const DRAW = '#8a8a8a'
const LOSS = '#e2533f'

// Barre de progression fine (0 à `max`), valeur écrite à droite par l'appelant.
export function MeterBar({ value, max = 100, tone = 'accent', title }: { value: number; max?: number; tone?: 'accent' | 'warn' | 'bad' | 'muted'; title?: string }) {
  const w = Math.max(0, Math.min(100, (value / max) * 100))
  const color = tone === 'accent' ? WIN : tone === 'warn' ? '#f7c631' : tone === 'bad' ? LOSS : '#6b6b6b'
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-3" title={title}>
      <div className="h-full rounded-full" style={{ width: `${w}%`, background: color }} />
    </div>
  )
}

// Victoires / nulles / défaites empilées, interstice de 2 px entre segments non vides.
export function WdlBar({ wins, draws, losses, className = '' }: { wins: number; draws: number; losses: number; className?: string }) {
  const n = wins + draws + losses
  if (n === 0) return <div className={`h-2.5 rounded-full bg-surface-3 ${className}`} />
  const parts = [
    { v: wins, c: WIN, t: `${wins} victoire${wins > 1 ? 's' : ''}` },
    { v: draws, c: DRAW, t: `${draws} nulle${draws > 1 ? 's' : ''}` },
    { v: losses, c: LOSS, t: `${losses} défaite${losses > 1 ? 's' : ''}` },
  ].filter((p) => p.v > 0)
  return (
    <div className={`flex h-2.5 gap-[2px] ${className}`} role="img" aria-label={parts.map((p) => p.t).join(', ')}>
      {parts.map((p, i) => (
        <div
          key={i}
          title={p.t}
          className={`h-full ${i === 0 ? 'rounded-l-full' : ''} ${i === parts.length - 1 ? 'rounded-r-full' : ''}`}
          style={{ width: `${(p.v / n) * 100}%`, background: p.c, minWidth: 4 }}
        />
      ))}
    </div>
  )
}

export function WdlLegend({ wins, draws, losses }: { wins: number; draws: number; losses: number }) {
  const dot = (c: string) => <span className="inline-block h-2 w-2 rounded-full" style={{ background: c }} />
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-neutral-300">
      <span className="flex items-center gap-1">{dot(WIN)} {wins} V</span>
      <span className="flex items-center gap-1">{dot(DRAW)} {draws} N</span>
      <span className="flex items-center gap-1">{dot(LOSS)} {losses} D</span>
    </div>
  )
}

// Précision par partie, la plus ancienne à gauche. Un point par partie (couleur du résultat,
// survol : précision et date), la moyenne en pointillé, étiquettes seulement min, max et dernière.
export function AccuracySpark({ points, mean }: { points: { acc: number; result: 'win' | 'draw' | 'loss'; label: string }[]; mean: number | null }) {
  const W = 320
  const H = 96
  const padX = 8
  const padY = 14
  if (points.length === 0) return null
  const lo = Math.max(0, Math.min(...points.map((p) => p.acc)) - 5)
  const hi = Math.min(100, Math.max(...points.map((p) => p.acc)) + 5)
  const x = (i: number) => (points.length === 1 ? W / 2 : padX + (i * (W - 2 * padX)) / (points.length - 1))
  const y = (v: number) => padY + ((hi - v) * (H - 2 * padY)) / Math.max(1, hi - lo)
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.acc).toFixed(1)}`).join(' ')
  const iMin = points.reduce((b, p, i) => (p.acc < points[b].acc ? i : b), 0)
  const iMax = points.reduce((b, p, i) => (p.acc > points[b].acc ? i : b), 0)
  const labelled = [...new Set([iMin, iMax, points.length - 1])]
  const color = (r: string) => (r === 'win' ? WIN : r === 'draw' ? DRAW : LOSS)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img" aria-label="Précision par partie, de la plus ancienne à la plus récente">
      {mean !== null && (
        <line x1={padX} x2={W - padX} y1={y(mean)} y2={y(mean)} stroke="#6b6b6b" strokeWidth={1} strokeDasharray="3 4" />
      )}
      <path d={path} fill="none" stroke="#bdbdbd" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={x(i)} cy={y(p.acc)} r={4} fill={color(p.result)} stroke="var(--color-surface-2, #262421)" strokeWidth={2}>
            <title>{p.label}</title>
          </circle>
          {/* Cible de survol plus grande que la marque. */}
          <circle cx={x(i)} cy={y(p.acc)} r={10} fill="transparent">
            <title>{p.label}</title>
          </circle>
        </g>
      ))}
      {labelled.map((i) => (
        <text
          key={`t${i}`}
          x={Math.min(W - 14, Math.max(14, x(i)))}
          y={i === iMin ? y(points[i].acc) + 12 : y(points[i].acc) - 7}
          textAnchor="middle"
          className="fill-neutral-300 text-[10px] font-semibold"
        >
          {Math.round(points[i].acc)}
        </text>
      ))}
    </svg>
  )
}
