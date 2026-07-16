// Barre d'évaluation horizontale (sous l'en-tête du bilan) : remplissage
// blanc = avantage blanc, étiquette de score à gauche.
import { winPct } from '../lib/review'

interface HEvalBarProps {
  cp: number | null // point de vue blanc
  mate: number | null
}

export function HEvalBar({ cp, mate }: HEvalBarProps) {
  let share = 50
  let label = '0,00'
  if (mate !== null) {
    share = mate === 0 ? ((cp ?? 0) > 0 ? 100 : 0) : mate > 0 ? 100 : 0
    label = mate === 0 ? '#' : `M${Math.abs(mate)}`
  } else if (cp !== null) {
    share = winPct(cp)
    label = ((cp > 0 ? '+' : '') + (cp / 100).toFixed(2)).replace('.', ',')
  }
  return (
    <div className="relative h-7 w-full overflow-hidden rounded bg-neutral-800">
      <div className="absolute inset-y-0 left-0 bg-neutral-100 transition-all duration-300" style={{ width: `${share}%` }} />
      <span
        className={`absolute top-1/2 left-2 -translate-y-1/2 text-xs font-black ${share > 12 ? 'text-neutral-900' : 'text-neutral-100'}`}
      >
        {label}
      </span>
    </div>
  )
}
