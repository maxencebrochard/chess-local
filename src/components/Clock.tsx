interface ClockProps {
  ms: number
  active: boolean
  label: string
}

export function Clock({ ms, active, label }: ClockProps) {
  const totalSec = Math.max(0, Math.ceil(ms / 1000))
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  const low = ms < 20000
  const text =
    ms < 10000 && ms > 0
      ? `${min}:${String(sec).padStart(2, '0')}.${Math.floor((ms % 1000) / 100)}`
      : `${min}:${String(sec).padStart(2, '0')}`

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-neutral-400">{label}</span>
      <div
        className={`rounded px-3 py-1 font-mono text-xl font-bold tabular-nums ${
          active ? (low ? 'bg-red-900 text-red-200' : 'bg-neutral-100 text-neutral-900') : 'bg-surface-3 text-neutral-400'
        }`}
      >
        {text}
      </div>
    </div>
  )
}
