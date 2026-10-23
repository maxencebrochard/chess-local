// « Finales au chrono » (/finales/chrono) : la fin de partie de bullet. Choix de la cadence (temps
// et incrément, records par cadence), puis une famille de finales théoriques ou le mélange ; un
// tap lance la série contre Stockfish pleine force.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ENDGAME_CLOCK_RETURN_SCREEN, EndgameClockRun, type ClockReturn } from '../components/EndgameClockRun'
import { PageHeader } from '../components/PageHeader'
import { Engine } from '../lib/engine'
import { clearExercise, isRestore, readExercise } from '../lib/exerciseReturn'
import {
  BASES_S, baseLabel, DEFAULT_CADENCE, ENDGAME_CLOCK_DOMAIN, ENDGAME_CLOCK_PREFS_KEY, FAMILIES, INCREMENTS_S, MIX, parseCadence, cadenceKey,
  cadenceLabel, recordKey,
  type ClockCadence, type ClockFamily,
} from '../lib/endgameClock'
import { loadMatsStats, type MatsStats } from '../lib/mates'
import { endgameTheme, THEME_LABEL, type EndgameTheme } from '../lib/positionGame'

const THEME_ORDER: EndgameTheme[] = ['pawns', 'rooks', 'queen', 'other']

function readCadence(): ClockCadence {
  try {
    const raw = JSON.parse(localStorage.getItem(ENDGAME_CLOCK_PREFS_KEY) ?? '{}') as { cadence?: unknown }
    return (typeof raw.cadence === 'string' && parseCadence(raw.cadence)) || DEFAULT_CADENCE
  } catch {
    return DEFAULT_CADENCE
  }
}

function writeCadence(c: ClockCadence) {
  try {
    localStorage.setItem(ENDGAME_CLOCK_PREFS_KEY, JSON.stringify({ cadence: cadenceKey(c) }))
  } catch {}
}

export default function EndgameClock() {
  const navigate = useNavigate()
  const location = useLocation()
  // Retour de l'analyseur : bilan de la série close, réaffiché avec sa cadence.
  const [returned] = useState(() => (isRestore(location.state) ? readExercise<ClockReturn>(ENDGAME_CLOCK_RETURN_SCREEN) : null))
  const [cadence, setCadence] = useState(() => returned?.cadence ?? readCadence())
  const [stats, setStats] = useState<MatsStats | null>(null)
  const [run, setRun] = useState<string | null>(returned?.serie ?? null)
  const [restored, setRestored] = useState(returned?.summary)
  const engineRef = useRef<Engine | null>(null)

  function refresh() {
    void loadMatsStats(ENDGAME_CLOCK_DOMAIN).then(setStats)
  }

  useEffect(() => {
    refresh()
    if (location.state) navigate('.', { replace: true, state: null })
    clearExercise()
    // Le moteur démarre dès l'accueil (1 à 2 s de WASM sur iPhone) : la première réponse est prête.
    getEngine()
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

  function choose(c: ClockCadence) {
    setCadence(c)
    writeCadence(c)
  }

  const sections = useMemo(
    () =>
      THEME_ORDER.map((theme) => ({
        theme,
        items: FAMILIES.filter((f) => endgameTheme(f.positions[0].fen) === theme).sort((a, b) => a.difficulty - b.difficulty),
      })).filter((s) => s.items.length > 0),
    [],
  )

  const best = (serie: string) => stats?.byKey[recordKey(serie, cadence)]?.best ?? null

  if (run) {
    return (
      <EndgameClockRun
        serie={run}
        cadence={cadence}
        stats={stats?.byKey[recordKey(run, cadence)] ?? null}
        getEngine={getEngine}
        onDone={refresh}
        onMenu={() => {
          setRestored(undefined)
          setRun(null)
        }}
        restored={restored}
      />
    )
  }

  const positions = FAMILIES.reduce((n, f) => n + f.positions.length, 0)
  const toWin = FAMILIES.filter((f) => f.objective === 'win').length

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader title="⏱ Finales au chrono" back={{ label: 'Apprendre', onClick: () => navigate('/apprendre') }}
        description="La fin de partie de bullet : une finale théorique, Stockfish à pleine force, quelques secondes à ta pendule. Gagne ou tiens la nulle avant la chute du drapeau." />

      <p className="mb-1.5 text-sm font-semibold text-neutral-400">Temps</p>
      <div role="radiogroup" aria-label="Temps" className="mb-3 flex gap-2">
        {BASES_S.map((s) => (
          <Choice key={s} label={baseLabel(s)} checked={cadence.baseS === s} onClick={() => choose({ ...cadence, baseS: s })} />
        ))}
      </div>
      <p className="mb-1.5 text-sm font-semibold text-neutral-400">Incrément par coup</p>
      <div role="radiogroup" aria-label="Incrément" className="mb-4 flex gap-2">
        {INCREMENTS_S.map((s) => (
          <Choice key={s} label={s === 0 ? 'Aucun' : `+${s} s`} checked={cadence.incS === s} onClick={() => choose({ ...cadence, incS: s })} />
        ))}
      </div>

      <button
        data-serie={MIX}
        onClick={() => setRun(MIX)}
        className="mb-5 flex w-full cursor-pointer items-center gap-3 rounded-xl bg-accent/15 p-3 text-left ring-1 ring-accent/40 hover:bg-accent/25"
      >
        <span aria-hidden className="text-2xl">🎲</span>
        <span className="min-w-0 flex-1">
          <span className="block font-bold">Mélange</span>
          <span className="block text-xs text-neutral-400">
            {positions} positions vérifiées sur les tables de finales : {toWin} familles à gagner, {FAMILIES.length - toWin} à tenir
          </span>
        </span>
        <Record best={best(MIX)} />
      </button>

      {sections.map(({ theme, items }) => (
        <section key={theme} data-section={theme} className="mb-4">
          <h2 className="mb-2 text-sm font-semibold text-neutral-400">{THEME_LABEL[theme]}</h2>
          <div className="grid gap-2 md:grid-cols-2">
            {items.map((f) => (
              <FamilyCard key={f.id} family={f} best={best(f.id)} onClick={() => setRun(f.id)} />
            ))}
          </div>
        </section>
      ))}
      <p className="text-xs text-neutral-400">
        Records en {cadenceLabel(cadence)}. Ta pendule ne tourne qu'à ton trait ; un prémouvement coûte 0,1 s.
      </p>
    </div>
  )
}

function Choice({ label, checked, onClick }: { label: string; checked: boolean; onClick: () => void }) {
  return (
    <button
      role="radio"
      aria-checked={checked}
      onClick={onClick}
      className={`min-h-11 flex-1 cursor-pointer rounded-lg py-2 text-sm font-bold ${
        checked ? 'bg-accent text-on-accent' : 'bg-surface-2 text-neutral-300 hover:bg-surface-3'
      }`}
    >
      {label}
    </button>
  )
}

function Record({ best }: { best: number | null }) {
  return best === null ? (
    <span aria-hidden="true" className="shrink-0 text-xl text-neutral-500">›</span>
  ) : (
    <span data-record={best} className="shrink-0 text-right leading-tight">
      <span className="block text-lg font-black text-accent">{best}</span>
      <span className="block text-[10px] text-neutral-400">record</span>
    </span>
  )
}

function FamilyCard({ family, best, onClick }: { family: ClockFamily; best: number | null; onClick: () => void }) {
  return (
    <button
      data-serie={family.id}
      onClick={onClick}
      className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl bg-surface-2 px-3 py-2.5 text-left hover:bg-surface-3"
    >
      <span className="min-w-0 flex-1">
        <span className="block truncate font-bold">{family.title}</span>
        <span className="mt-0.5 flex items-center gap-2 text-xs">
          <span
            className={`rounded px-1.5 py-0.5 font-semibold ${
              family.objective === 'win' ? 'bg-accent/15 text-accent-light' : 'bg-sky-900/40 text-sky-300'
            }`}
          >
            {family.objective === 'win' ? 'Gagner' : 'Tenir la nulle'}
          </span>
          <span className="text-neutral-400">{family.difficulty}</span>
        </span>
      </span>
      <Record best={best} />
    </button>
  )
}
