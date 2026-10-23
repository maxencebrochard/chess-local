import { useCallback, useEffect, useRef, useState } from 'react'
import { Chess, type Move } from 'chess.js'
import { ActivityCard } from '../components/ActivityCard'
import { PageHeader } from '../components/PageHeader'
import { Board, type BoardArrow } from '../components/Board'
import { CoachBubble } from '../components/CoachBubble'
import { EngineContinuation, GoFurtherRow } from '../components/EngineContinuation'
import { CourseSheet } from '../components/CourseSheet'
import { Cta } from '../components/Cta'
import { HEvalBar } from '../components/HEvalBar'
import { MistakeExercise } from '../components/MistakeExercise'
import { PuzzlePlayer } from '../components/PuzzlePlayer'
import { puzzleContinuationStart, puzzlePlayerColor, useExerciseContinuation } from '../components/useExerciseContinuation'
import { courseFor, type Course } from '../lib/courses'
import { db } from '../lib/db'
import { lessonForExercise } from '../lib/endgameCourse'
import { Engine } from '../lib/engine'
import {
  buildEndgameSession, buildSession, DOMAIN_META, domainRating, pickNextDomain, scoreItem,
  type EndgameGoal, type LearnDomain, type Session, type SessionItem,
} from '../lib/learn'
import { openingDe, openingFamilyFr } from '../lib/openingNames'
import { loadReviewQueue, type ReviewQueue } from '../lib/revision'
import { LEVELS, stepById } from '../lib/learningPath'
import { recordPathRun } from '../lib/learningPathStore'
import { usePathState } from '../components/usePathState'
import { figurine } from '../lib/review'
import { sounds } from '../lib/sounds'
import { useLocation, useNavigate } from 'react-router-dom'
import { LESSONS_ROOT, REVIEW_ROOT, TRAINING_ROOT } from '../lib/navigation'

type ItemPhase = 'lesson' | 'play' | 'success' | 'fail'

const SESSION_KEY = 'learn-session-v1'

interface StoredSession {
  session: Session
  itemIdx: number
  phase: ItemPhase
  results: boolean[]
  scoredItems: number[]
  pendingResult?: boolean
  returnTo?: string // page à rouvrir en fin de séance : leçon du cours de finales, Insights
  returnLabel?: string
  pathStep?: string // étape du parcours d'apprentissage qui a ouvert la séance de finale
}

export default function Learn() {
  const navigate = useNavigate()
  const location = useLocation()
  const [ratings, setRatings] = useState<Record<string, number | null>>({})
  const [session, setSession] = useState<Session | null>(null)
  const [itemIdx, setItemIdx] = useState(0)
  const [phase, setPhase] = useState<ItemPhase>('lesson')
  const [results, setResults] = useState<boolean[]>([])
  const [ratingDelta, setRatingDelta] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [retryTick, setRetryTick] = useState(0)
  const [showCourse, setShowCourse] = useState(false)
  const [returnTo, setReturnTo] = useState<string | null>(null)
  const [returnLabel, setReturnLabel] = useState('Retour au cours')
  const [lessonsDone, setLessonsDone] = useState<number | null>(null)
  // Séance demandée par un groupe d'Entraînement, Réviser mes parties ou Insights (`state.domain`,
  // `state.tactic`) : écran de préparation à la place du hub, qui ne doit pas clignoter.
  const [preparing, setPreparing] = useState(() => {
    const st = location.state as { domain?: unknown; tactic?: unknown } | null
    return Boolean(st?.domain || st?.tactic)
  })
  const [review, setReview] = useState<ReviewQueue | null>(null)
  // Séance de finale ouverte par une étape du parcours : toute réussite (même après Réessayer)
  // valide l'étape, une fois par séance (ligne `path`, sans Elo).
  const [pathStep, setPathStep] = useState<string | null>(null)
  const pathSaved = useRef(false)
  const [pendingResult, setPendingResult] = useState<boolean | undefined>(undefined)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(false)
  const finishing = useRef(false)
  const path = usePathState()
  const scoredItems = useRef(new Set<number>())
  const engineRef = useRef<Engine | null>(null)

  // Classements des domaines (écran de fin de séance) et leçons terminées (carte Toutes les
  // leçons), lues dans la base sans charger les cours : un id de leçon par ligne `course`.
  const refresh = useCallback(async () => {
    const [entries, courseRows] = await Promise.all([
      Promise.all((['endgame', 'tactic', 'opening', 'strategy'] as LearnDomain[]).map(async (d) => [d, await domainRating(d)] as const)),
      db.learnSessions.where('domain').equals('course').toArray(),
    ])
    setRatings(Object.fromEntries(entries))
    setLessonsDone(new Set(courseRows.map((r) => r.itemId)).size)
  }, [])

  useEffect(() => {
    void refresh()
    // La file de révision relit trois tables entières : au montage seulement, pas après chaque exercice.
    void loadReviewQueue().then(setReview)
  }, [refresh])

  useEffect(
    () => () => {
      engineRef.current?.quit()
      engineRef.current = null
    },
    [],
  )

  // Retour depuis l'analyseur (bouton « Analyser ») : restaure la séance en cours.
  // Venue d'une leçon (« S'entraîner ») : séance sur l'exercice demandé, avec retour au cours.
  // Venue d'Insights (plan d'entraînement) : séance Tactiques sur le thème demandé, avec retour.
  // Venue d'un groupe d'Entraînement ou de Réviser mes parties : séance du domaine, avec retour.
  useEffect(() => {
    const state = location.state as { restore?: boolean; endgame?: string; tactic?: string; domain?: LearnDomain; returnTo?: string; returnLabel?: string; pathStep?: string } | null
    if (state?.domain && state.domain in DOMAIN_META) {
      const { domain, returnTo: back, returnLabel: label } = state
      navigate('.', { replace: true, state: null })
      void start(domain, undefined, back ?? null, label)
    } else if (state?.tactic) {
      const { tactic, returnTo: back, returnLabel: label } = state
      navigate('.', { replace: true, state: null })
      void start('tactic', tactic, back ?? null, label)
    } else if (state?.endgame) {
      const s = buildEndgameSession(state.endgame)
      if (s) {
        setSession(s)
        setItemIdx(0)
        setResults([])
        setRatingDelta(null)
        scoredItems.current.clear()
        setPhase('lesson')
        setReturnTo(state.returnTo ?? null)
        setReturnLabel(state.returnLabel ?? 'Retour au cours')
        setPathStep(state.pathStep ?? null)
        pathSaved.current = false
      }
      navigate('.', { replace: true, state: null })
    } else {
      const raw = sessionStorage.getItem(SESSION_KEY)
      if (raw) {
        try {
          const saved = JSON.parse(raw) as StoredSession
          if (!state?.restore && saved.pendingResult === undefined) return
          setPendingResult(saved.pendingResult)
          setSession(saved.session)
          setItemIdx(saved.itemIdx)
          setPhase(saved.phase)
          setResults(saved.results)
          scoredItems.current = new Set(saved.scoredItems)
          setReturnTo(saved.returnTo ?? null)
          setReturnLabel(saved.returnLabel ?? 'Retour au cours')
          setPathStep(saved.pathStep ?? null)
        } catch {}
      }
      // Sans state, rien à effacer : naviguer ici ramènerait sur Apprendre un onglet tapé entre-temps.
      if (state) navigate('.', { replace: true, state: null })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Persiste la séance active pour pouvoir la restaurer après un aller-retour vers l'analyseur.
  useEffect(() => {
    if (session && session.items.length > 0) {
      const stored: StoredSession = {
        session, itemIdx, phase, results, pendingResult, scoredItems: [...scoredItems.current], returnTo: returnTo ?? undefined, returnLabel, pathStep: pathStep ?? undefined,
      }
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(stored))
    } else {
      sessionStorage.removeItem(SESSION_KEY)
    }
  }, [session, itemIdx, phase, results, pendingResult, returnTo, returnLabel, pathStep])

  function getEngine(): Engine {
    engineRef.current ??= new Engine()
    return engineRef.current
  }

  // `theme` : séance Tactiques ciblée ; `back`/`label` : page de retour de fin de séance (Insights),
  // gardée par « Encore une séance » sur le même thème.
  async function start(domain?: LearnDomain, theme?: string, back: string | null = null, label = 'Retour au cours') {
    setLoading(true)
    let ok = false
    try {
      const d = domain ?? (await pickNextDomain())
      const s = await buildSession(d, { theme })
      if (s.items.length === 0) return
      ok = true
      setSession(s)
      setItemIdx(0)
      setResults([])
      setRatingDelta(null)
      scoredItems.current.clear()
      setPhase('lesson')
      setReturnTo(back)
      setReturnLabel(label)
      setPathStep(null)
    } catch (e) {
      // Puzzles injoignables (hors ligne avant le précache) : le bouton redevient actif.
      console.error('[apprendre] séance non construite', e)
    } finally {
      setLoading(false)
      setPreparing(false)
      // Séance demandée depuis une autre page et impossible à construire (puzzles injoignables,
      // aucune faute à rejouer) : retour à cette page, qui l'annonce.
      if (!ok && back) navigate(back, { replace: true, state: { sessionFailed: true } })
    }
  }

  async function finishItem(success: boolean) {
    if (!session || finishing.current) return
    finishing.current = true
    setPendingResult(success)
    setSaving(true)
    setSaveError(false)
    const item = session.items[itemIdx]
    const firstAttempt = !scoredItems.current.has(itemIdx)
    const savePath = success && pathStep && item.kind === 'endgame' && !pathSaved.current
    const before = item.kind === 'mistake' ? null : (ratings[session.domain] ?? 800)
    try {
      const after = await db.transaction('rw', db.ratings, db.learnSessions, db.mistakes, async () => {
        let rating: number | null = null
        if (firstAttempt) {
          rating = await scoreItem(session.domain, itemKey(item), success, item.difficulty)
          if (item.kind === 'mistake') {
            await db.mistakes.update(item.mistake.id!, {
              attempts: item.mistake.attempts + 1,
              solved: success ? 1 : 0,
            })
          }
        } else if (item.kind === 'mistake' && success) {
          await db.mistakes.update(item.mistake.id!, { solved: 1 })
        }
        if (savePath) await recordPathRun(pathStep!, 1, true)
        return rating
      })
      if (savePath) pathSaved.current = true
      if (firstAttempt) {
        scoredItems.current.add(itemIdx)
        if (after !== null && before !== null) setRatingDelta(after - before)
        setResults((r) => [...r, success])
      }
      if (item.kind !== 'tactic' && item.kind !== 'strategy') (success ? sounds.success : sounds.fail)()
      void refresh()
      setPhase(success ? 'success' : 'fail')
      setPendingResult(undefined)
    } catch {
      setSaveError(true)
    } finally {
      finishing.current = false
      setSaving(false)
    }
  }

  // « Recommencer » d'une séance de finale ouverte par le parcours : même finale, même retour.
  function restartEndgame() {
    const ex = stepById(pathStep)?.exercise
    const s = ex?.kind === 'endgame' ? buildEndgameSession(ex.id) : null
    if (!s) return
    setSession(s)
    setItemIdx(0)
    setResults([])
    setRatingDelta(null)
    scoredItems.current.clear()
    pathSaved.current = false
    setPhase('lesson')
  }

  function retryItem() {
    setRetryTick((t) => t + 1)
    setPhase('play')
    setShowCourse(false)
  }

  // Ouvre la position de l'exercice dans l'analyseur Stockfish.
  function analyseItem() {
    if (!session) return
    const item = session.items[itemIdx]
    const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
    const returnTo = '/apprendre'
    if (item.kind === 'endgame') {
      navigate('/analyse', { state: { fen: item.endgame.fen, orientation: item.endgame.side, label: item.endgame.title, returnTo } })
    } else if (item.kind === 'tactic' || item.kind === 'strategy') {
      const p = item.puzzle
      navigate('/analyse', {
        state: {
          fen: p.fen,
          uci: p.moves,
          viewIndex: 0,
          orientation: p.fen.split(' ')[1] === 'w' ? 'b' : 'w',
          label: `Puzzle ${p.id} (${p.rating})`,
          returnTo,
        },
      })
    } else if (item.kind === 'opening') {
      navigate('/analyse', {
        state: { fen: START, uci: item.line.uci.slice(0, item.depth), viewIndex: 0, orientation: item.line.playerColor, label: openingFamilyFr(item.line.name), returnTo },
      })
    } else {
      navigate('/analyse', { state: { fen: item.mistake.fenBefore, orientation: new Chess(item.mistake.fenBefore).turn(), label: item.mistake.gameLabel, returnTo } })
    }
  }

  function nextItem() {
    if (!session) return
    setShowCourse(false)
    if (itemIdx + 1 < session.items.length) {
      setItemIdx(itemIdx + 1)
      setPhase('lesson')
    } else {
      setPhase('lesson')
      setSession({ ...session, items: [] }) // écran de fin
    }
  }

  // Quitte la séance : vers la leçon d'origine si elle vient du cours, sinon accueil d'Apprendre.
  function closeSession() {
    setSession(null)
    setResults([])
    void loadReviewQueue().then(setReview) // une séance (Mes erreurs surtout) change ce qui est dû
    if (returnTo) {
      setReturnTo(null)
      navigate(returnTo, { replace: true })
    }
  }

  // ---------- Écran de fin de séance ----------
  if (session && session.items.length === 0) {
    const ok = results.filter(Boolean).length
    return (
      <div className="pt-safe pb-safe fixed inset-0 z-40 bg-surface">
        <div className="mx-auto flex h-full max-w-lg flex-col items-center justify-center gap-4 p-6 text-center">
          <div className="text-6xl">{ok === results.length ? '🏆' : ok > 0 ? '💪' : '📚'}</div>
          <h1 className="text-2xl font-black">
            {ok}/{results.length} réussi{ok > 1 ? 's' : ''}
          </h1>
          <p className="text-neutral-400">
            {DOMAIN_META[session.domain].emoji} {DOMAIN_META[session.domain].label}
            {ratings[session.domain] !== null && ratings[session.domain] !== undefined && (
              <> · classement <b className="text-white">{ratings[session.domain]}</b></>
            )}
          </p>
          {returnTo && (
            <Cta className="w-full" onClick={closeSession}>
              {returnLabel}
            </Cta>
          )}
          {pathStep ? (
            <Cta variant="secondary" className="w-full" onClick={restartEndgame}>
              Recommencer
            </Cta>
          ) : (
            <Cta
              variant={returnTo ? 'secondary' : 'primary'}
              className="w-full"
              onClick={() => void (returnTo ? start(session.domain, session.theme, returnTo, returnLabel) : start())}
            >
              Encore une séance
            </Cta>
          )}
          {!returnTo && (
            <Cta variant="secondary" className="w-full" onClick={closeSession}>
              Terminer
            </Cta>
          )}
        </div>
      </div>
    )
  }

  // ---------- Écran de séance ----------
  if (session) {
    const item = session.items[itemIdx]
    const courseId = courseIdForItem(item)
    const course = courseId ? courseFor(courseId) : null
    return (
      <div className="pt-safe pb-safe fixed inset-0 z-40 overflow-y-auto overscroll-contain bg-surface">
        {pendingResult !== undefined && (
          <div className="pt-safe pb-safe fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-surface p-6 text-center" data-testid="learn-save">
            <p role={saveError ? 'alert' : 'status'}>
              {saveError ? 'Impossible d’enregistrer le résultat. Il est conservé : libère de l’espace puis réessaie.' : saving ? 'Enregistrement du résultat…' : 'Ton résultat est conservé et attend son enregistrement.'}
            </p>
            <Cta disabled={saving} onClick={() => void finishItem(pendingResult)}>
              {saveError ? 'Réessayer l’enregistrement' : 'Enregistrer le résultat'}
            </Cta>
          </div>
        )}
        <div className="mx-auto flex min-h-full max-w-2xl flex-col" inert={pendingResult !== undefined} style={pendingResult !== undefined ? { visibility: 'hidden' } : undefined}>
          <header className="flex items-center px-3 py-1">
            <button
              onClick={closeSession}
              aria-label="Quitter la séance"
              className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-2xl leading-none text-neutral-400 hover:text-white"
            >
              ✕
            </button>
            <h1 className="flex-1 text-center text-lg font-black">
              {DOMAIN_META[session.domain].emoji} {DOMAIN_META[session.domain].label}
              <span className="ml-2 text-sm font-semibold text-neutral-400">
                {itemIdx + 1}/{session.items.length}
              </span>
            </h1>
            {course ? (
              <button
                onClick={() => setShowCourse(true)}
                title="Voir le cours"
                aria-label="Voir le cours"
                className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-lg font-black text-neutral-400 hover:text-white"
              >
                ?
              </button>
            ) : (
              <span className="w-11 shrink-0" />
            )}
          </header>
          <ExerciseView
            key={`${itemIdx}-${retryTick}-${itemKey(item)}`}
            item={item}
            phase={phase}
            setPhase={setPhase}
            onFinish={(s) => void finishItem(s)}
            onNext={nextItem}
            onRetry={retryItem}
            onAnalyse={analyseItem}
            getEngine={getEngine}
            ratingDelta={ratingDelta}
            course={course}
            onShowCourse={() => setShowCourse(true)}
          />
          {showCourse && course && <CourseSheet course={course} onClose={() => setShowCourse(false)} />}
        </div>
      </div>
    )
  }

  // ---------- Préparation d'une séance demandée par une autre page ----------
  if (preparing) {
    return (
      <div className="pt-safe pb-safe fixed inset-0 z-40 flex items-center justify-center bg-surface p-6">
        <p role="status" className="text-muted">Préparation de la séance…</p>
      </div>
    )
  }

  // ---------- Accueil Apprendre : hub guidé ----------
  // Un prochain pas (le parcours), puis trois portes : les leçons, l'entraînement par compétence
  // et la révision de ses parties. Chaque porte est une sous-page routée (docs/ux-refonte.md, lot 5).
  const due = review?.due.length ?? 0
  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader title="Apprendre" description="Un prochain pas clair, ou l'entraînement à la carte." />

      <PathHero state={path.state} onOpen={() => navigate('/apprendre/parcours')} />

      <div className="grid gap-2">
        <ActivityCard
          to={LESSONS_ROOT}
          data-learn="lecons"
          icon="📚"
          title="Toutes les leçons"
          description={lessonsDone ? `Les bases, les finales, l'attaque, la défense et les structures · ${lessonsDone} leçon${lessonsDone > 1 ? 's' : ''} terminée${lessonsDone > 1 ? 's' : ''}` : "Les bases, les finales, l'attaque, la défense et les structures"}
        />
        <ActivityCard
          to={TRAINING_ROOT}
          data-learn="entrainement"
          icon="🎯"
          title="S'entraîner à la carte"
          description="Tactique, attaque et défense, finales, ouvertures, stratégie"
        />
        <ActivityCard
          to={REVIEW_ROOT}
          data-learn="mes-parties"
          icon="🔁"
          title="Réviser mes parties"
          description={due > 0 ? `À réviser aujourd'hui : ${due} exercice${due > 1 ? 's' : ''}` : 'Tes erreurs, attaques manquées, défenses ratées et moments critiques'}
          aside={due > 0 ? <span data-review-count className="shrink-0 rounded-full bg-amber-400 px-2.5 py-0.5 text-sm font-bold text-neutral-900">{due}</span> : undefined}
        />
      </div>

      {/* Séance rapide : la séance automatique existante (un domaine choisi par pickNextDomain),
          entrée secondaire tant que la séance du jour de l'Accueil ne la remplace pas. */}
      <section aria-labelledby="learn-quick" className="mt-6">
        <h2 id="learn-quick" className="text-lg font-semibold">Pas le temps de choisir ?</h2>
        <p className="mt-1 mb-3 text-sm text-muted">Une séance de 1 à 2 minutes, sur le domaine que tu as le moins travaillé.</p>
        <Cta variant="secondary" className="w-full" onClick={() => void start()} disabled={loading}>
          {loading ? 'Préparation…' : 'Séance rapide'}
        </Cta>
      </section>
    </div>
  )
}

// Entrée principale du parcours d'apprentissage, en tête de l'accueil d'Apprendre : niveau, étape
// courante et progression, façon carte Problèmes de l'Accueil.
function PathHero({ state, onOpen }: { state: ReturnType<typeof usePathState>['state']; onOpen: () => void }) {
  const cur = state?.current ?? null
  const level = cur ? LEVELS[cur.level] : null
  const fresh = state !== null && state.done === 0 && state.placement === 0
  return (
    <button
      onClick={onOpen}
      data-testid="path-hero"
      className="mb-4 block w-full cursor-pointer rounded-2xl bg-gradient-to-br from-[#4e7837] to-[#2e4a20] p-3 text-left shadow-lg transition hover:brightness-110 md:p-4"
    >
      <span className="flex items-center gap-3">
        <span className="min-w-0 flex-1">
          <span className="block text-xl font-black text-white">🗺️ Mon parcours</span>
          <span className="mt-0.5 block truncate text-sm text-white/80">
            {state === null ? '…'
              : cur && level ? `${level.title} · ${cur.step.title}`
              : 'Parcours terminé : bravo !'}
          </span>
        </span>
        <span className="shrink-0 rounded-xl bg-accent px-4 py-2 text-base font-black text-on-accent shadow-[0_3px_0_#5d9948]">
          {fresh ? 'Commencer' : cur ? 'Continuer' : 'Revoir'}
        </span>
      </span>
      {state && (
        <span className="mt-2.5 flex items-center gap-2">
          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-black/30">
            <span className="block h-full rounded-full bg-white/90" style={{ width: `${(state.done / state.total) * 100}%` }} />
          </span>
          <span data-testid="path-hero-progress" className="text-xs font-bold text-white/80">
            {state.done}/{state.total} étapes
          </span>
        </span>
      )}
    </button>
  )
}

function itemKey(item: SessionItem): string {
  switch (item.kind) {
    case 'endgame': return item.endgame.id
    case 'tactic': return item.puzzle.id
    case 'strategy': return `${item.card.id}:${item.puzzle.id}`
    case 'opening': return item.line.eco
    case 'mistake': return String(item.mistake.id)
  }
}

// ---------- Rendu d'un exercice ----------
// Cours détaillé associé à l'exercice (finale → id, tactique → thème,
// stratégie → thème de la carte, ouverture → principes généraux).
function courseIdForItem(item: SessionItem): string | null {
  return item.kind === 'endgame' ? item.endgame.id
    : item.kind === 'tactic' ? item.theme
    : item.kind === 'strategy' ? (item.card.themes.find((t) => courseFor(t)) ?? item.card.id)
    : item.kind === 'opening' ? 'opening-principles'
    : null
}

interface ExerciseProps {
  item: SessionItem
  phase: ItemPhase
  setPhase: (p: ItemPhase) => void
  onFinish: (success: boolean) => void
  onNext: () => void
  onRetry: () => void
  onAnalyse: () => void
  getEngine: () => Engine
  ratingDelta: number | null
  course: Course | null
  onShowCourse: () => void
  onPuzzleStep?: (step: number) => void
}

function ExerciseView(props: ExerciseProps) {
  const { item, phase, setPhase, onNext, course, onShowCourse } = props
  // « Aller plus loin » (puzzles) : hors score, n'agit ni sur la phase ni sur le verdict.
  const puzzle = item.kind === 'tactic' || item.kind === 'strategy' ? item.puzzle : null
  const furthers = useExerciseContinuation(`${item.kind}:${itemKey(item)}`, phase === 'success' || phase === 'fail')
  const furtherStart = puzzle && (phase === 'success' || phase === 'fail')
    ? puzzleContinuationStart(puzzle, furthers.step, phase === 'success')
    : null
  const navigate = useNavigate()
  const lessonId = item.kind === 'endgame' ? lessonForExercise(item.endgame.id) : null

  const lesson =
    item.kind === 'endgame' ? { title: item.endgame.title, text: item.endgame.lesson }
    : item.kind === 'strategy' ? { title: item.card.title, text: item.card.lesson }
    : item.kind === 'tactic' ? { title: item.themeLabel, text: `Trois positions, un même motif : ${item.themeLabel.toLowerCase()}. Prends deux secondes pour le repérer avant de calculer : il est présent à chaque fois.` }
    : item.kind === 'opening' ? { title: openingFamilyFr(item.line.name), text: `Objectif : dérouler les ${Math.ceil(item.depth / 2)} premiers coups ${openingDe(item.line.name)} sans te tromper. En cas d'erreur, je te montre le bon coup et on continue.` }
    : { title: 'Répare ta partie', text: `${item.mistake.gameLabel} : tu avais joué ${figurine(item.mistake.playedSan)}, et ce coup t'a coûté cher. Reprends la position et trouve plus fort.` }

  if (phase === 'lesson') {
    return (
      <div className="flex flex-1 flex-col justify-center gap-3 p-4">
        <CoachBubble
          mood="happy"
          headline={lesson.title}
          footer={(course || lessonId) && (
            <span className="flex flex-wrap gap-x-4 gap-y-1">
              {course && (
                <button onClick={onShowCourse} className="cursor-pointer text-sm font-semibold text-accent underline underline-offset-2">
                  Voir le cours complet
                </button>
              )}
              {lessonId && (
                <button
                  onClick={() => navigate(`/apprendre/finales/${lessonId}`, { state: { fromSession: true } })}
                  className="cursor-pointer text-sm font-semibold text-accent underline underline-offset-2"
                >
                  Voir la leçon
                </button>
              )}
            </span>
          )}
        >
          {lesson.text}
        </CoachBubble>
        <Cta className="w-full" onClick={() => setPhase('play')}>
          C'est parti
        </Cta>
      </div>
    )
  }

  const verdictBar = (phase === 'success' || phase === 'fail') && (
    // Une seule rangée à 393 px (LEARN-10) : verdict et delta empilés dans un bloc qui ne
    // rétrécit pas (un libellé ne passe jamais à la ligne), actions serrées à droite.
    <div className="flex items-center gap-2 px-3 py-2">
      <div className="flex shrink-0 flex-col whitespace-nowrap">
        <span className={`text-lg leading-tight font-black ${phase === 'success' ? 'text-accent' : 'text-red-400'}`}>
          {phase === 'success' ? '✓ Réussi !' : '✗ Raté'}
        </span>
        {props.ratingDelta !== null && props.ratingDelta !== 0 && (
          <span className={`text-sm leading-tight font-semibold ${props.ratingDelta > 0 ? 'text-accent' : 'text-red-400'}`}>
            {props.ratingDelta > 0 ? '+' : ''}{props.ratingDelta}
          </span>
        )}
      </div>
      <div className="ml-auto flex items-center gap-1">
        <button
          onClick={props.onRetry}
          className="flex cursor-pointer flex-col items-center rounded px-1.5 py-1 text-xs font-semibold text-neutral-300 hover:text-white"
        >
          <span className="text-lg leading-none">↺</span>
          Réessayer
        </button>
        <button
          onClick={props.onAnalyse}
          className="flex cursor-pointer flex-col items-center rounded px-1.5 py-1 text-xs font-semibold text-neutral-300 hover:text-white"
        >
          <span className="text-lg leading-none">♞</span>
          Analyser
        </button>
        <Cta className="ml-1 px-5 py-2 text-base" onClick={onNext}>
          Suivant
        </Cta>
      </div>
    </div>
  )

  return (
    <div className="flex flex-1 flex-col">
      {(item.kind === 'tactic' || item.kind === 'strategy') && (
        <PuzzleExercise {...props} onPuzzleStep={(s) => { if (phase === 'play') furthers.recordStep(s) }} />
      )}
      {item.kind === 'endgame' && <EndgameExercise {...props} />}
      {item.kind === 'opening' && <OpeningExercise {...props} />}
      {item.kind === 'mistake' && (
        <MistakeExercise mistake={item.mistake} active={phase === 'play'} onFinish={props.onFinish} getEngine={props.getEngine} />
      )}
      {verdictBar}
      {furtherStart && (
        <GoFurtherRow
          planLabel={item.kind === 'strategy' ? 'Voir le plan' : 'Voir la suite'}
          planFirst={item.kind === 'strategy'}
          onOpen={(mode) => furthers.open(mode, furtherStart)}
        />
      )}
      {puzzle && furthers.overlay && (phase === 'success' || phase === 'fail') && (
        <EngineContinuation
          startFen={furthers.overlay.startFen}
          playerColor={puzzlePlayerColor(puzzle)}
          mode={furthers.overlay.mode}
          initialMoves={furthers.overlay.moves}
          initialResigned={furthers.overlay.resigned}
          label={`Puzzle ${puzzle.id} (${puzzle.rating}), suite`}
          returnTo="/apprendre"
          onBeforeAnalyse={furthers.leave}
          onClose={furthers.close}
        />
      )}
    </div>
  )
}

// ---------- Puzzle (tactique / stratégie) ----------
function PuzzleExercise({ item, phase, onFinish, onPuzzleStep }: ExerciseProps) {
  if (item.kind !== 'tactic' && item.kind !== 'strategy') return null
  const puzzle = item.kind === 'tactic' ? item.puzzle : item.puzzle
  return (
    <div className="flex justify-center px-1">
      <div className="boardbox md:w-[min(60vh,560px)]">
        <PuzzlePlayer
          puzzle={puzzle}
          onStep={onPuzzleStep}
          onComplete={(ok) => {
            if (phase === 'play') onFinish(ok)
          }}
        />
      </div>
    </div>
  )
}

// ---------- Finale contre Stockfish ----------
// L'échiquier tranche (mat, pat, répétition, matériel, 50 coups), puis l'objectif de l'exercice
// (`goal`) : mat sur l'échiquier, promotion, capture du matériel adverse, ou tenir la nulle.
// L'évaluation ne sert qu'à confirmer une promotion ou une capture, et à détecter un avantage lâché.
function EndgameExercise({ item, phase, onFinish, getEngine }: ExerciseProps) {
  const eg = item.kind === 'endgame' ? item.endgame : null
  // Séance restaurée depuis un stockage antérieur au champ `goal` : le mat ou la nulle restent l'objectif.
  const goal: EndgameGoal = eg?.goal ?? (eg?.objective === 'draw' ? 'hold' : 'mate')
  const chessRef = useRef(new Chess(eg?.fen))
  const [fen, setFen] = useState(chessRef.current.fen())
  const [liveCp, setLiveCp] = useState<number | null>(null)
  const [liveMate, setLiveMate] = useState<number | null>(null)
  // Motif du verdict, affiché à la place de l'objectif une fois l'exercice conclu.
  const [outcome, setOutcome] = useState<{ ok: boolean; reason: string } | null>(null)
  const plies = useRef(0)
  const badStreak = useRef(0)
  const promoted = useRef(false)
  const finished = useRef(false)
  // Exercice démonté (page quittée, séance fermée) : une recherche qui finit après ne doit ni
  // conclure ni relancer le moteur (getEngine en recréerait un, jamais quitté). Remis à vrai au
  // montage : StrictMode simule un démontage puis un remontage.
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  const conclude = useCallback((ok: boolean, reason: string) => {
    if (finished.current || !alive.current || phase !== 'play') return
    finished.current = true
    setOutcome({ ok, reason })
    onFinish(ok)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onFinish, phase])

  // Évaluation à profondeur fixe, ramenée au point de vue du joueur (mat > 0 = il mate), et barre
  // mise à jour côté blanc, plafonnée à ±10 pour l'affichage.
  const evaluate = useCallback(async (): Promise<{ cp: number; mate: number | null }> => {
    const c = chessRef.current
    const fen = c.fen()
    const turn = c.turn()
    const res = await getEngine().search({ fen, depth: 10, multipv: 1 })
    const line = res.lines[0]
    const sign = turn === eg!.side ? 1 : -1
    const mate = line?.scoreMate != null ? sign * line.scoreMate : null
    const cp = mate !== null ? (mate > 0 ? 10000 : -10000) : sign * (line?.scoreCp ?? 0)
    const white = eg!.side === 'w' ? 1 : -1
    setLiveCp(Math.max(-1000, Math.min(1000, white * cp)))
    setLiveMate(mate === null ? null : white * mate)
    return { cp, mate }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eg, getEngine])

  const evalAndCheck = useCallback(async () => {
    if (!eg || finished.current) return
    const c = chessRef.current
    const hold = goal === 'hold'
    const missed = hold ? 'objectif atteint.' : "le gain t'a échappé."
    if (c.isCheckmate()) {
      const mine = c.turn() !== eg.side
      conclude(mine, mine ? 'Mat ! Objectif atteint.' : 'Tu es mat.')
      return
    }
    if (c.isStalemate()) { conclude(hold, `Pat : la partie est nulle, ${missed}`); return }
    if (c.isThreefoldRepetition()) { conclude(hold, `Nulle par répétition : ${missed}`); return }
    if (c.isInsufficientMaterial()) { conclude(hold, `Plus assez de matériel pour mater : nulle, ${missed}`); return }
    if (c.isDrawByFiftyMoves()) { conclude(hold, `Règle des 50 coups : nulle, ${missed}`); return }
    const { cp, mate } = await evaluate()
    if (finished.current || !alive.current) return
    const winning = cp >= 300 || (mate !== null && mate > 0)
    if (goal === 'promote' && promoted.current && winning) { conclude(true, "Pion promu : c'est gagné."); return }
    if (goal === 'capture' && winning && c.board().flat().filter((p) => p && p.color !== eg.side).length === 1) {
      conclude(true, 'Matériel adverse capturé : le reste est technique.')
      return
    }
    if (hold) {
      badStreak.current = cp <= -350 ? badStreak.current + 1 : 0
      if (badStreak.current >= 4) conclude(false, 'La position est perdue.')
      else if (plies.current >= 30 && badStreak.current === 0) conclude(true, 'Tu as tenu 15 coups sans faiblir : nulle acquise.')
    } else {
      badStreak.current = cp <= 80 ? badStreak.current + 1 : 0
      if (badStreak.current >= 4) conclude(false, cp < -300 ? 'La position est perdue.' : "L'avantage est parti : la position est nulle.")
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eg, goal, conclude, evaluate])

  const botMove = useCallback(async () => {
    if (!eg || finished.current || !alive.current) return
    const c = chessRef.current
    if (c.isGameOver()) return
    const engine = getEngine()
    const res = await engine.search({ fen: c.fen(), movetimeMs: 350, multipv: 1 })
    if (finished.current || !alive.current || !res.bestMove || res.bestMove.length < 4) return
    try {
      c.move({ from: res.bestMove.slice(0, 2), to: res.bestMove.slice(2, 4), promotion: res.bestMove[4] })
    } catch {
      return
    }
    plies.current++
    setFen(c.fen())
    void evalAndCheck()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eg, getEngine, evalAndCheck])

  // Barre d'éval renseignée dès l'affichage, sans attendre le premier coup.
  useEffect(() => {
    if (eg && phase === 'play') void evaluate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!eg) return null

  function handleMove(from: string, to: string, promotion?: string): Move | false {
    const c = chessRef.current
    if (phase !== 'play' || c.turn() !== eg!.side) return false
    let mv
    try {
      mv = c.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    if (mv.promotion) promoted.current = true
    plies.current++
    setFen(c.fen())
    void (async () => {
      await evalAndCheck()
      if (!finished.current) await botMove()
    })()
    return mv
  }

  return (
    <div className="flex flex-col gap-2 px-3">
      <div
        className={`rounded px-3 py-1.5 text-center text-sm font-semibold ${
          outcome ? (outcome.ok ? 'bg-accent/15 text-accent-light' : 'bg-red-900/40 text-red-200') : 'bg-surface-2'
        }`}
      >
        {outcome
          ? outcome.reason
          : `Objectif : ${eg.objective === 'win' ? 'gagne cette position' : 'tiens la nulle'}, trait aux ${eg.side === 'w' ? 'Blancs' : 'Noirs'}`}
      </div>
      <HEvalBar cp={liveCp} mate={liveMate} />
      <div className="flex justify-center">
        <div className="boardbox md:w-[min(56vh,520px)]">
          <Board fen={fen} orientation={eg.side} interactive={phase === 'play'} movableColor={eg.side} onMove={handleMove} />
        </div>
      </div>
    </div>
  )
}

// ---------- Drill d'ouverture ----------
function OpeningExercise({ item, phase, onFinish }: ExerciseProps) {
  const line = item.kind === 'opening' ? item.line : null
  const depth = item.kind === 'opening' ? item.depth : 0
  const chessRef = useRef(new Chess())
  const [fen, setFen] = useState(chessRef.current.fen())
  const [step, setStep] = useState(0)
  const [faults, setFaults] = useState(0)
  const [hintArrow, setHintArrow] = useState<BoardArrow | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const finished = useRef(false)

  const playerColor = line?.playerColor ?? 'w'

  // L'app joue le camp adverse.
  useEffect(() => {
    if (!line || finished.current || phase !== 'play') return
    const c = chessRef.current
    if (step >= depth) {
      finished.current = true
      onFinish(faults <= 1)
      return
    }
    if (c.turn() !== playerColor) {
      const t = setTimeout(() => {
        const uci = line.uci[step]
        try {
          c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
          setStep((s) => s + 1)
          setFen(c.fen())
        } catch {
          finished.current = true
          onFinish(faults <= 1)
        }
      }, 450)
      return () => clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, phase, line, depth, playerColor, faults])

  if (!line) return null

  function handleMove(from: string, to: string, promotion?: string): Move | false {
    const c = chessRef.current
    if (phase !== 'play' || c.turn() !== playerColor || finished.current) return false
    const expected = line!.uci[step]
    let mv
    try {
      mv = c.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    const played = mv.from + mv.to + (mv.promotion ?? '')
    if (played === expected) {
      setHintArrow(null)
      setMsg(null)
      setStep(step + 1)
      setFen(c.fen())
      return mv
    }
    // Mauvais coup : correction et nouvel essai.
    c.undo()
    setFen(c.fen())
    setFaults(faults + 1)
    setHintArrow({ startSquare: expected.slice(0, 2), endSquare: expected.slice(2, 4), color: '#69c3f2' })
    setMsg(`Pas la ligne : ici, la théorie joue ${figurine(new Chess(c.fen()).move({ from: expected.slice(0, 2), to: expected.slice(2, 4), promotion: expected[4] }).san, playerColor)}. Rejoue-le.`)
    return false
  }

  return (
    <div className="flex flex-col gap-2 px-3">
      <div className="truncate rounded bg-surface-2 px-3 py-1.5 text-center text-sm font-semibold">
        {openingFamilyFr(line.name)} : les {Math.ceil(depth / 2)} premiers coups, côté {playerColor === 'w' ? 'blanc' : 'noir'}
      </div>
      {/* Hauteur réservée : l'apparition du message ne doit pas faire sauter le board. */}
      <p className={`min-h-[34px] rounded px-3 py-1.5 text-sm ${msg ? 'bg-red-900/40 text-red-200' : ''}`}>
        {msg ?? ' '}
      </p>
      <div className="flex justify-center">
        <div className="boardbox md:w-[min(56vh,520px)]">
          <Board
            fen={fen}
            orientation={playerColor}
            interactive={phase === 'play'}
            movableColor={playerColor}
            onMove={handleMove}
            arrows={hintArrow ? [hintArrow] : []}
          />
        </div>
      </div>
    </div>
  )
}

