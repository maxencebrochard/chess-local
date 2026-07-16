// Bande de coups horizontale (bilan guidé) : numéros, SAN en figurines,
// pastilles de classe, coup courant surligné et centré automatiquement.
import { useEffect, useRef } from 'react'
import { ClassIcon } from './ClassIcon'
import { CLASS_META, figurine, type MoveClass } from '../lib/review'

interface MoveStripProps {
  sans: string[]
  classes: (MoveClass | null)[]
  currentIndex: number
  onSelect: (index: number) => void
  // Trait au premier demi-coup ('b' pour un départ custom où les noirs jouent).
  startTurn?: 'w' | 'b'
}

const SHOWN: MoveClass[] = ['brilliant', 'great', 'best', 'book', 'inaccuracy', 'mistake', 'miss', 'missedWin', 'blunder']

export function MoveStrip({ sans, classes, currentIndex, onSelect, startTurn = 'w' }: MoveStripProps) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    // Scroll horizontal manuel : scrollIntoView scrollerait aussi les
    // conteneurs verticaux ancêtres et rognerait la bulle du coach.
    const strip = ref.current
    const el = strip?.querySelector<HTMLElement>('[data-current="true"]')
    if (!strip || !el) return
    strip.scrollTo({ left: el.offsetLeft - strip.clientWidth / 2 + el.clientWidth / 2, behavior: 'smooth' })
  }, [currentIndex])

  return (
    <div ref={ref} className="flex items-center gap-1.5 overflow-x-auto px-2 py-1.5 [scrollbar-width:none]">
      {sans.map((san, i) => {
        const cls = classes[i]
        return (
          <span key={i} className="flex shrink-0 items-center gap-1">
            {i % 2 === 0 && <span className="text-sm text-neutral-500">{i / 2 + 1}.</span>}
            <button
              data-current={i === currentIndex}
              onClick={() => onSelect(i)}
              className={`flex cursor-pointer items-center gap-1 rounded px-1.5 py-1 text-[15px] font-bold ${
                i === currentIndex
                  ? 'bg-neutral-100 text-neutral-900 underline underline-offset-2'
                  : cls && cls !== 'best' && SHOWN.includes(cls)
                    ? ''
                    : 'text-neutral-200'
              }`}
              style={
                i !== currentIndex && cls && SHOWN.includes(cls) && cls !== 'best' && cls !== 'book'
                  ? { color: clsColor(cls) }
                  : undefined
              }
            >
              {figurine(san, (i % 2 === 0) === (startTurn === 'w') ? 'w' : 'b')}
            </button>
            {cls && SHOWN.includes(cls) && <ClassIcon cls={cls} size={16} />}
          </span>
        )
      })}
    </div>
  )
}

function clsColor(cls: MoveClass): string {
  return CLASS_META[cls].color
}
