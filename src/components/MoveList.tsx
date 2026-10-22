import { useEffect, useRef } from 'react'
import { figurine, type MoveClass } from '../lib/review'
import { ClassIcon } from './ClassIcon'

interface MoveListProps {
  sans: string[]
  currentIndex: number // -1 = position initiale
  onSelect: (index: number) => void
  classes?: (MoveClass | null)[]
  // Trait au premier demi-coup ('b' pour un départ custom où les noirs jouent) : case blanche vide.
  startTurn?: 'w' | 'b'
}

export function MoveList({ sans, currentIndex, onSelect, classes, startTurn = 'w' }: MoveListProps) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    ref.current?.querySelector('[data-current="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [currentIndex])

  const rows: { num: number; white?: number; black?: number }[] = []
  // Décalage d'un demi-coup quand les noirs commencent : l'indice -1 est la case blanche vide.
  const shift = startTurn === 'b' ? 1 : 0
  for (let i = sans.length ? -shift : 0; i < sans.length; i += 2) {
    rows.push({ num: (i + shift) / 2 + 1, white: i >= 0 ? i : undefined, black: i + 1 < sans.length ? i + 1 : undefined })
  }

  const cell = (idx?: number) => {
    if (idx === undefined) return <span className="flex-1" />
    const cls = classes?.[idx]
    const marked = cls && !['best', 'excellent', 'good', 'book'].includes(cls)
    return (
      <button
        data-current={idx === currentIndex}
        onClick={() => onSelect(idx)}
        className={`flex flex-1 cursor-pointer items-center gap-1.5 rounded px-1.5 py-0.5 text-left text-sm font-medium ${
          idx === currentIndex ? 'bg-accent/30 text-white' : 'text-neutral-200 hover:bg-surface-3'
        }`}
      >
        {figurine(sans[idx], (idx + shift) % 2 === 0 ? 'w' : 'b')}
        {marked && <ClassIcon cls={cls} size={18} />}
      </button>
    )
  }

  return (
    <div ref={ref} className="h-full overflow-y-auto overscroll-contain rounded bg-surface-2 p-2">
      {rows.length === 0 && <p className="p-2 text-sm text-neutral-500">Aucun coup joué.</p>}
      {rows.map((r) => (
        <div key={r.num} className="flex items-center gap-1 py-px">
          <span className="w-7 shrink-0 text-right text-xs text-neutral-500">{r.num}.</span>
          {cell(r.white)}
          {cell(r.black)}
        </div>
      ))}
    </div>
  )
}
