// Série de puzzles de mat façon Puzzle Rush (mat en N, géométrie, motifs) : 3 min, 5 min ou survie,
// trois erreurs et c'est fini. Après chaque mat, le réseau s'affiche sur la position réellement
// atteinte, chrono suspendu. Une ligne de record par série, écrite dès le premier mat.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Board } from '../Board'
import { FAIL_FLASH_MS, PuzzlePlayer, type PuzzleData } from '../PuzzlePlayer'
import { BigClock, RunHeader, RunSummary } from './RunParts'
import { NetLegend } from './NetBoard'
import { analyseMate, netView, principleOf, TAG_PRINCIPLE } from '../../lib/mateNet'
import {
  CADENCE_LABEL, CADENCE_MS, pickPuzzle, puzzlePool, RunRecorder, runKey,
  type Cadence, type Drill, type RunStats,
} from '../../lib/mates'

const NET_MS = 1500
const NEXT_MS = 400

interface Props {
  drill: Drill
  cadence: Cadence
  all: PuzzleData[]
  stats: RunStats | null
  showNet: boolean
  onDone: () => void
  onMenu: () => void
}

export function PuzzleRun(props: Props) {
  const [series, setSeries] = useState(0)
  return <PuzzleSeries key={series} {...props} onReplay={() => setSeries((s) => s + 1)} />
}

type Phase = 'play' | 'net' | 'over'

function PuzzleSeries({ drill, cadence, all, stats, showNet, onDone, onMenu, onReplay }: Props & { onReplay: () => void }) {
  const navigate = useNavigate()
  const total = CADENCE_MS[cadence]
  const pool = useMemo(() => puzzlePool(drill, all), [drill, all])
  const [newRecord, setNewRecord] = useState(false)
  const recorder = useRef(new RunRecorder(runKey(drill.id, cadence))).current
  const used = useRef(new Set<string>()).current
  const [puzzle, setPuzzle] = useState<PuzzleData | null>(() => pickPuzzle(pool, 0, used) ?? null)
  const [phase, setPhase] = useState<Phase>('play')
  const [score, setScore] = useState(0)
  const [strikes, setStrikes] = useState(0)
  const [netFen, setNetFen] = useState<string | null>(null)
  const [missed, setMissed] = useState<PuzzleData[]>([])
  const [left, setLeft] = useState(total ?? 0)
  const phaseRef = useRef<Phase>('play')
  const scoreRef = useRef(0)
  const strikesRef = useRef(0)
  const endAt = useRef(total === null ? null : Date.now() + total)
  const pausedAt = useRef<number | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const tick = () => {
      if (endAt.current === null || pausedAt.current !== null || phaseRef.current === 'over') return
      const l = Math.max(0, endAt.current - Date.now())
      setLeft(l)
      if (l === 0) finish()
    }
    tick()
    const id = setInterval(tick, 100)
    document.addEventListener('visibilitychange', tick)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', tick)
      if (timer.current) clearTimeout(timer.current)
      // Quitter en pleine série : ses mats sont déjà enregistrés (ligne écrite à chaque mat) ; on
      // ne touche pas à la phase, StrictMode rejoue ce nettoyage au montage sans démontage réel.
      if (phaseRef.current !== 'over' && scoreRef.current > 0) void recorder.save(scoreRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function later(fn: () => void, ms: number) {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      timer.current = null
      fn()
    }, ms)
  }

  // `stopped` : arrêt par le joueur (✕) ; une série arrêtée à zéro n'est pas enregistrée.
  function finish(stopped = false) {
    if (phaseRef.current === 'over') return
    phaseRef.current = 'over'
    if (timer.current) clearTimeout(timer.current)
    setPhase('over')
    void recorder.finish(scoreRef.current, !stopped).then((record) => {
      setNewRecord(record)
      onDone()
    })
  }

  function next() {
    if (phaseRef.current === 'over') return
    if (pausedAt.current !== null && endAt.current !== null) endAt.current += Date.now() - pausedAt.current
    pausedAt.current = null
    const p = pickPuzzle(pool, scoreRef.current, used)
    if (!p) {
      finish()
      return
    }
    setNetFen(null)
    setPuzzle(p)
    phaseRef.current = 'play'
    setPhase('play')
  }

  function onComplete(success: boolean, _step: number, fen: string) {
    if (phaseRef.current !== 'play' || !puzzle || used.has(puzzle.id)) return
    used.add(puzzle.id)
    // Chrono écoulé entre deux ticks : le coup arrive trop tard.
    if (endAt.current !== null && pausedAt.current === null && Date.now() >= endAt.current) {
      finish()
      return
    }
    if (success) {
      scoreRef.current += 1
      setScore(scoreRef.current)
      void recorder.save(scoreRef.current)
      if (showNet && analyseMate(fen)) {
        // Le chrono s'arrête le temps de lire le réseau : la lecture n'est pas une taxe.
        pausedAt.current = Date.now()
        phaseRef.current = 'net'
        setNetFen(fen)
        setPhase('net')
        later(next, NET_MS)
      } else {
        later(next, NEXT_MS)
      }
      return
    }
    strikesRef.current += 1
    setStrikes(strikesRef.current)
    setMissed((m) => [...m, puzzle])
    if (strikesRef.current >= 3) later(finish, FAIL_FLASH_MS)
    else later(next, FAIL_FLASH_MS)
  }

  const net = netFen ? analyseMate(netFen) : null
  const view = net && netFen ? netView(net, netFen) : null
  // Géométrie : un autre mat que celui de la ligne principale peut ne pas avoir la géométrie visée.
  const other = !!(net && drill.geo && !net.tags.includes(drill.geo))
  const principle = net ? (drill.geo && !other ? TAG_PRINCIPLE[drill.geo] : principleOf(net)) : ''

  function analyse(p: PuzzleData) {
    navigate('/analyse', {
      state: {
        fen: p.fen,
        uci: p.moves,
        viewIndex: 0, // après le coup d'amorce adverse
        orientation: p.fen.split(' ')[1] === 'w' ? 'b' : 'w',
        label: `Puzzle ${p.id} (${p.rating})`,
        returnTo: `/mats?d=${drill.id}`,
      },
    })
  }

  return (
    <div data-run="puzzle" data-puzzle={puzzle?.id ?? ''} data-phase={phase} className="mx-auto flex w-full max-w-2xl flex-col gap-2 pb-4">
      <RunHeader title={`${drill.title} · ${CADENCE_LABEL[cadence]}`} score={score} onQuit={() => finish(true)} />
      <div className="flex items-stretch gap-2 px-3">
        <div className="flex-1">
          {total !== null ? (
            <BigClock ms={left} running={phase === 'play'} warnMs={20_000} />
          ) : (
            <div className="rounded-xl bg-surface-3 py-1 text-center text-3xl leading-[3.75rem] font-black text-neutral-300">♾ Survie</div>
          )}
        </div>
        <div aria-label={`${strikes} erreur${strikes > 1 ? 's' : ''} sur 3`} className="flex items-center gap-1 rounded-xl bg-surface-2 px-3 text-2xl">
          {[0, 1, 2].map((i) => (
            <span key={i} className={i < strikes ? 'text-red-500' : 'text-neutral-600'}>
              ✗
            </span>
          ))}
        </div>
      </div>
      <p className={`min-h-6 text-center text-base font-bold ${phase === 'net' ? 'text-accent' : 'text-neutral-300'}`}>
        {phase === 'net' ? (other ? '✓ Mat ! (autre mat que la ligne prévue)' : '✓ Mat !') : phase === 'over' ? '' : 'Trouve le mat'}
      </p>
      {phase !== 'over' && (
        <div className="flex justify-center">
          <div className="boardbox md:w-[min(60vh,560px)]">
            {phase === 'net' && netFen && view ? (
              <Board
                fen={netFen}
                orientation={net!.mated === 'w' ? 'b' : 'w'}
                interactive={false}
                arrows={view.arrows}
                markSquares={view.marks}
              />
            ) : (
              puzzle && <PuzzlePlayer key={puzzle.id} puzzle={puzzle} onComplete={onComplete} />
            )}
          </div>
        </div>
      )}
      {phase === 'net' && view && (
        <div className="px-3">
          <NetLegend principle={principle} view={view} />
        </div>
      )}
      {phase === 'over' && (
        <div className="px-3">
          <RunSummary score={score} stats={stats} newRecord={newRecord} onReplay={onReplay} onMenu={onMenu}>
            {missed.length > 0 && (
              <div className="space-y-1 text-left">
                <p className="text-sm font-semibold text-neutral-400">Mats manqués</p>
                {missed.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => analyse(p)}
                    className="flex w-full cursor-pointer items-center justify-between rounded-lg bg-surface-3 px-3 py-2 text-sm hover:bg-surface-3/70"
                  >
                    <span>Puzzle {p.id} · {p.rating}</span>
                    <span className="font-semibold text-accent">♞ Voir la solution</span>
                  </button>
                ))}
              </div>
            )}
          </RunSummary>
        </div>
      )}
    </div>
  )
}
