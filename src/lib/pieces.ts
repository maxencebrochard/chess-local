// Jeux de pièces : provenance et autorisations dans public/pieces/LICENSES.md.
// rien ne vient de chess.com. `classique` = pièces intégrées à react-chessboard (aucun fichier).

export interface PieceSet {
  id: string
  name: string
  // Échelle du dessin dans sa case sur l'échiquier (1 par défaut). Les jeux qui dessinent jusqu'au bord
  // de la case sont réduits pour laisser libres les coins des coordonnées : chaque facteur est l'échelle
  // maximale mesurée sans contact sur une case de 47 px (iPhone), moins environ 1,5 % de marge.
  scale?: number
}

export const PIECE_SETS: PieceSet[] = [
  { id: 'atelier', name: 'Atelier' },
  { id: 'wikimedia', name: 'Wikimedia' },
  { id: 'celtique', name: 'Celtique', scale: 0.8 },
  { id: 'chessnut', name: 'Chessnut', scale: 0.94 },
  { id: 'fantasy', name: 'Fantasy', scale: 0.83 },
  { id: 'spatial', name: 'Spatial', scale: 0.77 },
  { id: 'classique', name: 'Classique', scale: 0.87 },
]

export const DEFAULT_PIECE_SET = 'atelier'

export const PIECE_CODES = ['wK', 'wQ', 'wR', 'wB', 'wN', 'wP', 'bK', 'bQ', 'bR', 'bB', 'bN', 'bP'] as const
export type PieceCode = (typeof PIECE_CODES)[number]

export function isPieceSet(id: unknown): boolean {
  return PIECE_SETS.some((s) => s.id === id)
}

export function pieceScale(id: string): number {
  return PIECE_SETS.find((s) => s.id === id)?.scale ?? 1
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
