// Bulle du coach façon chess.com : avatar rond + bulle blanche avec pointe,
// en-tête optionnel (pastille de classe, coup en gras, badge d'éval, actions).
import type { ReactNode } from 'react'
import { ClassIcon } from './ClassIcon'
import type { MoveClass } from '../lib/review'

export type CoachMood = 'happy' | 'thinking' | 'worried'

interface CoachBubbleProps {
  cls?: MoveClass
  headline?: string
  evalBadge?: string
  children: ReactNode
  mood?: CoachMood
  // Hauteur dure (en-tête + 3 lignes, 2 sous 700 px de haut pour garder l'échiquier au-dessus
  // du pli) : sur les écrans avec échiquier, la bulle ne fait jamais bouger l'échiquier quand
  // le texte ou l'état change. Le corps défile au besoin.
  fixed?: boolean
  // Boutons dans la rangée d'en-tête, à droite du titre (Réessayer : Solution / Quitter).
  actions?: ReactNode
  // Rangée sous le corps (lien « Voir le cours complet » de la leçon).
  footer?: ReactNode
}

const AVATAR = 48
const MOOD_LABEL: Record<CoachMood, string> = { happy: 'coach content', thinking: 'coach qui réfléchit', worried: 'coach inquiet' }

// Visage vectoriel : même dessin sur tous les écrans, jamais rogné, sans dépendre d'une
// police emoji. Trois humeurs : bouche, sourcils et yeux changent.
export function CoachAvatar({ mood = 'thinking', size = AVATAR }: { mood?: CoachMood; size?: number }) {
  const face = Math.round(size * 0.75)
  const mouth =
    mood === 'happy' ? 'M11 21 Q16 27 21 21'
    : mood === 'worried' ? 'M11 24 Q16 19 21 24'
    : 'M12 22 L20 22'
  const brows =
    mood === 'happy' ? 'M9 11 Q12 9 15 11 M17 11 Q20 9 23 11'
    : mood === 'worried' ? 'M9 10 L15 12 M17 12 L23 10'
    : 'M9 12 L15 11 M17 10 Q20 8 23 10'
  return (
    <span
      data-coach-avatar
      data-mood={mood}
      role="img"
      aria-label={MOOD_LABEL[mood]}
      className="flex shrink-0 items-center justify-center rounded-full bg-gradient-to-b from-neutral-500 to-neutral-700 text-white"
      style={{ width: size, height: size }}
    >
      <svg data-face viewBox="0 0 32 32" width={face} height={face} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
        <circle cx={16} cy={16} r={13} fill="#f5d7b5" stroke="none" />
        <path d={brows} stroke="#3d2b1f" />
        {mood === 'happy' ? (
          <path d="M10 15 Q12 13 14 15 M18 15 Q20 13 22 15" stroke="#3d2b1f" />
        ) : (
          <>
            <circle cx={12} cy={15} r={1.6} fill="#3d2b1f" stroke="none" />
            <circle cx={20} cy={15} r={1.6} fill="#3d2b1f" stroke="none" />
          </>
        )}
        <path d={mouth} stroke="#3d2b1f" />
      </svg>
    </span>
  )
}

// Figurines agrandies dans un texte : ♗e2 reste lisible à côté du gras (REV-16).
const FIG_RE = /([♔♕♖♗♘♚♛♜♝♞])/g
export function FigText({ text }: { text: string }) {
  return (
    <>
      {text.split(FIG_RE).map((part, i) =>
        i % 2 === 1 ? (
          <span key={i} data-figurine className="text-[1.3em] leading-none align-[-0.12em]">{part}</span>
        ) : (
          part
        ),
      )}
    </>
  )
}

export function CoachBubble({ cls, headline, evalBadge, children, mood = 'thinking', fixed = false, actions, footer }: CoachBubbleProps) {
  const showHeader = !!headline || !!cls || !!actions
  return (
    <div className="flex items-start gap-1.5">
      <CoachAvatar mood={mood} />
      <div
        className={`relative flex min-w-0 flex-1 flex-col rounded-2xl bg-white p-2.5 text-neutral-900 shadow-lg ${fixed ? 'h-[116px] [@media(max-height:700px)]:h-24' : ''}`}
      >
        <div className="absolute top-[18px] -left-1.5 h-3 w-3 rotate-45 bg-white" />
        {showHeader && (
          <div className={`mb-1 flex shrink-0 items-center gap-2 ${fixed ? 'h-7' : 'min-h-7'}`}>
            {cls && <ClassIcon cls={cls} size={22} />}
            <span className={`min-w-0 flex-1 text-[15px] leading-tight font-bold ${fixed ? 'truncate' : 'line-clamp-2'}`}>
              {headline && <FigText text={headline} />}
            </span>
            {evalBadge && (
              <span className="shrink-0 rounded-md bg-neutral-700 px-2 py-1 text-sm font-bold text-white">
                {evalBadge}
              </span>
            )}
            {actions && <div className="flex shrink-0 gap-1.5">{actions}</div>}
          </div>
        )}
        <div
          data-coach-body
          className={`text-[15px] leading-snug ${fixed ? 'min-h-0 flex-1 overflow-y-auto' : 'min-h-[42px]'}`}
        >
          {typeof children === 'string' ? <FigText text={children} /> : children}
        </div>
        {footer && <div className="mt-1.5 shrink-0">{footer}</div>}
      </div>
    </div>
  )
}
