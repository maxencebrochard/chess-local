// Bulle du coach façon chess.com : avatar rond + bulle blanche avec pointe,
// en-tête optionnel (pastille de classe, coup en gras, badge d'éval).
import { ClassIcon } from './ClassIcon'
import type { MoveClass } from '../lib/review'

interface CoachBubbleProps {
  cls?: MoveClass
  headline?: string
  evalBadge?: string
  children: React.ReactNode
  mood?: 'happy' | 'thinking' | 'worried'
}

const MOODS = { happy: '😄', thinking: '🤔', worried: '😬' }

export function CoachBubble({ cls, headline, evalBadge, children, mood = 'thinking' }: CoachBubbleProps) {
  return (
    <div className="flex items-start gap-1">
      <div className="relative mt-1 flex h-14 w-14 shrink-0 items-end justify-center overflow-hidden rounded-full bg-gradient-to-b from-neutral-500 to-neutral-700 text-4xl">
        <span className="translate-y-0.5">{MOODS[mood]}</span>
      </div>
      <div className="relative min-w-0 flex-1 rounded-2xl bg-white p-3 text-neutral-900 shadow-lg">
        <div className="absolute top-5 -left-1.5 h-3 w-3 rotate-45 bg-white" />
        {headline && (
          <div className="mb-1 flex items-center gap-2">
            {cls && <ClassIcon cls={cls} size={22} />}
            <span className="min-w-0 flex-1 text-[15px] leading-tight font-bold">{headline}</span>
            {evalBadge && (
              <span className="shrink-0 rounded-md bg-neutral-700 px-2 py-1 text-sm font-bold text-white">
                {evalBadge}
              </span>
            )}
          </div>
        )}
        <div className="text-[15px] leading-snug">{children}</div>
      </div>
    </div>
  )
}
