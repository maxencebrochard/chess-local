// Série des Finales au chrono : une finale théorique à gagner ou à tenir nulle contre Stockfish
// pleine force, pendule du joueur seule (elle ne tourne qu'à son trait), incrément après chaque
// coup, prémouvement débité de 100 ms. Positions enchaînées jusqu'au premier raté (drapeau,
// objectif manqué) ; une ligne de record par série, écrite dès la première réussite.
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Chess, type Move } from 'chess.js'
import { Board } from './Board'
import { Cta } from './Cta'
import { EngineContinuation } from './EngineContinuation'
import { BigClock, RunHeader, RunSummary } from './mates/RunParts'
import { PREMOVE_COST_MS, usePlayerClock } from './usePlayerClock'
import type { Engine, SearchResult } from '../lib/engine'
import {
  CLOCK_HINT, drawnStreak, ENDGAME_CLOCK_DOMAIN, familyById, familyOf, holdReached, HOLD_MOVES, judgeBoard, MIX,
  cadenceLabel, recordKey, secondsLabel, seriesRound, VERDICT_NODES, WIN_DRAWN_TURNS,
  type ClockCadence, type ClockPosition, type EngineScore, type Verdict,
} from '../lib/endgameClock'
import { RunRecorder, type RunStats } from '../lib/mates'
import { stashExercise } from '../lib/exerciseReturn'
import { playComputerMove, playMoveSound, sounds } from '../lib/sounds'

const BOT_MOVETIME_MS = 150
const ENGINE_TIMEOUT_MS = 6000
const WIN_PAUSE_MS = 1400 // verdict affiché avant la position suivante

type Phase = 'play' | 'won' | 'over'

// Bilan d'une série close laissé pour l'analyseur (exerciseReturn.ts) : la page le réaffiche au
// retour, sans nouvelle écriture ni pendule relancée.
export const ENDGAME_CLOCK_RETURN_SCREEN = 'finales-chrono'
export interface ClockRunSummary {
  score: number
  reason: string | null
  stopped: boolean
  newRecord: boolean
  pos: ClockPosition
  moves: string[] // coups UCI joués sur la dernière position
  left: number // temps restant affiché à la fin (ms)
}
export interface ClockReturn {
  serie: string
  cadence: ClockCadence
  summary: ClockRunSummary
}

interface Props {
  serie: string // id de famille ou MIX
  cadence: ClockCadence
  stats: RunStats | null
  getEngine: () => Engine
  onDone: () => void // série enregistrée : l'appelant relit les records
  onMenu: () => void
  restored?: ClockRunSummary // retour de l'analyseur : bilan de la série close, réaffiché tel quel
}

export function EndgameClockRun(props: Props) {
  const [series, setSeries] = useState(0) // « Rejouer » remonte tout
  return <ClockSeries key={series} {...props} restored={series === 0 ? props.restored : undefined} onReplay={() => setSeries((s) => s + 1)} />
}

function ClockSeries({ serie, cadence, stats, getEngine, onDone, onMenu, onReplay, restored }: Props & { onReplay: () => void }) {
  const navigate = useNavigate()
  const budget = cadence.baseS * 1000
  const incMs = cadence.incS * 1000
  const queue = useRef<ClockPosition[]>([])
  const recorder = useRef(new RunRecorder(recordKey(serie, cadence), ENDGAME_CLOCK_DOMAIN)).current
  const [pos, setPos] = useState<ClockPosition>(() => restored?.pos ?? nextPosition())
  const chessRef = useRef<Chess | null>(null)
  // Bilan restauré : la dernière position telle que la série l'a laissée (coups rejoués).
  chessRef.current ??= replay(pos.fen, restored?.moves ?? [])
  const family = familyOf(pos.id)!
  const playerColor = new Chess(pos.fen).turn()
  const [fen, setFen] = useState(() => chessRef.current!.fen())
  const [lastMove, setLastMove] = useState<Move | null>(() => chessRef.current!.history({ verbose: true }).at(-1) ?? null)
  const [thinking, setThinking] = useState(false)
  // Bilan restauré : la série est close, rien ne tourne ni ne s'écrit (phase 'over' dès le départ).
  const [phase, setPhase] = useState<Phase>(restored ? 'over' : 'play')
  const [played, setPlayed] = useState(0) // coups du joueur sur la position
  const [score, setScore] = useState(restored?.score ?? 0)
  const [reason, setReason] = useState<string | null>(restored?.reason ?? null)
  const [successMs, setSuccessMs] = useState<number | null>(null)
  const [newRecord, setNewRecord] = useState(restored?.newRecord ?? false)
  const [stopped, setStopped] = useState(restored?.stopped ?? false)
  const [solution, setSolution] = useState(false)
  const clock = usePlayerClock(restored?.left ?? budget, () => fail('Temps écoulé : le drapeau est tombé.'))
  // Miroirs hors rendu : phase, score, coups, temps consommé, génération (réponse périmée ignorée).
  const phaseRef = useRef<Phase>(restored ? 'over' : 'play')
  const scoreRef = useRef(restored?.score ?? 0)
  const playedRef = useRef(0)
  const spent = useRef(0)
  const drawn = useRef(0) // réponses de suite où le gain semble envolé
  const timeouts = useRef(0) // délais de garde du moteur dépassés de suite
  const gen = useRef({ n: 0 }).current
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  function nextPosition(): ClockPosition {
    if (queue.current.length === 0) queue.current = seriesRound(serie).reverse()
    return queue.current.pop()!
  }

  useEffect(() => {
    if (!restored) clock.start()
    return () => {
      if (timer.current) clearTimeout(timer.current)
      gen.n++
      // Quitter en pleine série : ses réussites sont déjà enregistrées ; on ne touche pas à la
      // phase, StrictMode rejoue ce nettoyage au montage sans démontage réel.
      if (phaseRef.current !== 'over' && scoreRef.current > 0) void recorder.save(scoreRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // `why` null : série arrêtée par le joueur (✕). `keepEmpty` faux : une série à zéro n'est pas
  // écrite (arrêt du joueur, moteur en panne).
  function fail(why: string | null, keepEmpty = why !== null) {
    if (phaseRef.current !== 'play' && !(why === null && phaseRef.current === 'won')) return
    if (timer.current) clearTimeout(timer.current)
    phaseRef.current = 'over'
    clock.stop()
    gen.n++
    setThinking(false)
    setReason(why)
    setStopped(why === null)
    setPhase('over')
    if (why !== null) sounds.fail()
    void recorder.finish(scoreRef.current, keepEmpty).then((record) => {
      setNewRecord(record)
      onDone()
    })
  }

  function conclude(v: Verdict) {
    if (!v.success) {
      fail(v.reason)
      return
    }
    clock.stop()
    phaseRef.current = 'won'
    scoreRef.current += 1
    setScore(scoreRef.current)
    setSuccessMs(spent.current)
    setReason(v.reason)
    setPhase('won')
    sounds.success()
    void recorder.save(scoreRef.current)
    timer.current = setTimeout(() => {
      timer.current = null
      loadNext()
    }, WIN_PAUSE_MS)
  }

  // Position suivante, pendule pleine.
  function loadNext() {
    const next = nextPosition()
    chessRef.current = new Chess(next.fen)
    clock.reset(budget)
    spent.current = 0
    drawn.current = 0
    playedRef.current = 0
    setPos(next)
    setFen(next.fen)
    setLastMove(null)
    setPlayed(0)
    setSuccessMs(null)
    setReason(null)
    setThinking(false)
    phaseRef.current = 'play'
    setPhase('play')
    clock.start()
  }

  async function guarded(search: Promise<SearchResult>): Promise<SearchResult | null> {
    let guard: ReturnType<typeof setTimeout> | undefined
    const res = await Promise.race([
      search,
      new Promise<null>((r) => {
        guard = setTimeout(() => r(null), ENGINE_TIMEOUT_MS)
      }),
    ])
    clearTimeout(guard)
    return res
  }

  async function reply(g: number) {
    const c = chessRef.current!
    const searched = c.fen()
    setThinking(true)
    // La réponse dure au moins BOT_MOVETIME_MS même si Stockfish rend la main tout de suite (un
    // seul coup légal) : la pièce adverse ne se téléporte pas, la pendule arrêtée l'est visiblement.
    const [res] = await Promise.all([
      guarded(getEngine().search({ fen: searched, movetimeMs: BOT_MOVETIME_MS, multipv: 1 })),
      new Promise((r) => setTimeout(r, BOT_MOVETIME_MS)),
    ])
    if (g !== gen.n || phaseRef.current !== 'play') return
    const needsVerdict = res !== null && (family.objective === 'win' || playedRef.current >= HOLD_MOVES)
    const judged = needsVerdict
      ? await guarded(getEngine().search({ fen: searched, nodes: VERDICT_NODES, newGame: true, multipv: 1 }))
      : null
    if (g !== gen.n || phaseRef.current !== 'play') return
    setThinking(false)
    const uci = res?.bestMove
    let move: Move | null = null
    if (uci && uci.length >= 4) {
      try {
        move = c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
      } catch {
        move = null
      }
    }
    if (!move) {
      // Moteur muet : une fois, la position est passée sans pénalité ; deux fois de suite, le
      // worker est bloqué et la série s'arrête, sans écrire de série vide.
      timeouts.current += 1
      if (timeouts.current >= 2) fail('Stockfish ne répond plus : série arrêtée. Recharge la page pour le relancer.', false)
      else loadNext()
      return
    }
    timeouts.current = 0
    playComputerMove(move)
    setFen(c.fen())
    setLastMove(move)
    const v = judgeBoard(c, playerColor, family.objective, pos.fen, playedRef.current)
    if (v) {
      conclude(v)
      return
    }
    // Avis du moteur sur la position qu'il vient de jouer (de son point de vue, il avait le trait).
    const line = judged?.lines.find((l) => l.multipv === 1) ?? judged?.lines[0]
    const eng: EngineScore | null = line ? { cp: line.scoreCp, mate: line.scoreMate } : null
    if (family.objective === 'draw' && holdReached(playedRef.current, eng)) {
      conclude({ success: true, reason: `Nulle tenue : ${playedRef.current} coups sans rien lâcher.`, end: null })
      return
    }
    if (family.objective === 'win') {
      drawn.current = drawnStreak(drawn.current, eng)
      if (drawn.current >= WIN_DRAWN_TURNS) {
        fail('Le gain s\'est envolé : Stockfish tient la nulle.')
        return
      }
    }
    clock.start()
  }

  function onMove(from: string, to: string, promotion?: string, premove = false): boolean {
    const c = chessRef.current!
    if (phaseRef.current !== 'play' || thinking || c.turn() !== playerColor) return false
    // Drapeau tombé entre deux ticks : le coup arrive trop tard.
    if (clock.expired()) {
      fail('Temps écoulé : le drapeau est tombé.')
      return false
    }
    let move: Move
    try {
      move = c.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    spent.current += clock.stop()
    if (premove && !clock.debitPremove()) {
      c.undo() // Le coût du prémouvement fait tomber le drapeau : aucun coup joué.
      fail('Temps écoulé : le drapeau est tombé.')
      return false
    }
    if (premove) spent.current += PREMOVE_COST_MS
    clock.addIncrement(incMs)
    playMoveSound(move, false)
    playedRef.current += 1
    setPlayed(playedRef.current)
    setFen(c.fen())
    setLastMove(move)
    const v = judgeBoard(c, playerColor, family.objective, pos.fen, playedRef.current)
    if (v) conclude(v)
    else void reply(++gen.n)
    return true
  }

  // Série close : son bilan est gardé pour le retour, puis l'analyseur ouvre la dernière position.
  function stash() {
    const moves = chessRef.current!.history({ verbose: true }).map((m) => m.lan)
    const summary: ClockRunSummary = { score, reason, stopped, newRecord, pos, moves, left: clock.left }
    stashExercise(ENDGAME_CLOCK_RETURN_SCREEN, { serie, cadence, summary } satisfies ClockReturn)
    return moves
  }

  function analyse() {
    const moves = stash()
    navigate('/analyse', {
      state: { fen: pos.fen, uci: moves, orientation: playerColor, label: title, returnTo: '/finales/chrono', returnLabel: 'Retour au bilan' },
    })
  }

  const toHold = HOLD_MOVES - played
  const status = phase === 'won'
    ? `✓ Objectif atteint en ${secondsLabel(successMs ?? 0)}`
    : phase === 'over'
      ? stopped ? 'Série arrêtée' : '✗ Raté'
      : thinking
        ? 'Stockfish réfléchit…'
        : family.objective === 'win'
          ? played === 0 ? 'À toi : gagne' : 'À toi'
          : toHold > 0 ? `À toi : tiens encore ${toHold} coup${toHold > 1 ? 's' : ''}` : 'Tiens bon : Stockfish insiste'
  const title = `${serie === MIX ? `${family.title} (mélange)` : (familyById(serie)?.title ?? family.title)} · ${cadenceLabel(cadence)}`

  return (
    <div
      data-run="endgame-clock"
      data-fen={fen}
      data-phase={phase}
      data-position={pos.id}
      data-objective={family.objective}
      className="mx-auto flex w-full max-w-2xl flex-col gap-2 pb-4"
    >
      <RunHeader title={title} score={score} onQuit={() => fail(null)} />
      <div className="flex items-center gap-2 px-3">
        <span
          className={`shrink-0 rounded px-2 py-1 text-sm font-bold ${
            family.objective === 'win' ? 'bg-accent/15 text-accent-light' : 'bg-sky-900/40 text-sky-300'
          }`}
        >
          {family.objective === 'win' ? 'Gagner' : 'Tenir la nulle'}
        </span>
        <span className="min-w-0 text-xs leading-snug text-neutral-400">{CLOCK_HINT[family.goal]}</span>
      </div>
      <div className="px-3">
        <BigClock ms={clock.left} running={phase === 'play' && !thinking} />
      </div>
      <p
        data-status
        className={`text-center text-base font-bold ${
          phase === 'won' ? 'text-accent' : phase === 'over' && !stopped ? 'text-red-400' : 'text-neutral-300'
        }`}
      >
        {status}
      </p>
      {phase === 'won' && reason && <p className="-mt-1 px-3 text-center text-sm text-neutral-400">{reason}</p>}
      <div className="flex justify-center">
        <div className="boardbox md:w-[min(60vh,560px)]">
          <Board
            fen={fen}
            orientation={playerColor}
            interactive={phase === 'play' && !thinking}
            allowPremove={phase === 'play'}
            movableColor={playerColor}
            onMove={onMove}
            lastMove={lastMove ? { from: lastMove.from, to: lastMove.to } : null}
            // Sons joués au coup lui-même, par cette série.
            silent
          />
        </div>
      </div>
      {phase === 'over' && (
        <div className="px-3">
          <RunSummary
            score={score}
            stats={stats}
            newRecord={newRecord}
            reason={reason}
            units={['finale réussie', 'finales réussies']}
            onReplay={onReplay}
            onMenu={onMenu}
          >
            <p data-principle className="rounded-lg bg-surface-3/60 px-3 py-2 text-left text-sm text-neutral-300">
              <span className="font-bold text-white">{family.title} : </span>
              {family.principle}
            </p>
            <Cta variant="secondary" className="w-full py-2 text-base" onClick={() => setSolution(true)}>
              💡 Voir la solution de Stockfish
            </Cta>
            <Cta variant="secondary" className="w-full py-2 text-base" onClick={analyse}>
              ♞ Analyser avec Stockfish
            </Cta>
          </RunSummary>
        </div>
      )}
      {solution && (
        <EngineContinuation
          startFen={pos.fen}
          playerColor={playerColor}
          mode="plan"
          label={title}
          returnTo="/finales/chrono"
          onBeforeAnalyse={() => void stash()}
          onClose={() => setSolution(false)}
        />
      )}
    </div>
  )
}

function replay(fen: string, moves: string[]): Chess {
  const c = new Chess(fen)
  for (const m of moves) c.move({ from: m.slice(0, 2), to: m.slice(2, 4), promotion: m[4] })
  return c
}
