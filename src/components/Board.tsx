import { useMemo, useState } from 'react'
import { Chess, type Square } from 'chess.js'
import { Chessboard } from 'react-chessboard'
import { useSettings, currentTheme } from '../store/settings'

export interface BoardArrow {
  startSquare: string
  endSquare: string
  color: string
}

interface BoardProps {
  fen: string
  orientation: 'w' | 'b'
  interactive: boolean
  // Retourne true si le coup est accepté. promotion en minuscule ('q','r','b','n').
  onMove?: (from: string, to: string, promotion?: string) => boolean
  lastMove?: { from: string; to: string } | null
  arrows?: BoardArrow[]
  // Le joueur ne peut bouger que cette couleur (undefined = les deux).
  movableColor?: 'w' | 'b'
}

export function Board({ fen, orientation, interactive, onMove, lastMove, arrows, movableColor }: BoardProps) {
  const { themeId, showLegalMoves } = useSettings()
  const theme = currentTheme(themeId)
  const [selected, setSelected] = useState<Square | null>(null)
  const [pendingPromotion, setPendingPromotion] = useState<{ from: string; to: string } | null>(null)

  const chess = useMemo(() => new Chess(fen), [fen])

  const legalTargets = useMemo(() => {
    if (!selected) return new Set<string>()
    return new Set(chess.moves({ square: selected, verbose: true }).map((m) => m.to))
  }, [chess, selected])

  const checkSquare = useMemo(() => {
    if (!chess.inCheck()) return null
    const color = chess.turn()
    for (const row of chess.board()) {
      for (const sq of row) {
        if (sq && sq.type === 'k' && sq.color === color) return sq.square
      }
    }
    return null
  }, [chess])

  function canMoveFrom(square: string): boolean {
    if (!interactive) return false
    const piece = chess.get(square as Square)
    if (!piece) return false
    if (piece.color !== chess.turn()) return false
    if (movableColor && piece.color !== movableColor) return false
    return true
  }

  function isPromotion(from: string, to: string): boolean {
    const piece = chess.get(from as Square)
    if (!piece || piece.type !== 'p') return false
    return (piece.color === 'w' && to[1] === '8') || (piece.color === 'b' && to[1] === '1')
  }

  function tryMove(from: string, to: string): boolean {
    if (!legalMove(from, to)) return false
    if (isPromotion(from, to)) {
      setPendingPromotion({ from, to })
      setSelected(null)
      return true
    }
    setSelected(null)
    return onMove?.(from, to) ?? false
  }

  function legalMove(from: string, to: string): boolean {
    return chess.moves({ square: from as Square, verbose: true }).some((m) => m.to === to)
  }

  function handleSquareClick({ square }: { piece: unknown; square: string }) {
    if (!interactive) return
    if (selected && legalTargets.has(square)) {
      tryMove(selected, square)
      return
    }
    setSelected(canMoveFrom(square) ? (square as Square) : null)
  }

  const squareStyles: Record<string, React.CSSProperties> = {}
  if (lastMove) {
    squareStyles[lastMove.from] = { backgroundColor: 'rgba(255, 255, 51, 0.4)' }
    squareStyles[lastMove.to] = { backgroundColor: 'rgba(255, 255, 51, 0.4)' }
  }
  if (checkSquare) {
    squareStyles[checkSquare] = {
      background: 'radial-gradient(circle, rgba(255,0,0,0.55) 20%, rgba(255,0,0,0.15) 70%)',
    }
  }
  if (selected) {
    squareStyles[selected] = { backgroundColor: 'rgba(255, 255, 51, 0.5)' }
    if (showLegalMoves) {
      for (const t of legalTargets) {
        const occupied = chess.get(t as Square)
        squareStyles[t] = {
          ...squareStyles[t],
          background: occupied
            ? `radial-gradient(circle, transparent 55%, rgba(0,0,0,0.25) 56%) ${squareStyles[t]?.backgroundColor ?? ''}`
            : `radial-gradient(circle, rgba(0,0,0,0.25) 25%, transparent 26%)`,
        }
      }
    }
  }

  const promoColor = pendingPromotion ? chess.turn() : 'w'

  return (
    <div className="relative select-none">
      <Chessboard
        options={{
          position: fen,
          boardOrientation: orientation === 'w' ? 'white' : 'black',
          allowDragging: interactive,
          canDragPiece: ({ square }) => canMoveFrom(square ?? ''),
          onPieceDrop: ({ sourceSquare, targetSquare }) => {
            if (!targetSquare) return false
            return tryMove(sourceSquare, targetSquare)
          },
          onSquareClick: handleSquareClick,
          squareStyles,
          arrows: arrows?.map((a) => ({ ...a })) ?? [],
          darkSquareStyle: { backgroundColor: theme.dark },
          lightSquareStyle: { backgroundColor: theme.light },
          animationDurationInMs: 150,
          boardStyle: { borderRadius: 4, overflow: 'hidden' },
        }}
      />
      {pendingPromotion && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/60 rounded">
          <div className="flex gap-2 rounded-lg bg-surface-2 p-3 shadow-xl">
            {(['q', 'r', 'b', 'n'] as const).map((p) => (
              <button
                key={p}
                className="h-16 w-16 cursor-pointer rounded bg-surface-3 text-4xl hover:bg-accent/30"
                onClick={() => {
                  const { from, to } = pendingPromotion
                  setPendingPromotion(null)
                  onMove?.(from, to, p)
                }}
              >
                {PROMO_GLYPHS[promoColor][p]}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const PROMO_GLYPHS: Record<'w' | 'b', Record<string, string>> = {
  w: { q: '♕', r: '♖', b: '♗', n: '♘' },
  b: { q: '♛', r: '♜', b: '♝', n: '♞' },
}
