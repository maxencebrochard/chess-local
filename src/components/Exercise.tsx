// Habillage commun des exercices enchaînés (maquette « Exercice type » de docs/ux-refonte.md) :
// écran immersif, en-tête (quitter, titre, progression de la série), scène où l'échiquier prend
// la place restante, et zone de décision réservée sous lui (consigne avant le coup, verdict et
// actions après). Purement présentationnel : aucun score, aucune écriture, aucune navigation.
// Utilisé par la séance d'Apprendre et la révision espacée ; le lot 8 l'étend à PositionGame et
// aux cours.
import type { ComponentProps, ReactNode } from 'react'
import { Cta } from './Cta'

const NB = ' '

// Plein écran au-dessus de la navigation, zones sûres comprises. La colonne a une hauteur
// définie (h-full) : la scène peut ainsi dimensionner l'échiquier sur la hauteur restante.
export function ExerciseScreen({ children, overlay, hidden, ...column }: ComponentProps<'div'> & {
  overlay?: ReactNode // calque posé par-dessus (enregistrement en attente)
  hidden?: boolean // colonne inerte et invisible sous le calque
}) {
  return (
    <div className="pt-safe pb-safe fixed inset-0 z-40 overflow-y-auto overscroll-contain bg-surface">
      {overlay}
      <div
        {...column}
        className="mx-auto flex h-full max-w-2xl flex-col"
        inert={hidden}
        style={hidden ? { visibility: 'hidden' } : undefined}
      >
        {children}
      </div>
    </div>
  )
}

// `done` : exercices déjà jugés de la série (barre) ; `index`/`total` : position affichée « n/N ».
export function ExerciseHeader({ title, index, total, done, onClose, closeLabel, action }: {
  title: ReactNode
  index: number
  total: number
  done: number
  onClose: () => void
  closeLabel: string
  action?: ReactNode // bouton rond de 44 px à droite (« ? » du cours)
}) {
  const pct = total > 0 ? Math.min(100, Math.max(0, (done / total) * 100)) : 0
  return (
    <div data-exercise-header className="shrink-0">
      <header className="flex items-center px-3 py-1">
        <button
          type="button"
          onClick={onClose}
          aria-label={closeLabel}
          className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-2xl leading-none text-neutral-400 hover:bg-surface-3 hover:text-white"
        >
          ✕
        </button>
        <h1 className="min-w-0 flex-1 truncate text-center text-lg font-black">
          {title}
          <span className="ml-2 text-sm font-semibold text-neutral-400 tabular-nums">
            {index}/{total}
          </span>
        </h1>
        {action ?? <span className="w-11 shrink-0" />}
      </header>
      <div
        role="progressbar"
        aria-label="Progression de la série"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={done}
        aria-valuetext={`${done} sur ${total} terminé${done > 1 ? 's' : ''}`}
        className="mx-3 h-1 overflow-hidden rounded-full bg-surface-3"
      >
        <span className="block h-full rounded-full bg-accent transition-[width] duration-300 motion-reduce:transition-none" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

// Bouton rond d'en-tête (même gabarit que la croix).
export function ExerciseHeaderButton(props: ComponentProps<'button'>) {
  return (
    <button
      type="button"
      {...props}
      className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-lg font-black text-neutral-400 hover:bg-surface-3 hover:text-white"
    />
  )
}

// Scène : une colonne de la largeur de l'échiquier, centrée : `above` (barre d'éval de 28 px,
// hauteur réservée), échiquier, zone de décision de hauteur fixe, `below` (options après le
// verdict, qui peuvent passer sous le pli). L'échiquier est le plus grand carré qui laisse la
// zone de décision visible (index.css, `.exercise-stage`) : rien de ce qui change au verdict ne
// le déplace ni ne le redimensionne.
export function ExerciseStage({ above, children, feedback, below }: {
  above?: ReactNode
  children: ReactNode // l'échiquier
  feedback: ReactNode // ExerciseFeedback
  below?: ReactNode
}) {
  return (
    <div className={`exercise-stage min-h-0 flex-1 pt-2 ${above ? 'exercise-stage-above' : ''}`}>
      <div className="exercise-column" data-exercise-column>
        {above && <div className="exercise-above">{above}</div>}
        <div className="exercise-board" data-exercise-board>
          {children}
        </div>
        {feedback}
        {/* GoFurtherRow porte son propre px-3 : -mx-1.5 l’aligne sur le texte de la zone. */}
        {below && <div className="-mx-1.5 pt-2">{below}</div>}
      </div>
    </div>
  )
}

export interface ExerciseVerdict {
  ok: boolean
  reason: ReactNode // une phrase : ce qui s'est passé et quoi faire ensuite
  note?: ReactNode // à droite du verdict : variation de classement, prochaine échéance
}

// Zone de décision, de hauteur fixe sous l'échiquier. Avant le verdict : la consigne (`prompt`).
// Après : « ✓ Réussi » ou « À revoir » et une explication, jamais un verdict seul (principe 9),
// puis les actions. Une réussite propose Suivant en principal, un échec Réessayer ; Analyser et
// Pourquoi ? (s'il est fourni) restent secondaires.
export function ExerciseFeedback({ verdict, prompt, onNext, onRetry, onAnalyse, onWhy }: {
  verdict: ExerciseVerdict | null
  prompt: ReactNode
  onNext: () => void
  onRetry: () => void
  onAnalyse: () => void
  onWhy?: () => void
}) {
  if (!verdict) {
    return (
      <div data-exercise-feedback="prompt" className="exercise-zone px-1.5 pt-2">
        <div data-exercise-prompt className="rounded-xl bg-surface-2 px-3 py-2 text-sm leading-5 text-neutral-200">
          {prompt}
        </div>
      </div>
    )
  }
  const next = { label: 'Suivant', icon: '→', onClick: onNext }
  const retry = { label: 'Réessayer', icon: '↺', onClick: onRetry }
  const [primary, first] = verdict.ok ? [next, retry] : [retry, next]
  const secondary = [first, { label: 'Analyser', icon: '♞', onClick: onAnalyse }]
  if (onWhy) secondary.push({ label: `Pourquoi${NB}?`, icon: '💡', onClick: onWhy })
  return (
    <div data-exercise-feedback={verdict.ok ? 'success' : 'review'} className="exercise-zone px-1.5 pt-2">
      <div role="status">
        <p className="flex h-6 items-baseline gap-2">
          <span data-exercise-verdict className={`shrink-0 text-lg leading-6 font-black ${verdict.ok ? 'text-accent' : 'text-amber-300'}`}>
            {verdict.ok ? '✓ Réussi' : '✗ À revoir'}
          </span>
          {verdict.note && <span data-exercise-note className="ml-auto min-w-0 truncate text-sm font-semibold text-muted">{verdict.note}</span>}
        </p>
        <p data-exercise-reason className="mt-1 line-clamp-2 h-10 text-sm leading-5 text-neutral-300">
          {verdict.reason}
        </p>
      </div>
      <div className="mt-1.5 flex items-center gap-1">
        {secondary.map((a) => (
          <button
            key={a.label}
            type="button"
            onClick={a.onClick}
            className="flex min-h-11 min-w-11 cursor-pointer flex-col items-center justify-center rounded-lg px-2 text-xs font-semibold text-neutral-300 hover:bg-surface-3 hover:text-white"
          >
            <span aria-hidden="true" className="text-lg leading-none">{a.icon}</span>
            {a.label}
          </button>
        ))}
        <Cta className="ml-auto px-5 py-2 text-base" onClick={primary.onClick}>
          {primary.label}
        </Cta>
      </div>
    </div>
  )
}
