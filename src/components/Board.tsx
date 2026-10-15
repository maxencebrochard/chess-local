import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Chess, type Move, type Square } from 'chess.js'
import { Chessboard, defaultPieces, type PieceRenderObject } from 'react-chessboard'
import { useSettings, currentTheme } from '../store/settings'
import { ClassIcon } from './ClassIcon'
import { ATTACK_RED } from './AttackLegend'
import { attackCounts } from '../lib/kingAttack'
import { PieceIcon } from './PieceIcon'
import { DEFAULT_PIECE_SET, PIECE_CODES, isPieceSet, preloadPieceSet } from '../lib/pieces'
import { playMoveSound, sounds } from '../lib/sounds'
import { premoveTargets } from '../lib/premove'
import type { MoveClass } from '../lib/review'

export interface BoardArrow {
  startSquare: string
  endSquare: string
  color: string
}

interface BoardProps {
  fen: string
  orientation: 'w' | 'b'
  interactive: boolean
  // Opt-in du propriétaire : partie active au direct, avec un camp joueur explicite.
  allowPremove?: boolean
  // Retourne true si le coup est accepté. promotion en minuscule ('q','r','b','n').
  // Le dernier argument signale l'exécution d'un prémouvement aux propriétaires de pendule.
  onMove?: (from: string, to: string, promotion?: string, premove?: boolean) => boolean
  lastMove?: { from: string; to: string } | null
  arrows?: BoardArrow[]
  // Le joueur ne peut bouger que cette couleur (undefined = les deux).
  movableColor?: 'w' | 'b'
  // Pastille de classification affichée sur une case (coin haut-droit), façon chess.com.
  badge?: { square: string; cls: MoveClass } | null
  // Teintes de cases supplémentaires (ex : case du coup fautif en rouge).
  markSquares?: Record<string, string>
  // Calque « Compte les attaquants » : cadre sur la zone de chaque roi, rouge quand les attaquants
  // dépassent les défenseurs. Les comptes s'affichent sous l'échiquier (AttackLegend).
  showAttackers?: boolean
  // Diagramme : aucun son quand la position change.
  silent?: boolean
}

export function Board({ fen, orientation, interactive, onMove, lastMove, arrows, movableColor, badge, markSquares, showAttackers, silent, allowPremove = false }: BoardProps) {
  const { themeId, showLegalMoves, premoves, pieceSet: storedSet } = useSettings()
  // Un jeu inconnu (localStorage abîmé) retombe sur le défaut plutôt que sur des images 404.
  const pieceSet = isPieceSet(storedSet) ? storedSet : DEFAULT_PIECE_SET
  const theme = currentTheme(themeId)
  const [selected, setSelected] = useState<Square | null>(null)
  const [pendingPromotion, setPendingPromotion] = useState<{ from: string; to: string } | null>(null)
  const [drag, setDrag] = useState<{ from: string; target: string | null; touch: boolean; lift: number } | null>(null)
  const [premove, setPremove] = useState<{ from: string; to: string; fen: string; color: 'w' | 'b' } | null>(null)
  const queued = useRef(premove)
  const premoveSound = useRef(false)
  const touchInput = useRef(false)
  const root = useRef<HTMLDivElement>(null)
  const contact = useRef({ x: 0, y: 0 })
  // Identifiant DOM propre à chaque échiquier : react-chessboard retrouve ses cases par
  // getElementById (fin d'un tap tactile). Avec l'id par défaut partagé, un second échiquier
  // monté (calque par-dessus un exercice) testait le tap contre les cases du premier.
  const boardId = `chessboard-${useId().replace(/[^a-zA-Z0-9]/g, '')}`

  const chess = useMemo(() => new Chess(fen), [fen])
  const premoveEnabled = allowPremove && premoves && !!movableColor && !chess.isGameOver()
  const preparing = premoveEnabled && chess.turn() !== movableColor
  const zones = useMemo(() => (showAttackers ? attackCounts(fen) : null), [fen, showAttackers])

  useEffect(() => preloadPieceSet(pieceSet), [pieceSet])

  // Son du coup, joué par l'échiquier lui-même : toute page dont la position avance d'un coup
  // sonne comme chess.com (puzzle, exercice, navigation dans l'analyse...). Restent muets : un saut
  // (nouveau puzzle, chargement, plusieurs coups d'un coup), un retour en arrière (coup faux repris)
  // et, seulement si `lastMove` est fourni, un coup différent de celui-ci (`null` rend le coup
  // muet aussi : coup faux affiché en rouge, que suit le son d'échec).
  // `silent` : la page joue ses sons elle-même, ou affiche un saut de position
  // (réessayer de l'analyse) ; une position vue sous `silent` ne sert jamais de point de départ,
  // la sortie du mode est donc muette elle aussi.
  // Un coup moins de 60 ms après le précédent reste muet, tous échiquiers confondus : deux
  // échiquiers montés sur le même coup ou un défilement rapide ne doivent pas empiler les sons.
  // Exception : le prémouvement exécuté doit sonner même juste après la réponse adverse.
  const prevFen = useRef<string | null>(null)
  const me = movableColor ?? orientation
  const lastFrom = lastMove?.from
  const lastTo = lastMove?.to
  const lastMoveGiven = lastMove !== undefined
  useEffect(() => {
    const executedPremove = premoveSound.current
    premoveSound.current = false
    const prev = prevFen.current
    prevFen.current = silent ? null : fen
    if (silent || prev === null || prev === fen) return
    const move = oneMoveBetween(prev, fen)
    if (!move) return
    if (lastMoveGiven && (move.from !== lastFrom || move.to !== lastTo)) return
    const now = performance.now()
    if (!executedPremove && now - lastBoardSoundAt < 60) return
    lastBoardSoundAt = now
    playMoveSound(move, move.color !== me)
    // Fen et `silent` seuls déclenchent : un changement de surlignage seul n'est pas un coup.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fen, silent])

  function clearPremove() {
    queued.current = null
    setPremove(null)
  }

  useEffect(() => {
    const planned = queued.current
    if (!planned) return
    if (!premoveEnabled || planned.color !== movableColor) {
      clearPremove()
      return
    }
    if (fen === planned.fen) return
    // Une seule réponse adverse, pas un retour arrière ni une nouvelle position.
    if (!oneMoveBetween(planned.fen, fen) || chess.turn() !== planned.color) {
      clearPremove()
      return
    }
    if (!interactive) return
    // Consommer avant le callback : aucun double coup sous StrictMode ou lors d'un rerendu.
    clearPremove()
    const move = chess.moves({ square: planned.from as Square, verbose: true })
      .find((m) => m.to === planned.to && (!m.promotion || m.promotion === 'q'))
    if (move) {
      premoveSound.current = !silent
      if (!onMove?.(move.from, move.to, move.promotion, true)) premoveSound.current = false
    }
  }, [fen, chess, premove, premoveEnabled, movableColor, interactive, onMove, silent])

  useEffect(() => {
    setSelected(null)
    setPendingPromotion(null)
    setDrag(null)
  }, [fen, interactive, allowPremove])

  const legalTargets = useMemo(() => {
    if (!selected) return new Set<string>()
    return preparing ? premoveTargets(chess, selected)
      : new Set(chess.moves({ square: selected, verbose: true }).map((m) => m.to))
  }, [chess, selected, preparing])

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
    if (!interactive && !preparing) return false
    const piece = chess.get(square as Square)
    if (!piece) return false
    if (!preparing && piece.color !== chess.turn()) return false
    if (movableColor && piece.color !== movableColor) return false
    return true
  }

  function isPromotion(from: string, to: string): boolean {
    const piece = chess.get(from as Square)
    if (!piece || piece.type !== 'p') return false
    return (piece.color === 'w' && to[1] === '8') || (piece.color === 'b' && to[1] === '1')
  }

  function tryMove(from: string, to: string): boolean {
    if (!canMoveFrom(from)) return false
    if (preparing) {
      if (!premoveTargets(chess, from as Square).has(to)) return false
      const planned = { from, to, fen, color: movableColor! }
      queued.current = planned
      setPremove(planned)
      setSelected(null)
      return true
    }
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

  function returnPiece(from: string) {
    // Anime la vraie pièce source après le retrait du clone, sans copie de position ni minuterie.
    const piece = root.current?.querySelector<HTMLElement>(`[data-square="${from}"] .board-piece`)
    if (!piece || matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const r = piece.getBoundingClientRect()
    const dx = contact.current.x - r.x - r.width / 2
    const dy = contact.current.y - r.y - r.height / 2 - (touchInput.current ? r.height * .85 : 0)
    piece.animate([
      { transform: `translate(${dx}px, ${dy}px) scale(${touchInput.current ? 1.7 : 1.2})`, zIndex: 20 },
      { transform: 'none', zIndex: 20 },
    ], { duration: 120, easing: 'ease-out' })
  }

  function handleSquareClick({ square }: { piece: unknown; square: string }) {
    if (!interactive && !preparing) return
    if (queued.current) { clearPremove(); setSelected(null); return }
    if (selected === square) {
      setSelected(null) // re-tap : désélection
      return
    }
    if (canMoveFrom(square)) {
      setSelected(square as Square)
      return
    }
    if (selected && legalTargets.has(square)) {
      tryMove(selected, square)
      return
    }
    setSelected(canMoveFrom(square) ? (square as Square) : null)
  }

  // Teintes en `backgroundColor`, motifs (échec, pastille, anneau) en `backgroundImage`, jamais le
  // raccourci `background` : quand React le retire, il vide aussi `backgroundColor` sans le
  // reposer, et la teinte du dernier coup disparaissait après une désélection.
  const squareStyles: Record<string, React.CSSProperties> = {}
  if (markSquares) {
    for (const [sq, color] of Object.entries(markSquares)) {
      squareStyles[sq] = { backgroundColor: color }
    }
  }
  if (lastMove) {
    squareStyles[lastMove.from] = { backgroundColor: 'rgba(255, 255, 51, 0.4)' }
    squareStyles[lastMove.to] = { backgroundColor: 'rgba(255, 255, 51, 0.4)' }
  }
  if (checkSquare) {
    squareStyles[checkSquare] = {
      ...squareStyles[checkSquare],
      backgroundImage: 'radial-gradient(circle, rgba(255,0,0,0.55) 20%, rgba(255,0,0,0.15) 70%)',
    }
  }
  if (selected) {
    squareStyles[selected] = { backgroundColor: 'rgba(255, 255, 51, 0.5)' }
    if (showLegalMoves) {
      for (const t of legalTargets) {
        // Anneau sur une pièce à prendre, pastille sur une case vide, par-dessus la teinte éventuelle.
        squareStyles[t] = {
          ...squareStyles[t],
          backgroundImage: chess.get(t as Square)
            ? 'radial-gradient(circle, transparent 50%, rgba(0,0,0,0.34) 51%)'
            : 'radial-gradient(circle, rgba(0,0,0,0.34) 22%, transparent 23%)',
        }
      }
    }
  }

  if (premove && premoveEnabled) {
    squareStyles[premove.from] = { backgroundColor: 'rgba(220, 50, 50, 0.65)' }
    squareStyles[premove.to] = { backgroundColor: 'rgba(220, 50, 50, 0.65)' }
  }

  const promoColor = pendingPromotion ? chess.turn() : 'w'

  return (
    <div ref={root} tabIndex={-1} className="relative select-none" data-board=""
      onPointerDownCapture={(e) => {
        root.current?.focus({ preventScroll: true })
        touchInput.current = e.pointerType === 'touch'
        contact.current = { x: e.clientX, y: e.clientY }
      }}
      onPointerMoveCapture={(e) => { contact.current = { x: e.clientX, y: e.clientY } }}
      onPointerCancelCapture={() => { setDrag(null); setSelected(null) }}
      onKeyDownCapture={(e) => { if (e.key === 'Escape') { clearPremove(); setDrag(null); setSelected(null) } }}
    >
      <Chessboard
        options={{
          id: boardId,
          position: fen,
          boardOrientation: orientation === 'w' ? 'white' : 'black',
          allowDragging: interactive || preparing,
          canDragPiece: ({ square }) => canMoveFrom(square ?? ''),
          onPieceDrag: ({ square }) => {
            if (!square) return
            clearPremove()
            setSelected(square as Square)
            setDrag({ from: square, target: square, touch: touchInput.current, lift: (root.current?.clientWidth ?? 0) / 8 * .85 })
          },
          onMouseOverSquare: ({ square }) => setDrag((d) => d ? { ...d, target: square } : null),
          onMouseOutSquare: ({ square }) => setDrag((d) => d?.target === square ? { ...d, target: null } : d),
          onPieceDrop: ({ sourceSquare, targetSquare }) => {
            setDrag(null)
            setSelected(null)
            if (!targetSquare) { returnPiece(sourceSquare); return false }
            if (preparing) {
              if (!tryMove(sourceSquare, targetSquare)) {
                if (targetSquare !== sourceSquare && canMoveFrom(sourceSquare)) sounds.illegal()
                returnPiece(sourceSquare)
              }
              // La position reste inchangée : ne pas marquer la destination comme déjà déplacée.
              return false
            }
            // Pièce jouable lâchée sur une case interdite : son « coup illégal » (pas pour un
            // lâcher sur sa propre case, qui annule simplement le geste).
            if (targetSquare !== sourceSquare && canMoveFrom(sourceSquare) && !legalMove(sourceSquare, targetSquare)) {
              sounds.illegal()
              returnPiece(sourceSquare)
              return false
            }
            const accepted = tryMove(sourceSquare, targetSquare)
            if (!accepted) returnPiece(sourceSquare)
            return accepted
          },
          onSquareClick: handleSquareClick,
          squareStyles,
          pieces: piecesFor(pieceSet),
          arrows: arrows?.map((a) => ({ ...a })) ?? [],
          darkSquareStyle: { backgroundColor: theme.dark },
          lightSquareStyle: { backgroundColor: theme.light },
          // Les coordonnées sont peintes par-dessus la pièce, hors de sa zone de saisie : un doigt
          // posé sur le chiffre ou la lettre doit traverser et saisir la pièce (la lib fusionne
          // ces styles avec ses défauts, la couleur et la taille sont conservées).
          lightSquareNotationStyle: { pointerEvents: 'none' },
          darkSquareNotationStyle: { pointerEvents: 'none' },
          dropSquareStyle: { boxShadow: drag?.touch ? 'none' : 'inset 0 0 0 3px rgba(255,255,255,0.65)' },
          // Décaler le dessin, pas le rectangle mesuré par dnd-kit : son recentrage annulerait le décalage.
          draggingPieceStyle: { transform: drag?.touch ? 'scale(1.7)' : 'scale(1.2)', '--piece-lift': drag?.touch ? `-${drag.lift / 1.7}px` : '0px', filter: 'drop-shadow(0 3px 2px rgb(0 0 0 / 0.18))' } as React.CSSProperties,
          draggingPieceGhostStyle: { opacity: 0 },
          animationDurationInMs: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 120,
          dragActivationDistance: 1,
          boardStyle: { borderRadius: 4, overflow: 'hidden' },
        }}
      />
      {drag?.touch && drag.target && (
        <div data-testid="drag-target" aria-hidden="true" className="board-drag-target"
          style={{ ...zoneRect([drag.target], orientation), width: '25%', height: '25%', transform: 'translate(-25%, -25%)' }} />
      )}
      {zones &&
        (['w', 'b'] as const).map((side) => {
          const z = zones[side]
          const over = z.attackers.length > z.defenders.length
          return (
            <div
              key={side}
              data-testid="king-zone"
              data-side={side}
              data-over={over ? '1' : '0'}
              aria-hidden="true"
              className="pointer-events-none absolute z-[5] rounded-md border-2"
              style={{
                ...zoneRect(z.zone, orientation),
                borderColor: over ? ATTACK_RED : 'rgba(255,255,255,0.55)',
                backgroundColor: over ? 'rgba(255,119,105,0.14)' : 'transparent',
              }}
            />
          )
        })}
      {badge && badge.square.length === 2 && (
        <div
          className="pointer-events-none absolute z-10"
          style={badgePosition(badge.square, orientation)}
        >
          <ClassIcon cls={badge.cls} size={22} />
        </div>
      )}
      {pendingPromotion && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/60 rounded">
          <div className="flex gap-2 rounded-lg bg-surface-2 p-3 shadow-xl">
            {(['q', 'r', 'b', 'n'] as const).map((p) => (
              <button
                key={p}
                className="h-16 w-16 cursor-pointer rounded bg-surface-3 p-1 hover:bg-accent/30"
                aria-label={PROMO_LABELS[p]}
                onClick={() => {
                  const { from, to } = pendingPromotion
                  setPendingPromotion(null)
                  onMove?.(from, to, p)
                }}
              >
                <PieceIcon set={pieceSet} code={`${promoColor}${p.toUpperCase()}`} />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const PROMO_LABELS: Record<string, string> = { q: 'Dame', r: 'Tour', b: 'Fou', n: 'Cavalier' }

// Horodatage du dernier son de coup joué par un échiquier (anti-empilement, voir l'effet ci-dessus).
let lastBoardSoundAt = 0

// Rendus de pièces par jeu, construits une fois : un objet stable évite de re-rendre les 32 pièces.
const piecesCache = new Map<string, PieceRenderObject>()
function piecesFor(set: string): PieceRenderObject {
  let pieces = piecesCache.get(set)
  if (!pieces) {
    pieces = {}
    for (const code of PIECE_CODES) {
      const Classic = defaultPieces[code]
      pieces[code] = (props) => <div className="board-piece">{set === 'classique' ? <Classic {...props} /> : <PieceIcon set={set} code={code} />}</div>
    }
    piecesCache.set(set, pieces)
  }
  return pieces
}

// Le coup légal qui mène de `from` à `to` (placement et trait), ou null.
function oneMoveBetween(from: string, to: string): Move | null {
  let c: Chess
  try {
    c = new Chess(from)
  } catch {
    return null
  }
  const target = to.split(' ').slice(0, 2).join(' ')
  for (const m of c.moves({ verbose: true })) {
    if (m.after.split(' ').slice(0, 2).join(' ') === target) return m
  }
  return null
}

// Rectangle couvrant les cases de la zone (toujours un bloc 3x3), en % de l'échiquier, selon
// l'orientation. Le cadre suit le bord des cases ; la teinte légère du surnombre laisse les pièces lisibles.
function zoneRect(zone: string[], orientation: 'w' | 'b'): React.CSSProperties {
  const files = zone.map((s) => s.charCodeAt(0) - 97)
  const ranks = zone.map((s) => +s[1] - 1)
  const fMin = Math.min(...files)
  const fMax = Math.max(...files)
  const rMin = Math.min(...ranks)
  const rMax = Math.max(...ranks)
  const left = orientation === 'w' ? fMin : 7 - fMax
  const top = orientation === 'w' ? 7 - rMax : rMin
  return {
    left: `${left * 12.5}%`,
    top: `${top * 12.5}%`,
    width: `${(fMax - fMin + 1) * 12.5}%`,
    height: `${(rMax - rMin + 1) * 12.5}%`,
  }
}

// Coin haut-droit de la case, en % de l'échiquier, selon l'orientation.
// Au bord droit visuel, rentrer la pastille pour éviter un débordement horizontal sur mobile.
function badgePosition(square: string, orientation: 'w' | 'b'): React.CSSProperties {
  let file = square.charCodeAt(0) - 97 // a=0
  let rankFromTop = 8 - +square[1]
  if (orientation === 'b') {
    file = 7 - file
    rankFromTop = 7 - rankFromTop
  }
  return {
    left: `${(file + 1) * 12.5}%`,
    top: `${rankFromTop * 12.5}%`,
    transform: file === 7 ? 'translate(-100%, -40%)' : 'translate(-60%, -40%)',
  }
}
