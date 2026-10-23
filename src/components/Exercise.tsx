// Habillage commun des exercices (maquette « Exercice type » de docs/ux-refonte.md) : écran
// immersif, en-tête (quitter, titre, progression facultative), scène où l'échiquier prend la place
// restante, et zone de décision réservée sous lui (consigne avant le coup, verdict et actions
// après). Purement présentationnel : aucun score, aucune écriture, aucune navigation.
// Lot 7 : séance d'Apprendre et révision espacée. Lot 8 : PositionGame, OpeningDrill, séance du
// jour, séries du parcours et lignes des cours.
// Sur desktop (lg), la scène passe en deux colonnes : échiquier à gauche, zone de décision et
// options à droite (index.css, `.exercise-column`).
import type { ComponentProps, ReactNode } from 'react'
import { Cta } from './Cta'

const NB = '\u00a0'

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
        className="exercise-screen mx-auto flex h-full max-w-2xl flex-col"
        inert={hidden}
        style={hidden ? { visibility: 'hidden' } : undefined}
      >
        {children}
      </div>
    </div>
  )
}

// `done` : exercices déjà jugés de la série (barre) ; `index`/`total` : position affichée « n/N ».
// Sans `total`, ni compteur ni barre (partie isolée). `counterProps` : attributs du compteur
// (marqueurs des suites E2E).
export function ExerciseHeader({ title, index, total, done, onClose, closeLabel, action, wideAction, compact, counterProps }: {
  title: ReactNode
  index?: number
  total?: number
  done?: number
  onClose: () => void
  closeLabel: string
  action?: ReactNode // à droite : bouton rond de 44 px (« ? » du cours) ou puce de niveau
  wideAction?: boolean // action plus large qu'un bouton rond (puce de niveau) : côtés de 80 px
  compact?: boolean // titre de 16 px sur téléphone (titres longs des leçons)
  counterProps?: Record<string, string>
}) {
  const series = total !== undefined && total > 0
  const value = done ?? 0
  const side = wideAction ? 'w-20' : 'w-11'
  const pct = series ? Math.min(100, Math.max(0, (value / total) * 100)) : 0
  return (
    <div data-exercise-header className={`shrink-0 ${series ? '' : 'pb-1'}`}>
      <header className="flex items-center px-3 py-1">
        {/* Deux côtés de même largeur gardent le titre centré, même avec une puce à droite. */}
        <div className={`flex shrink-0 justify-start ${side}`}>
          <button
            type="button"
            onClick={onClose}
            aria-label={closeLabel}
            className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-2xl leading-none text-neutral-400 hover:bg-surface-3 hover:text-white"
          >
            ✕
          </button>
        </div>
        <h1 className={`min-w-0 flex-1 truncate text-center font-black ${compact ? 'text-base md:text-lg' : 'text-lg'}`}>
          {title}
          {series && (
            <span {...counterProps} className="ml-2 text-sm font-semibold text-neutral-400 tabular-nums">
              {index}/{total}
            </span>
          )}
        </h1>
        <div className={`flex shrink-0 justify-end ${side}`}>{action}</div>
      </header>
      {series && (
        <div
          role="progressbar"
          aria-label="Progression de la série"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={value}
          aria-valuetext={`${value} sur ${total} terminé${value > 1 ? 's' : ''}`}
          className="mx-3 h-1 overflow-hidden rounded-full bg-surface-3"
        >
          <span className="block h-full rounded-full bg-accent transition-[width] duration-300 motion-reduce:transition-none" style={{ width: `${pct}%` }} />
        </div>
      )}
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

// Scène : une colonne de la largeur de l'échiquier, centrée : `above` (bande de 28 px, hauteur
// réservée : barre d'éval, adversaire, points de la série), échiquier, zone de décision de hauteur
// fixe, `below` (options qui peuvent passer sous le pli). L'échiquier est le plus grand carré qui
// laisse la zone de décision visible (index.css, `.exercise-stage`) : rien de ce qui change au
// verdict ne le déplace ni ne le redimensionne. `zone` : hauteur de la zone en rem, si son contenu
// demande plus que la valeur commune (consigne et rangée d'actions d'une partie).
export function ExerciseStage({ above, children, feedback, below, zone }: {
  above?: ReactNode
  children: ReactNode // l'échiquier
  feedback: ReactNode // ExerciseFeedback
  below?: ReactNode
  zone?: number
}) {
  return (
    <div
      className={`exercise-stage min-h-0 flex-1 pt-2 ${above ? 'exercise-stage-above' : ''}`}
      style={zone ? ({ '--exercise-zone': `${zone}rem` } as React.CSSProperties) : undefined}
    >
      <div className="exercise-column" data-exercise-column>
        <div className="exercise-left">
          {above && <div className="exercise-above">{above}</div>}
          <div className="exercise-board" data-exercise-board>
            {children}
          </div>
        </div>
        {feedback}
        {/* GoFurtherRow porte son propre px-3 : -mx-1.5 l’aligne sur le texte de la zone. */}
        {below && <div className="exercise-below -mx-1.5 pt-2">{below}</div>}
      </div>
    </div>
  )
}

// Trois tons, toujours un symbole et un mot (le vert n'est jamais le seul indice) : réussi,
// à revoir (échec franc), neutre (nulle, partie tenue en partie, abandon, essai non compté),
// qui décrit l'issue sans la présenter comme une faute.
export type ExerciseTone = 'success' | 'review' | 'neutral'

export interface ExerciseVerdict {
  tone: ExerciseTone
  label?: ReactNode // à la place de « Réussi » / « À revoir » / « Terminé » (titre propre à l'écran)
  reason: ReactNode // une phrase : ce qui s'est passé et quoi faire ensuite
  note?: ReactNode // à droite du verdict : variation de classement, prochaine échéance
}

export interface ExerciseAction {
  label: string
  icon: string
  onClick: () => void
  disabled?: boolean
}

const TONE: Record<ExerciseTone, { glyph: string; label: string; className: string }> = {
  success: { glyph: '✓', label: 'Réussi', className: 'text-accent' },
  review: { glyph: '✗', label: 'À revoir', className: 'text-amber-300' },
  neutral: { glyph: '◐', label: 'Terminé', className: 'text-sky-300' },
}

// Bouton secondaire de la zone : icône au-dessus du libellé, cible de 44 px.
// `grow` : rangée pleine qui se partage la place restante (cinq actions de jeu d'une partie, en
// 11 px comme la barre de Jouer : « Recommencer » tient encore sous un échiquier de 315 px).
export function ExerciseActionButton({ action, grow }: { action: ExerciseAction; grow?: boolean }) {
  return (
    <button
      type="button"
      onClick={action.onClick}
      disabled={action.disabled}
      className={`flex min-h-11 min-w-11 cursor-pointer flex-col items-center justify-center rounded-lg font-semibold whitespace-nowrap text-neutral-300 hover:bg-surface-3 hover:text-white disabled:cursor-default disabled:opacity-35 disabled:hover:bg-transparent ${grow ? 'flex-auto px-1 text-[11px]' : 'px-2 text-xs'}`}
    >
      <span aria-hidden="true" className="text-lg leading-none">{action.icon}</span>
      {action.label}
    </button>
  )
}

function ActionRow({ secondary, primary }: { secondary: ExerciseAction[]; primary?: ExerciseAction }) {
  return (
    <div data-exercise-actions className="mt-1.5 flex items-center gap-0.5">
      {secondary.map((a) => <ExerciseActionButton key={a.label} action={a} />)}
      {primary && (
        <Cta className="ml-auto shrink-0 px-5 py-2 text-base whitespace-nowrap" onClick={primary.onClick} disabled={primary.disabled}>
          {primary.label}
        </Cta>
      )}
    </div>
  )
}

// Zone de décision, de hauteur fixe sous l'échiquier. Avant le verdict : la consigne (`prompt`),
// suivie des actions de jeu (`promptActions`) s'il y en a. Après : le verdict (symbole et mot, ou
// `label`) et une explication, jamais un verdict seul (principe 9), puis les actions. Par défaut,
// une réussite ou une issue neutre propose Suivant en principal, un échec Réessayer ; Analyser et
// Pourquoi ? (s'il est fourni) restent secondaires. `actions` remplace ce jeu par défaut (partie
// contre Stockfish : Annuler, Plan, Rejouer…). `testIds` : marqueurs du bloc de verdict et de
// l'explication pour les suites des écrans qui en avaient.
export function ExerciseFeedback({ verdict, prompt, promptActions, actions, onNext, onRetry, onAnalyse, onWhy, nextLabel = 'Suivant', testIds, zoneProps, reasonLines = 2, fluid }: {
  verdict: ExerciseVerdict | null
  prompt: ReactNode
  promptActions?: ReactNode
  actions?: { secondary: ExerciseAction[]; primary?: ExerciseAction }
  onNext?: () => void
  onRetry?: () => void
  onAnalyse?: () => void
  onWhy?: () => void
  nextLabel?: string
  testIds?: { status?: string; reason?: string }
  zoneProps?: Record<string, string | undefined> // attributs de la zone (marqueurs des suites E2E)
  reasonLines?: 2 | 3 // lignes réservées à l'explication (la scène prévoit alors `zone` en conséquence)
  // Hors scène (lignes des cours) : zone et explication à la hauteur du texte, jamais coupé ; les
  // actions vivent ailleurs. L'échiquier, dimensionné sur le viewport et placé au-dessus, ne bouge pas.
  fluid?: boolean
}) {
  const zone = fluid ? '' : 'exercise-zone px-1.5 pt-2'
  if (!verdict) {
    return (
      <div {...zoneProps} data-exercise-feedback="prompt" className={zone}>
        <div data-exercise-prompt className={`rounded-xl bg-surface-2 px-3 py-2 text-neutral-200 ${fluid ? 'text-[15px] leading-snug' : 'text-sm leading-5'}`}>
          {prompt}
        </div>
        {promptActions}
      </div>
    )
  }
  const tone = TONE[verdict.tone]
  let row = actions
  if (!row) {
    const next = onNext && { label: nextLabel, icon: '→', onClick: onNext }
    const retry = onRetry && { label: 'Réessayer', icon: '↺', onClick: onRetry }
    const [primary, first] = verdict.tone === 'review' && retry ? [retry, next] : [next ?? retry, next ? retry : undefined]
    const secondary = [first, onAnalyse && { label: 'Analyser', icon: '♞', onClick: onAnalyse }, onWhy && { label: `Pourquoi${NB}?`, icon: '💡', onClick: onWhy }]
    row = { primary: primary || undefined, secondary: secondary.filter((a): a is ExerciseAction => !!a) }
  }
  return (
    <div {...zoneProps} data-exercise-feedback={verdict.tone} className={zone}>
      {/* Ligne de cours (`fluid`) : un retour à chaque coup, qui ne doit pas être annoncé coup par coup. */}
      <div role={fluid ? undefined : 'status'} data-testid={testIds?.status}>
        <p className={`flex items-baseline gap-2 ${fluid ? 'min-h-6' : 'h-6'}`}>
          <span data-exercise-verdict className={`shrink-0 text-lg leading-6 font-black ${tone.className}`}>
            {tone.glyph} {verdict.label ?? tone.label}
          </span>
          {verdict.note && <span data-exercise-note className="ml-auto min-w-0 truncate text-sm font-semibold text-muted">{verdict.note}</span>}
        </p>
        <p data-exercise-reason data-testid={testIds?.reason} className={`mt-1 text-neutral-300 ${fluid ? 'text-[15px] leading-snug' : `text-sm leading-5 ${reasonLines === 3 ? 'line-clamp-3 h-15' : 'line-clamp-2 h-10'}`}`}>
          {verdict.reason}
        </p>
      </div>
      {(row.primary || row.secondary.length > 0) && <ActionRow secondary={row.secondary} primary={row.primary} />}
    </div>
  )
}

// Rangée d'actions sous la consigne (avant le verdict), même gabarit que celle du verdict.
export function ExercisePromptActions({ secondary, primary }: { secondary: ExerciseAction[]; primary?: ExerciseAction }) {
  return <ActionRow secondary={secondary} primary={primary} />
}
