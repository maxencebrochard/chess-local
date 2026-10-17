import type { ReactNode } from 'react'

// Le propriétaire conserve la destination, le state et la sémantique replace/push du retour.
export function PageHeader({ title, description, back, action }: {
  title: ReactNode
  description?: ReactNode
  back?: { label: string; onClick: () => void }
  action?: ReactNode
}) {
  return (
    <header className="mb-4">
      {back && (
        <button type="button" onClick={back.onClick} className="ui-back mb-2 inline-flex min-h-11 min-w-11 cursor-pointer items-center gap-2 rounded-lg px-2 text-sm font-semibold text-muted hover:bg-surface-3 hover:text-white" aria-label={`Retour à ${back.label}`}>
          <span aria-hidden="true">←</span>{back.label}
        </button>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="min-w-0 text-2xl leading-tight font-bold wrap-break-word">{title}</h1>
        {action}
      </div>
      {description && <p className="ui-description mt-2 text-base leading-6 text-muted">{description}</p>}
    </header>
  )
}
