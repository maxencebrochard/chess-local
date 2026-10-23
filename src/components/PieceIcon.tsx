import { defaultPieces } from 'react-chessboard'
import { DEFAULT_PIECE_SET, isPieceSet, pieceUrl } from '../lib/pieces'
import centers from '../data/pieceCenters.json'

// Une pièce du jeu choisi, à la taille de son conteneur. L'image ne capte aucun geste
// (pointer-events: none) : pas de menu « Enregistrer l'image » d'iOS sur appui long, et le
// toucher arrive à la case ou à la pièce de react-chessboard en dessous.
// `scale` réduit le dessin autour du centre de la case, sans toucher au conteneur (glissé et décalage
// tactile restent ceux de la case).
export function PieceIcon({ set, code, scale = 1 }: { set: string; code: string; scale?: number }) {
  const selected = isPieceSet(set) ? set : DEFAULT_PIECE_SET
  // Marges mesurées hors ligne : les silhouettes restent centrées sans altérer les SVG sous licence.
  const [x, y] = (centers as Record<string, number[]>)[`${selected}/${code}`] ?? [0, 0]
  // L'échelle d'abord : le recentrage mesuré à l'échelle 1 est réduit avec la silhouette et la compense encore.
  const transform = `${scale === 1 ? '' : `scale(${scale}) `}translate(${x}%, ${y}%)`
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
