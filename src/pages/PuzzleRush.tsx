import { useEffect, useMemo, useRef, useState } from 'react'
import { Cta } from '../components/Cta'
import { PuzzlePlayer, type PuzzleData } from '../components/PuzzlePlayer'
import { db } from '../lib/db'
import { loadPuzzles } from '../lib/puzzles'

type RushMode = '3min' | '5min' | 'survival'
const MODE_MS: Record<RushMode, number | null> = { '3min': 180_000, '5min': 300_000, survival: null }

// Difficulté croissante façon chess.com : démarre facile, monte avec le score.
function targetRating(score: number): number {
  return 500 + score * 55
}

function pickRushPuzzle(all: PuzzleData[], score: number, used: Set<string>): PuzzleData {
  const target = targetRating(score)
  let pool = all.filter((p) => Math.abs(p.rating - target) < 100 && !used.has(p.id))
  if (pool.length === 0) pool = all.filter((p) => !used.has(p.id))
  return pool[Math.floor(Math.random() * pool.length)]
}

export default function PuzzleRush() {
  const [mode, setMode] = useState<RushMode>('3min')
  const [state, setState] = useState<'menu' | 'running' | 'done'>('menu')
  const [score, setScore] = useState(0)
  const [strikes, setStrikes] = useState(0)
  const [timeLeft, setTimeLeft] = useState(0)
  const [puzzle, setPuzzle] = useState<PuzzleData | null>(null)
  const [best, setBest] = useState<Record<RushMode, number>>({ '3min': 0, '5min': 0, survival: 0 })
  const usedRef = useRef(new Set<string>())
  const scoreRef = useRef(0)
  const [allPuzzles, setAllPuzzles] = useState<PuzzleData[] | null>(null)

  useEffect(() => {
    void loadPuzzles().then(setAllPuzzles)
  }, [])

  useEffect(() => {
    void (async () => {
      const scores = await db.rushScores.toArray()
      const b = { '3min': 0, '5min': 0, survival: 0 } as Record<RushMode, number>
      for (const s of scores) b[s.mode] = Math.max(b[s.mode], s.score)
      setBest(b)
    })()
  }, [state])

  useEffect(() => {
    if (state !== 'running' || MODE_MS[mode] === null) return
    const interval = setInterval(() => {
      setTimeLeft((t) => {
        if (t <= 1000) {
          finish()
          return 0
        }
        return t - 1000
      })
    }, 1000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, mode])

  function start(m: RushMode) {
    if (!allPuzzles) return
    setMode(m)
    usedRef.current = new Set()
    scoreRef.current = 0
    setScore(0)
    setStrikes(0)
    setTimeLeft(MODE_MS[m] ?? 0)
    setPuzzle(pickRushPuzzle(allPuzzles, 0, usedRef.current))
    setState('running')
  }

  function finish() {
    setState((s) => {
      if (s !== 'running') return s
      void db.rushScores.add({ mode, score: scoreRef.current, date: Date.now() })
      return 'done'
    })
  }

  function handleComplete(success: boolean) {
    if (state !== 'running' || !puzzle || !allPuzzles) return
    usedRef.current.add(puzzle.id)
    if (success) {
      scoreRef.current += 1
      setScore(scoreRef.current)
      setTimeout(() => setPuzzle(pickRushPuzzle(allPuzzles, scoreRef.current, usedRef.current)), 400)
    } else {
      setStrikes((k) => {
        const next = k + 1
        if (next >= 3) {
          setTimeout(finish, 300)
        } else {
          setTimeout(() => setPuzzle(pickRushPuzzle(allPuzzles, scoreRef.current, usedRef.current)), 400)
        }
        return next
      })
    }
  }

  const clockText = useMemo(() => {
    const s = Math.ceil(timeLeft / 1000)
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  }, [timeLeft])

  if (state === 'menu') {
    return (
      <div className="mx-auto max-w-xl p-8">
        <h1 className="mb-2 text-2xl font-bold">⚡ Puzzle Rush</h1>
        <p className="mb-6 text-neutral-400">
          Enchaîne un maximum de puzzles. Trois erreurs et c'est fini. La difficulté monte avec ton score.
        </p>
        <div className="space-y-3">
          {(['3min', '5min', 'survival'] as RushMode[]).map((m) => (
            <button
              key={m}
              onClick={() => start(m)}
              disabled={!allPuzzles}
              className="flex w-full cursor-pointer items-center justify-between rounded-lg bg-surface-2 p-4 hover:bg-surface-3 disabled:cursor-default disabled:opacity-50"
            >
              <span className="text-lg font-semibold">
                {m === '3min' ? '⏱ 3 minutes' : m === '5min' ? '⏱ 5 minutes' : '♾ Survie'}
              </span>
              <span className="text-sm text-neutral-400">Record : {best[m]}</span>
            </button>
          ))}
        </div>
      </div>
    )
  }

  if (state === 'done') {
    return (
      <div className="mx-auto max-w-xl p-8 text-center">
        <h1 className="mb-2 text-3xl font-bold">{score >= best[mode] && score > 0 ? '🏆 Nouveau record !' : 'Terminé'}</h1>
        <p className="mb-1 text-6xl font-black text-accent">{score}</p>
        <p className="mb-6 text-neutral-400">puzzles résolus · record {Math.max(best[mode], score)}</p>
        <div className="flex justify-center gap-3">
          <Cta onClick={() => start(mode)}>Rejouer</Cta>
          <Cta variant="secondary" onClick={() => setState('menu')}>
            Menu
          </Cta>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col items-center justify-start gap-3 p-2 md:flex-row md:justify-center md:gap-6 md:p-4">
      <div className="boardbox">
        {puzzle && <PuzzlePlayer key={puzzle.id} puzzle={puzzle} onComplete={handleComplete} />}
      </div>
      <div className="flex w-full flex-row gap-2 px-1 pb-2 md:w-64 md:flex-col md:gap-3 md:px-0 md:pb-0">
        {MODE_MS[mode] !== null && (
          <div className={`flex-1 rounded-lg p-2 text-center font-mono text-2xl font-bold md:flex-none md:p-4 md:text-4xl ${timeLeft < 30_000 ? 'bg-red-900/60 text-red-200' : 'bg-surface-2'}`}>
            {clockText}
          </div>
        )}
        <div className="flex-1 rounded-lg bg-surface-2 p-2 text-center md:flex-none md:p-4">
          <div className="text-2xl font-black text-accent md:text-5xl">{score}</div>
          <div className="text-xs text-neutral-400 md:text-sm">résolus</div>
        </div>
        <div className="flex flex-1 items-center justify-center rounded-lg bg-surface-2 p-2 text-center text-xl tracking-widest md:flex-none md:p-4 md:text-2xl">
          <span>
            {[0, 1, 2].map((i) => (
              <span key={i} className={i < strikes ? 'text-red-500' : 'text-neutral-600'}>
                ✗
              </span>
            ))}
          </span>
        </div>
        <button onClick={finish} className="cursor-pointer rounded bg-surface-3 px-3 py-2 font-semibold hover:bg-red-900">
          <span className="md:hidden">✕</span>
          <span className="hidden md:inline">Arrêter</span>
        </button>
      </div>
    </div>
  )
}
