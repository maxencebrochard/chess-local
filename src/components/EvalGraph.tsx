// Graphe d'évaluation façon chess.com : aire blanche = avantage blanc,
// pastilles colorées sur les moments clés, tap/clic pour naviguer.
import { useMemo } from 'react'
import { CLASS_META, type GameReview, type MoveClass } from '../lib/review'

const MARKED: MoveClass[] = ['brilliant', 'great', 'blunder', 'missedWin', 'miss', 'mistake']

interface EvalGraphProps {
  review: GameReview
  currentIndex: number // -1 = position initiale
  onSelect: (index: number) => void
}

export function EvalGraph({ review, currentIndex, onSelect }: EvalGraphProps) {
  const W = 100
  const H = 32
  const n = review.winPctSeries.length // coups + 1
  const x = (i: number) => (n > 1 ? (i / (n - 1)) * W : 0)
  const y = (pct: number) => H - (pct / 100) * H

  const areaPath = useMemo(() => {
    const pts = review.winPctSeries.map((pct, i) => `${x(i).toFixed(2)},${y(pct).toFixed(2)}`)
    return `M0,${H} L${pts.join(' L')} L${W},${H} Z`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [review])

  function handlePointer(e: React.PointerEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = (e.clientX - rect.left) / rect.width
    const idx = Math.round(ratio * (n - 1))
    onSelect(Math.max(-1, Math.min(review.moves.length - 1, idx - 1)))
  }

  const cursorX = x(currentIndex + 1)

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className="h-16 w-full cursor-pointer touch-none rounded bg-neutral-900"
      onPointerDown={handlePointer}
      onPointerMove={(e) => e.buttons === 1 && handlePointer(e)}
    >
      <path d={areaPath} fill="#e8e6e3" />
      <line x1="0" y1={H / 2} x2={W} y2={H / 2} stroke="#81b64c" strokeWidth="0.3" strokeDasharray="1,1" />
      <line x1={cursorX} y1="0" x2={cursorX} y2={H} stroke="#81b64c" strokeWidth="0.5" />
      {review.moves.map((m, i) =>
        MARKED.includes(m.class) ? (
          <circle
            key={i}
            cx={x(i + 1)}
            cy={y(review.winPctSeries[i + 1])}
            r="1.4"
            fill={CLASS_META[m.class].color}
            stroke="#262421"
            strokeWidth="0.35"
          />
        ) : null,
      )}
    </svg>
  )
}
