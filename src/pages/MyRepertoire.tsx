// Mon répertoire (/repertoire) : où le joueur sort de la théorie dans ses parties chess.com, et ce
// que la sortie lui coûte. Parties : bilans d'Insights en cache (table `reviews`, hors ligne), plus
// les parties récentes chargées sur demande (`fetchRecentGames`, même appel que l'import), gardées
// en mémoire pour la session de l'app. Chaque sortie devient une séance « Prochain coup » de
// l'entraîneur d'ouvertures (tentatives `opening-drill`, itemId `next:<camp>:<UCI>`).
// Camp et cadence vivent dans l'URL (?camp=&cadence=) : retour depuis l'Analyse sur la même vue.
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Cta } from '../components/Cta'
import { OpeningDrill, type DrillItem } from '../components/OpeningDrill'
import { Segmented } from '../components/Segmented'
import { extractGameId, fetchRecentGames, normalizeUsername, outcomeFor, type ChesscomGame } from '../lib/chesscom'
import { db } from '../lib/db'
import { Engine } from '../lib/engine'
import { validRow } from '../lib/insights'
import {
  computeRepertoire, drillLines, type Color, type Deviation, type OpeningReport, type RepGame,
} from '../lib/myRepertoire'
import { openingFamilyFr, openingFr } from '../lib/openingNames'
import { DRILL_DOMAIN, drillItemId, lineFamily, recordDrill, type Family } from '../lib/openingTrainer'
import { figurine } from '../lib/review'
import { useSettings } from '../store/settings'

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
const FETCH_MONTHS = 3
const FETCH_LIMIT = 200
const SHOWN_DEVIATIONS = 3

const CADENCES = [
  { id: 'all', label: 'Toutes' },
  { id: 'bullet', label: 'Bullet' },
  { id: 'blitz', label: 'Blitz' },
  { id: 'rapid', label: 'Rapide' },
] as const
type CadenceId = (typeof CADENCES)[number]['id']

// Parties chargées depuis chess.com, gardées pour la session de l'app (aller-retour vers l'Analyse,
// changement d'onglet) ; un chargement en cours est partagé (double tap, page quittée puis rouverte).
const loaded = new Map<string, { games: ChesscomGame[]; at: number }>()
const inflight = new Map<string, Promise<ChesscomGame[]>>()

function loadRecent(user: string): Promise<ChesscomGame[]> {
  let p = inflight.get(user)
  if (!p) {
    p = fetchRecentGames(user, FETCH_MONTHS, FETCH_LIMIT).then(
      (games) => {
        inflight.delete(user)
        loaded.set(user, { games, at: Date.now() })
        return games
      },
      (e: unknown) => {
        inflight.delete(user)
        throw e
      },
    )
    inflight.set(user, p)
  }
  return p
}

function storedUser(raw: string): string | null {
  try {
    return raw.trim() ? normalizeUsername(raw) : null
  } catch {
    return null
  }
}

function fromChesscom(g: ChesscomGame): RepGame | null {
  const id = extractGameId(g.url)
  if (!id) return null
  return {
    key: `chesscom:${id}`,
    pgn: g.pgn,
    playerColor: g.playerColor,
    result: outcomeFor(g),
    timeClass: g.timeClass,
    date: g.endTime * 1000,
    opponent: (g.playerColor === 'w' ? g.black : g.white).username,
    review: null,
  }
}

type DrillState = 'fixed' | 'review' | null

interface Attempt {
  date: number
  success: 0 | 1
}

// État d'une sortie : la dernière tentative « Prochain coup » sur l'une de ses positions, faite
// après la partie la plus récente qui y est sortie (une réussite plus ancienne ne corrige rien).
function stateOf(d: Deviation, attempts: Map<string, Attempt[]>): DrillState {
  let last: Attempt | null = null
  for (const p of d.prefixes) {
    for (const a of attempts.get(drillItemId('next', d.color, p ? p.split(' ') : [])) ?? []) {
      if (a.date > d.last.date && (!last || a.date >= last.date)) last = a
    }
  }
  return last === null ? null : last.success ? 'fixed' : 'review'
}

async function loadAttempts(): Promise<Map<string, Attempt[]>> {
  const rows = await db.learnSessions.where('domain').equals(DRILL_DOMAIN).toArray()
  const out = new Map<string, Attempt[]>()
  for (const r of rows) {
    if (!r.itemId.startsWith('next:')) continue
    const list = out.get(r.itemId) ?? []
    list.push({ date: r.date, success: r.success })
    out.set(r.itemId, list)
  }
  return out
}

const moveLabel = (d: Pick<Deviation, 'moveNumber' | 'color'>, san: string) =>
  `${d.moveNumber}${d.color === 'w' ? '.' : '…'}${figurine(san, d.color)}`

const plural = (n: number, word: string) => `${n} ${word}${n > 1 ? 's' : ''}`

function resultsText(t: { wins: number; draws: number; losses: number }): string {
  return `${t.wins} V · ${t.draws} N · ${t.losses} D`
}

export default function MyRepertoire() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const color: Color = params.get('camp') === 'b' ? 'b' : 'w'
  const cadence = (CADENCES.find((c) => c.id === params.get('cadence'))?.id ?? 'all') as CadenceId
  const { chesscomUsername, setChesscomUsername } = useSettings()
  const user = storedUser(chesscomUsername)

  const [userInput, setUserInput] = useState(chesscomUsername)
  const [cached, setCached] = useState<RepGame[] | null>(null)
  const [fetched, setFetched] = useState(() => (user ? (loaded.get(user) ?? null) : null))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [attempts, setAttempts] = useState<Map<string, Attempt[]>>(new Map())
  const [saveError, setSaveError] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  // Séance : file des sorties (figée au départ), position dans la file, clé du drill.
  const [drill, setDrill] = useState<{ queue: Deviation[]; at: number; key: number; retry: boolean } | null>(null)
  const [session, setSession] = useState({ ok: 0, total: 0 })
  const engineRef = useRef<Engine | null>(null)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      engineRef.current?.quit()
      engineRef.current = null
    }
  }, [])

  // Bilans d'Insights de ce compte : la source hors ligne, avec l'évaluation des sorties.
  useEffect(() => {
    let live = true
    if (!user) {
      setCached([])
      return
    }
    void db.reviews.toArray().then(
      (rows) => {
        if (!live) return
        setCached(
          rows
            .filter((r) => r.source === 'chesscom' && r.username === user && validRow(r))
            .map((r) => ({
              key: r.key, pgn: r.pgn, playerColor: r.playerColor, result: r.result, timeClass: r.timeClass,
              date: r.date, opponent: r.opponent, review: r.review,
            })),
        )
      },
      () => live && setCached([]),
    )
    setFetched(loaded.get(user) ?? null)
    return () => {
      live = false
    }
  }, [user])

  useEffect(() => {
    void loadAttempts().then((a) => alive.current && setAttempts(a), () => undefined)
  }, [])

  // Ligne du cache d'abord : à clé égale, elle porte le bilan.
  const games = useMemo(() => {
    const list = [...(cached ?? [])]
    const keys = new Set(list.map((g) => g.key))
    for (const g of fetched?.games ?? []) {
      const r = fromChesscom(g)
      if (r && !keys.has(r.key)) {
        keys.add(r.key)
        list.push(r)
      }
    }
    return list
  }, [cached, fetched])
  const reviewedCount = cached?.length ?? 0

  const report = useMemo(() => (cached === null ? null : computeRepertoire(games, cadence)), [games, cadence, cached])
  const colorReport = report?.byColor[color] ?? null

  // Famille synthétique de la sortie en cours (lignes réécrites depuis les coups de la partie).
  const current = drill ? drill.queue[drill.at] : null
  const fam: Family | null = useMemo(
    () => (current ? lineFamily(current.opening, drillLines(current.prefix, current.opening)) : null),
    [current],
  )

  function setOption(name: 'camp' | 'cadence', value: string) {
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        next.set(name, value)
        return next
      },
      { replace: true },
    )
  }

  async function load(raw: string) {
    let u: string
    try {
      u = normalizeUsername(raw)
    } catch (e) {
      setError((e as Error).message)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const list = await loadRecent(u)
      if (!alive.current) return
      // Pseudo mémorisé seulement s'il existe (comme l'import).
      setChesscomUsername(u)
      setUserInput(u)
      setFetched({ games: list, at: loaded.get(u)?.at ?? Date.now() })
    } catch (e) {
      if (!alive.current) return
      setError(e instanceof Error ? e.message : 'Impossible de lire tes parties.')
    } finally {
      if (alive.current) setLoading(false)
    }
  }

  function startSession(from?: Deviation) {
    if (!colorReport || colorReport.deviations.length === 0) return
    const queue = colorReport.deviations
    const at = from ? Math.max(0, queue.findIndex((d) => d.id === from.id)) : 0
    setSession({ ok: 0, total: 0 })
    setDrill((s) => ({ queue, at, key: (s?.key ?? 0) + 1, retry: false }))
  }

  async function onResult(d: Deviation, retry: boolean, success: boolean) {
    // « Prochain coup » : seule la 1re tentative d'une position compte, comme dans l'entraîneur.
    if (retry) return
    setSession((s) => ({ ok: s.ok + (success ? 1 : 0), total: s.total + 1 }))
    try {
      await recordDrill('next', d.color, d.prefix, success)
      const a = await loadAttempts()
      if (alive.current) {
        setAttempts(a)
        setSaveError(false)
      }
    } catch {
      if (alive.current) setSaveError(true)
    }
  }

  const back = () => ({ returnTo: `/repertoire?${params.toString()}`, returnLabel: 'Retour au répertoire' })

  function openGame(d: Deviation) {
    navigate('/analyse', {
      state: {
        fen: START_FEN,
        uci: d.last.moves,
        viewIndex: d.ply,
        orientation: d.color,
        label: `${openingFr(d.opening)} · contre ${d.last.opponent}`,
        ...back(),
      },
    })
  }

  // ---------- Séance ----------
  if (drill && current && fam) {
    const item: DrillItem = { mode: 'next', variant: null, start: current.prefix.length, position: current.prefix }
    const n = drill.queue.length
    const played = current.played.map((m) => figurine(m.san, current.color)).join(', ')
    return (
      <OpeningDrill
        key={drill.key}
        fam={fam}
        color={current.color}
        item={item}
        plyTarget={null}
        getEngine={() => (engineRef.current ??= new Engine())}
        session={session}
        title={`🗺️ Sortie ${drill.at + 1}/${n}`}
        subtitle={`Tu as joué ${played} dans ${plural(current.games, 'partie')}${session.total ? ` · ${session.ok}/${session.total} réussies` : ''}`}
        nextLabel={n > 1 ? 'Sortie suivante' : 'Recommencer'}
        onResult={(ok) => void onResult(current, drill.retry, ok)}
        onRetry={() => setDrill({ ...drill, key: drill.key + 1, retry: true })}
        onNext={() => setDrill({ ...drill, at: (drill.at + 1) % n, key: drill.key + 1, retry: false })}
        onClose={() => setDrill(null)}
        onAnalyse={(moves) =>
          navigate('/analyse', {
            state: { fen: START_FEN, uci: moves, orientation: current.color, label: openingFr(current.opening), ...back() },
          })
        }
      />
    )
  }

  // ---------- Page ----------
  const total = games.length
  const sideFr = color === 'w' ? 'Blancs' : 'Noirs'
  const devCount = colorReport?.deviations.length ?? 0
  const fetchedAt = fetched ? new Date(fetched.at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) : null

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <Link to="/apprendre" className="mb-2 -ml-1 inline-block px-1 py-1 text-sm font-semibold text-neutral-400 hover:text-white">
        ‹ Apprendre
      </Link>
      <h1 className="mb-1 text-2xl font-black">🗺️ Mon répertoire</h1>
      <p className="mb-4 text-sm text-neutral-400">
        Où tu sors de la théorie dans tes parties chess.com, ce que ça te coûte, et le coup à jouer à la place.
      </p>

      <section data-source className="mb-4 rounded-xl bg-surface-2 p-3">
        {user ? (
          <>
            <p className="text-sm text-neutral-200">
              <b data-games-count={total}>{plural(total, 'partie')}</b> de <b>{user}</b>
              {' · '}
              <span data-reviewed-count={reviewedCount}>{reviewedCount} avec bilan Stockfish</span>
            </p>
            <p className="mt-0.5 text-xs text-neutral-400">
              {fetchedAt
                ? `Parties récentes chargées à ${fetchedAt} (${FETCH_MONTHS} derniers mois, ${FETCH_LIMIT} au plus).`
                : 'Seules tes parties déjà analysées par Insights sont là : charge tes parties récentes pour compléter.'}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
              <button
                data-load
                onClick={() => void load(user)}
                disabled={loading}
                className="cursor-pointer rounded-lg bg-surface-3 px-3 py-2 text-sm font-bold text-neutral-100 hover:bg-surface-3/80 disabled:cursor-default disabled:opacity-50"
              >
                {loading ? 'Chargement…' : fetched ? 'Recharger mes parties chess.com' : 'Charger mes parties chess.com'}
              </button>
              <Link to="/insights" className="text-xs font-semibold text-neutral-400 underline-offset-2 hover:text-white hover:underline">
                Bilans Stockfish : Insights ›
              </Link>
            </div>
          </>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              void load(userInput)
            }}
          >
            <label htmlFor="rep-user" className="mb-1.5 block text-sm font-semibold text-neutral-200">
              Ton pseudo chess.com
            </label>
            <div className="flex gap-2">
              <input
                id="rep-user"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                placeholder="pseudo"
                className="min-w-0 flex-1 rounded-lg bg-surface px-3 py-2 text-base text-white placeholder:text-neutral-500 focus:ring-2 focus:ring-accent focus:outline-none"
              />
              <button
                type="submit"
                data-load
                disabled={loading || !userInput.trim()}
                className="shrink-0 cursor-pointer rounded-lg bg-accent px-3 py-2 text-sm font-bold text-white hover:bg-accent-hover disabled:cursor-default disabled:opacity-40"
              >
                {loading ? 'Chargement…' : 'Charger'}
              </button>
            </div>
          </form>
        )}
        {error && (
          <p role="alert" className="mt-2 rounded bg-red-900/40 px-3 py-2 text-sm text-red-200">
            {error}
          </p>
        )}
      </section>

      {saveError && (
        <p role="alert" className="mb-4 rounded bg-red-900/40 px-3 py-2 text-sm text-red-200">
          La dernière tentative n'a pas pu être enregistrée (stockage indisponible).
        </p>
      )}

      <div className="mb-4 flex flex-col gap-2">
        <Segmented label="Camp" options={[{ id: 'w', label: 'Blancs' }, { id: 'b', label: 'Noirs' }]} value={color} onChange={(v) => setOption('camp', v)} />
        <Segmented label="Cadence" options={CADENCES.map((c) => ({ id: c.id, label: c.label }))} value={cadence} onChange={(v) => setOption('cadence', v)} />
      </div>

      {report === null ? (
        <p className="py-6 text-center text-sm text-neutral-500">Lecture de tes parties…</p>
      ) : total === 0 ? (
        <p data-empty="none" className="py-6 text-center text-sm text-neutral-400">
          Aucune partie pour l'instant. Charge tes parties chess.com récentes, ou analyse-les dans Insights pour mesurer ce que te coûtent tes sorties.
        </p>
      ) : colorReport!.games === 0 ? (
        <p data-empty="color" className="py-6 text-center text-sm text-neutral-400">
          Aucune partie avec les {sideFr} {cadence === 'all' ? '' : `en ${CADENCES.find((c) => c.id === cadence)!.label.toLowerCase()} `}parmi tes parties.
        </p>
      ) : (
        <>
          <p data-summary className="mb-3 text-sm text-neutral-300">
            <b>{plural(colorReport!.games, 'partie')}</b> avec les {sideFr}
            {' · '}
            tu sors le premier de la théorie dans <b>{colorReport!.mine}</b>
            {colorReport!.typicalMove !== null && (
              <>
                {' · '}en général au coup <b>{colorReport!.typicalMove}</b>
              </>
            )}
          </p>
          <Cta data-start className="mb-5 w-full text-base" disabled={devCount === 0} onClick={() => startSession()}>
            {devCount ? `🎯 S'entraîner sur mes sorties (${devCount})` : 'Aucune sortie à travailler'}
          </Cta>
          <ul className="flex flex-col gap-3">
            {colorReport!.openings.map((op) => (
              <li key={op.family}>
                <OpeningCard
                  op={op}
                  expanded={expanded.has(op.family)}
                  onExpand={() => setExpanded((s) => new Set(s).add(op.family))}
                  stateOf={(d) => stateOf(d, attempts)}
                  onTrain={startSession}
                  onGame={openGame}
                />
              </li>
            ))}
          </ul>
          {report.skipped > 0 && (
            <p className="mt-3 text-xs text-neutral-500">
              {plural(report.skipped, 'partie')} ignorée{report.skipped > 1 ? 's' : ''} (PGN illisible ou partie depuis une position).
            </p>
          )}
        </>
      )}
    </div>
  )
}

function OpeningCard({ op, expanded, onExpand, stateOf, onTrain, onGame }: {
  op: OpeningReport
  expanded: boolean
  onExpand: () => void
  stateOf: (d: Deviation) => DrillState
  onTrain: (d: Deviation) => void
  onGame: (d: Deviation) => void
}) {
  const shown = expanded ? op.deviations : op.deviations.slice(0, SHOWN_DEVIATIONS)
  const label = op.family === '?' ? 'Ouverture inconnue' : openingFamilyFr(op.family)
  const notes: string[] = []
  if (op.mine) notes.push(`tu sors au coup ${op.typicalMove}`)
  if (op.theirs) notes.push(`l'adversaire sort le premier dans ${plural(op.theirs, 'partie')}`)
  if (!op.mine && !op.theirs) notes.push('tu restes dans la théorie')
  return (
    <div data-opening={op.family} className="rounded-xl bg-surface-2 p-3">
      <div className="flex items-baseline gap-2">
        <h2 className="min-w-0 flex-1 truncate text-base font-black">{label}</h2>
        <span data-opening-games={op.games} className="shrink-0 text-sm font-bold text-neutral-300">
          {plural(op.games, 'partie')}
        </span>
      </div>
      <p className="text-xs text-neutral-400">
        {resultsText(op)} · {notes.join(' · ')}
      </p>
      {shown.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1.5">
          {shown.map((d) => (
            <li key={d.id}>
              <DeviationRow d={d} state={stateOf(d)} onTrain={() => onTrain(d)} onGame={() => onGame(d)} />
            </li>
          ))}
        </ul>
      )}
      {!expanded && op.deviations.length > SHOWN_DEVIATIONS && (
        <button onClick={onExpand} className="mt-2 w-full cursor-pointer rounded-lg bg-surface-3/60 py-2 text-xs font-bold text-neutral-300 hover:bg-surface-3">
          Voir les {op.deviations.length - SHOWN_DEVIATIONS} autres sorties
        </button>
      )}
    </div>
  )
}

function DeviationRow({ d, state, onTrain, onGame }: { d: Deviation; state: DrillState; onTrain: () => void; onGame: () => void }) {
  const played = d.played.map((m) => `${moveLabel(d, m.san)}${d.played.length > 1 ? ` (${m.games})` : ''}`).join(', ')
  const theory = d.expected.map((e) => figurine(e.san, d.color)).join(', ')
  const cost = d.verdict === 'costly'
    ? { text: `−${Math.round(d.avgDrop!)} % de gain`, cls: 'bg-red-900/50 text-red-300' }
    : d.verdict === 'ok'
      ? { text: 'sans dommage', cls: 'bg-surface-3 text-neutral-300' }
      : { text: 'sans bilan', cls: 'bg-surface-3 text-neutral-400' }
  return (
    <div data-deviation={d.id} data-verdict={d.verdict} data-state={state ?? ''} className="rounded-lg bg-surface p-2.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span data-played className="min-w-0 text-sm font-bold text-neutral-100">
          {played}
        </span>
        <span data-cost className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-bold ${cost.cls}`} title={d.reviewed ? `Moyenne sur ${plural(d.reviewed, 'bilan')}` : undefined}>
          {cost.text}
        </span>
        {state && (
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-bold ${state === 'fixed' ? 'bg-accent/20 text-accent' : 'bg-amber-400/20 text-amber-300'}`}>
            {state === 'fixed' ? 'Corrigée' : 'À revoir'}
          </span>
        )}
      </div>
      <p data-theory className="mt-0.5 text-xs text-neutral-300">
        Théorie : <b className="text-[#b5dc8c]">{theory}</b>
      </p>
      <div className="mt-1.5 flex items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-xs text-neutral-400">
          {plural(d.games, 'partie')} · {resultsText(d)}
        </span>
        <button onClick={onGame} className="shrink-0 cursor-pointer rounded-md px-2 py-1 text-xs font-bold text-neutral-300 hover:bg-surface-3 hover:text-white">
          ♞ Partie
        </button>
        <button data-train onClick={onTrain} className="shrink-0 cursor-pointer rounded-md bg-accent/20 px-2.5 py-1 text-xs font-bold text-accent hover:bg-accent/30">
          🎯 S'entraîner
        </button>
      </div>
    </div>
  )
}
