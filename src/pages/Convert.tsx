// Entraîneur « Convertir l'avantage » : positions de vraies parties où l'on est nettement mieux
// (+2 à +4, `/convertir`, par catégorie : finale, matériel, position), puis partie contre Stockfish
// bridé à l'Elo choisi, sans plafond de coups, jusqu'au mat ou à un avantage décisif tenu
// (`/convertir/:id`). Toute nulle est un échec : c'est la partie gagnante qu'on laisse filer.
import { useEffect, useMemo, useState } from 'react'
import { Navigate, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ConfirmSheet } from '../components/ConfirmSheet'
import { Cta } from '../components/Cta'
import { LEVEL_HELP, LevelPicker } from '../components/LevelPicker'
import { PositionGame } from '../components/PositionGame'
import { attackStats, opponentFor, outcomeOf, statsKey, type AttackStats, type Level } from '../lib/attack'
import { recordReplaced } from '../lib/attempts'
import {
  CATEGORY_LABEL, CATEGORY_ORDER, CONVERSION_DOMAIN, CONVERSIONS, CONVERT_DECISIVE_CP, gameKey, loadLevel, recordAttempt, saveLevel,
  type ConversionCategory, type ConversionPosition,
} from '../lib/conversion'
import { inProgressKey, loadStoredGame, resumedGame, validFen } from '../lib/positionGame'

const PICKER_LABEL = 'Niveau du défenseur'

// Consigne sans le thème (déjà affiché) : « Pion passé : pousse ton pion passé d5. »
// -> « Pousse ton pion passé d5. »
function action(goal: string): string {
  const s = goal.slice(goal.indexOf(' : ') + 3)
  return s.charAt(0).toUpperCase() + s.slice(1)
}

const byCategory = (c: ConversionCategory) => CONVERSIONS.filter((p) => p.category === c)

function useStats(): Map<string, AttackStats> {
  const [stats, setStats] = useState<Map<string, AttackStats>>(new Map())
  useEffect(() => {
    void attackStats(CONVERSION_DOMAIN).then(setStats)
  }, [])
  return stats
}

export default function Convert() {
  const { id } = useParams()
  return id ? <ConvertPlay key={id} id={id} /> : <ConvertList />
}

// ---------- Liste ----------

function rate(items: ConversionPosition[], stats: Map<string, AttackStats>) {
  let solved = 0
  let finished = 0
  let successes = 0
  for (const p of items) {
    const s = stats.get(statsKey(p))
    if (!s) continue
    if (s.successes > 0) solved++
    finished += s.finished
    successes += s.successes
  }
  return { solved, pct: finished ? Math.round((100 * successes) / finished) : null }
}

function ConvertList() {
  const navigate = useNavigate()
  const stats = useStats()
  const [params, setParams] = useSearchParams()
  const cat: ConversionCategory = CATEGORY_ORDER.includes(params.get('c') as ConversionCategory) ? (params.get('c') as ConversionCategory) : 'finale'
  const [level, setLevel] = useState<Level>(loadLevel)
  const [inProgress] = useState(inProgressKey)
  const items = useMemo(() => byCategory(cat), [cat])

  function pickLevel(l: Level) {
    setLevel(l)
    saveLevel(l)
  }

  // Au hasard dans la catégorie affichée : d'abord les positions jamais réussies.
  function random() {
    const fresh = items.filter((p) => !(stats.get(statsKey(p))?.successes ?? 0))
    const pool = fresh.length ? fresh : items
    if (pool.length) navigate(`/convertir/${pool[Math.floor(Math.random() * pool.length)].id}`)
  }

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <div className="mb-1 flex items-center gap-1">
        <button
          onClick={() => navigate('/apprendre')}
          aria-label="Retour à Apprendre"
          className="-ml-2 flex h-10 w-10 cursor-pointer items-center justify-center rounded-full text-2xl text-neutral-400 hover:text-white"
        >
          ←
        </button>
        <h1 className="text-2xl font-black">🏆 Convertir l'avantage</h1>
      </div>
      <p className="mb-4 text-sm text-neutral-400">
        Tu es nettement mieux : gagne la partie, jusqu'au mat ou à un avantage décisif tenu. Une nulle compte comme un échec.
      </p>

      <section data-testid="defender" className="mb-4 rounded-xl bg-surface-2 p-3">
        <div className="mb-2 flex items-baseline justify-between gap-2">
          <h2 className="font-bold">🛡️ Défenseur</h2>
          <span className="text-sm font-semibold text-accent">{level === null ? 'Stockfish pleine force' : `Stockfish Elo ${level}`}</span>
        </div>
        <LevelPicker value={level} onChange={pickLevel} label={PICKER_LABEL} />
        <p className="mt-2 text-xs text-neutral-500">{LEVEL_HELP}</p>
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
              <span className="text-[11px] tabular-nums text-neutral-400">
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
          const s = stats.get(statsKey(p))
          const going = inProgress === `${gameKey(p.id)}|${p.fen}`
          return (
            <button
              key={p.id}
              data-testid="conversion-item"
              data-id={p.id}
              onClick={() => navigate(`/convertir/${p.id}`)}
              className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl bg-surface-2 px-3 py-2.5 text-left hover:bg-surface-3"
            >
              <span className="w-6 shrink-0 text-center text-sm font-bold tabular-nums text-neutral-500">{i + 1}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-bold">
                  {p.theme} <span className="font-normal text-neutral-500">· {p.player === 'w' ? 'Blancs' : 'Noirs'}</span>
                </span>
                <span className="block truncate text-xs text-neutral-400">{action(p.goal)}</span>
              </span>
              {going ? (
                <span className="shrink-0 rounded-full bg-amber-900/40 px-2 py-0.5 text-xs font-semibold text-amber-200">En cours</span>
              ) : s && s.successes > 0 ? (
                <span data-testid="conversion-solved" className="shrink-0 text-right text-xs font-bold text-accent">
                  ✓ battu à {s.bestLevel === null ? 'Max' : s.bestLevel}
                </span>
              ) : s ? (
                <span className="shrink-0 text-xs text-neutral-500">{s.attempts} essai{s.attempts > 1 ? 's' : ''}</span>
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

function ConvertPlay({ id }: { id: string }) {
  const navigate = useNavigate()
  const location = useLocation()
  const restore = !!(location.state as { restore?: boolean } | null)?.restore
  const pos = CONVERSIONS.find((p) => p.id === id)
  // Niveau de la partie : celui d'une tentative reprise, sinon le niveau choisi.
  const [level, setLevel] = useState<Level>(() => {
    const stored = pos ? resumedGame(gameKey(pos.id), pos.fen, restore) : null
    return stored?.level !== undefined ? stored.level : loadLevel()
  })
  const [attempt, setAttempt] = useState(0) // remonte la partie au changement de niveau
  const [picking, setPicking] = useState<Level | undefined>(undefined)

  if (!pos) return <Navigate to="/convertir" replace />
  if (!validFen(pos.fen) || pos.fen.split(' ')[1] !== pos.player) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 p-6 text-center">
        <p className="text-neutral-300">Cette position est invalide : impossible de la jouer.</p>
        <button onClick={() => navigate('/convertir', { replace: true })} className="cursor-pointer rounded-lg bg-surface-3 px-4 py-2 font-semibold hover:bg-surface-3/70">
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
    saveLevel(l)
    const stored = loadStoredGame()
    if (stored && stored.key === gameKey(pos!.id) && stored.startFen === pos!.fen && !stored.end && !stored.recorded && stored.uci.length > 0) {
      void recordAttempt(pos!, 'abandon', stored.level ?? null, stored.assisted)
    }
    setLevel(l)
    setAttempt((a) => a + 1)
  }

  return (
    <>
      <PositionGame
        key={attempt}
        gameKey={gameKey(pos.id)}
        startFen={pos.fen}
        title={pos.theme}
        objective="win"
        goalHint={action(pos.goal)} // le thème est déjà le titre
        lesson={pos.plan}
        lessonLabel="Conseils"
        successTitle="Avantage converti"
        decisiveReason="Avantage décisif tenu : la partie est gagnée."
        resume={attempt === 0}
        restoreFinished={restore && attempt === 0}
        returnTo={`/convertir/${pos.id}`}
        returnLabel="Retour à la position"
        opponent={opponentFor(level)}
        decisiveCp={CONVERT_DECISIVE_CP}
        allowDraw={false}
        planButton
        headerAction={
          <button
            onClick={() => setPicking(level)}
            aria-label={PICKER_LABEL}
            data-testid="level-chip"
            className="flex h-8 shrink-0 cursor-pointer items-center gap-1 rounded-full bg-surface-2 px-2.5 text-xs font-bold tabular-nums text-neutral-200 hover:bg-surface-3"
          >
            🛡️ {level ?? 'Max'}
          </button>
        }
        // La liste est l'entrée d'en dessous quand on vient d'elle ; sinon (lien direct) on la pose.
        onExit={() =>
          ((window.history.state as { idx?: number } | null)?.idx ?? 0) > 0
            ? navigate(-1)
            : navigate(`/convertir?c=${pos.category}`, { replace: true })
        }
        onOther={() => navigate(`/convertir/${next.id}`, { replace: true })}
        otherLabel="Suivante"
        onFinished={(_, info) => void recordAttempt(pos, outcomeOf(info.end, pos.player), level, info.assisted)}
        onAbandon={({ assisted }) => void recordAttempt(pos, 'abandon', level, assisted)}
        onReplace={recordReplaced}
      />
      {picking !== undefined && (
        <ConfirmSheet
          title={PICKER_LABEL}
          confirmLabel="Appliquer"
          testId="level"
          onConfirm={() => applyLevel(picking)}
          onCancel={() => setPicking(undefined)}
        >
          <LevelPicker value={picking} onChange={setPicking} label={PICKER_LABEL} />
          <p className="text-xs text-neutral-500">{LEVEL_HELP}</p>
          <p>Changer de niveau recommence la position.</p>
        </ConfirmSheet>
      )}
    </>
  )
}
