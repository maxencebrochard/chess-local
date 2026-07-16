import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Cta } from '../components/Cta'
import { PuzzlePlayer, type PuzzleData } from '../components/PuzzlePlayer'
import { applyRating, db, getRating } from '../lib/db'
import { loadPuzzles } from '../lib/puzzles'

type Phase = 'solving' | 'solved' | 'failed'

export default function Puzzles() {
  const navigate = useNavigate()
  const [rating, setRating] = useState<number | null>(null)
  const [puzzle, setPuzzle] = useState<PuzzleData | null>(null)
  const [phase, setPhase] = useState<Phase>('solving')
  const [ratingDelta, setRatingDelta] = useState<number | null>(null)
  const [scored, setScored] = useState(false) // rating déjà appliqué (1er essai)
  const [streak, setStreak] = useState(0)
  const [hint, setHint] = useState<string | null>(null)
  const [attemptKey, setAttemptKey] = useState(0)
  const [stepIndex, setStepIndex] = useState(0)

  const pickPuzzle = useCallback(async (currentRating: number) => {
    const all = await loadPuzzles()
    const recent = new Set(
      (await db.puzzleAttempts.orderBy('date').reverse().limit(2000).toArray()).map((a) => a.puzzleId),
    )
    const candidates = all.filter(
      (p) => Math.abs(p.rating - currentRating) < 120 && !recent.has(p.id),
    )
    const pool = candidates.length > 0
      ? candidates
      : all.filter((p) => Math.abs(p.rating - currentRating) < 300)
    const chosen = pool[Math.floor(Math.random() * pool.length)] ?? all[0]
    setPuzzle(chosen)
    setPhase('solving')
    setRatingDelta(null)
    setScored(false)
    setHint(null)
    setAttemptKey((k) => k + 1)
  }, [])

  useEffect(() => {
    void (async () => {
      const r = await getRating('puzzle')
      setRating(r.value)
      await pickPuzzle(r.value)
    })()
  }, [pickPuzzle])

  async function score(success: boolean) {
    if (scored || !puzzle || rating === null) return
    setScored(true)
    const before = rating
    const after = await applyRating('puzzle', puzzle.rating, success ? 1 : 0)
    await db.puzzleAttempts.add({
      puzzleId: puzzle.id,
      date: Date.now(),
      success,
      puzzleRating: puzzle.rating,
      ratingAfter: after,
    })
    setRating(after)
    setRatingDelta(after - before)
    setStreak(success ? streak + 1 : 0)
  }

  function handleComplete(success: boolean) {
    if (success) {
      setPhase('solved')
      void score(true)
    } else {
      setPhase('failed')
      void score(false)
    }
  }

  const themesLabel = useMemo(
    () => puzzle?.themes.filter((t) => !['short', 'long', 'veryLong', 'oneMove'].includes(t)).slice(0, 4).join(', '),
    [puzzle],
  )

  if (!puzzle || rating === null) return <div className="p-8 text-neutral-400">Chargement…</div>

  const sideToPlay = puzzle.fen.split(' ')[1] === 'w' ? 'Noirs' : 'Blancs'
  const playerColor: 'w' | 'b' = puzzle.fen.split(' ')[1] === 'w' ? 'b' : 'w'

  // Ouvre l'analyse sur le puzzle : position initiale + séquence jouée,
  // pour pouvoir naviguer coup par coup dans la solution.
  function openInAnalysis() {
    if (!puzzle) return
    navigate('/analyse', {
      state: {
        fen: puzzle.fen,
        uci: puzzle.moves.slice(0, Math.max(stepIndex, 1)),
        orientation: playerColor,
        label: `Puzzle ${puzzle.id} (${puzzle.rating})`,
      },
    })
  }

  return (
    <div className="flex h-full flex-col items-center justify-start gap-3 p-2 md:flex-row md:justify-center md:gap-6 md:p-4">
      <div className="boardbox">
        <PuzzlePlayer
          key={`${puzzle.id}-${attemptKey}`}
          puzzle={puzzle}
          onComplete={handleComplete}
          onStep={(s) => { setStepIndex(s); setHint(null) }}
          hintSquare={hint}
        />
      </div>

      <div className="flex w-full flex-col gap-3 px-1 pb-2 md:w-80 md:px-0 md:pb-0">
        <div className="rounded-lg bg-surface-2 p-4 text-center">
          <div className="text-3xl font-bold">
            {rating}
            {ratingDelta !== null && (
              <span className={`ml-2 text-lg ${ratingDelta >= 0 ? 'text-accent' : 'text-red-400'}`}>
                {ratingDelta >= 0 ? '+' : ''}{ratingDelta}
              </span>
            )}
          </div>
          <div className="text-sm text-neutral-400">Classement puzzles</div>
          {streak > 1 && <div className="mt-1 text-sm text-orange-400">🔥 Série de {streak}</div>}
        </div>

        <div className="rounded-lg bg-surface-2 p-4">
          {phase === 'solving' && (
            <>
              <p className="mb-1 font-semibold">Trait aux {sideToPlay}</p>
              <p className="text-sm text-neutral-400">Trouve le meilleur coup.</p>
            </>
          )}
          {phase === 'solved' && (
            <>
              <p className="mb-1 font-semibold text-accent">✓ Résolu !</p>
              <p className="text-sm text-neutral-400">Puzzle {puzzle.id} · {puzzle.rating} · {themesLabel}</p>
            </>
          )}
          {phase === 'failed' && (
            <>
              <p className="mb-1 font-semibold text-red-400">✗ Raté</p>
              <p className="text-sm text-neutral-400">Le bon coup était {puzzle.moves.length > 1 ? formatUci(puzzle) : ''}. Tu peux réessayer sans enjeu.</p>
            </>
          )}
        </div>

        <div className="flex gap-2">
          {phase === 'solving' && (
            <button
              onClick={() => setHint(puzzle.moves[stepIndex % 2 === 1 ? stepIndex : stepIndex + 1]?.slice(0, 2) ?? null)}
              className="flex-1 cursor-pointer rounded bg-surface-3 py-2 font-semibold hover:bg-surface-3/70"
            >
              💡 Indice
            </button>
          )}
          {phase === 'failed' && (
            <button
              onClick={() => { setPhase('solving'); setHint(null); setAttemptKey((k) => k + 1) }}
              className="flex-1 cursor-pointer rounded bg-surface-3 py-2 font-semibold hover:bg-surface-3/70"
            >
              ↺ Réessayer
            </button>
          )}
          <Cta className="flex-1" onClick={() => void pickPuzzle(rating)}>
            {phase === 'solving' ? 'Passer' : 'Suivant'}
          </Cta>
        </div>

        {phase !== 'solving' && (
          <button
            onClick={openInAnalysis}
            className="cursor-pointer rounded-lg bg-surface-2 py-2.5 font-semibold text-neutral-200 hover:bg-surface-3"
          >
            ♞ Analyser avec Stockfish
          </button>
        )}
      </div>
    </div>
  )
}

function formatUci(puzzle: PuzzleData): string {
  const uci = puzzle.moves[1]
  return uci ? `${uci.slice(0, 2)}→${uci.slice(2, 4)}` : ''
}
