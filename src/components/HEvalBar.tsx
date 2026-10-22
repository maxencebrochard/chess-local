// Barre d'évaluation horizontale (sous l'en-tête du bilan) : remplissage
// blanc = avantage blanc. L'étiquette se pose du côté du camp qui mène, toujours sur sa propre
// couleur : à gauche en noir sur le blanc, à droite en blanc sur le noir (à gauche, un petit
// remplissage blanc passait sous un texte blanc et le rendait illisible).
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
        data-eval-label
        className={`absolute top-1/2 -translate-y-1/2 text-xs font-black ${share >= 50 ? 'left-2 text-neutral-900' : 'right-2 text-neutral-100'}`}
      >
        {label}
      </span>
    </div>
  )
}
