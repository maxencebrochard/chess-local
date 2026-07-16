// Pastille ronde de classification de coup, style chess.com : fond coloré,
// symbole blanc gras. Réutilisée dans tallies, bulle coach, bande de coups,
// badge sur l'échiquier.
import { CLASS_META, type MoveClass } from '../lib/review'

interface ClassIconProps {
  cls: MoveClass
  size?: number // px
}

export function ClassIcon({ cls, size = 24 }: ClassIconProps) {
  const meta = CLASS_META[cls]
  const isEmoji = cls === 'book' || cls === 'excellent'
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full font-black text-white shadow-sm"
      style={{
        width: size,
        height: size,
        background: meta.color,
        fontSize: isEmoji ? size * 0.55 : cls === 'best' ? size * 0.6 : size * 0.52,
        lineHeight: 1,
      }}
    >
      {meta.symbol}
    </span>
  )
}
