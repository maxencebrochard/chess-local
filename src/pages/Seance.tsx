// Séance du jour (/seance) : entraînement guidé de 10 à 15 minutes qui enchaîne quelques blocs
// courts (révision due, puzzles à son niveau, variante ratée, attaque ou finale), chacun joué avec
// le lecteur de son écran d'origine et noté là où cet écran note. Plan dans lib/seance.ts,
// chargement et persistance dans lib/seanceRun.ts ; un rendu par type de bloc (RENDER).
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Chess, DEFAULT_POSITION } from 'chess.js'
import { Cta } from '../components/Cta'
import { PageHeader } from '../components/PageHeader'
import { MistakeExercise } from '../components/MistakeExercise'
import { OpeningDrill } from '../components/OpeningDrill'
import { PositionGame } from '../components/PositionGame'
import { PuzzlePlayer, type PuzzleData } from '../components/PuzzlePlayer'
import { ATTACKS, attackGameProps, gameKey, loadLevel } from '../lib/attack'
import { recordReplaced } from '../lib/attempts'
import { getRating, type Mistake } from '../lib/db'
import { Engine } from '../lib/engine'
import { ENDGAMES } from '../lib/learn'
import { recordDrill } from '../lib/openingTrainer'
import { endgameGameProps, loadStoredGame, resumedGame } from '../lib/positionGame'
import { recordRatedPuzzle } from '../lib/puzzles'
import { displayThemes } from '../lib/puzzleThemes'
import { recordReview, resolveVariant, returnLabel, statusLabel, variantKey, type ReviewPayload } from '../lib/revision'
import {
  BLOCK_META, estimateMinutes, minutesLabel, stepDuration, streak, streakLabel, summarize, type BlockKind, type PlannedBlock,
} from '../lib/seance'
import {
  buildSeance, readStoredSeance, recordSeance, seanceDates, writeStoredSeance, type SeanceResult, type Step, type StoredSeance,
} from '../lib/seanceRun'
import { sounds } from '../lib/sounds'

const BACK = { returnTo: '/seance', returnLabel: 'Retour à la séance' }

interface Preview {
  blocks: PlannedBlock[]
  steps: Step[]
  rating: number
  puzzlesUnavailable: boolean
}

interface Recap {
  kinds: BlockKind[]
  results: SeanceResult[]
  ratingStart: number
}

export default function Seance() {
  const navigate = useNavigate()
  const location = useLocation()
  // Séance en cours (null : accueil de la séance ou bilan).
  const [run, setRun] = useState<StoredSeance | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [recap, setRecap] = useState<Recap | null>(null)
  const [dates, setDates] = useState<number[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [restored, setRestored] = useState(false) // retour de l'analyse
  const [retryTick, setRetryTick] = useState(0)
  const [saveError, setSaveError] = useState(false)
  const engineRef = useRef<Engine | null>(null)
  // Étapes déjà jugées, posées de façon synchrone : un second verdict (Réessayer, Rejouer) n'écrit
  // jamais deux fois pour la séance.
  const recorded = useRef(new Set<number>())
  // Une seule chaîne pour toutes les écritures des étapes : l'Elo puzzle est lu puis écrit, deux
  // puzzles enchaînés vite ne doivent pas partir du même classement. Le bilan attend la dernière.
  const writes = useRef<Promise<unknown>>(Promise.resolve())
  // Compléments de résultat rendus par les écritures (note, classement), relus par le bilan.
  const patches = useRef(new Map<number, Partial<SeanceResult>>())
  const ended = useRef(false) // bilan déjà lancé : une seule ligne `seance`, même en StrictMode

  useEffect(
    () => () => {
      engineRef.current?.quit()
      engineRef.current = null
    },
    [],
  )

  // Arrivée : séance en cours reprise (tuile « Reprendre », retour de l'analyse, rechargement),
  // sinon plan d'une nouvelle séance.
  useEffect(() => {
    const restore = !!(location.state as { restore?: boolean } | null)?.restore
    if (location.state) navigate('.', { replace: true, state: null })
    void seanceDates().then(setDates, () => setDates([]))
    const saved = readStoredSeance()
    if (saved) {
      recorded.current = new Set(saved.results.map((r) => r.idx))
      // Une variante déjà jugée ne se restaure pas sur son verdict (le drill repartirait du premier
      // coup) : la séance reprend à l'étape suivante, ou à son bilan.
      const judgedVariant = drillOf(saved.steps[saved.idx]) !== null && saved.results.some((r) => r.idx === saved.idx)
      setLoading(false)
      if (judgedVariant && saved.idx + 1 >= saved.steps.length) {
        void end(saved)
        return
      }
      setRestored(restore)
      setRun(judgedVariant ? { ...saved, idx: saved.idx + 1, phase: 'play', stepStartedAt: Date.now() } : saved)
      return
    }
    void prepare()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Persistance de la séance en cours. Tant que rien n'est chargé, la clé n'est pas touchée : en
  // StrictMode, les effets du montage rejouent, et un retrait ici ferait perdre la séance à reprendre.
  useEffect(() => {
    if (loading) return
    writeStoredSeance(run)
  }, [run, loading])

  const step = run ? run.steps[run.idx] : null
  const isGame = step?.kind === 'attack' || step?.kind === 'endgame'
  // Partie contre Stockfish : PositionGame a son propre moteur, celui de la séance (fautes,
  // drills) s'arrête. Étape ouverte : sa partie se reprendra telle quelle.
  useEffect(() => {
    if (!isGame || !run) return
    engineRef.current?.quit()
    engineRef.current = null
    if (!run.opened.includes(run.idx)) setRun((r) => (r && !r.opened.includes(r.idx) ? { ...r, opened: [...r.opened, r.idx] } : r))
  }, [isGame, run])

  async function prepare() {
    setLoading(true)
    setRecap(null)
    try {
      const built = await buildSeance()
      setPreview({ blocks: built.plan.blocks, steps: built.steps, rating: built.rating, puzzlesUnavailable: built.puzzlesUnavailable })
    } catch {
      setPreview({ blocks: [], steps: [], rating: 0, puzzlesUnavailable: false })
    }
    setLoading(false)
  }

  function start() {
    if (!preview || !preview.steps.length) return
    recorded.current.clear()
    patches.current.clear()
    ended.current = false
    setSaveError(false)
    setRestored(false)
    setRetryTick(0)
    const now = Date.now()
    setRun({ startedAt: now, steps: preview.steps, idx: 0, phase: 'play', results: [], stepStartedAt: now, opened: [], ratingStart: preview.rating })
  }

  function getEngine(): Engine {
    engineRef.current ??= new Engine()
    return engineRef.current
  }

  // Verdict d'une étape : seule la première tentative compte pour la séance. `write` : l'écriture
  // de l'écran d'origine (absente pour attaque et finale, que PositionGame note lui-même), qui peut
  // compléter le résultat (note affichée sous le verdict, classement).
  function judge(success: boolean, write?: () => Promise<Partial<SeanceResult> | null>, note: string | null = null) {
    if (!run) return
    const idx = run.idx
    const kind = run.steps[idx].kind
    setRun((r) => (r && r.idx === idx ? { ...r, phase: success ? 'success' : 'fail' } : r))
    if (recorded.current.has(idx)) return
    recorded.current.add(idx)
    const result: SeanceResult = { idx, kind, ok: success, ms: stepDuration(run.stepStartedAt, Date.now()), note }
    setRun((r) => (r ? { ...r, results: [...r.results, result] } : r))
    if (!write) return
    // Chaîne jamais empoisonnée : un échec d'écriture est signalé, sans bloquer la suite.
    writes.current = writes.current.then(write).then(
      (patch) => {
        setSaveError(false)
        if (!patch) return
        patches.current.set(idx, patch)
        setRun((r) => (r ? { ...r, results: r.results.map((x) => (x.idx === idx ? { ...x, ...patch } : x)) } : r))
      },
      () => setSaveError(true),
    )
  }

  function next() {
    if (!run) return
    if (run.idx + 1 < run.steps.length) {
      setRetryTick(0)
      setRestored(false)
      setRun({ ...run, idx: run.idx + 1, phase: 'play', stepStartedAt: Date.now() })
    } else {
      void end(run)
    }
  }

  // Bilan : après la dernière écriture, la séance quitte sessionStorage et s'inscrit une fois dans
  // `learnSessions` (série de jours).
  async function end(r: StoredSeance) {
    if (ended.current) return
    ended.current = true
    await writes.current
    const results = r.results.map((x) => ({ ...x, ...patches.current.get(x.idx) }))
    const kinds = r.steps.map((s) => s.kind)
    setRecap({ kinds, results, ratingStart: r.ratingStart })
    setRun(null)
    writeStoredSeance(null)
    try {
      await recordSeance(kinds, results.filter((x) => x.ok).length)
    } catch {
      setSaveError(true)
    }
    setDates(await seanceDates().catch(() => []))
  }

  function retry() {
    setRetryTick((t) => t + 1)
    setRun((r) => (r ? { ...r, phase: 'play' } : r))
  }

  function quit() {
    navigate('/', { replace: true })
  }

  function analyse(s: Step, moves?: string[]) {
    const p = puzzleOf(s)
    const m = s.kind === 'revision' ? mistakeOf(s.payload) : null
    const d = drillOf(s)
    if (p) {
      navigate('/analyse', {
        state: { fen: p.fen, uci: p.moves, viewIndex: 0, orientation: p.fen.split(' ')[1] === 'w' ? 'b' : 'w', label: `Puzzle ${p.id} (${p.rating})`, ...BACK },
      })
    } else if (m) {
      navigate('/analyse', { state: { fen: m.fenBefore, orientation: new Chess(m.fenBefore).turn(), label: m.gameLabel, ...BACK } })
    } else if (d) {
      navigate('/analyse', { state: { fen: DEFAULT_POSITION, uci: moves ?? d.uci.split(' '), orientation: d.color, label: d.label, ...BACK } })
    }
  }

  // ---------- Chargement ----------
  if (loading) return <div className="p-8 text-center text-neutral-400">Préparation de la séance…</div>

  const s = dates ? streak(dates) : null

  // ---------- Bilan ----------
  if (recap) {
    const ok = recap.results.filter((r) => r.ok).length
    const total = recap.results.length
    const ms = recap.results.reduce((a, r) => a + r.ms, 0)
    const lastRating = [...recap.results].reverse().find((r) => r.rating !== undefined)?.rating
    return (
      <div data-seance-end className="pt-safe pb-safe fixed inset-0 z-40 overflow-y-auto overscroll-contain bg-surface">
        <div className="mx-auto flex min-h-full max-w-lg flex-col items-center justify-center gap-4 p-6 text-center">
          <div className="text-6xl" aria-hidden="true">{total > 0 && ok === total ? '🏆' : ok > 0 ? '💪' : '📚'}</div>
          <h1 className="text-2xl font-black">Séance terminée</h1>
          <p data-seance-score className="-mt-2 text-lg font-bold">
            {ok}/{total} réussi{ok > 1 ? 's' : ''} · {minutesLabel(ms)}
          </p>
          {s && s.days > 0 && (
            <p data-seance-streak className="rounded-full bg-orange-500/15 px-4 py-1.5 text-base font-black text-orange-300">
              {streakLabel(s.days)} d'affilée
            </p>
          )}
          {saveError && <SaveAlert />}
          <ul className="w-full text-left text-sm">
            {summarize(recap.kinds, recap.results).map((b, i) => (
              <li key={i} data-seance-block={b.kind} className="flex items-center gap-3 border-b border-white/10 py-2.5">
                <span className="text-xl" aria-hidden="true">{BLOCK_META[b.kind].emoji}</span>
                <span className="min-w-0 flex-1">
                  <span className="block font-bold">{BLOCK_META[b.kind].label}</span>
                  {b.kind === 'puzzles' && lastRating !== undefined && (
                    <span data-seance-rating className="block text-xs text-neutral-400">
                      Classement {recap.ratingStart} → {lastRating}
                    </span>
                  )}
                </span>
                <span className={`shrink-0 font-black tabular-nums ${b.ok === b.steps ? 'text-accent' : b.ok > 0 ? 'text-neutral-200' : 'text-red-400'}`}>
                  {b.ok}/{b.steps}
                </span>
              </li>
            ))}
          </ul>
          <Cta className="w-full" onClick={quit}>
            Terminer
          </Cta>
        </div>
      </div>
    )
  }

  // ---------- Accueil de la séance ----------
  if (!run || !step) {
    const steps = preview?.steps ?? []
    const blocks = (preview?.blocks ?? []).map((b) => ({ ...b, count: steps.filter((x) => x.kind === b.kind).length })).filter((b) => b.count > 0)
    return (
      <div data-seance-intro className="mx-auto max-w-lg p-4 md:p-6">
        <PageHeader title="☀️ Séance du jour" back={{ label: 'Accueil', onClick: quit }}
          description="Quelques blocs courts, choisis d'après ce que tu as à travailler, enchaînés sans avoir à choisir." />

        <div className="mb-4 flex items-center gap-2 rounded-xl bg-surface-2 px-4 py-3">
          <span className="min-w-0 flex-1">
            <span data-seance-estimate className="block text-lg font-black">≈ {estimateMinutes(steps.map((x) => x.kind))} min</span>
            <span className="block text-xs text-neutral-400">
              {steps.length} étape{steps.length > 1 ? 's' : ''}
            </span>
          </span>
          {s && (
            <span data-seance-streak className={`shrink-0 text-right text-sm font-bold ${s.days > 0 ? 'text-orange-300' : 'text-neutral-400'}`}>
              {s.days > 0 ? streakLabel(s.days) : 'Pas encore de série'}
              {s.today && <span className="block text-xs font-semibold text-accent">✓ Faite aujourd'hui</span>}
            </span>
          )}
        </div>

        {preview?.puzzlesUnavailable && (
          <p role="alert" className="mb-3 rounded bg-amber-900/40 px-3 py-2 text-sm text-amber-200">
            Puzzles indisponibles (vérifie ta connexion) : la séance continue sans eux.
          </p>
        )}

        {blocks.length > 0 ? (
          <ol className="mb-5 flex flex-col gap-2">
            {blocks.map((b, i) => (
              <li key={i} data-seance-plan={b.kind} className="flex items-center gap-3 rounded-xl bg-surface-2 px-3 py-2.5">
                <span className="text-2xl" aria-hidden="true">{BLOCK_META[b.kind].emoji}</span>
                <span className="min-w-0 flex-1">
                  <span className="block font-bold">
                    {BLOCK_META[b.kind].label}
                    {b.count > 1 && <span className="font-semibold text-neutral-400"> · {b.count}</span>}
                  </span>
                  <span className="block text-xs text-neutral-400">{b.reason}</span>
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mb-5 rounded-xl bg-surface-2 px-4 py-6 text-center text-sm text-neutral-400">Impossible de préparer une séance pour le moment.</p>
        )}

        {blocks.length > 0 ? (
          <Cta className="w-full" onClick={start}>
            {s?.today ? 'Refaire une séance' : 'Commencer'}
          </Cta>
        ) : (
          <Cta className="w-full" onClick={() => void prepare()}>
            Réessayer
          </Cta>
        )}
        <div className="mt-4 text-center">
          <Link to="/" replace className="inline-flex min-h-11 items-center text-sm font-semibold text-accent underline underline-offset-2">
            Retour à l'accueil
          </Link>
        </div>
      </div>
    )
  }

  // ---------- Étape en cours ----------
  const cur = run
  const result = cur.results.find((r) => r.idx === cur.idx) ?? null
  const progress = `${cur.idx + 1}/${cur.steps.length}`
  const nextLabel = cur.idx + 1 >= cur.steps.length ? 'Voir le bilan' : 'Suivant'
  const key = `${cur.idx}-${retryTick}`
  const blockLabel = `${BLOCK_META[step.kind].emoji} ${BLOCK_META[step.kind].label}`

  // Variante (révision ou bloc ouverture) : le drill porte lui-même son plein écran.
  function renderDrill(d: { color: 'w' | 'b'; uci: string; label: string }, review: ReviewPayload | null) {
    // La famille (non sérialisable) se résout au rendu ; le repli ne sert qu'à une séance reprise
    // après une mise à jour d'openings.json.
    const resolved = resolveVariant(variantKey(d.color, d.uci))
    if (!resolved) return <Missing text="Cette variante n'existe plus dans la base d'ouvertures." onNext={next} label={nextLabel} />
    return (
      <OpeningDrill
        key={key}
        fam={resolved.fam}
        color={resolved.color}
        item={{ mode: 'full', variant: resolved.variant, start: 0, position: null }}
        plyTarget={null}
        getEngine={getEngine}
        session={{ ok: 0, total: 0 }}
        title={`☀️ Séance ${progress}`}
        subtitle={review ? `${blockLabel} · ${statusLabel(review.item)}` : blockLabel}
        onResult={(ok) =>
          judge(
            ok,
            async () => {
              if (review) await recordReview(review, ok)
              else await recordDrill('full', d.color, d.uci.split(' '), ok)
              return null
            },
            review ? returnLabel(ok ? review.item.box + 1 : 0) : null,
          )
        }
        onRetry={retry}
        onNext={next}
        onClose={quit}
        onAnalyse={(moves) => analyse(step!, moves)}
        nextLabel={nextLabel}
        resultNote={result?.note ?? null}
      />
    )
  }

  // Attaque, finale : la partie contre Stockfish de l'écran d'origine (mêmes clé, défenseur et
  // écritures). À la première ouverture, une partie en cours de la même position est reprise, sauf
  // une tentative déjà notée ; une étape jugée reprend sa partie terminée (analyse, rechargement).
  function renderGame(gk: string, fen: string, game: (resume: boolean, restoreFinished: boolean, level: number | null) => ReactNode) {
    const judged = result !== null
    const firstOpen = !cur.opened.includes(cur.idx)
    const resume = judged || !firstOpen || !resumedGame(gk, fen, false)?.recorded
    const stored = loadStoredGame()
    const same = resume && stored && stored.key === gk && stored.startFen === fen && stored.level !== undefined
    return (
      <div data-seance-step={step!.kind} className="pt-safe pb-safe fixed inset-0 z-40 bg-surface">
        {game(resume, judged || restored, same ? stored.level! : loadLevel())}
      </div>
    )
  }

  const chip = (
    <span data-seance-progress className="flex h-8 shrink-0 items-center rounded-full bg-surface-2 px-2.5 text-xs font-bold tabular-nums text-neutral-200">
      ☀️ {progress}
    </span>
  )

  function renderAttack(id: string) {
    const pos = ATTACKS.find((a) => a.id === id)
    if (!pos) return <Missing text="Cette position d'attaque n'existe plus." onNext={next} label={nextLabel} />
    return renderGame(gameKey(pos.id), pos.fen, (resume, restoreFinished, level) => {
      const base = attackGameProps(pos, level)
      return (
        <PositionGame
          key={key}
          {...base}
          resume={resume}
          restoreFinished={restoreFinished}
          {...BACK}
          headerAction={chip}
          onExit={quit}
          onOther={next}
          otherLabel={nextLabel}
          onReplace={recordReplaced}
          onFinished={(ok, info) => {
            base.onFinished(ok, info)
            judge(ok)
          }}
        />
      )
    })
  }

  function renderEndgame(id: string) {
    const eg = ENDGAMES.find((e) => e.id === id)
    if (!eg) return <Missing text="Cette finale n'existe plus." onNext={next} label={nextLabel} />
    return renderGame(`finale:${eg.id}`, eg.fen, (resume, restoreFinished) => {
      const base = endgameGameProps(eg)
      return (
        <PositionGame
          key={key}
          {...base}
          resume={resume}
          restoreFinished={restoreFinished}
          {...BACK}
          headerAction={chip}
          onExit={quit}
          onOther={next}
          otherLabel={nextLabel}
          onReplace={recordReplaced}
          onFinished={(ok) => {
            base.onFinished(ok)
            judge(ok)
          }}
        />
      )
    })
  }

  // Puzzle (classé ou de révision), faute de partie, attaque manquée, défense ratée : cadre de la
  // séance autour du lecteur, même gabarit que la révision.
  function renderFramed(review: ReviewPayload | null, puzzle: PuzzleData | null) {
    const mistake = review ? mistakeOf(review) : null
    const phase = cur.phase
    // Les thèmes (« Mat en 1 », « Fourchette ») livreraient la solution : après le verdict seulement.
    const banner = puzzle
      ? `Puzzle ${puzzle.id} · ${puzzle.rating}${phase !== 'play' ? ` · ${displayThemes(puzzle.themes).join(', ')}` : ''}`
      : review?.kind === 'missed-attack' ? 'Attaque manquée' : review?.kind === 'missed-defense' ? 'Défense ratée' : null
    const subtitle = review ? `${blockLabel} · ${statusLabel(review.item)}` : blockLabel

    function onVerdict(ok: boolean) {
      if (!review && puzzle) {
        const p = puzzle
        judge(ok, async () => {
          const before = (await getRating('puzzle')).value
          const after = await recordRatedPuzzle(p, ok)
          return { note: `Classement ${after} (${after >= before ? '+' : ''}${after - before})`, rating: after }
        })
      } else if (review) {
        // Puzzles de révision : PuzzlePlayer a déjà joué le verdict ; les fautes le jouent ici.
        if (mistake) (ok ? sounds.success : sounds.fail)()
        judge(
          ok,
          async () => {
            await recordReview(review, ok)
            return null
          },
          returnLabel(ok ? review.item.box + 1 : 0),
        )
      }
    }

    return (
      <div data-seance-step={step!.kind} className="pt-safe pb-safe fixed inset-0 z-40 overflow-y-auto overscroll-contain bg-surface">
        <div data-seance-item={mistake ? 'mistake' : 'puzzle'} className="mx-auto flex min-h-full max-w-2xl flex-col">
          <header className="flex items-center px-3 py-1">
            <button onClick={quit} aria-label="Quitter la séance" className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-2xl leading-none text-neutral-400 hover:text-white">
              ✕
            </button>
            <h1 className="flex-1 text-center text-lg font-black">
              ☀️ Séance
              <span data-seance-progress className="ml-2 text-sm font-semibold text-neutral-400">{progress}</span>
            </h1>
            <span className="w-9" />
          </header>
          <p className="px-3 pb-2 text-center text-xs font-semibold text-neutral-400">{subtitle}</p>
          {saveError && <div className="mx-3 mb-2"><SaveAlert /></div>}
          {banner && <p data-seance-banner className="mx-3 mb-2 truncate rounded bg-surface-2 px-3 py-1.5 text-center text-sm font-semibold">{banner}</p>}
          {puzzle ? (
            <div className="flex justify-center px-3">
              <div className="boardbox md:w-[min(56vh,520px)]">
                <PuzzlePlayer
                  key={key}
                  puzzle={puzzle}
                  onComplete={(ok) => {
                    if (phase === 'play') onVerdict(ok)
                  }}
                />
              </div>
            </div>
          ) : mistake ? (
            <MistakeExercise key={key} mistake={mistake} active={phase === 'play'} onFinish={onVerdict} getEngine={getEngine} />
          ) : null}
          {phase !== 'play' && (
            // Une seule rangée à 393 px : verdict et note empilés, actions serrées à droite.
            <div className="flex items-center gap-2 px-3 py-2">
              <div className="flex min-w-0 shrink-0 flex-col whitespace-nowrap">
                <span className={`text-lg leading-tight font-black ${phase === 'success' ? 'text-accent' : 'text-red-400'}`}>
                  {phase === 'success' ? '✓ Réussi !' : '✗ Raté'}
                </span>
                {result?.note && (
                  <span data-seance-note className="text-xs leading-tight font-semibold text-neutral-400">
                    {result.note}
                  </span>
                )}
              </div>
              <div className="ml-auto flex items-center gap-1">
                <button onClick={retry} className="flex cursor-pointer flex-col items-center rounded px-1.5 py-1 text-xs font-semibold text-neutral-300 hover:text-white">
                  <span className="text-lg leading-none">↺</span>
                  Réessayer
                </button>
                <button onClick={() => analyse(step!)} className="flex cursor-pointer flex-col items-center rounded px-1.5 py-1 text-xs font-semibold text-neutral-300 hover:text-white">
                  <span className="text-lg leading-none">♞</span>
                  Analyser
                </button>
                <Cta className="ml-1 px-5 py-2 text-base" onClick={next}>
                  {nextLabel}
                </Cta>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // Un rendu par type de bloc : un type ajouté sans son rendu ne compile pas.
  const RENDER: Record<BlockKind, (s: Step) => ReactNode> = {
    revision: (s) => {
      const review = (s as Extract<Step, { kind: 'revision' }>).payload
      return review.kind === 'variant' ? renderDrill(review, review) : renderFramed(review, review.kind === 'puzzle' ? review.puzzle : null)
    },
    puzzles: (s) => renderFramed(null, (s as Extract<Step, { kind: 'puzzles' }>).puzzle),
    opening: (s) => renderDrill(s as Extract<Step, { kind: 'opening' }>, null),
    endgame: (s) => renderEndgame((s as Extract<Step, { kind: 'endgame' }>).id),
    attack: (s) => renderAttack((s as Extract<Step, { kind: 'attack' }>).id),
  }
  return RENDER[step.kind](step)
}

// Variante à jouer d'une étape (bloc ouverture, ou variante de la révision), sinon null.
function drillOf(step: Step | undefined): { color: 'w' | 'b'; uci: string; label: string } | null {
  if (!step) return null
  if (step.kind === 'opening') return step
  if (step.kind === 'revision' && step.payload.kind === 'variant') return step.payload
  return null
}

// Puzzle d'une étape (classé, ou de la révision), sinon null.
function puzzleOf(step: Step): PuzzleData | null {
  if (step.kind === 'puzzles') return step.puzzle
  if (step.kind === 'revision' && step.payload.kind === 'puzzle') return step.payload.puzzle
  return null
}

function Missing({ text, onNext, label }: { text: string; onNext: () => void; label: string }) {
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-4 p-6 pt-12 text-center">
      <p className="text-neutral-400">{text}</p>
      <Cta onClick={onNext}>{label}</Cta>
    </div>
  )
}

function SaveAlert() {
  return (
    <p role="alert" className="w-full rounded bg-red-900/40 px-3 py-2 text-sm text-red-200">
      La dernière tentative n'a pas pu être enregistrée (stockage indisponible).
    </p>
  )
}

// Faute à retrouver d'une révision (faute de partie, attaque manquée, défense ratée), sinon null.
function mistakeOf(review: ReviewPayload): Mistake | null {
  return review.kind === 'puzzle' || review.kind === 'variant' ? null : review.mistake
}
