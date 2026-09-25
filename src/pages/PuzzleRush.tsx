import { useEffect, useMemo, useRef, useState } from 'react'
import { Cta } from '../components/Cta'
import { FAIL_FLASH_MS, PuzzlePlayer, type PuzzleData } from '../components/PuzzlePlayer'
import { db } from '../lib/db'
import { loadPuzzles } from '../lib/puzzles'

type RushMode = '3min' | '5min' | 'survival'
type RushState = 'menu' | 'running' | 'done'
const MODE_MS: Record<RushMode, number | null> = { '3min': 180_000, '5min': 300_000, survival: null }
const NEXT_DELAY_MS = 400 // après un succès ; après un échec c'est la durée du flash rouge
const NO_BEST: Record<RushMode, number> = { '3min': 0, '5min': 0, survival: 0 }

// Difficulté croissante façon chess.com : démarre facile, monte avec le score.
function targetRating(score: number): number {
  return 500 + score * 55
}

function pickRushPuzzle(all: PuzzleData[], score: number, used: Set<string>): PuzzleData | undefined {
  const target = targetRating(score)
  let pool = all.filter((p) => Math.abs(p.rating - target) < 100 && !used.has(p.id))
  if (pool.length === 0) pool = all.filter((p) => !used.has(p.id))
  return pool[Math.floor(Math.random() * pool.length)]
}

export default function PuzzleRush() {
  const [mode, setMode] = useState<RushMode>('3min')
  const [state, setState] = useState<RushState>('menu')
  const [score, setScore] = useState(0)
  const [strikes, setStrikes] = useState(0)
  const [timeLeft, setTimeLeft] = useState(0)
  const [puzzle, setPuzzle] = useState<PuzzleData | null>(null)
  const [best, setBest] = useState<Record<RushMode, number>>(NO_BEST)
  const [newRecord, setNewRecord] = useState(false)
  const [allPuzzles, setAllPuzzles] = useState<PuzzleData[] | null>(null)
  const [loadError, setLoadError] = useState(false)
  // Miroirs hors rendu : verdicts, chrono et démontage lisent l'état à l'instant T, sans passer
  // par un updater React (jamais d'effet de bord dans un updater : il peut être rejoué).
  const stateRef = useRef<RushState>('menu')
  const modeRef = useRef<RushMode>('3min')
  const usedRef = useRef(new Set<string>())
  const scoreRef = useRef(0)
  const strikesRef = useRef(0)
  const bestRef = useRef<Record<RushMode, number>>(NO_BEST)
  const endAtRef = useRef(0) // échéance du chrono (heure réelle)
  const nextTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function load() {
    setLoadError(false)
    loadPuzzles().then(setAllPuzzles).catch(() => setLoadError(true))
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    void (async () => {
      const scores = await db.rushScores.toArray()
      const b = { ...NO_BEST }
      for (const s of scores) b[s.mode] = Math.max(b[s.mode], s.score)
      // Jamais en dessous du miroir : un run vient peut-être d'y être ajouté avant son écriture.
      for (const m of Object.keys(b) as RushMode[]) b[m] = Math.max(b[m], bestRef.current[m])
      bestRef.current = b
      setBest(b)
    })()
  }, [state])

  // Chrono sur l'heure réelle : une échéance, pas un compte de ticks. iOS suspend le JS d'une
  // PWA en arrière-plan et un intervalle dérive sous charge : on recalcule au retour.
  useEffect(() => {
    if (state !== 'running' || MODE_MS[mode] === null) return
    const tick = () => {
      const left = Math.max(0, endAtRef.current - Date.now())
      setTimeLeft(Math.ceil(left / 1000) * 1000) // arrondi à la seconde : un rendu par seconde
      if (left === 0) finish()
    }
    tick()
    const interval = setInterval(tick, 250)
    document.addEventListener('visibilitychange', tick)
    return () => {
      clearInterval(interval)
      document.removeEventListener('visibilitychange', tick)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, mode])

  // Quitter la page en plein run (nav basse, lien) : le score est enregistré, pas perdu.
  useEffect(
    () => () => {
      closeRun()
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  function clearNextTimer() {
    if (nextTimerRef.current) clearTimeout(nextTimerRef.current)
    nextTimerRef.current = null
  }

  function start(m: RushMode) {
    if (!allPuzzles) return
    clearNextTimer()
    modeRef.current = m
    setMode(m)
    usedRef.current = new Set()
    scoreRef.current = 0
    strikesRef.current = 0
    setScore(0)
    setStrikes(0)
    setNewRecord(false)
    endAtRef.current = Date.now() + (MODE_MS[m] ?? 0)
    setTimeLeft(MODE_MS[m] ?? 0)
    setPuzzle(pickRushPuzzle(allPuzzles, 0, usedRef.current) ?? null)
    stateRef.current = 'running'
    setState('running')
  }

  // Clôt le run, une seule fois quelle que soit l'origine (3e erreur, chrono, Arrêter, démontage),
  // et enregistre le score. Renvoie true pour un nouveau record, null si aucun run ne tournait.
  function closeRun(): boolean | null {
    if (stateRef.current !== 'running') return null
    stateRef.current = 'done'
    clearNextTimer()
    const m = modeRef.current
    const s = scoreRef.current
    const record = s > bestRef.current[m]
    bestRef.current = { ...bestRef.current, [m]: Math.max(bestRef.current[m], s) }
    void db.rushScores.add({ mode: m, score: s, date: Date.now() })
    return record
  }

  function finish() {
    const record = closeRun()
    if (record === null) return
    setNewRecord(record)
    setState('done')
  }

  function scheduleNext(ms: number) {
    clearNextTimer()
    nextTimerRef.current = setTimeout(() => {
      nextTimerRef.current = null
      if (stateRef.current !== 'running' || !allPuzzles) return
      const next = pickRushPuzzle(allPuzzles, scoreRef.current, usedRef.current)
      if (next) setPuzzle(next)
      else finish() // plus aucun puzzle disponible
    }, ms)
  }

  function handleComplete(success: boolean) {
    if (stateRef.current !== 'running' || !puzzle || !allPuzzles) return
    if (usedRef.current.has(puzzle.id)) return // un seul verdict par puzzle
    usedRef.current.add(puzzle.id)
    if (success) {
      scoreRef.current += 1
      setScore(scoreRef.current)
      scheduleNext(NEXT_DELAY_MS)
      return
    }
    strikesRef.current += 1
    setStrikes(strikesRef.current)
    // Le temps du flash rouge du coup faux, puis fin du run ou puzzle suivant.
    if (strikesRef.current >= 3) {
      clearNextTimer()
      nextTimerRef.current = setTimeout(finish, FAIL_FLASH_MS)
    } else {
      scheduleNext(FAIL_FLASH_MS)
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
        {loadError && (
          <div className="mb-4 rounded-lg bg-surface-2 p-4 text-center">
            <p className="mb-3 text-sm text-neutral-400">Impossible de charger les puzzles. Vérifie ta connexion, puis réessaie.</p>
            <Cta onClick={load}>Réessayer</Cta>
          </div>
        )}
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
        <h1 className="mb-2 text-3xl font-bold">{newRecord ? '🏆 Nouveau record !' : 'Terminé'}</h1>
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
