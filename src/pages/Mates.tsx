// « Mats éclair » (/mats) : entraînement aux schémas de mat pour le bullet.
// Accueil (quatre familles d'exercices et records) → fiche d'un schéma (`?d=<id>` : le retour
// arrière du téléphone ramène à l'accueil) → série (contre la montre ou puzzles).
import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { BackButton, PageHeader } from '../components/PageHeader'
import { PuzzleModes } from '../components/PuzzleModes'
import { groupBack, originGroup } from '../lib/navigation'
import { Cta } from '../components/Cta'
import type { PuzzleData } from '../components/PuzzlePlayer'
import { ChronoRun } from '../components/mates/ChronoRun'
import { NetBoard } from '../components/mates/NetBoard'
import { PuzzleRun } from '../components/mates/PuzzleRun'
import { Sparkline } from '../components/mates/RunParts'
import { Engine } from '../lib/engine'
import {
  CADENCE_LABEL, CHRONO_CADENCES, chronoPool, drillBest, drillById, DRILLS, loadMatsStats, pieceCount, puzzleFinalFen,
  MATS_RETURN_SCREEN, puzzlePool, readPrefs, RUSH_CADENCES, runKey, SECTIONS, writePrefs,
  type Cadence, type ChronoRunSummary, type Drill, type MatsReturn, type MatsStats, type PuzzleRunSummary,
} from '../lib/mates'
import { clearExercise, isRestore, readExercise } from '../lib/exerciseReturn'
import { loadPuzzles } from '../lib/puzzles'

export default function Mates() {
  const location = useLocation()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const drill = drillById(params.get('d') ?? '') ?? null
  const [stats, setStats] = useState<MatsStats | null>(null)
  const [run, setRun] = useState<{ drill: Drill; cadence: Cadence; restored?: PuzzleRunSummary | ChronoRunSummary } | null>(null)
  // Retour de l'analyseur : bilan de la série close, réaffiché sur la fiche de son schéma.
  const returned = useRef(isRestore(location.state) ? readExercise<MatsReturn>(MATS_RETURN_SCREEN) : null)
  const [puzzles, setPuzzles] = useState<PuzzleData[] | null>(null)
  const [loadError, setLoadError] = useState(false)
  const engineRef = useRef<Engine | null>(null)

  function refresh() {
    void loadMatsStats().then(setStats)
  }

  useEffect(() => {
    refresh()
    // Seul le retour de l'analyseur est consommé : le `from` d'un raccourci d'Apprendre reste dans
    // l'entrée d'historique, pour le retour vers le groupe.
    if (isRestore(location.state)) navigate(location.pathname + location.search, { replace: true, state: null })
    clearExercise()
    return () => {
      engineRef.current?.quit()
      engineRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function getEngine(): Engine {
    engineRef.current ??= new Engine()
    return engineRef.current
  }

  const needsPuzzles = !!drill && drill.section !== 'chrono'
  function load() {
    setLoadError(false)
    loadPuzzles().then(setPuzzles).catch(() => setLoadError(true))
  }
  useEffect(() => {
    // Retour arrière ou avant vers une autre page de /mats : la série en cours est close. Retour de
    // l'analyseur sur la fiche du schéma : son bilan revient (StrictMode rejoue cet effet).
    const r = returned.current
    if (r && drill && r.drillId === drill.id) setRun({ drill, cadence: r.cadence, restored: r.summary })
    else {
      returned.current = null
      setRun(null)
    }
    if (needsPuzzles && !puzzles) load()
    // Contre la montre : le moteur démarre dès la fiche (1 à 2 s de WASM sur iPhone).
    if (drill?.section === 'chrono') getEngine()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drill?.id])

  // Le state d'entrée (`from` du raccourci d'Apprendre) suit la fiche et revient avec l'accueil.
  const entryState = useLocation().state as unknown
  function open(id: string | null) {
    setRun(null)
    setParams(id ? { d: id } : {}, { state: entryState })
  }

  // Une série se joue par-dessus la fiche ; le retour arrière ou un autre schéma la ferment.
  if (run && drill && run.drill.id === drill.id) {
    const runStats = stats?.byKey[runKey(run.drill.id, run.cadence)] ?? null
    return run.drill.section === 'chrono' ? (
      <ChronoRun
        drill={run.drill}
        cadence={run.cadence}
        stats={runStats}
        getEngine={getEngine}
        onDone={refresh}
        onMenu={() => setRun(null)}
        restored={run.restored?.kind === 'chrono' ? run.restored : undefined}
      />
    ) : puzzles ? (
      <PuzzleRun
        drill={run.drill}
        cadence={run.cadence}
        all={puzzles}
        stats={runStats}
        showNet={readPrefs().showNet}
        onDone={refresh}
        onMenu={() => setRun(null)}
        restored={run.restored?.kind === 'puzzle' ? run.restored : undefined}
      />
    ) : null
  }

  if (drill) {
    return (
      <DrillSheet
        drill={drill}
        stats={stats}
        puzzles={puzzles}
        loadError={needsPuzzles && loadError}
        onRetry={load}
        onBack={() => open(null)}
        onStart={(cadence) => setRun({ drill, cadence })}
      />
    )
  }

  return <Hub stats={stats} onOpen={open} />
}

// Taille des symboles de pièces des cartes : un symbole seul est trace fine, il lui faut plus grand.
const GLYPH_SIZE: Record<number, string> = { 1: 'text-4xl', 2: 'text-3xl', 3: 'text-xl tracking-tighter' }

// ---------- Accueil ----------
// Mode de l'onglet Puzzles : le sélecteur des modes est sa sortie. Ouvert depuis le raccourci du
// groupe Tactique et calcul d'Apprendre (`state.from`, slug du groupe), il garde en plus un retour
// vers ce groupe ; ce state vit dans l'entrée d'historique de l'accueil, retrouvé au retour depuis
// une fiche.
function Hub({ stats, onOpen }: { stats: MatsStats | null; onOpen: (id: string) => void }) {
  const navigate = useNavigate()
  const state = useLocation().state as { from?: string } | null
  const group = originGroup(state)
  const back = group ? groupBack(group) : null
  return (
    <div className="mx-auto max-w-3xl p-4 md:p-6">
      {back && (
        <BackButton label={back.label} onClick={() => navigate(back.to)} />
      )}
      <PuzzleModes current="/mats" className="mb-4" />
      <PageHeader title="Mats éclair" description="Automatise les mats du bullet : vite, juste, sans réfléchir." />

      <div className="mb-5 grid grid-cols-2 gap-2">
        <div className="rounded-xl bg-surface-2 p-3 text-center">
          <div data-total-mates className="text-2xl font-black text-accent">{stats?.totalMates ?? '…'}</div>
          <div className="text-xs text-neutral-400">mats réussis</div>
        </div>
        <div className="rounded-xl bg-surface-2 p-3 text-center">
          <div className="text-2xl font-black">{stats?.totalRuns ?? '…'}</div>
          <div className="text-xs text-neutral-400">séries jouées</div>
        </div>
      </div>

      {SECTIONS.map((s) => (
        <section key={s.id} data-section={s.id} className="mb-5">
          <h2 className="text-lg font-black">{s.title}</h2>
          <p className="mb-2 text-sm text-neutral-400">{s.subtitle}</p>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {DRILLS.filter((d) => d.section === s.id).map((d) => {
              const best = drillBest(stats, d.id)
              return (
                <button
                  key={d.id}
                  data-drill={d.id}
                  onClick={() => onOpen(d.id)}
                  className="flex min-h-16 cursor-pointer items-center gap-2.5 rounded-xl bg-surface-2 p-3 text-left hover:bg-surface-3"
                >
                  <span
                    aria-hidden
                    className={`w-14 shrink-0 text-center leading-none font-black whitespace-nowrap ${GLYPH_SIZE[Math.min([...d.glyph].length, 3)]}`}
                  >
                    {d.glyph}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm leading-tight font-bold">{d.title}</span>
                    <span className="block text-xs text-neutral-400">{best === null ? 'À découvrir' : `Record ${best.best} · ${CADENCE_LABEL[best.cadence]}`}</span>
                  </span>
                </button>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}

// ---------- Fiche d'un schéma ----------
function DrillSheet({ drill, stats, puzzles, loadError, onRetry, onBack, onStart }: {
  drill: Drill
  stats: MatsStats | null
  puzzles: PuzzleData[] | null
  loadError: boolean
  onRetry: () => void
  onBack: () => void
  onStart: (cadence: Cadence) => void
}) {
  const chrono = drill.section === 'chrono'
  const cadences = chrono ? CHRONO_CADENCES : RUSH_CADENCES
  const [prefs, setPrefs] = useState(readPrefs)
  const cadence = prefs.cadence[drill.id] ?? drill.defaultCadence
  const runStats = stats?.byKey[runKey(drill.id, cadence)] ?? null

  function update(p: typeof prefs) {
    setPrefs(p)
    writePrefs(p)
  }

  // Diagramme : position type écrite pour le schéma, sinon le mat final du puzzle le plus épuré
  // du motif (thème lichess).
  const pool = useMemo(() => (!chrono && puzzles ? puzzlePool(drill, puzzles) : null), [chrono, puzzles, drill])
  const lessonFen = useMemo(() => {
    if (drill.lessonFen) return drill.lessonFen
    if (!pool) return null
    const simplest = [...pool].sort((a, b) => pieceCount(a.fen) - pieceCount(b.fen) || a.rating - b.rating)
    for (const p of simplest.slice(0, 20)) {
      const fen = puzzleFinalFen(p)
      if (fen) return fen
    }
    return null
  }, [drill, pool])

  const positions = chrono ? chronoPool(drill.pattern ?? 'mix') : null
  const range = positions && positions.length
    ? `${positions.length} positions vérifiées sur les tables de finales, mat en ${Math.min(...positions.map((p) => p.mateIn))} à ${Math.max(...positions.map((p) => p.mateIn))} coups au mieux.`
    : null
  const ready = chrono || (!!pool && pool.length > 0)

  return (
    <div data-sheet={drill.id} className="mx-auto max-w-3xl p-4 md:p-6">
      {/* Flèche : la fiche remonte au catalogue de Mats éclair (même entrée d'historique que le
          retour arrière du téléphone, `?d=` retiré). */}
      <BackButton label="Mats éclair" onClick={onBack} />
      <div className="md:grid md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:gap-6">
        <div>
          <h1 className="text-2xl font-black">
            <span aria-hidden className="mr-2">{drill.glyph}</span>
            {drill.title}
          </h1>
          <p data-principle className="mt-1 mb-3 text-base font-semibold text-accent">{drill.principle}</p>
          {lessonFen ? (
            <div className="mx-auto mb-3 max-w-[420px]">
              <NetBoard fen={lessonFen} principle="" />
            </div>
          ) : (
            !chrono && !loadError && <p className="mb-3 text-sm text-neutral-400">Chargement des puzzles…</p>
          )}
        </div>
        <div>
          <p className="mb-2 text-sm leading-relaxed text-neutral-300">{drill.text}</p>
          {range && <p className="mb-3 text-xs text-neutral-400">{range}</p>}
          {pool && <p className="mb-3 text-xs text-neutral-400">{pool.length} positions dans ce vivier.</p>}

          <p className="mb-1.5 text-sm font-semibold text-neutral-400">{chrono ? 'Temps pour mater' : 'Durée de la série'}</p>
          <div role="radiogroup" aria-label={chrono ? 'Temps pour mater' : 'Durée de la série'} className="mb-3 flex gap-2">
            {cadences.map((c) => (
              <button
                key={c}
                role="radio"
                aria-checked={c === cadence}
                onClick={() => update({ ...prefs, cadence: { ...prefs.cadence, [drill.id]: c } })}
                className={`min-h-11 flex-1 cursor-pointer rounded-lg py-2 text-sm font-bold ${
                  c === cadence ? 'bg-accent text-on-accent' : 'bg-surface-2 text-neutral-300 hover:bg-surface-3'
                }`}
              >
                {CADENCE_LABEL[c]}
              </button>
            ))}
          </div>
          {!chrono && (
            <label className="mb-3 flex min-h-11 cursor-pointer items-center gap-2 text-sm text-neutral-300">
              <input
                type="checkbox"
                checked={prefs.showNet}
                onChange={(e) => update({ ...prefs, showNet: e.target.checked })}
                className="h-4 w-4 accent-[var(--color-accent)]"
              />
              Montrer le réseau après chaque mat (chrono suspendu)
            </label>
          )}

          <div className="mb-4 rounded-xl bg-surface-2 p-3">
            <div className="mb-2 flex items-baseline justify-between">
              <span className="text-sm font-semibold text-neutral-400">Record ({CADENCE_LABEL[cadence]})</span>
              <span data-record className="text-2xl font-black text-accent">{runStats?.best ?? 0}</span>
            </div>
            <Sparkline values={runStats?.last ?? []} />
          </div>

          {loadError && (
            <div className="mb-3 rounded-lg bg-surface-2 p-3 text-center">
              <p className="mb-2 text-sm text-neutral-400">Impossible de charger les puzzles. Vérifie ta connexion, puis réessaie.</p>
              <Cta variant="secondary" onClick={onRetry}>Réessayer</Cta>
            </div>
          )}
          <Cta className="w-full py-4 text-xl" disabled={!ready} onClick={() => onStart(cadence)}>
            {ready ? 'Commencer' : 'Chargement…'}
          </Cta>
        </div>
      </div>
    </div>
  )
}

