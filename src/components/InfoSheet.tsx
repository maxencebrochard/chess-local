// Feuille de lecture (conseils, plan ou leçon d'une partie) : feuille basse sur mobile, centrée dès
// `md`. Fond, ✕, « Retour à la partie » ou Échap la ferment ; le focus va sur ✕ à l'ouverture et
// revient au déclencheur à la fermeture. Rien ne bouge sous elle : l'échiquier reste en place.
import { useEffect, useRef, type ReactNode } from 'react'

export function InfoSheet({ title, children, onClose, closeLabel = 'Retour à la partie' }: {
  title: string
  children: ReactNode
  onClose: () => void
  closeLabel?: string
}) {
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    return () => opener?.focus?.()
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 md:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        data-testid="info-sheet"
        className="pb-safe flex max-h-[85dvh] w-full max-w-lg flex-col rounded-t-2xl bg-surface-2 md:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center border-b border-black/30 py-1 pr-1 pl-4">
          <h2 className="flex-1 text-lg font-black">{title}</h2>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Fermer"
            className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-2xl leading-none text-neutral-400 hover:bg-surface-3 hover:text-white"
          >
            ✕
          </button>
        </header>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain p-4">
          <p className="text-[15px] leading-snug text-neutral-200">{children}</p>
          <button
            type="button"
            onClick={onClose}
            className="min-h-11 w-full cursor-pointer rounded-lg bg-surface-3 py-2.5 font-semibold text-neutral-200 hover:bg-surface-3/70"
          >
            {closeLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
