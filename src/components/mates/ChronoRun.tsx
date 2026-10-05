// Contre la montre : mater Stockfish (pleine force, il défend au mieux) avant la chute du drapeau.
// Le chrono ne tourne qu'au trait du joueur, comme une pendule. Mats enchaînés jusqu'au premier
// raté (drapeau, pat, nulle) ; une ligne de record par série, écrite dès le premier mat.
import { useEffect, useRef, useState } from 'react'
import { Chess, type Move } from 'chess.js'
import { Board } from '../Board'
import { Cta } from '../Cta'
import { EngineContinuation } from '../EngineContinuation'
import { BigClock, RunHeader, RunSummary } from './RunParts'
import { NetLegend } from './NetBoard'
import type { Engine } from '../../lib/engine'
import { analyseMate, netView, principleOf } from '../../lib/mateNet'
import {
  CADENCE_LABEL, CADENCE_MS, chronoPool, chronoTitle, RunRecorder, runKey,
  type Cadence, type ChronoPosition, type Drill, type RunStats,
} from '../../lib/mates'
import { sounds } from '../../lib/sounds'
import { useSettings } from '../../store/settings'

const BOT_MOVETIME_MS = 150
const ENGINE_TIMEOUT_MS = 6000
const WIN_PAUSE_MS = 1400 // réseau du mat affiché avant la position suivante
const TICK_MS = 100

type Phase = 'play' | 'won' | 'over'

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

function drawReason(c: Chess, last: Move | null): string {
  if (c.isStalemate()) return 'Pat : le roi n\'a plus de coup et n\'est pas en échec. Nulle.'
  if (c.isInsufficientMaterial()) {
    return last?.captured ? 'Ta pièce a été prise : il ne reste plus assez de matériel pour mater. Nulle.' : 'Nulle : il ne reste plus assez de matériel pour mater.'
  }
  if (c.isThreefoldRepetition()) return 'Nulle par triple répétition.'
  return 'Nulle par la règle des 50 coups.'
}

interface Props {
  drill: Drill
  cadence: Cadence
  stats: RunStats | null
  getEngine: () => Engine
  onDone: () => void // série enregistrée : l'appelant relit les records
  onMenu: () => void
}

export function ChronoRun({ drill, cadence, stats, getEngine, onDone, onMenu }: Props) {
  const { playSounds } = useSettings()
  const budget = CADENCE_MS[cadence] ?? 30_000
  const [series, setSeries] = useState(0) // « Rejouer » remonte tout
  return (
    <ChronoSeries
      key={series}
      drill={drill}
      cadence={cadence}
      budget={budget}
      stats={stats}
      playSounds={playSounds}
      getEngine={getEngine}
      onDone={onDone}
      onMenu={onMenu}
      onReplay={() => setSeries((s) => s + 1)}
    />
  )
}

function ChronoSeries({ drill, cadence, budget, stats, playSounds, getEngine, onDone, onMenu, onReplay }: Props & {
  budget: number
  playSounds: boolean
  onReplay: () => void
}) {
  const [newRecord, setNewRecord] = useState(false)
  const [played, setPlayed] = useState(0) // coups du joueur sur la position
  const timeouts = useRef(0) // délais de garde du moteur dépassés de suite
  const queue = useRef<ChronoPosition[]>([])
  const recorder = useRef(new RunRecorder(runKey(drill.id, cadence))).current
  const chessRef = useRef<Chess | null>(null)
  const [pos, setPos] = useState<ChronoPosition>(() => nextPosition())
  chessRef.current ??= new Chess(pos.fen)
  const playerColor = new Chess(pos.fen).turn()
  const [fen, setFen] = useState(pos.fen)
  const [lastMove, setLastMove] = useState<Move | null>(null)
  const [thinking, setThinking] = useState(false)
  const [phase, setPhase] = useState<Phase>('play')
  const [score, setScore] = useState(0)
  const [reason, setReason] = useState<string | null>(null)
  const [left, setLeft] = useState(budget)
  const [mateMs, setMateMs] = useState<number | null>(null)
  const [solution, setSolution] = useState(false)
  const [stopped, setStopped] = useState(false)
  // Miroirs hors rendu : chrono, phase, score et génération (réponse moteur périmée ignorée).
  const leftRef = useRef(budget)
  const deadline = useRef<number | null>(null)
  const phaseRef = useRef<Phase>('play')
  const scoreRef = useRef(0)
  const gen = useRef({ n: 0 }).current
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  function nextPosition(): ChronoPosition {
    if (queue.current.length === 0) queue.current = shuffle(chronoPool(drill.pattern ?? 'mix'))
    return queue.current.pop()!
  }

  // Démarrage du chrono au trait du joueur ; arrêt (temps restant figé) à son coup.
  function startClock() {
    deadline.current = Date.now() + leftRef.current
  }
  function stopClock() {
    if (deadline.current !== null) leftRef.current = Math.max(0, deadline.current - Date.now())
    deadline.current = null
    setLeft(leftRef.current)
  }

  useEffect(() => {
    startClock()
    const tick = () => {
      if (deadline.current === null || phaseRef.current !== 'play') return
      const l = Math.max(0, deadline.current - Date.now())
      setLeft(l)
      if (l === 0) fail('Temps écoulé : le drapeau est tombé.')
    }
    const id = setInterval(tick, TICK_MS)
    document.addEventListener('visibilitychange', tick)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', tick)
      if (timer.current) clearTimeout(timer.current)
      gen.n++
      // Quitter en pleine série : ses mats sont déjà enregistrés (ligne écrite à chaque mat) ; on
      // ne touche pas à la phase, StrictMode rejoue ce nettoyage au montage sans démontage réel.
      if (phaseRef.current !== 'over' && scoreRef.current > 0) void recorder.save(scoreRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // `why` null : série arrêtée par le joueur (✕), sans motif d'échec.
  function fail(why: string | null) {
    if (phaseRef.current !== 'play' && !(why === null && phaseRef.current === 'won')) return
    if (timer.current) clearTimeout(timer.current)
    phaseRef.current = 'over'
    stopClock()
    gen.n++
    setThinking(false)
    setReason(why)
    setStopped(why === null)
    setPhase('over')
    if (playSounds && why !== null) sounds.fail()
    void recorder.finish(scoreRef.current, why !== null).then((record) => {
      setNewRecord(record)
      onDone()
    })
  }

  function win() {
    stopClock()
    phaseRef.current = 'won'
    scoreRef.current += 1
    setScore(scoreRef.current)
    setMateMs(budget - leftRef.current)
    setPhase('won')
    if (playSounds) sounds.success()
    void recorder.save(scoreRef.current)
    timer.current = setTimeout(() => {
      timer.current = null
      loadNext()
    }, WIN_PAUSE_MS)
  }

  // Position suivante, chrono plein.
  function loadNext() {
    const next = nextPosition()
    chessRef.current = new Chess(next.fen)
    leftRef.current = budget
    setLeft(budget)
    setPos(next)
    setFen(next.fen)
    setLastMove(null)
    setMateMs(null)
    setPlayed(0)
    setThinking(false)
    phaseRef.current = 'play'
    setPhase('play')
    startClock()
  }

  // Fin de partie après un coup : mat du joueur, ou nulle (raté).
  function settle(last: Move): boolean {
    const c = chessRef.current!
    if (!c.isGameOver()) return false
    if (c.isCheckmate() && c.turn() !== playerColor) win()
    else fail(c.isCheckmate() ? 'Mat… pour Stockfish.' : drawReason(c, last))
    return true
  }

  function sound(move: Move) {
    if (!playSounds) return
    if (chessRef.current!.inCheck()) sounds.check()
    else if (move.captured) sounds.capture()
    else sounds.move()
  }

  async function reply(g: number) {
    const c = chessRef.current!
    setThinking(true)
    let guard: ReturnType<typeof setTimeout> | undefined
    const res = await Promise.race([
      getEngine().search({ fen: c.fen(), movetimeMs: BOT_MOVETIME_MS, multipv: 1 }),
      new Promise<null>((r) => {
        guard = setTimeout(() => r(null), ENGINE_TIMEOUT_MS)
      }),
    ])
    clearTimeout(guard)
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
      // worker est bloqué (ses commandes sont en file) et la série s'arrête.
      timeouts.current += 1
      if (timeouts.current >= 2) fail('Stockfish ne répond plus : série arrêtée. Recharge la page pour le relancer.')
      else loadNext()
      return
    }
    timeouts.current = 0
    sound(move)
    setFen(c.fen())
    setLastMove(move)
    if (!settle(move)) startClock()
  }

  function onMove(from: string, to: string, promotion?: string): boolean {
    const c = chessRef.current!
    if (phaseRef.current !== 'play' || thinking || c.turn() !== playerColor) return false
    // Drapeau tombé entre deux ticks : le coup arrive trop tard.
    if (deadline.current !== null && Date.now() >= deadline.current) {
      fail('Temps écoulé : le drapeau est tombé.')
      return false
    }
    let move: Move
    try {
      move = c.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    stopClock()
    sound(move)
    setFen(c.fen())
    setLastMove(move)
    setPlayed((n) => n + 1)
    if (!settle(move)) void reply(++gen.n)
    return true
  }

  const net = phase === 'won' ? analyseMate(fen) : null
  const view = net ? netView(net, fen) : null
  const title = `${drill.pattern === 'mix' ? `${chronoTitle(pos.pattern)} (mélange)` : drill.title} · ${CADENCE_LABEL[cadence]}`
  const status = phase === 'won'
    ? `✓ Mat en ${((mateMs ?? 0) / 1000).toFixed(1).replace('.', ',')} s`
    : phase === 'over'
      ? stopped ? 'Série arrêtée' : '✗ Raté'
      : thinking
        ? 'Stockfish défend…'
        : played === 0 ? `À toi : mat en ${pos.mateIn} au mieux` : 'À toi'

  return (
    <div data-run="chrono" data-fen={fen} data-phase={phase} className="mx-auto flex w-full max-w-2xl flex-col gap-2 pb-4">
      <RunHeader title={title} score={score} onQuit={() => fail(null)} />
      <div className="px-3">
        <BigClock ms={left} running={phase === 'play' && !thinking} />
      </div>
      <p
        className={`text-center text-base font-bold ${
          phase === 'won' ? 'text-accent' : phase === 'over' && !stopped ? 'text-red-400' : 'text-neutral-300'
        }`}
      >
        {status}
      </p>
      <div className="flex justify-center">
        <div className="boardbox md:w-[min(60vh,560px)]">
          <Board
            fen={fen}
            orientation={playerColor}
            interactive={phase === 'play' && !thinking}
            movableColor={playerColor}
            onMove={onMove}
            lastMove={view ? null : lastMove ? { from: lastMove.from, to: lastMove.to } : null}
            arrows={view?.arrows}
            markSquares={view?.marks}
          />
        </div>
      </div>
      {net && view && (
        <div className="px-3">
          <NetLegend principle={principleOf(net)} view={view} />
        </div>
      )}
      {phase === 'over' && (
        <div className="px-3">
          <RunSummary
            score={score}
            stats={stats}
            newRecord={newRecord}
            reason={reason}
            onReplay={onReplay}
            onMenu={onMenu}
          >
            <Cta variant="secondary" className="w-full py-2 text-base" onClick={() => setSolution(true)}>
              💡 Voir la solution de Stockfish
            </Cta>
          </RunSummary>
        </div>
      )}
      {solution && (
        <EngineContinuation startFen={pos.fen} playerColor={playerColor} mode="plan" onClose={() => setSolution(false)} />
      )}
    </div>
  )
}
