import { defaultPieces } from 'react-chessboard'
import { DEFAULT_PIECE_SET, isPieceSet, pieceUrl } from '../lib/pieces'

// Une pièce du jeu choisi, à la taille de son conteneur. L'image ne capte aucun geste
// (pointer-events: none) : pas de menu « Enregistrer l'image » d'iOS sur appui long, et le
// toucher arrive à la case ou à la pièce de react-chessboard en dessous.
export function PieceIcon({ set, code }: { set: string; code: string }) {
  if (set === 'classique') return defaultPieces[code]?.() ?? null
  return (
    <img
      src={pieceUrl(isPieceSet(set) ? set : DEFAULT_PIECE_SET, code)}
      alt=""
      draggable={false}
      style={{ width: '100%', height: '100%', display: 'block', pointerEvents: 'none', userSelect: 'none', WebkitTouchCallout: 'none' }}
    />
  )
}
