// Jeux de pièces de l'échiquier. Tous sous licence libre (public/pieces/LICENSES.md) :
// rien ne vient de chess.com. `classique` = pièces intégrées à react-chessboard (aucun fichier).

export interface PieceSet {
  id: string
  name: string
}

export const PIECE_SETS: PieceSet[] = [
  { id: 'wikimedia', name: 'Wikimedia' },
  { id: 'celtique', name: 'Celtique' },
  { id: 'chessnut', name: 'Chessnut' },
  { id: 'fantasy', name: 'Fantasy' },
  { id: 'spatial', name: 'Spatial' },
  { id: 'classique', name: 'Classique' },
]

export const DEFAULT_PIECE_SET = 'wikimedia'

export const PIECE_CODES = ['wK', 'wQ', 'wR', 'wB', 'wN', 'wP', 'bK', 'bQ', 'bR', 'bB', 'bN', 'bP'] as const
export type PieceCode = (typeof PIECE_CODES)[number]

export function isPieceSet(id: unknown): boolean {
  return PIECE_SETS.some((s) => s.id === id)
}

// URL d'une pièce d'un jeu à fichiers (servie depuis public/, donc relative à BASE_URL : jamais de
// chemin absolu, l'app tourne aussi sous /chess-local/).
export function pieceUrl(setId: string, code: string): string {
  return `${import.meta.env.BASE_URL}pieces/${setId}/${code}.svg`
}

// Les 12 images d'un jeu, chargées et décodées d'avance et gardées en mémoire : react-chessboard
// remonte la pièce à chaque fin d'animation et à chaque début de drag, et une image pas encore
// décodée y laisserait une case vide le temps d'une frame.
const preloaded = new Map<string, HTMLImageElement[]>()
export function preloadPieceSet(setId: string) {
  if (setId === 'classique' || !isPieceSet(setId) || preloaded.has(setId)) return
  preloaded.set(
    setId,
    PIECE_CODES.map((code) => {
      const img = new Image()
      img.src = pieceUrl(setId, code)
      void img.decode().catch(() => {})
      return img
    }),
  )
}
