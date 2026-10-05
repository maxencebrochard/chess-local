// Joue un puzzle lichess : fen = position avant le coup adverse d'amorce,
// moves[0] = coup adverse joué automatiquement, puis alternance joueur/adverse.
import { useEffect, useRef, useState } from 'react'
import { Chess } from 'chess.js'
import { Board } from './Board'
import { sounds } from '../lib/sounds'
import { useSettings } from '../store/settings'

export interface PuzzleData {
  id: string
  fen: string
  moves: string[]
  rating: number
  themes: string[]
}

// Le coup faux reste affiché (cases en rouge) ce temps-là, puis la position revient.
// Exporté : le Rush cale le changement de puzzle sur la fin du flash.
export const FAIL_FLASH_MS = 600
const WRONG_SQUARE = 'rgba(239, 68, 68, 0.75)'

interface PuzzlePlayerProps {
  puzzle: PuzzleData
  // Appelé une seule fois par puzzle, dès le verdict : succès (toute la séquence) ou échec
  // (premier coup faux, l'échiquier est alors verrouillé). `step` est l'index dans
  // `puzzle.moves` du coup attendu à ce moment : la solution du coup raté. `fen` : position
  // réellement atteinte (sur un succès, elle peut différer de la solution : autre mat accepté).
  onComplete: (success: boolean, step: number, fen: string) => void
  // Notifie l'avancement dans la séquence (index du prochain coup attendu).
  onStep?: (stepIndex: number) => void
  hintSquare?: string | null
}

export function PuzzlePlayer({ puzzle, onComplete, onStep, hintSquare }: PuzzlePlayerProps) {
  const { playSounds } = useSettings()
  const chessRef = useRef(new Chess(puzzle.fen))
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [fen, setFen] = useState(puzzle.fen)
  const [stepIndex, setStepIndex] = useState(0) // index dans puzzle.moves
  const [lastMove, setLastMove] = useState<{ from: string; to: string } | null>(null)
  const [wrongMove, setWrongMove] = useState<{ from: string; to: string } | null>(null) // coup faux affiché
  const [done, setDone] = useState(false) // verdict rendu : échiquier verrouillé
  const playerColor: 'w' | 'b' = new Chess(puzzle.fen).turn() === 'w' ? 'b' : 'w'

  // Un seul timer en attente (amorce, réponse adverse, fin du flash), annulé au changement de
  // puzzle et au démontage : un puzzle remplacé ne joue ni son ni coup, et ne notifie rien.
  function later(fn: () => void, ms: number) {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      timerRef.current = null
      fn()
    }, ms)
  }

  // Reset complet quand le puzzle change.
  useEffect(() => {
    chessRef.current = new Chess(puzzle.fen)
    setFen(puzzle.fen)
    setStepIndex(0)
    setLastMove(null)
    setWrongMove(null)
    setDone(false)
    later(() => applyUci(puzzle.moves[0], 0), 500)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [puzzle.id])

  function applyUci(uci: string, currentStep: number) {
    const c = chessRef.current
    const move = c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
    if (playSounds) (move.san.includes('x') ? sounds.capture : sounds.move)()
    setFen(c.fen())
    setLastMove({ from: move.from, to: move.to })
    setStepIndex(currentStep + 1)
    onStep?.(currentStep + 1)
  }

  function handleMove(from: string, to: string, promotion?: string): boolean {
    if (done || stepIndex === 0 || stepIndex % 2 === 0) return false
    const c = chessRef.current
    const expected = puzzle.moves[stepIndex]
    let move
    try {
      move = c.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    const played = move.from + move.to + (move.promotion ?? '')
    // Tout mat immédiat compte comme correct (règle lichess).
    if (played !== expected && !c.isCheckmate()) {
      if (playSounds) sounds.fail()
      // Verdict immédiat et échiquier verrouillé : un seul coup faux par puzzle.
      setDone(true)
      onComplete(false, stepIndex, c.fen())
      // Le coup faux reste visible, cases en rouge, puis la position revient.
      setFen(c.fen())
      setWrongMove({ from: move.from, to: move.to })
      later(() => {
        c.undo()
        setFen(c.fen())
        setWrongMove(null)
      }, FAIL_FLASH_MS)
      return true
    }
    setFen(c.fen())
    setLastMove({ from: move.from, to: move.to })
    const next = stepIndex + 1
    setStepIndex(next)
    onStep?.(next)
    if (next >= puzzle.moves.length || c.isCheckmate()) {
      if (playSounds) sounds.success()
      setDone(true)
      onComplete(true, next, c.fen())
      return true
    }
    if (playSounds) (move.san.includes('x') ? sounds.capture : sounds.move)()
    later(() => applyUci(puzzle.moves[next], next), 350)
    return true
  }

  return (
    <Board
      fen={fen}
      orientation={playerColor}
      interactive={!done}
      movableColor={playerColor}
      onMove={handleMove}
      // Pendant le flash, pas de surlignage jaune : Board le peindrait par-dessus le rouge.
      lastMove={wrongMove ? null : hintSquare ? { from: hintSquare, to: hintSquare } : lastMove}
      markSquares={wrongMove ? { [wrongMove.from]: WRONG_SQUARE, [wrongMove.to]: WRONG_SQUARE } : undefined}
      badge={wrongMove ? { square: wrongMove.to, cls: 'blunder' } : null}
    />
  )
}
