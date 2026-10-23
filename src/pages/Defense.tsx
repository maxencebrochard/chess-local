// Entraîneur de défense, pendant de l'entraîneur d'attaque : positions de milieu de partie où le
// joueur subit une vraie attaque sur son roi mais peut tenir (`/defense`, par catégorie de
// roques), puis partie contre Stockfish bridé à l'Elo choisi (`/defense/:id`) : tenir HOLD_MOVES
// coups sans que l'éval passe sous le plancher, ou obtenir une nulle de l'échiquier ou un gain.
import { useEffect, useMemo, useState } from 'react'
import { Navigate, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ConfirmSheet } from '../components/ConfirmSheet'
import { Cta } from '../components/Cta'
import { PageHeader } from '../components/PageHeader'
import { LEVEL_HELP, LevelPicker as Picker } from '../components/LevelPicker'
import { PositionGame } from '../components/PositionGame'
import { opponentFor, type Level } from '../lib/attack'
import { recordReplaced } from '../lib/attempts'
import {
  CATEGORY_LABEL, CATEGORY_ORDER, DEFENSES, defenseKey, defenseOutcomeOf, defenseStats, defenseStatsKey, loadDefenseLevel,
  recordDefense, saveDefenseLevel, type DefenseCategory, type DefensePosition, type DefenseStats,
} from '../lib/defense'
import { HOLD_FLOOR_CP, HOLD_MOVES, inProgressKey, loadStoredGame, resumedGame, validFen, type HoldRule } from '../lib/positionGame'

const HOLD: HoldRule = { moves: HOLD_MOVES, floorCp: HOLD_FLOOR_CP }

// Consigne sans la catégorie (déjà donnée par l'onglet) : « Roques opposés : freine son pion h. »
// -> « Freine son pion h. »
function action(goal: string): string {
  const s = goal.slice(goal.indexOf(' : ') + 3)
  return s.charAt(0).toUpperCase() + s.slice(1)
}

const byCategory = (c: DefenseCategory) => DEFENSES.filter((d) => d.category === c)

function useStats(): Map<string, DefenseStats> {
  const [stats, setStats] = useState<Map<string, DefenseStats>>(new Map())
  useEffect(() => {
    void defenseStats().then(setStats)
  }, [])
  return stats
}

export default function Defense() {
  const { id } = useParams()
  return id ? <DefensePlay key={id} id={id} /> : <DefenseList />
}

function LevelPicker({ value, onChange }: { value: Level; onChange: (l: Level) => void }) {
  return <Picker value={value} onChange={onChange} label="Niveau de l'attaquant" />
}

// ---------- Liste ----------

function rate(items: DefensePosition[], stats: Map<string, DefenseStats>) {
  let solved = 0
  let finished = 0
  let successes = 0
  for (const p of items) {
    const s = stats.get(defenseStatsKey(p))
    if (!s) continue
    if (s.successes > 0) solved++
    finished += s.finished
    successes += s.successes
  }
  return { solved, pct: finished ? Math.round((100 * successes) / finished) : null }
}

function DefenseList() {
  const navigate = useNavigate()
  const stats = useStats()
  const [params, setParams] = useSearchParams()
  const cat: DefenseCategory = CATEGORY_ORDER.includes(params.get('c') as DefenseCategory) ? (params.get('c') as DefenseCategory) : 'opposes'
  const [level, setLevel] = useState<Level>(loadDefenseLevel)
  const [inProgress] = useState(inProgressKey)
  const items = useMemo(() => byCategory(cat), [cat])

  function pickLevel(l: Level) {
    setLevel(l)
    saveDefenseLevel(l)
  }

  // Au hasard dans la catégorie affichée : d'abord les positions jamais tenues.
  function random() {
    const fresh = items.filter((p) => !(stats.get(defenseStatsKey(p))?.successes ?? 0))
    const pool = fresh.length ? fresh : items
    if (pool.length) navigate(`/defense/${pool[Math.floor(Math.random() * pool.length)].id}`)
  }

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader title="🛡️ Entraîneur de défense" back={{ label: 'Apprendre', onClick: () => navigate('/apprendre') }}
        description={<>Ton roi est attaqué, mais la position se défend : tiens {HOLD_MOVES} coups sans que l'éval passe sous {HOLD_FLOOR_CP / 100}. Une nulle ou un gain comptent aussi.</>} />

      <section data-testid="attacker" className="mb-4 rounded-xl bg-surface-2 p-3">
        <div className="mb-2 flex items-baseline justify-between gap-2">
          <h2 className="font-bold">⚔️ Attaquant</h2>
          <span className="text-sm font-semibold text-accent">{level === null ? 'Stockfish pleine force' : `Stockfish Elo ${level}`}</span>
        </div>
        <LevelPicker value={level} onChange={pickLevel} />
        <p className="mt-2 text-xs text-neutral-400">{LEVEL_HELP}</p>
      </section>

      <div role="tablist" aria-label="Catégories" className="mb-3 grid grid-cols-3 gap-1 rounded-xl bg-surface-2 p-1">
        {CATEGORY_ORDER.map((c) => {
          const on = c === cat
          const all = byCategory(c)
          const r = rate(all, stats)
          return (
            <button
              key={c}
              role="tab"
              aria-selected={on}
              data-category={c}
              onClick={() => setParams({ c }, { replace: true })}
              className={`flex min-h-12 min-w-0 cursor-pointer flex-col items-center justify-center rounded-lg px-1 py-1 ${
                on ? 'bg-surface-3 text-white' : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <span className="w-full truncate text-center text-[13px] font-bold">{CATEGORY_LABEL[c]}</span>
              <span className={`text-[11px] tabular-nums ${on ? 'text-neutral-300' : 'text-neutral-400'}`}>
                {r.solved}/{all.length}{r.pct !== null && ` · ${r.pct} %`}
              </span>
            </button>
          )
        })}
      </div>

      <Cta className="mb-4 w-full" onClick={random} disabled={!items.length}>
        🎲 Position au hasard
      </Cta>

      <div className="flex flex-col gap-2">
        {items.map((p, i) => {
          const s = stats.get(defenseStatsKey(p))
          const going = inProgress === `${defenseKey(p.id)}|${p.fen}`
          return (
            <button
              key={p.id}
              data-testid="defense-item"
              data-id={p.id}
              onClick={() => navigate(`/defense/${p.id}`)}
              className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl bg-surface-2 px-3 py-2.5 text-left hover:bg-surface-3"
            >
              <span className="w-6 shrink-0 text-center text-sm font-bold tabular-nums text-neutral-400">{i + 1}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-bold">
                  {p.theme} <span className="font-normal text-neutral-400">· {p.defender === 'w' ? 'Blancs' : 'Noirs'}</span>
                </span>
                <span className="block truncate text-xs text-neutral-400">{action(p.goal)}</span>
              </span>
              {going ? (
                <span className="shrink-0 rounded-full bg-amber-900/40 px-2 py-0.5 text-xs font-semibold text-amber-200">En cours</span>
              ) : s && s.successes > 0 ? (
                <span data-testid="defense-solved" className="shrink-0 text-right text-xs font-bold text-accent">
                  ✓ tenu à {s.bestLevel === null ? 'Max' : s.bestLevel}
                </span>
              ) : s ? (
                <span data-testid="defense-attempts" className="shrink-0 text-xs text-neutral-400">{s.attempts} essai{s.attempts > 1 ? 's' : ''}</span>
              ) : (
                <span aria-hidden="true" className="shrink-0 text-xl text-neutral-500">›</span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ---------- Partie ----------

function DefensePlay({ id }: { id: string }) {
  const navigate = useNavigate()
  const location = useLocation()
  const restore = !!(location.state as { restore?: boolean } | null)?.restore
  const pos = DEFENSES.find((d) => d.id === id)
  // Niveau de la partie : celui d'une tentative reprise, sinon le niveau choisi.
  const [level, setLevel] = useState<Level>(() => {
    const stored = pos ? resumedGame(defenseKey(pos.id), pos.fen, restore) : null
    return stored?.level !== undefined ? stored.level : loadDefenseLevel()
  })
  const [attempt, setAttempt] = useState(0) // remonte la partie au changement de niveau
  const [picking, setPicking] = useState<Level | undefined>(undefined)

  if (!pos) return <Navigate to="/defense" replace />
  if (!validFen(pos.fen) || pos.fen.split(' ')[1] !== pos.defender) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 p-6 text-center">
        <p className="text-neutral-300">Cette position de défense est invalide : impossible de la jouer.</p>
        <button onClick={() => navigate('/defense', { replace: true })} className="cursor-pointer rounded-lg bg-surface-3 px-4 py-2 font-semibold hover:bg-surface-3/70">
          Toutes les positions
        </button>
      </div>
    )
  }
  const list = byCategory(pos.category)
  const next = list[(list.indexOf(pos) + 1) % list.length]

  // Nouveau niveau : mémorisé, et la position repart (la tentative en cours est notée abandonnée).
  function applyLevel(l: Level) {
    setPicking(undefined)
    if (l === level) return
    saveDefenseLevel(l)
    const stored = loadStoredGame()
    if (stored && stored.key === defenseKey(pos!.id) && stored.startFen === pos!.fen && !stored.end && !stored.recorded && stored.uci.length > 0) {
      void recordDefense(pos!, 'abandon', stored.level ?? null, stored.assisted)
    }
    setLevel(l)
    setAttempt((a) => a + 1)
  }

  return (
    <>
      <PositionGame
        key={attempt}
        gameKey={defenseKey(pos.id)}
        startFen={pos.fen}
        title={pos.theme}
        objective="hold"
        hold={HOLD}
        goalHint={pos.goal}
        lesson={pos.plan}
        lessonLabel="Conseils"
        successTitle="Défense réussie"
        resume={attempt === 0}
        restoreFinished={restore && attempt === 0}
        returnTo={`/defense/${pos.id}`}
        returnLabel="Retour à la défense"
        opponent={opponentFor(level)}
        allowDraw={false}
        planButton
        headerAction={
          <button
            onClick={() => setPicking(level)}
            aria-label="Niveau de l'attaquant"
            data-testid="level-chip"
            className="flex h-11 shrink-0 cursor-pointer items-center gap-1 rounded-full bg-surface-2 px-2.5 text-xs font-bold tabular-nums text-neutral-200 hover:bg-surface-3"
          >
            ⚔️ {level ?? 'Max'}
          </button>
        }
        // La liste est l'entrée d'en dessous quand on vient d'elle ; sinon (lien direct) on la pose.
        onExit={() =>
          ((window.history.state as { idx?: number } | null)?.idx ?? 0) > 0
            ? navigate(-1)
            : navigate(`/defense?c=${pos.category}`, { replace: true })
        }
        onOther={() => navigate(`/defense/${next.id}`, { replace: true })}
        otherLabel="Suivante"
        onFinished={(_, info) => void recordDefense(pos, defenseOutcomeOf(info.end, pos.defender), level, info.assisted)}
        onAbandon={({ assisted }) => void recordDefense(pos, 'abandon', level, assisted)}
        onReplace={recordReplaced}
      />
      {picking !== undefined && (
        <ConfirmSheet
          title="Niveau de l'attaquant"
          confirmLabel="Appliquer"
          testId="level"
          onConfirm={() => applyLevel(picking)}
          onCancel={() => setPicking(undefined)}
        >
          <LevelPicker value={picking} onChange={setPicking} />
          <p className="text-xs text-neutral-400">{LEVEL_HELP}</p>
          <p>Changer de niveau recommence la position.</p>
        </ConfirmSheet>
      )}
    </>
  )
}
