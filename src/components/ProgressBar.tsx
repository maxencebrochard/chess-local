export function ProgressBar({ value, total, label, testId, unit = '' }: {
  value: number; total: number; label: string; testId?: string; unit?: string
}) {
  return (
    <span className="mt-2 flex min-w-0 items-center gap-3">
      <span role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={total} aria-valuenow={value}
        className="h-2 min-w-4 flex-1 overflow-hidden rounded-full bg-surface-3">
        <span className="block h-full rounded-full bg-accent" style={{ width: `${total > 0 ? Math.min(100, Math.max(0, value / total * 100)) : 0}%` }} />
      </span>
      <span data-testid={testId} className="ui-progress-text shrink-0 text-sm font-semibold text-muted tabular-nums">{value}/{total}{unit && ` ${unit}`}</span>
    </span>
  )
}
