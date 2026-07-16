import { useEffect, useRef } from 'react'
import { CLASS_META, type MoveClass } from '../lib/review'

interface MoveListProps {
  sans: string[]
  currentIndex: number // -1 = position initiale
  onSelect: (index: number) => void
  classes?: (MoveClass | null)[]
}

export function MoveList({ sans, currentIndex, onSelect, classes }: MoveListProps) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    ref.current?.querySelector('[data-current="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [currentIndex])

  const rows: { num: number; white?: number; black?: number }[] = []
  for (let i = 0; i < sans.length; i += 2) {
    rows.push({ num: i / 2 + 1, white: i, black: i + 1 < sans.length ? i + 1 : undefined })
  }

  const cell = (idx?: number) => {
    if (idx === undefined) return <span className="flex-1" />
    const cls = classes?.[idx]
    const meta = cls ? CLASS_META[cls] : null
    return (
      <button
        data-current={idx === currentIndex}
        onClick={() => onSelect(idx)}
        className={`flex-1 cursor-pointer rounded px-1.5 py-0.5 text-left text-sm font-medium ${
          idx === currentIndex ? 'bg-accent/30 text-white' : 'text-neutral-200 hover:bg-surface-3'
        }`}
      >
        {sans[idx]}
        {meta && cls !== 'book' && cls !== 'best' && cls !== 'excellent' && cls !== 'good' && (
          <span className="ml-1 text-xs font-bold" style={{ color: meta.color }}>
            {meta.symbol}
          </span>
        )}
      </button>
    )
  }

  return (
    <div ref={ref} className="h-full overflow-y-auto rounded bg-surface-2 p-2">
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
