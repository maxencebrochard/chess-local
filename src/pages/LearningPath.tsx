// Parcours d'apprentissage (#/apprendre/parcours), façon chess.com Path : carte verticale des
// étapes par niveau, page d'étape (leçon puis exercice), séries notées (puzzles, variantes
// d'ouverture) et test de placement. Données et logique pure dans src/lib/learningPath.ts,
// progression dans learnSessions (src/lib/learningPathStore.ts).
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { CourseBody } from '../components/CourseSheet'
import { usePathState } from '../components/usePathState'
import { Cta } from '../components/Cta'
import { OpeningDrill } from '../components/OpeningDrill'
import { PuzzlePlayer, type PuzzleData } from '../components/PuzzlePlayer'
import { courseFor } from '../lib/courses'
import { Engine } from '../lib/engine'
import { ENDGAMES } from '../lib/learn'
import {
  exerciseGoal, isScored, lessonRef, LEVELS, levelOf, PLACEMENT_ID, PLACEMENT_PER_LEVEL,
  placementLevels, placementOver, starsFor, stepById, STEPS,
  type OpeningExercise, type PathExercise, type PathLevel, type PathState, type PathStep, type StepState,
} from '../lib/learningPath'
import {
  PATH_SESSION_KEY, pickPlacementPuzzles, pickStepPuzzles, recordPathRun, recordPlacement,
} from '../lib/learningPathStore'
import { getFamily, loadProgress, playerMoveCount, recordDrill, variantStatus, type Family, type Variant } from '../lib/openingTrainer'
import { openingFamilyFr } from '../lib/openingNames'
import { loadPuzzles } from '../lib/puzzles'
import { displayThemes, puzzleThemeLabel } from '../lib/puzzleThemes'

const MAP_PATH = '/apprendre/parcours'
const stepPath = (id: string) => `${MAP_PATH}/${id}`

// Libellé de la série d'un exercice : thème, famille ou titre de la finale.
function exerciseLabel(ex: PathExercise): string {
  if (ex.kind === 'puzzles') return ex.themes.map(puzzleThemeLabel).join(', ').toLowerCase()
  if (ex.kind === 'opening') return openingFamilyFr(ex.family).replace(/^./, (c) => c.toLowerCase())
  return ENDGAMES.find((e) => e.id === ex.id)?.title ?? ex.id
}

function goalOf(ex: PathExercise): string {
  const draw = ex.kind === 'endgame' && ENDGAMES.find((e) => e.id === ex.id)?.objective === 'draw'
  return exerciseGoal(ex, exerciseLabel(ex), draw)
}

function Stars({ n, size = 'text-sm' }: { n: number; size?: string }) {
  return (
    <span data-stars={n} aria-label={`${n} étoile${n > 1 ? 's' : ''} sur 3`} className={`${size} leading-none tracking-tight`}>
      {[0, 1, 2].map((i) => (
        <span key={i} className={i < n ? 'text-amber-400' : 'text-neutral-600'}>
          ★
        </span>
      ))}
    </span>
  )
}

// ---------- Carte du parcours ----------
export default function LearningPathMap() {
  const navigate = useNavigate()
  const { state } = usePathState()
  const scrolled = useRef(false)

  // Reprise : la carte s'ouvre sur l'étape courante (une fois, après le premier chargement).
  useLayoutEffect(() => {
    if (!state || scrolled.current) return
    scrolled.current = true
    if (state.current && state.current.index > 0) document.querySelector('[data-current-step]')?.scrollIntoView({ block: 'center' })
  }, [state])

  if (!state) return <div className="p-8 text-center text-neutral-400">Chargement du parcours…</div>
  const fresh = state.done === 0 && state.placement === 0
  const cur = state.current
  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <button onClick={() => navigate('/apprendre', { replace: true })} className="mb-2 cursor-pointer text-sm font-semibold text-neutral-400 hover:text-white">
        ← Apprendre
      </button>
      <h1 className="mb-1 text-2xl font-black">🗺️ Parcours d'apprentissage</h1>
      <p className="mb-3 text-sm text-neutral-400">
        Du premier coup au niveau 2000, étape par étape. Chaque étape, c'est une courte leçon puis des exercices à réussir pour débloquer la suivante.
      </p>
      <div className="mb-4 flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-3">
          <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${(state.done / state.total) * 100}%` }} />
        </div>
        <span data-testid="path-progress" className="text-sm font-bold text-neutral-300">
          {state.done}/{state.total}
        </span>
      </div>

      {cur ? (
        <button
          onClick={() => navigate(stepPath(cur.step.id))}
          data-testid="path-continue"
          className="mb-3 flex w-full cursor-pointer items-center gap-3 rounded-2xl bg-surface-2 p-3 text-left shadow-lg ring-1 ring-white/5 hover:bg-surface-3"
        >
          <StepIcon icon={cur.step.icon} color={LEVELS[cur.level].color} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[11px] font-bold tracking-wide uppercase" style={{ color: LEVELS[cur.level].color }}>
              {LEVELS[cur.level].title} · {cur.index - firstIndex(state, cur.level) + 1}/{state.levels[cur.level].total}
            </span>
            <span className="block font-bold leading-tight">{cur.step.title}</span>
          </span>
          <span className="shrink-0 rounded-xl bg-accent px-3.5 py-2 text-[15px] font-black text-white shadow-[0_3px_0_#5d9948]">{fresh ? 'Commencer' : 'Continuer'}</span>
        </button>
      ) : (
        <div data-testid="path-finished" className="mb-3 rounded-2xl bg-surface-2 p-4 text-center">
          <div className="text-4xl">🎓</div>
          <div className="mt-1 font-black">Parcours terminé</div>
          <p className="text-sm text-neutral-400">Toutes les étapes sont validées ou acquises. Les séances d'Apprendre restent là pour entretenir tout ça.</p>
        </div>
      )}

      {fresh && (
        <button
          onClick={() => navigate(stepPath(PLACEMENT_ID))}
          data-testid="placement-card"
          className="mb-5 flex w-full cursor-pointer items-center gap-3 rounded-xl border border-dashed border-white/15 p-3 text-left hover:bg-surface-2"
        >
          <span className="text-2xl" aria-hidden="true">🧪</span>
          <span className="min-w-0 flex-1">
            <span className="block font-bold">Tu connais déjà les bases ?</span>
            <span className="block text-xs text-neutral-400">Test de placement : {PLACEMENT_PER_LEVEL} puzzles par niveau, pour sauter ceux que tu maîtrises</span>
          </span>
          <span className="text-xl text-neutral-500" aria-hidden="true">›</span>
        </button>
      )}

      {state.levels.map((lv, li) => (
        <LevelSection key={lv.level.id} state={state} li={li} onOpen={(id) => navigate(stepPath(id))} />
      ))}

      {!fresh && (
        <button
          onClick={() => navigate(stepPath(PLACEMENT_ID))}
          className="mt-2 mb-2 w-full cursor-pointer py-2 text-center text-sm font-semibold text-neutral-400 underline underline-offset-2 hover:text-white"
        >
          Refaire le test de placement
        </button>
      )}
    </div>
  )
}

function firstIndex(state: PathState, li: number): number {
  return state.steps.find((s) => s.level === li)!.index
}

function StepIcon({ icon, color }: { icon: string; color: string }) {
  return (
    <span
      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-lg font-black text-white"
      style={{ backgroundColor: `${color}33`, boxShadow: `inset 0 0 0 2px ${color}` }}
      aria-hidden="true"
    >
      {icon}
    </span>
  )
}

function LevelSection({ state, li, onOpen }: { state: PathState; li: number; onOpen: (id: string) => void }) {
  const lv = state.levels[li]
  const { level } = lv
  const steps = state.steps.filter((s) => s.level === li)
  return (
    <section data-level={level.id} className="mb-6">
      <div className="mb-3 flex items-center gap-3">
        <span className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: level.color }} aria-hidden="true" />
        <h2 className="text-lg font-black" style={{ color: level.color }}>
          {level.title}
        </h2>
        <span className="text-sm font-semibold text-neutral-500">≈ {level.elo}</span>
        <span className="ml-auto flex items-center gap-2">
          {lv.acquired && (
            <span data-testid="level-acquired" className="rounded-full bg-surface-3 px-2 py-0.5 text-[11px] font-bold text-neutral-300">
              Acquis au test
            </span>
          )}
          <span data-testid={`level-progress-${level.id}`} className="text-sm font-bold text-neutral-400">
            {lv.done}/{lv.total}
          </span>
        </span>
      </div>
      <p className="mb-3 text-sm leading-snug text-neutral-400">{level.intro}</p>
      <ol>
        {steps.map((s, i) => (
          <StepRow key={s.step.id} s={s} color={level.color} n={i + 1} first={i === 0} onOpen={onOpen} />
        ))}
        <li className="flex items-center gap-3" data-level-end={lv.complete ? 'complete' : 'pending'}>
          <span className="relative flex w-12 shrink-0 justify-center self-stretch">
            <span className="absolute top-0 h-1/2 w-1" style={{ backgroundColor: steps.at(-1)?.done || steps.at(-1)?.acquired ? level.color : 'var(--color-surface-3)' }} />
            <span
              className={`relative z-10 my-1 flex h-12 w-12 items-center justify-center rounded-full text-2xl ${lv.complete ? '' : 'opacity-40 grayscale'}`}
              style={{ backgroundColor: lv.complete ? level.color : 'var(--color-surface-2)' }}
              aria-hidden="true"
            >
              🎓
            </span>
          </span>
          <span className={`text-sm font-bold ${lv.complete ? 'text-white' : 'text-neutral-500'}`}>
            {lv.complete ? `Niveau ${level.title.toLowerCase()} terminé` : `Fin du niveau ${level.title.toLowerCase()}`}
          </span>
        </li>
      </ol>
    </section>
  )
}

function StepRow({ s, color, n, first, onOpen }: { s: StepState; color: string; n: number; first: boolean; onOpen: (id: string) => void }) {
  const lit = s.done || s.acquired
  const status = s.done ? 'done' : s.acquired ? 'acquired' : s.current ? 'current' : s.unlocked ? 'open' : 'locked'
  return (
    <li data-step={s.step.id} data-status={status} data-current-step={s.current ? '' : undefined} className="flex items-stretch gap-3">
      {/* Rail : segment vers l'étape précédente, nœud, segment vers la suivante. */}
      <span className="relative flex w-12 shrink-0 flex-col items-center">
        <span className="h-2 w-1" style={{ backgroundColor: first ? 'transparent' : s.unlocked ? color : 'var(--color-surface-3)' }} />
        <button
          onClick={() => onOpen(s.step.id)}
          aria-label={`${s.step.title}${s.done ? ', validée' : s.unlocked ? '' : ', verrouillée'}`}
          className={`relative z-10 flex h-12 w-12 shrink-0 cursor-pointer items-center justify-center rounded-full text-lg font-black transition ${
            s.current ? 'ring-4 ring-white/25' : ''
          }`}
          style={{
            backgroundColor: s.done ? color : s.current ? color : 'var(--color-surface-2)',
            color: s.done || s.current ? '#fff' : s.unlocked ? '#d4d4d4' : '#737373',
            boxShadow: !s.done && !s.current && lit ? `inset 0 0 0 2px ${color}` : s.done || s.current ? '0 3px 0 rgba(0,0,0,0.35)' : undefined,
          }}
        >
          {s.done ? '✓' : s.acquired ? <span style={{ color }}>✓</span> : s.unlocked ? n : '🔒'}
        </button>
        <span className="w-1 flex-1" style={{ backgroundColor: lit ? color : 'var(--color-surface-3)' }} />
      </span>
      <button
        onClick={() => onOpen(s.step.id)}
        className={`mb-3 flex min-w-0 flex-1 cursor-pointer items-center gap-2 rounded-xl p-3 text-left transition ${
          s.current ? 'bg-surface-3 ring-1 ring-white/10' : 'bg-surface-2 hover:bg-surface-3'
        } ${s.unlocked ? '' : 'opacity-60'}`}
      >
        <span className="min-w-0 flex-1">
          <span className="block font-bold leading-tight">{s.step.title}</span>
          <span className="mt-0.5 block text-[13px] leading-snug text-neutral-400">{s.step.summary}</span>
          {(s.stars !== null || s.acquired) && (
            <span className="mt-1 flex items-center gap-2">
              {s.stars !== null && <Stars n={s.stars} />}
              {s.acquired && !s.done && <span className="text-[11px] font-semibold text-neutral-500">acquise au test</span>}
            </span>
          )}
        </span>
        {s.current && <span className="shrink-0 rounded-full bg-accent px-2.5 py-1 text-xs font-black text-white">À toi</span>}
      </button>
    </li>
  )
}

// ---------- Page d'une étape ----------
export function PathStepRoute() {
  const { id } = useParams()
  if (id === PLACEMENT_ID) return <PlacementPage />
  const step = stepById(id)
  if (!step) return <Navigate to={MAP_PATH} replace />
  return <StepPage key={step.id} step={step} />
}

type RunItem = { kind: 'puzzle'; puzzle: PuzzleData } | { kind: 'variant'; uci: string }

// Série en cours, persistée dans sessionStorage (PATH_SESSION_KEY).
interface StoredRun {
  key: string // id d'étape ou PLACEMENT_ID
  nonce: number // une série neuve remonte le lecteur (gardes de verdict remises à zéro)
  items: RunItem[]
  idx: number
  results: boolean[] // verdicts des items 0..n-1, dans l'ordre
}

function readRun(key: string): StoredRun | null {
  try {
    const raw = sessionStorage.getItem(PATH_SESSION_KEY)
    const run = raw ? (JSON.parse(raw) as StoredRun) : null
    if (!run || run.key !== key || !Array.isArray(run.items) || run.items.length === 0 || !Array.isArray(run.results)) return null
    // Une variante déjà jugée ne se rejoue pas (le drill repartirait du premier coup) : la série
    // reprend à l'item suivant, comme la révision espacée.
    if (run.items[run.idx]?.kind === 'variant' && run.results.length > run.idx && run.idx + 1 < run.items.length) return { ...run, idx: run.idx + 1 }
    return run
  } catch {
    return null
  }
}

function writeRun(run: StoredRun) {
  try {
    sessionStorage.setItem(PATH_SESSION_KEY, JSON.stringify(run))
  } catch {}
}

function clearRun() {
  try {
    sessionStorage.removeItem(PATH_SESSION_KEY)
  } catch {}
}

// Variantes d'une série d'ouverture : distinctes, où le joueur joue au moins 3 coups, les non
// maîtrisées d'abord.
async function pickVariants(fam: Family, color: 'w' | 'b', count: number, exclude: string[] = []): Promise<string[]> {
  const progress = await loadProgress().catch(() => null)
  const pool = fam.variants.filter((v) => playerMoveCount(v, color) >= 3 && !exclude.includes(v.line.uci))
  const fresh = progress ? pool.filter((v) => variantStatus(progress, color, v) !== 'mastered') : pool
  const shuffled = (arr: Variant[]) => [...arr].sort(() => Math.random() - 0.5)
  const ordered = [...shuffled(fresh), ...shuffled(pool.filter((v) => !fresh.includes(v)))]
  return ordered.slice(0, count).map((v) => v.line.uci)
}

function StepPage({ step }: { step: PathStep }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { state, reload } = usePathState()
  const [run, setRun] = useState<StoredRun | null>(() => readRun(step.id))
  const [ended, setEnded] = useState<{ score: number; passed: boolean } | null>(null)
  const [preparing, setPreparing] = useState(false)
  const [loadError, setLoadError] = useState(false)

  // Retour de l'analyseur (`state.restore`) : la série vient de sessionStorage ; le state est effacé.
  useEffect(() => {
    if (location.state) navigate('.', { replace: true, state: null })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const s = state?.steps.find((x) => x.step.id === step.id) ?? null
  const level = levelOf(step)
  const ex = step.exercise
  const ref = lessonRef(step.lesson)
  const read = step.read ? courseFor(step.read) : null
  const next = STEPS[STEPS.indexOf(step) + 1] ?? null

  async function startRun() {
    if (!isScored(ex)) return
    setPreparing(true)
    setLoadError(false)
    try {
      let items: RunItem[]
      if (ex.kind === 'puzzles') {
        items = pickStepPuzzles(await loadPuzzles(), ex).map((puzzle) => ({ kind: 'puzzle', puzzle }))
      } else {
        const fam = getFamily(ex.family)
        items = fam ? (await pickVariants(fam, ex.color, ex.count)).map((uci) => ({ kind: 'variant', uci })) : []
      }
      if (items.length === 0) throw new Error('série vide')
      const r: StoredRun = { key: step.id, nonce: Date.now(), items, idx: 0, results: [] }
      writeRun(r)
      setEnded(null)
      setRun(r)
    } catch (e) {
      console.error('[parcours] série non construite', e)
      setLoadError(true)
    } finally {
      setPreparing(false)
    }
  }

  async function finishRun(results: boolean[]) {
    if (!isScored(ex)) return
    const score = results.filter(Boolean).length
    const passed = score >= ex.pass
    await recordPathRun(step.id, score, passed)
    clearRun()
    setEnded({ score, passed })
    await reload()
  }

  function quitRun() {
    clearRun()
    setRun(null)
    setEnded(null)
  }

  if (run && isScored(ex)) {
    if (ended) {
      return (
        <RunEnd
          title={step.title}
          score={ended.score}
          count={ex.count}
          pass={ex.pass}
          passed={ended.passed}
          onNext={ended.passed && next ? () => navigate(stepPath(next.id), { replace: true }) : null}
          onRetry={() => void startRun()}
          onMap={() => navigate(MAP_PATH, { replace: true })}
        />
      )
    }
    return (
      <Runner
        key={run.nonce}
        run={run}
        setRun={setRun}
        exercise={ex}
        title={`${step.icon} ${step.title}`}
        backTo={stepPath(step.id)}
        isOver={(results) => results.length >= run.items.length}
        onOver={finishRun}
        onQuit={quitRun}
      />
    )
  }

  if (!state || !s) return <div className="p-8 text-center text-neutral-400">Chargement…</div>
  const levelSteps = state.steps.filter((x) => x.level === s.level)
  const cur = state.current

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6" data-step-page={step.id}>
      <button onClick={() => navigate(MAP_PATH, { replace: true })} className="mb-3 cursor-pointer text-sm font-semibold text-neutral-400 hover:text-white">
        ← Parcours
      </button>
      <div className="mb-1 flex items-center gap-2">
        <span className="rounded-full px-2.5 py-0.5 text-xs font-black text-neutral-900" style={{ backgroundColor: level.color }}>
          {level.title}
        </span>
        <span className="text-xs font-semibold text-neutral-500">
          Étape {s.index - levelSteps[0].index + 1}/{levelSteps.length}
        </span>
      </div>
      <h1 className="mb-1 flex items-center gap-2 text-2xl font-black">
        <span aria-hidden="true">{step.icon}</span>
        <span className="min-w-0">{step.title}</span>
      </h1>
      <p className="mb-4 text-sm text-neutral-400">{step.summary}</p>

      {s.done && (
        <div data-testid="step-validated" className="mb-4 flex items-center gap-3 rounded-xl bg-accent/15 px-4 py-3">
          <span className="text-2xl font-black text-accent">✓</span>
          <span className="min-w-0 flex-1 font-bold text-accent">Étape validée</span>
          {s.stars !== null && <Stars n={s.stars} size="text-lg" />}
        </div>
      )}

      {!s.unlocked ? (
        <div data-testid="step-locked" className="rounded-xl bg-surface-2 p-4 text-center">
          <div className="text-3xl">🔒</div>
          <p className="mt-1 mb-3 text-neutral-300">Valide d'abord les étapes précédentes : le parcours se suit dans l'ordre.</p>
          {cur && (
            <Cta className="w-full" onClick={() => navigate(stepPath(cur.step.id), { replace: true })}>
              Aller à l'étape en cours
            </Cta>
          )}
        </div>
      ) : (
        <ol className="space-y-3">
          {ref && (
            <PartCard n={1} done={s.lessonDone === true} title={`Leçon : ${ref.lesson.title}`} text={ref.lesson.summary} testId="part-lesson">
              <Cta
                variant={s.lessonDone ? 'secondary' : 'primary'}
                className="w-full py-2.5 text-base"
                onClick={() => navigate(`${ref.path}?parcours=${step.id}`, { replace: true })}
              >
                {s.lessonDone ? 'Revoir la leçon' : 'Ouvrir la leçon'}
              </Cta>
            </PartCard>
          )}
          {read && (
            <li className="space-y-4 rounded-xl bg-surface-2 p-4" data-testid="part-read">
              <div className="flex items-center gap-3">
                <PartNumber n={1} done={s.exerciseDone === true} />
                <h2 className="min-w-0 flex-1 font-bold leading-tight">Leçon : {read.title}</h2>
              </div>
              <CourseBody course={read} />
            </li>
          )}
          {ex && (
            <PartCard
              n={ref || read ? 2 : 1}
              done={s.exerciseDone === true}
              title={ex.kind === 'endgame' ? 'Exercice : finale contre Stockfish' : ex.kind === 'opening' ? "Exercice : variantes d'ouverture" : 'Exercice : puzzles'}
              text={goalOf(ex)}
              testId="part-exercise"
              extra={
                isScored(ex) && s.best !== null ? (
                  <span data-testid="step-best" className="flex items-center gap-2 text-sm text-neutral-400">
                    Meilleur score : <b className="text-white">{Math.min(s.best, ex.count)}/{ex.count}</b>
                    <Stars n={s.stars ?? 0} />
                  </span>
                ) : null
              }
            >
              {loadError && (
                <p role="alert" className="mb-2 rounded bg-red-900/40 px-3 py-2 text-sm text-red-200">
                  Impossible de préparer la série (puzzles injoignables ?). Réessaie.
                </p>
              )}
              <Cta
                variant={s.exerciseDone ? 'secondary' : 'primary'}
                className="w-full py-2.5 text-base"
                disabled={preparing || s.lessonDone === false}
                onClick={() => {
                  if (ex.kind === 'endgame') {
                    navigate('/apprendre', {
                      replace: true,
                      state: { endgame: ex.id, returnTo: stepPath(step.id), returnLabel: 'Retour au parcours', pathStep: step.id },
                    })
                  } else void startRun()
                }}
              >
                {preparing ? 'Préparation…' : s.exerciseDone ? 'Recommencer' : 'Commencer'}
              </Cta>
            </PartCard>
          )}
        </ol>
      )}

      {s.done && next && (
        <Cta className="mt-4 w-full" onClick={() => navigate(stepPath(next.id), { replace: true })}>
          Étape suivante
        </Cta>
      )}
    </div>
  )
}

function PartCard({ n, done, title, text, testId, extra, children }: {
  n: number
  done: boolean
  title: string
  text: string
  testId: string
  extra?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <li data-testid={testId} data-done={done ? '1' : '0'} className="rounded-xl bg-surface-2 p-4">
      <div className="mb-3 flex gap-3">
        <PartNumber n={n} done={done} />
        <span className="min-w-0 flex-1">
          <span className="block font-bold leading-tight">{title}</span>
          <span className="mt-0.5 block text-sm leading-snug text-neutral-400">{text}</span>
          {extra && <span className="mt-1.5 block">{extra}</span>}
        </span>
      </div>
      {children}
    </li>
  )
}

function PartNumber({ n, done }: { n: number; done: boolean }) {
  return (
    <span
      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-black ${done ? 'bg-accent text-white' : 'bg-surface-3 text-neutral-300'}`}
      aria-label={done ? 'Fait' : undefined}
    >
      {done ? '✓' : n}
    </span>
  )
}

// ---------- Série notée (puzzles, variantes, test de placement) ----------
function Runner({ run, setRun, exercise, title, backTo, isOver, onOver, onQuit, levelOfItem }: {
  run: StoredRun
  setRun: (r: StoredRun) => void
  exercise: PathExercise | null // null : test de placement (puzzles seuls)
  title: string
  backTo: string
  isOver: (results: boolean[]) => boolean
  onOver: (results: boolean[]) => Promise<void>
  onQuit: () => void
  levelOfItem?: (idx: number) => PathLevel
}) {
  const navigate = useNavigate()
  const engineRef = useRef<Engine | null>(null)
  const [retry, setRetry] = useState(0)
  // Verdicts posés de façon synchrone : un second verdict du même item (Réessayer du drill) est ignoré.
  const judged = useRef(new Set(run.results.map((_, i) => i)))
  const over = useRef(false)
  const [saveState, setSaveState] = useState<'idle' | 'ready' | 'saving' | 'error'>(() => isOver(run.results) ? 'ready' : 'idle')

  useEffect(
    () => () => {
      engineRef.current?.quit()
      engineRef.current = null
    },
    [],
  )

  function getEngine(): Engine {
    engineRef.current ??= new Engine()
    return engineRef.current
  }

  const item = run.items[run.idx]
  const verdict: boolean | undefined = run.results[run.idx]
  const phase = verdict === undefined ? 'play' : verdict ? 'success' : 'fail'

  function update(r: StoredRun) {
    writeRun(r)
    setRun(r)
  }

  function judge(ok: boolean) {
    if (judged.current.has(run.idx)) return
    judged.current.add(run.idx)
    const results = [...run.results, ok]
    update({ ...run, results })
    if (item.kind === 'variant' && exercise?.kind === 'opening') {
      const fam = getFamily(exercise.family)
      const v = fam?.variants.find((x) => x.line.uci === item.uci)
      if (v) void recordDrill('full', exercise.color, v.moves, ok).catch(() => {})
    }
  }

  async function advance() {
    if (run.results.length <= run.idx) return
    if (isOver(run.results)) {
      if (over.current) return
      over.current = true
      setSaveState('saving')
      try {
        await onOver(run.results)
      } catch {
        setSaveState('error')
        over.current = false
      }
      return
    }
    setRetry(0)
    update({ ...run, idx: run.idx + 1 })
  }

  // Variante sans coup du joueur (« non comptée ») : remplacée par une autre, la série n'avance pas.
  async function replaceVariant() {
    if (exercise?.kind !== 'opening') return
    const fam = getFamily(exercise.family)
    if (!fam) return
    const used = run.items.filter((i): i is { kind: 'variant'; uci: string } => i.kind === 'variant').map((i) => i.uci)
    const [uci] = await pickVariants(fam, exercise.color, 1, used)
    if (!uci) return
    const items = [...run.items]
    items[run.idx] = { kind: 'variant', uci }
    setRetry((t) => t + 1)
    update({ ...run, items })
  }

  function analyse(fen: string, moves: string[], orientation: 'w' | 'b', label: string) {
    navigate('/analyse', { state: { fen, uci: moves, viewIndex: 0, orientation, label, returnTo: backTo, returnLabel: 'Retour au parcours' } })
  }

  const dots = (
    <div className="flex justify-center gap-1.5 pb-2" data-testid="run-dots">
      {run.items.map((_, i) => (
        <span
          key={i}
          className={`h-2.5 w-2.5 rounded-full ${
            run.results[i] === true ? 'bg-accent' : run.results[i] === false ? 'bg-red-400' : i === run.idx ? 'bg-white' : 'bg-surface-3'
          }`}
        />
      ))}
    </div>
  )

  if (saveState !== 'idle') {
    return (
      <div className="pt-safe pb-safe fixed inset-0 z-40 flex flex-col items-center justify-center gap-4 bg-surface p-6 text-center" data-testid="run-save">
        <p role={saveState === 'error' ? 'alert' : 'status'}>
          {saveState === 'error' ? 'Impossible d’enregistrer le résultat. Il est conservé : libère de l’espace puis réessaie.' : saveState === 'saving' ? 'Enregistrement du résultat…' : 'Ton résultat est conservé et attend son enregistrement.'}
        </p>
        <Cta disabled={saveState === 'saving'} onClick={() => void advance()}>
          {saveState === 'error' ? 'Réessayer l’enregistrement' : 'Enregistrer le résultat'}
        </Cta>
      </div>
    )
  }

  if (item.kind === 'variant' && exercise?.kind === 'opening') {
    const fam = getFamily(exercise.family)
    const variant = fam?.variants.find((v) => v.line.uci === item.uci)
    if (!fam || !variant) {
      return (
        <div className="mx-auto flex max-w-lg flex-col items-center gap-4 p-6 pt-12 text-center">
          <p className="text-neutral-400">Cette variante n'existe plus dans la base d'ouvertures.</p>
          <Cta onClick={() => void replaceVariant()}>Une autre variante</Cta>
        </div>
      )
    }
    return (
      <OpeningDrill
        key={`${run.idx}-${retry}`}
        fam={fam}
        color={exercise.color}
        item={{ mode: 'full', variant, start: 0, position: null }}
        plyTarget={null}
        getEngine={getEngine}
        session={{ ok: 0, total: 0 }}
        title={`Variante ${run.idx + 1}/${run.items.length}`}
        subtitle={`Réussis ${(exercise as OpeningExercise).pass} variantes sur ${exercise.count} pour valider l'étape.`}
        onResult={judge}
        onRetry={() => setRetry((t) => t + 1)}
        onNext={() => (run.results.length > run.idx ? advance() : void replaceVariant())}
        onClose={onQuit}
        onAnalyse={(moves) => analyse('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', moves, exercise.color, openingFamilyFr(fam.key))}
        nextLabel={run.results.length > run.idx && isOver(run.results) ? 'Voir le résultat' : 'Suivant'}
      />
    )
  }
  if (item.kind !== 'puzzle') return null
  const p = item.puzzle
  const lvl = levelOfItem?.(run.idx)
  // Les thèmes livreraient la solution : après le verdict seulement.
  const banner = `Puzzle ${p.id} · ${p.rating}${phase !== 'play' ? ` · ${displayThemes(p.themes).join(', ')}` : ''}`
  return (
    <div className="pt-safe pb-safe fixed inset-0 z-40 overflow-y-auto overscroll-contain bg-surface">
      <div data-run={run.key} data-puzzle-id={p.id} data-run-idx={run.idx} className="mx-auto flex min-h-full max-w-2xl flex-col">
        <header className="flex items-center px-3 py-1">
          <button onClick={onQuit} aria-label="Quitter la série" className="cursor-pointer p-1.5 text-2xl text-neutral-400 hover:text-white">
            ✕
          </button>
          <h1 className="min-w-0 flex-1 truncate text-center text-lg font-black">
            {title}
            <span className="ml-2 text-sm font-semibold text-neutral-500">
              {run.idx + 1}/{run.items.length}
            </span>
          </h1>
          <span className="w-9" />
        </header>
        {lvl && (
          <p className="pb-1 text-center text-xs font-bold tracking-wide uppercase" style={{ color: lvl.color }}>
            Niveau {lvl.title} · ≈ {lvl.elo}
          </p>
        )}
        {dots}
        <p className="mx-3 mb-2 truncate rounded bg-surface-2 px-3 py-1.5 text-center text-sm font-semibold">{banner}</p>
        <div className="flex justify-center px-3">
          <div className="boardbox md:w-[min(56vh,520px)]">
            <PuzzlePlayer
              key={`${run.idx}-${p.id}`}
              puzzle={p}
              onComplete={(ok) => {
                if (phase === 'play') judge(ok)
              }}
            />
          </div>
        </div>
        {phase !== 'play' && (
          <div className="flex items-center gap-2 px-3 py-2">
            <span className={`shrink-0 text-lg leading-tight font-black whitespace-nowrap ${phase === 'success' ? 'text-accent' : 'text-red-400'}`}>
              {phase === 'success' ? '✓ Réussi !' : '✗ Raté'}
            </span>
            <div className="ml-auto flex items-center gap-1">
              <button
                onClick={() => analyse(p.fen, p.moves, p.fen.split(' ')[1] === 'w' ? 'b' : 'w', `Puzzle ${p.id} (${p.rating})`)}
                className="flex cursor-pointer flex-col items-center rounded px-1.5 py-1 text-xs font-semibold text-neutral-300 hover:text-white"
              >
                <span className="text-lg leading-none">♞</span>
                Analyser
              </button>
              <Cta className="ml-1 px-5 py-2 text-base" onClick={advance}>
                {isOver(run.results) ? 'Voir le résultat' : 'Suivant'}
              </Cta>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function RunEnd({ title, score, count, pass, passed, onNext, onRetry, onMap }: {
  title: string
  score: number
  count: number
  pass: number
  passed: boolean
  onNext: (() => void) | null
  onRetry: () => void
  onMap: () => void
}) {
  const stars = starsFor(score, count, pass)
  return (
    <div data-run-end={passed ? 'passed' : 'failed'} className="pt-safe pb-safe fixed inset-0 z-40 overflow-y-auto overscroll-contain bg-surface">
      <div className="mx-auto flex min-h-full max-w-lg flex-col items-center justify-center gap-4 p-6 text-center">
        <div className="text-6xl">{passed ? '🏆' : '📚'}</div>
        <p className="text-sm font-semibold text-neutral-400">{title}</p>
        <h1 className="text-2xl font-black">
          {score}/{count} réussi{score > 1 ? 's' : ''}
        </h1>
        <Stars n={stars} size="text-4xl" />
        <p className={`font-bold ${passed ? 'text-accent' : 'text-neutral-300'}`}>
          {passed ? 'Étape validée !' : `Il en faut ${pass} sur ${count} pour valider l'étape.`}
        </p>
        {onNext && (
          <Cta className="w-full" onClick={onNext}>
            Étape suivante
          </Cta>
        )}
        <Cta variant={onNext ? 'secondary' : 'primary'} className="w-full" onClick={onRetry}>
          Recommencer
        </Cta>
        <Cta variant="secondary" className="w-full" onClick={onMap}>
          Retour au parcours
        </Cta>
      </div>
    </div>
  )
}

// ---------- Test de placement ----------
function PlacementPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [run, setRun] = useState<StoredRun | null>(() => readRun(PLACEMENT_ID))
  const [result, setResult] = useState<number | null>(null)
  const [preparing, setPreparing] = useState(false)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    if (location.state) navigate('.', { replace: true, state: null })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function start() {
    setPreparing(true)
    setLoadError(false)
    try {
      const items: RunItem[] = pickPlacementPuzzles(await loadPuzzles()).map((puzzle) => ({ kind: 'puzzle', puzzle }))
      const r: StoredRun = { key: PLACEMENT_ID, nonce: Date.now(), items, idx: 0, results: [] }
      writeRun(r)
      setRun(r)
    } catch (e) {
      console.error('[parcours] test non construit', e)
      setLoadError(true)
    } finally {
      setPreparing(false)
    }
  }

  async function finish(results: boolean[]) {
    const n = placementLevels(results)
    await recordPlacement(n)
    clearRun()
    setResult(n)
  }

  if (result !== null) {
    const startLevel = LEVELS[result] ?? null
    return (
      <div data-placement-end={result} className="pt-safe pb-safe fixed inset-0 z-40 overflow-y-auto overscroll-contain bg-surface">
        <div className="mx-auto flex min-h-full max-w-lg flex-col items-center justify-center gap-4 p-6 text-center">
          <div className="text-6xl">{result > 0 ? '🚀' : '🌱'}</div>
          <h1 className="text-2xl font-black">
            {result === 0 ? 'On commence par le début' : result >= LEVELS.length ? 'Tous les niveaux sont acquis' : `Niveau de départ : ${startLevel!.title}`}
          </h1>
          <p className="text-neutral-400">
            {result === 0
              ? 'Le niveau Débutant est fait pour toi : ses étapes iront vite si tu les connais déjà.'
              : `${LEVELS.slice(0, result).map((l) => l.title).join(', ')} : acquis. Leurs étapes restent ouvertes si tu veux les revoir.`}
          </p>
          <Cta className="w-full" onClick={() => navigate(MAP_PATH, { replace: true })}>
            Voir le parcours
          </Cta>
        </div>
      </div>
    )
  }

  if (run) {
    return (
      <Runner
        key={run.nonce}
        run={run}
        setRun={setRun}
        exercise={null}
        title="🧪 Test de placement"
        backTo={stepPath(PLACEMENT_ID)}
        isOver={(results) => placementOver(results)}
        onOver={finish}
        onQuit={() => {
          clearRun()
          navigate(MAP_PATH, { replace: true })
        }}
        levelOfItem={(idx) => LEVELS[Math.floor(idx / PLACEMENT_PER_LEVEL)]}
      />
    )
  }

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6" data-step-page={PLACEMENT_ID}>
      <button onClick={() => navigate(MAP_PATH, { replace: true })} className="mb-3 cursor-pointer text-sm font-semibold text-neutral-400 hover:text-white">
        ← Parcours
      </button>
      <h1 className="mb-1 text-2xl font-black">🧪 Test de placement</h1>
      <p className="mb-4 text-sm text-neutral-400">
        {PLACEMENT_PER_LEVEL} puzzles par niveau, du plus simple au plus dur. Réussis-en {2} sur {PLACEMENT_PER_LEVEL} pour valider un niveau et passer au
        suivant ; le test s'arrête au premier niveau manqué. Les niveaux validés sont acquis : tu commences au suivant.
      </p>
      <ul className="mb-4 space-y-2">
        {LEVELS.map((l) => (
          <li key={l.id} className="flex items-center gap-3 rounded-xl bg-surface-2 px-4 py-2.5">
            <span className="h-3 w-3 rounded-full" style={{ backgroundColor: l.color }} aria-hidden="true" />
            <span className="flex-1 font-bold">{l.title}</span>
            <span className="text-sm text-neutral-400">
              puzzles {l.placement.rating[0]} à {l.placement.rating[1]}
            </span>
          </li>
        ))}
      </ul>
      {loadError && (
        <p role="alert" className="mb-2 rounded bg-red-900/40 px-3 py-2 text-sm text-red-200">
          Impossible de charger les puzzles. Vérifie ta connexion, puis réessaie.
        </p>
      )}
      <Cta className="w-full" disabled={preparing} onClick={() => void start()}>
        {preparing ? 'Préparation…' : 'Commencer le test'}
      </Cta>
      <p className="mt-3 text-center text-xs text-neutral-500">Un test raté ne fait rien perdre : seul le meilleur résultat compte.</p>
    </div>
  )
}
