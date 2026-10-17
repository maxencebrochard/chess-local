import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function EmptyState({ title, children, to, action, replace = false, testId }: {
  title: string; children: ReactNode; to: string; action: string; replace?: boolean; testId?: string
}) {
  return (
    <section data-testid={testId} className="ui-empty rounded-xl bg-surface-2 p-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mt-2 text-base leading-6 text-muted">{children}</p>
      <Link to={to} replace={replace} className="mt-4 inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg bg-surface-3 px-4 py-2 text-sm font-semibold hover:brightness-110">{action}</Link>
    </section>
  )
}
