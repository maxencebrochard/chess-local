import { defaultPieces } from 'react-chessboard'
import { DEFAULT_PIECE_SET, isPieceSet, pieceUrl } from '../lib/pieces'
import centers from '../data/pieceCenters.json'

// Une pièce du jeu choisi, à la taille de son conteneur. L'image ne capte aucun geste
// (pointer-events: none) : pas de menu « Enregistrer l'image » d'iOS sur appui long, et le
// toucher arrive à la case ou à la pièce de react-chessboard en dessous.
export function PieceIcon({ set, code }: { set: string; code: string }) {
  const selected = isPieceSet(set) ? set : DEFAULT_PIECE_SET
  // Marges mesurées hors ligne : les silhouettes restent centrées sans altérer les SVG sous licence.
  const [x, y] = (centers as Record<string, number[]>)[`${selected}/${code}`] ?? [0, 0]
  const transform = `translate(${x}%, ${y}%)`
  if (selected === 'classique') return defaultPieces[code]?.({ svgStyle: { display: 'block', transform } }) ?? null
  return (
    <img
      src={pieceUrl(selected, code)}
      alt=""
      draggable={false}
      style={{ width: '100%', height: '100%', display: 'block', transform, pointerEvents: 'none', userSelect: 'none', WebkitTouchCallout: 'none' }}
    />
  )
}
