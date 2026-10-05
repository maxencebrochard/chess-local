// Ligne moteur façon chess.com : pastille de score (claire quand les Blancs sont mieux, sombre
// quand les Noirs le sont), puis la suite de coups numérotée, en figurines.
import { Chess } from 'chess.js'
import type { EngineLine } from '../lib/engine'
import { figurine } from '../lib/review'

const MAX_PLIES = 8

// Score côté blanc (les scores UCI sont du point de vue du trait). Mat : « M3 » quand les Blancs
// matent, « -M3 » quand ce sont les Noirs, comme chess.com.
function engineScore(line: EngineLine, turn: 'w' | 'b'): { label: string; whiteBetter: boolean } {
  const sign = turn === 'w' ? 1 : -1
  if (line.scoreMate !== null) {
    const m = sign * line.scoreMate
    const whiteBetter = m > 0
    return { label: `${whiteBetter ? '' : '-'}M${Math.abs(m)}`, whiteBetter }
  }
  const cp = (sign * (line.scoreCp ?? 0)) / 100
  return { label: ((cp > 0 ? '+' : '') + cp.toFixed(2)).replace('.', ','), whiteBetter: cp >= 0 }
}

// « 12. ♘f3 ♞c6 13. ♗b5 », ou « 12… ♞c6 13. ♗b5 » quand les Noirs ont le trait. La numérotation
// part du compteur du FEN : juste aussi depuis une position importée.
function moveText(line: EngineLine, fen: string): string {
  const c = new Chess(fen)
  let num = c.moveNumber()
  const parts: string[] = []
  for (const [i, uci] of line.pv.slice(0, MAX_PLIES).entries()) {
    const color = c.turn()
    let san: string
    try {
      san = c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] }).san
    } catch {
      break
    }
    if (color === 'w') parts.push(`${num}.`)
    else if (i === 0) parts.push(`${num}…`)
    parts.push(figurine(san, color))
    if (color === 'b') num++
  }
  return parts.join(' ')
}

interface EngineLineRowProps {
  line: EngineLine
  fen: string // position analysée (celle de la ligne)
  // Mobile : rangée de 17 px de haut, la zone des deux lignes a une hauteur fixe.
  compact?: boolean
}

export function EngineLineRow({ line, fen, compact = false }: EngineLineRowProps) {
  const turn = fen.split(' ')[1] === 'b' ? 'b' : 'w'
  const { label, whiteBetter } = engineScore(line, turn)
  return (
    <div
      data-engine-line
      className={`flex min-w-0 items-center ${compact ? 'h-[17px] gap-1.5 text-[13px] leading-[17px]' : 'gap-2 text-sm'}`}
    >
      <span
        data-engine-score
        className={`inline-flex shrink-0 items-center justify-center rounded-sm font-bold tabular-nums leading-none ${
          compact ? 'h-[15px] min-w-[42px] px-1 text-[11px]' : 'h-5 min-w-[52px] px-1.5 text-xs'
        } ${whiteBetter ? 'bg-neutral-100 text-neutral-900' : 'bg-neutral-950 text-neutral-100 ring-1 ring-white/15'}`}
      >
        {label}
      </span>
      <span className="min-w-0 truncate text-neutral-300">{moveText(line, fen)}</span>
    </div>
  )
}
