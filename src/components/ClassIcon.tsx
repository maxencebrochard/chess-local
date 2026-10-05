// Pastille ronde de classification de coup, style chess.com : fond coloré,
// symbole gras, sombre sur les fonds clairs et blanc sur les fonds sombres (A11Y-5).
// Réutilisée dans tallies, bulle coach, bande de coups, badge sur l'échiquier.
import { CLASS_META, type MoveClass } from '../lib/review'

interface ClassIconProps {
  cls: MoveClass
  // Diamètre exact en px. 18 px est le minimum lisible sur iPhone (listes de coups) ; au-delà,
  // l'appelant choisit la taille qui tient dans la hauteur de sa ligne.
  size?: number
}

const DARK = '#262421'

// Luminance relative (WCAG) d'une couleur #rrggbb.
function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function ClassIcon({ cls, size = 24 }: ClassIconProps) {
  const meta = CLASS_META[cls]
  const px = size
  const isEmoji = cls === 'book' || cls === 'excellent'
  return (
    <span
      role="img"
      aria-label={meta.label}
      data-class-icon={cls}
      className="inline-flex shrink-0 items-center justify-center rounded-full font-black shadow-sm"
      style={{
        width: px,
        height: px,
        background: meta.color,
        color: luminance(meta.color) > 0.25 ? DARK : '#ffffff',
        fontSize: isEmoji ? px * 0.55 : px * 0.62,
        lineHeight: 1,
      }}
    >
      {meta.symbol}
    </span>
  )
}
