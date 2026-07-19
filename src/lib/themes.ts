// Thèmes tactiques lichess exposés dans l'app, avec libellés FR.
// Les tags correspondent au champ `themes` de la base de puzzles.
export interface TacticTheme {
  tag: string
  label: string
  emoji: string
}

export const TACTIC_THEMES: TacticTheme[] = [
  { tag: 'fork', label: 'Fourchette', emoji: '🍴' },
  { tag: 'pin', label: 'Clouage', emoji: '📌' },
  { tag: 'skewer', label: 'Enfilade', emoji: '🍢' },
  { tag: 'discoveredAttack', label: 'Attaque à la découverte', emoji: '🎭' },
  { tag: 'mateIn1', label: 'Mat en 1', emoji: '🎯' },
  { tag: 'mateIn2', label: 'Mat en 2', emoji: '🎯' },
  { tag: 'mateIn3', label: 'Mat en 3', emoji: '🎯' },
  { tag: 'backRankMate', label: 'Mat du couloir', emoji: '🚪' },
  { tag: 'hangingPiece', label: 'Pièce en prise', emoji: '🎁' },
  { tag: 'sacrifice', label: 'Sacrifice', emoji: '💥' },
  { tag: 'deflection', label: 'Déviation', emoji: '🧲' },
  { tag: 'attraction', label: 'Attraction', emoji: '🕳' },
  { tag: 'promotion', label: 'Promotion', emoji: '👑' },
  { tag: 'trappedPiece', label: 'Pièce piégée', emoji: '🪤' },
  { tag: 'intermezzo', label: 'Coup intermédiaire', emoji: '⚡' },
  { tag: 'defensiveMove', label: 'Défense', emoji: '🛡' },
  { tag: 'rookEndgame', label: 'Finale de tours', emoji: '♜' },
  { tag: 'pawnEndgame', label: 'Finale de pions', emoji: '♟' },
  { tag: 'zugzwang', label: 'Zugzwang', emoji: '⏳' },
  { tag: 'exposedKing', label: 'Roi exposé', emoji: '🌪' },
]

export function themeLabel(tag: string): string {
  return TACTIC_THEMES.find((t) => t.tag === tag)?.label ?? tag
}
