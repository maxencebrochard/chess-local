// Feuille de confirmation avant une action destructive : dit ce qui va se passer, propose
// d'annuler. Feuille basse sur mobile, centrée dès `md`. Fond ou Échap = annuler. Le focus va
// sur Annuler à l'ouverture et revient à l'élément déclencheur à la fermeture.
import { useEffect, useRef, type ReactNode } from 'react'

interface ConfirmSheetProps {
  title: string
  children: ReactNode
  confirmLabel: string
  cancelLabel?: string
  danger?: boolean
  busy?: boolean // action en cours : boutons gelés, fermeture impossible
  testId?: string // préfixe des data-testid : `<id>-sheet`, `<id>-confirm`, `<id>-cancel`
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmSheet({
  title,
  children,
  confirmLabel,
  cancelLabel = 'Annuler',
  danger = false,
  busy = false,
  testId = 'confirm',
  onConfirm,
  onCancel,
}: ConfirmSheetProps) {
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    cancelRef.current?.focus()
    return () => opener?.focus?.()
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, onCancel])

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 md:items-center"
      onClick={() => !busy && onCancel()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        data-testid={`${testId}-sheet`}
        className="pb-safe flex max-h-[92dvh] w-full max-w-lg flex-col rounded-t-2xl bg-surface-2 outline-none md:max-h-[85dvh] md:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="border-b border-black/30 px-4 py-3 text-lg font-black">{title}</h2>
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4 text-sm text-neutral-300">{children}</div>
        <div className="flex gap-2 border-t border-black/30 p-4">
          <button
            ref={cancelRef}
            data-testid={`${testId}-cancel`}
            onClick={onCancel}
            disabled={busy}
            className="flex-1 cursor-pointer rounded-lg bg-surface-3 py-3 font-semibold text-neutral-200 hover:bg-surface-3/70 disabled:cursor-default disabled:opacity-40"
          >
            {cancelLabel}
          </button>
          <button
            data-testid={`${testId}-confirm`}
            onClick={onConfirm}
            disabled={busy}
            className={`flex-1 cursor-pointer rounded-lg py-3 font-bold text-white disabled:cursor-default disabled:opacity-40 ${
              danger ? 'bg-red-600 hover:bg-red-500' : 'bg-accent hover:bg-accent-hover'
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
