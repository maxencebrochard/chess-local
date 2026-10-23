// « Mes structures de pions » (/structures) : structures repérées dans mes parties, résultats par
// structure, puis partie contre Stockfish bridé depuis le moment où la structure est apparue
// (/structures/:key). Les structures sont recalculées depuis les parties, sans réseau ;
// les tentatives sont persistées selon le contrat `structure-play` de db.ts.
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { ConfirmSheet } from '../components/ConfirmSheet'
import { PageHeader } from '../components/PageHeader'
import { groupBack } from '../lib/navigation'
import { PositionGame } from '../components/PositionGame'
import { recordReplaced } from '../lib/attempts'
import { DECISIVE_CP, loadLevel, opponentFor, outcomeOf, saveLevel, type Level } from '../lib/attack'
import {
  loadMyStructures, playKey, positionKey, recordStructurePlay, sightingByKey, structurePath, structurePlayStats,
  type MyGame, type MyStructures as MyStructuresData, type PlayStats,
} from '../lib/myStructures'
import { inProgressKey, loadStoredGame, resumedGame } from '../lib/positionGame'
import { squaresFor, STRUCTURE_IDS, STRUCTURES, type Sighting, type StructureStat } from '../lib/structures'
import { STRUCTURES_COURSE } from '../lib/structuresCourse'
import { LEVEL_HELP, LevelPicker } from '../components/LevelPicker'

const SHOWN = 3 // positions affichées par structure avant « Tout voir »

export default function MyStructures() {
  const { key } = useParams()
  return key ? <StructurePlay key={key} posKey={key} /> : <StructureList />
}

// Carte d'entrée, sous la progression du sommaire du cours.
export function MyStructuresCard() {
  return (
    <Link to="/structures" data-testid="my-structures-card" className="mb-5 flex items-center gap-3 rounded-xl bg-surface-2 p-3 hover:bg-surface-3">
      <span className="text-2xl" aria-hidden="true">🔎</span>
      <span className="min-w-0 flex-1">
        <span className="block font-bold">Dans mes parties</span>
        <span className="block text-xs text-neutral-400">Tes structures les plus fréquentes, tes résultats, et leurs positions à rejouer</span>
      </span>
      <span className="text-xl text-neutral-500" aria-hidden="true">›</span>
    </Link>
  )
}

const back = (navigate: ReturnType<typeof useNavigate>, fallback: string) =>
  ((window.history.state as { idx?: number } | null)?.idx ?? 0) > 0 ? navigate(-1) : navigate(fallback, { replace: true })

const pct = (x: number) => `${Math.round(x * 100)} %`
const plural = (n: number, word: string) => `${n} ${word}${n > 1 ? 's' : ''}`

function summary(data: MyStructuresData): string {
  const top = data.stats[0]
  if (!top) return `Aucune structure typique dans tes ${plural(data.games, 'partie')} pour l'instant.`
  return `Sur ${plural(data.games, 'partie')}, ta structure la plus fréquente : ${STRUCTURES[top.id].name} (${plural(top.games, 'partie')}, ${pct(top.score)} des points).`
}

function StructureList() {
  const navigate = useNavigate()
  const [data, setData] = useState<MyStructuresData | null>(null)
  const [plays, setPlays] = useState<Map<string, PlayStats>>(new Map())
  const [level, setLevel] = useState<Level>(loadLevel)
  const [inProgress] = useState(inProgressKey)

  useEffect(() => {
    let live = true
    void Promise.all([loadMyStructures(), structurePlayStats()]).then(([d, p]) => {
      if (!live) return
      setData(d)
      setPlays(p)
    })
    return () => {
      live = false
    }
  }, [])

  const unseen = data ? STRUCTURE_IDS.filter((id) => !data.stats.some((s) => s.id === id)) : []

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader
        title="🔎 Mes structures de pions"
        description="Les structures typiques de tes parties et tes résultats avec chacune. Rejoue une position contre Stockfish depuis le moment où la structure est apparue."
        back={{ label: groupBack('strategie').label, onClick: () => navigate(groupBack('strategie').to) }}
      />

      {data === null ? (
        <p data-testid="structures-loading" className="rounded-xl bg-surface-2 p-4 text-sm text-neutral-400">Lecture de tes parties…</p>
      ) : (
        <>
          <p data-testid="structures-summary" className="mb-4 text-[15px] font-semibold text-neutral-100">{summary(data)}</p>

          {data.stats.length === 0 ? (
            <p data-testid="structures-empty" className="mb-4 rounded-xl bg-surface-2 p-4 text-sm text-neutral-300">
              Joue des parties contre les bots de l'app, ou lance Insights sur tes parties chess.com : leurs structures apparaîtront ici,
              avec tes résultats et des positions à rejouer.
            </p>
          ) : (
            <>
              <div className="flex flex-col gap-3">
                {data.stats.map((st) => (
                  <StructureCard key={st.id} stat={st} plays={plays} inProgress={inProgress} />
                ))}
              </div>
              <section data-testid="defender" className="mt-4 rounded-xl bg-surface-2 p-3">
                <div className="mb-2 flex items-baseline justify-between gap-2">
                  <h2 className="font-bold">🤖 Adversaire</h2>
                  <span className="text-sm font-semibold text-accent">{level === null ? 'Stockfish pleine force' : `Stockfish Elo ${level}`}</span>
                </div>
                <LevelPicker
                  value={level}
                  label="Niveau de Stockfish"
                  onChange={(l) => {
                    setLevel(l)
                    saveLevel(l)
                  }}
                />
                <p className="mt-2 text-xs text-neutral-400">{LEVEL_HELP}</p>
              </section>
            </>
          )}

          {unseen.length > 0 && (
            <section className="mt-5">
              <h2 className="mb-2 text-sm font-semibold text-neutral-400">Pas encore vues dans tes parties :</h2>
              <div className="flex flex-wrap gap-2">
                {unseen.map((id) => (
                  <Link
                    key={id}
                    to={`${STRUCTURES_COURSE.path}/${STRUCTURES[id].lesson}`}
                    data-testid="structure-unseen"
                    data-id={id}
                    className="rounded-full bg-surface-2 px-3 py-1.5 text-sm font-semibold text-neutral-300 hover:bg-surface-3"
                  >
                    {STRUCTURES[id].emoji} {STRUCTURES[id].name}
                  </Link>
                ))}
              </div>
            </section>
          )}
          <p className="mt-5 text-xs text-neutral-400">
            Comptées : tes parties contre les bots de l'app et les parties chess.com déjà passées au bilan par Insights (tous pseudos).
            Une structure compte dès le 10e demi-coup, quand chaque camp a encore trois pièces au moins (sauf la majorité, structure de
            finale), si elle tient quatre demi-coups de suite.
          </p>
        </>
      )}
    </div>
  )
}

function StructureCard({ stat, plays, inProgress }: { stat: StructureStat<MyGame>; plays: Map<string, PlayStats>; inProgress: string | null }) {
  const [all, setAll] = useState(false)
  const meta = STRUCTURES[stat.id]
  const shown = all ? stat.sightings : stat.sightings.slice(0, SHOWN)
  const against = stat.games - stat.owner
  return (
    <section data-testid="structure-card" data-id={stat.id} data-games={stat.games} className="rounded-xl bg-surface-2 p-3">
      <div className="flex items-center gap-3">
        <span className="text-2xl" aria-hidden="true">{meta.emoji}</span>
        <div className="min-w-0 flex-1">
          <h2 className="truncate font-bold">{meta.name}</h2>
          <p data-testid="structure-record" className="text-xs tabular-nums text-neutral-400">
            {plural(stat.games, 'partie')} · {stat.wins} V · {stat.draws} N · {stat.losses} D · <span className="font-bold text-neutral-200">{pct(stat.score)}</span>
          </p>
        </div>
        <Link
          to={`${STRUCTURES_COURSE.path}/${meta.lesson}`}
          data-testid="structure-lesson"
          className="shrink-0 rounded-lg bg-surface-3 px-3 py-1.5 text-sm font-semibold text-neutral-200 hover:bg-surface-3/70"
        >
          Leçon
        </Link>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-3" aria-hidden="true">
        <div className="h-full rounded-full bg-accent" style={{ width: `${stat.score * 100}%` }} />
      </div>
      <p data-testid="structure-sides" className="mt-2 text-xs text-neutral-400">
        Avec la structure : {stat.owner} · contre : {against}
      </p>
      <div className="mt-2 flex flex-col gap-1.5">
        {shown.map(({ game, sighting, owner }) => (
          <PositionRow key={positionKey(game, sighting)} game={game} sighting={sighting} owner={owner} plays={plays} inProgress={inProgress} />
        ))}
      </div>
      {stat.sightings.length > SHOWN && (
        <button onClick={() => setAll(!all)} className="mt-2 cursor-pointer text-sm font-semibold text-accent hover:underline">
          {all ? 'Réduire' : `Tout voir (${stat.sightings.length})`}
        </button>
      )}
    </section>
  )
}

function gameLabel(game: MyGame): string {
  const date = new Date(game.date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })
  return `${game.source === 'chesscom' ? 'chess.com · ' : ''}contre ${game.opponent} · ${date}`
}

const moveNumber = (s: Sighting) => Math.floor(s.ply / 2) + 1

function PositionRow({ game, sighting, owner, plays, inProgress }: {
  game: MyGame
  sighting: Sighting
  owner: boolean
  plays: Map<string, PlayStats>
  inProgress: string | null
}) {
  const navigate = useNavigate()
  const key = positionKey(game, sighting)
  const p = plays.get(`${key}|${sighting.fen}`)
  const going = inProgress === `${playKey(key)}|${sighting.fen}`
  const result = game.result === 'win' ? 'gagnée' : game.result === 'draw' ? 'nulle' : 'perdue'
  return (
    <button
      data-testid="structure-position"
      data-key={key}
      onClick={() => navigate(structurePath(key))}
      className="flex min-h-12 cursor-pointer items-center gap-2 rounded-lg bg-surface-3/60 px-2.5 py-2 text-left hover:bg-surface-3"
    >
      <span className={`w-14 shrink-0 rounded-full py-0.5 text-center text-[11px] font-bold ${owner ? 'bg-accent/20 text-accent-light' : 'bg-sky-900/40 text-sky-300'}`}>
        {owner ? 'avec' : 'contre'}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold">{gameLabel(game)}</span>
        <span className="block truncate text-xs text-neutral-400">
          Coup {moveNumber(sighting)}, {game.playerColor === 'w' ? 'Blancs' : 'Noirs'} · partie {result}
        </span>
      </span>
      {going ? (
        <span className="shrink-0 rounded-full bg-amber-900/40 px-2 py-0.5 text-xs font-semibold text-amber-200">En cours</span>
      ) : p && p.successes > 0 ? (
        <span data-testid="structure-solved" className="shrink-0 text-xs font-bold text-accent">✓ gagnée</span>
      ) : p ? (
        <span data-testid="structure-attempts" className="shrink-0 text-xs text-neutral-400">{plural(p.attempts, 'essai')}</span>
      ) : (
        <span aria-hidden="true" className="shrink-0 text-xl text-neutral-500">›</span>
      )}
    </button>
  )
}

// ---------- Partie ----------

function StructurePlay({ posKey }: { posKey: string }) {
  const [found, setFound] = useState<Awaited<ReturnType<typeof sightingByKey>> | undefined>(undefined)
  useEffect(() => {
    let live = true
    void sightingByKey(posKey).then((f) => live && setFound(f))
    return () => {
      live = false
    }
  }, [posKey])
  if (found === undefined) return null
  if (!found) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 p-6 text-center">
        <p data-testid="structure-missing" className="text-neutral-300">Cette position n'est plus dans tes parties.</p>
        <p className="text-sm text-neutral-400">La partie a été supprimée, ou la structure n'y est plus reconnue.</p>
        <Link to="/structures" replace className="rounded-lg bg-surface-3 px-4 py-2 font-semibold hover:bg-surface-3/70">
          Mes structures
        </Link>
      </div>
    )
  }
  return <StructureGame posKey={posKey} game={found.game} sighting={found.sighting} />
}

function StructureGame({ posKey, game, sighting }: { posKey: string; game: MyGame; sighting: Sighting }) {
  const navigate = useNavigate()
  const location = useLocation()
  const restore = !!(location.state as { restore?: boolean } | null)?.restore
  const meta = STRUCTURES[sighting.id]
  const owner = sighting.side === game.playerColor
  const gk = playKey(posKey)
  const [level, setLevel] = useState<Level>(() => {
    const stored = resumedGame(gk, sighting.fen, restore)
    return stored?.level !== undefined ? stored.level : loadLevel()
  })
  const [attempt, setAttempt] = useState(0)
  const [picking, setPicking] = useState<Level | undefined>(undefined)

  function applyLevel(l: Level) {
    setPicking(undefined)
    if (l === level) return
    saveLevel(l)
    const stored = loadStoredGame()
    if (stored && stored.key === gk && stored.startFen === sighting.fen && !stored.end && !stored.recorded && stored.uci.length > 0) {
      void recordStructurePlay(posKey, sighting.fen, 'abandon', stored.level ?? null, stored.assisted)
    }
    setLevel(l)
    setAttempt((a) => a + 1)
  }

  const plan = squaresFor(owner ? meta.planOwner : meta.planOpponent, sighting.side)
  const lesson = `${plan} Ta partie ${gameLabel(game)} : la structure est apparue au coup ${moveNumber(sighting)}.`

  return (
    <>
      <PositionGame
        key={attempt}
        gameKey={gk}
        startFen={sighting.fen}
        title={meta.name}
        objective={null}
        objectiveLabel="Objectif : joue le plan de la structure"
        goalHint={`${owner ? 'Avec' : 'Contre'} ${squaresFor(meta.owner, sighting.side)} · ta partie, coup ${moveNumber(sighting)}`}
        lesson={lesson}
        lessonLabel="Plan"
        resume={attempt === 0}
        restoreFinished={restore && attempt === 0}
        returnTo={structurePath(posKey)}
        returnLabel="Retour à la position"
        opponent={opponentFor(level)}
        decisiveCp={DECISIVE_CP}
        planButton
        headerAction={
          <button
            onClick={() => setPicking(level)}
            aria-label="Niveau de Stockfish"
            data-testid="level-chip"
            className="flex h-11 shrink-0 cursor-pointer items-center gap-1 rounded-full bg-surface-2 px-2.5 text-xs font-bold tabular-nums text-neutral-200 hover:bg-surface-3"
          >
            🤖 {level ?? 'Max'}
          </button>
        }
        onExit={() => back(navigate, '/structures')}
        onFinished={(_, info) => void recordStructurePlay(posKey, sighting.fen, outcomeOf(info.end, game.playerColor), level, info.assisted)}
        onAbandon={({ assisted }) => void recordStructurePlay(posKey, sighting.fen, 'abandon', level, assisted)}
        onReplace={recordReplaced}
      />
      {picking !== undefined && (
        <ConfirmSheet
          title="Niveau de Stockfish"
          confirmLabel="Appliquer"
          testId="level"
          onConfirm={() => applyLevel(picking)}
          onCancel={() => setPicking(undefined)}
        >
          <LevelPicker value={picking} onChange={setPicking} label="Niveau de Stockfish" />
          <p className="text-xs text-neutral-400">{LEVEL_HELP}</p>
          <p>Changer de niveau recommence la position.</p>
        </ConfirmSheet>
      )}
    </>
  )
}
