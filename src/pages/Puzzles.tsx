import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Chess } from 'chess.js'
import { Cta } from '../components/Cta'
import { PuzzlePlayer, type PuzzleData } from '../components/PuzzlePlayer'
import { applyRating, db, getRating } from '../lib/db'
import { loadPuzzles } from '../lib/puzzles'
import { displayThemes } from '../lib/puzzleThemes'
import { figurine } from '../lib/review'

type Phase = 'solving' | 'solved' | 'failed'

// Puzzle en cours, conservé d'une visite à l'autre (rechargement, aller-retour vers l'analyseur,
// changement d'onglet, PWA tuée par iOS) : quitter la page n'est pas un « passer » gratuit.
// localStorage plutôt que sessionStorage : iOS vide ce dernier en tuant la PWA.
const SESSION_KEY = 'chess-local-puzzle-session'

interface StoredSession {
  puzzle: PuzzleData
  phase: Phase
  ratingDelta: number | null
  scored: boolean
  failedStep: number | null
}

function readSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    const s = raw ? (JSON.parse(raw) as StoredSession) : null
    return s?.puzzle?.id && Array.isArray(s.puzzle.moves) ? s : null
  } catch {
    return null
  }
}

// Série en cours : les succès consécutifs les plus récents de l'historique, sans nouveau schéma.
async function currentStreak(): Promise<number> {
  return (await db.puzzleAttempts.orderBy('date').reverse().until((a) => !a.success).toArray()).length
}

export default function Puzzles() {
  const navigate = useNavigate()
  const location = useLocation()
  const [rating, setRating] = useState<number | null>(null)
  const [puzzle, setPuzzle] = useState<PuzzleData | null>(null)
  const [phase, setPhase] = useState<Phase>('solving')
  const [ratingDelta, setRatingDelta] = useState<number | null>(null)
  const [scored, setScored] = useState(false) // rating déjà appliqué (1er essai)
  const scoredRef = useRef(false) // même garde, hors du cycle de rendu : jamais deux écritures d'Elo
  const skippingRef = useRef(false) // « Passer » en cours : un double tap ne tire pas deux puzzles
  const [streak, setStreak] = useState(0)
  const [hint, setHint] = useState<string | null>(null)
  const [attemptKey, setAttemptKey] = useState(0)
  const [stepIndex, setStepIndex] = useState(0)
  const [failedStep, setFailedStep] = useState<number | null>(null) // coup attendu au moment de l'échec
  const [midFeedback, setMidFeedback] = useState(false)
  const [loadError, setLoadError] = useState(false)

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
    scoredRef.current = false
    setScored(false)
    setHint(null)
    setMidFeedback(false)
    setStepIndex(0)
    setFailedStep(null)
    setAttemptKey((k) => k + 1)
  }, [])

  // Tirage suivant ; un chargement de puzzles.json en échec donne l'état d'erreur, pas une pageerror.
  const goNext = useCallback(
    (currentRating: number) => pickPuzzle(currentRating).catch(() => setLoadError(true)),
    [pickPuzzle],
  )

  // Chargement : série depuis l'historique, puis puzzle conservé (tel quel) ou nouveau tirage.
  const init = useCallback(async () => {
    // Lecture synchrone AVANT tout await : l'effet de persistance ne doit rien pouvoir écraser.
    const saved = readSession()
    setLoadError(false)
    try {
      const r = await getRating('puzzle')
      setRating(r.value)
      setStreak(await currentStreak())
      if (saved) {
        setPuzzle(saved.puzzle)
        setPhase(saved.phase)
        setRatingDelta(saved.ratingDelta)
        scoredRef.current = saved.scored
        setScored(saved.scored)
        setFailedStep(saved.failedStep)
        setHint(null)
        setMidFeedback(false)
        setStepIndex(0)
        setAttemptKey((k) => k + 1)
        // Préchauffe la base en arrière-plan : « Suivant » ne doit pas payer le chargement des
        // 16 Mo sans retour visuel. Un échec ici est avalé, `goNext` le remontera proprement.
        void loadPuzzles().catch(() => {})
      } else {
        await pickPuzzle(r.value)
      }
    } catch {
      setLoadError(true)
    }
  }, [pickPuzzle])

  useEffect(() => {
    void init()
    // Retour depuis l'analyseur (`state.restore`) : le state ne doit pas survivre à un refresh.
    if (location.state) navigate('.', { replace: true, state: null })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Persiste le puzzle en cours. Jamais effacé : la prochaine visite le reprend.
  useEffect(() => {
    if (!puzzle) return
    const stored: StoredSession = { puzzle, phase, ratingDelta, scored, failedStep }
    try {
      localStorage.setItem(SESSION_KEY, JSON.stringify(stored))
    } catch {}
  }, [puzzle, phase, ratingDelta, scored, failedStep])

  // Note le puzzle (une seule fois) et renvoie le nouvel Elo, ou null s'il était déjà noté.
  async function score(success: boolean): Promise<number | null> {
    if (scoredRef.current || !puzzle || rating === null) return null
    scoredRef.current = true
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
    setStreak((s) => (success ? s + 1 : 0))
    return after
  }

  function handleComplete(success: boolean, step: number) {
    setHint(null)
    if (success) {
      setPhase('solved')
    } else {
      setPhase('failed')
      setFailedStep(step)
    }
    void score(success)
  }

  // « Passer » vaut un échec : un puzzle classé ne s'évite pas sans perdre de points.
  async function skip() {
    if (rating === null || skippingRef.current) return
    skippingRef.current = true
    try {
      const after = await score(false)
      await goNext(after ?? rating)
    } finally {
      skippingRef.current = false
    }
  }

  const themesLabel = useMemo(
    () => displayThemes(puzzle?.themes ?? []).join(', '), // motifs en français, méta exclus, 3 au plus
    [puzzle],
  )

  if (loadError) {
    return (
      <div className="mx-auto max-w-xl p-8 text-center">
        <p className="mb-1 font-semibold">Puzzles indisponibles</p>
        <p className="mb-4 text-sm text-neutral-400">Impossible de charger les puzzles. Vérifie ta connexion, puis réessaie.</p>
        <Cta onClick={() => void init()}>Réessayer</Cta>
      </div>
    )
  }

  if (!puzzle || rating === null) return <div className="p-8 text-neutral-400">Chargement…</div>

  const sideToPlay = puzzle.fen.split(' ')[1] === 'w' ? 'Noirs' : 'Blancs'
  const playerColor: 'w' | 'b' = puzzle.fen.split(' ')[1] === 'w' ? 'b' : 'w'

  // Ouvre l'analyse sur le puzzle : solution complète navigable, positionnée
  // sur la position clé (après le coup d'amorce) — le moteur y montre le
  // meilleur coup, c'est-à-dire la solution.
  function openInAnalysis() {
    if (!puzzle) return
    navigate('/analyse', {
      state: {
        fen: puzzle.fen,
        uci: puzzle.moves,
        viewIndex: 0,
        orientation: playerColor,
        label: `Puzzle ${puzzle.id} (${puzzle.rating})`,
        returnTo: '/puzzles',
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
          onStep={(s) => {
            setStepIndex(s)
            setHint(null)
            // Coup correct du joueur, puzzle pas fini : encouragement.
            setMidFeedback(s > 1 && s % 2 === 0)
          }}
          hintSquare={hint}
        />
      </div>

      <div className="flex w-full flex-col gap-3 px-1 pb-2 md:w-80 md:px-0 md:pb-0">
        <div className="rounded-lg bg-surface-2 p-4 text-center">
          <div className="flex items-center justify-center gap-4">
            <div>
              <div className="text-3xl font-bold">
                {rating}
                {ratingDelta !== null && (
                  <span className={`ml-2 text-lg ${ratingDelta >= 0 ? 'text-accent' : 'text-red-400'}`}>
                    {ratingDelta >= 0 ? '+' : ''}{ratingDelta}
                  </span>
                )}
              </div>
              <div className="text-sm text-neutral-400">Classement puzzles</div>
            </div>
            <div className={`text-center ${streak > 0 ? '' : 'opacity-30 grayscale'}`}>
              <div className="text-2xl">🔥</div>
              <div className="text-sm font-bold text-orange-400">{streak}</div>
            </div>
          </div>
        </div>

        <div className="rounded-lg bg-surface-2 p-4">
          {phase === 'solving' && midFeedback && (
            <p className="mb-2 rounded bg-accent/20 px-2 py-1 text-sm font-bold text-accent">✓ Trouvé ! Continue…</p>
          )}
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
              <p className="text-sm text-neutral-400">Le bon coup était {solutionSan(puzzle, failedStep ?? 1, playerColor)}. Tu peux réessayer sans enjeu.</p>
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
          {phase === 'solving' ? (
            <Cta variant="secondary" className="flex-1" onClick={() => void skip()}>
              Passer
            </Cta>
          ) : (
            <Cta className="flex-1" onClick={() => goNext(rating)}>
              Suivant
            </Cta>
          )}
        </div>

        {phase !== 'solving' && (
          <button
            onClick={openInAnalysis}
            className="cursor-pointer rounded-lg bg-surface-2 py-2.5 font-semibold text-neutral-200 hover:bg-surface-3"
          >
            ♞ Analyser avec Stockfish
          </button>
        )}

        <button
          onClick={() => navigate('/rush')}
          className="cursor-pointer rounded-lg bg-surface-2 py-2.5 font-semibold text-neutral-200 hover:bg-surface-3"
        >
          ⚡ Puzzle Rush
        </button>
      </div>
    </div>
  )
}

// Solution du coup raté en SAN figurines (promotion comprise), rejouée depuis la position du puzzle.
function solutionSan(puzzle: PuzzleData, step: number, color: 'w' | 'b'): string {
  const uci = puzzle.moves[step] ?? ''
  try {
    const c = new Chess(puzzle.fen)
    for (const u of puzzle.moves.slice(0, step)) c.move({ from: u.slice(0, 2), to: u.slice(2, 4), promotion: u[4] })
    return figurine(c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] }).san, color)
  } catch {
    return uci ? `${uci.slice(0, 2)}→${uci.slice(2, 4)}` : ''
  }
}
