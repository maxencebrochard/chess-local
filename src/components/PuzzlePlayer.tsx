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

interface PuzzlePlayerProps {
  puzzle: PuzzleData
  // Appelé à la fin : succès (toute la séquence) ou échec (premier coup faux).
  onComplete: (success: boolean) => void
  onFirstWrong?: () => void
  // Notifie l'avancement dans la séquence (index du prochain coup attendu).
  onStep?: (stepIndex: number) => void
  hintSquare?: string | null
}

export function PuzzlePlayer({ puzzle, onComplete, onFirstWrong, onStep, hintSquare }: PuzzlePlayerProps) {
  const { playSounds } = useSettings()
  const chessRef = useRef(new Chess(puzzle.fen))
  const [fen, setFen] = useState(puzzle.fen)
  const [stepIndex, setStepIndex] = useState(0) // index dans puzzle.moves
  const [lastMove, setLastMove] = useState<{ from: string; to: string } | null>(null)
  const [wrongOnce, setWrongOnce] = useState(false)
  const [done, setDone] = useState(false)
  const playerColor: 'w' | 'b' = new Chess(puzzle.fen).turn() === 'w' ? 'b' : 'w'

  // Reset complet quand le puzzle change.
  useEffect(() => {
    chessRef.current = new Chess(puzzle.fen)
    setFen(puzzle.fen)
    setStepIndex(0)
    setLastMove(null)
    setWrongOnce(false)
    setDone(false)
    const t = setTimeout(() => applyUci(puzzle.moves[0], 0), 500)
    return () => clearTimeout(t)
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
      c.undo()
      if (playSounds) sounds.fail()
      setWrongOnce(true)
      if (!wrongOnce) onFirstWrong?.()
      // Flash du mauvais coup puis retour.
      setFen(c.fen())
      onComplete(false)
      return false
    }
    setFen(c.fen())
    setLastMove({ from: move.from, to: move.to })
    const next = stepIndex + 1
    setStepIndex(next)
    onStep?.(next)
    if (next >= puzzle.moves.length || c.isCheckmate()) {
      if (playSounds) sounds.success()
      setDone(true)
      onComplete(true)
      return true
    }
    if (playSounds) (move.san.includes('x') ? sounds.capture : sounds.move)()
    setTimeout(() => applyUci(puzzle.moves[next], next), 350)
    return true
  }

  return (
    <Board
      fen={fen}
      orientation={playerColor}
      interactive={!done}
      movableColor={playerColor}
      onMove={handleMove}
      lastMove={hintSquare ? { from: hintSquare, to: hintSquare } : lastMove}
    />
  )
}
