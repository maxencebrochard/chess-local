// Libellés français des 73 thèmes lichess présents dans public/puzzles.json.
// Vocabulaire : usage français courant (Wikipédia FR, Europe Échecs) ; les mats nommés suivent la
// traduction fr-FR de lichess (Cozio, guéridon, arbalète, hameçon) sauf « mat étouffé » et « mat arabe »,
// termes consacrés que lichess rend par « à l'étouffée » et « des Arabes ».
// `src/lib/themes.ts` garde ses 20 tags avec emojis pour la séance Apprendre.

export const PUZZLE_THEMES_FR: Record<string, string> = {
  // --- Phases de la partie ---
  opening: 'Ouverture',
  middlegame: 'Milieu de partie',
  endgame: 'Finale',
  rookEndgame: 'Finale de tours',
  bishopEndgame: 'Finale de fous',
  knightEndgame: 'Finale de cavaliers',
  pawnEndgame: 'Finale de pions',
  queenEndgame: 'Finale de dames',
  queenRookEndgame: 'Finale dame et tour',

  // --- Motifs tactiques ---
  advancedPawn: 'Pion avancé',
  attackingF2F7: 'Attaque sur f2 ou f7',
  attraction: 'Attraction',
  capturingDefender: 'Élimination du défenseur',
  clearance: 'Dégagement',
  collinearMove: 'Coup colinéaire',
  defensiveMove: 'Coup défensif',
  deflection: 'Déviation',
  discoveredAttack: 'Attaque à la découverte',
  discoveredCheck: 'Échec à la découverte',
  doubleCheck: 'Échec double',
  exposedKing: 'Roi exposé',
  fork: 'Fourchette',
  hangingPiece: 'Pièce en prise',
  interference: 'Interception',
  intermezzo: 'Coup intermédiaire',
  kingsideAttack: "Attaque à l'aile roi",
  queensideAttack: "Attaque à l'aile dame",
  pin: 'Clouage',
  quietMove: 'Coup tranquille',
  sacrifice: 'Sacrifice',
  skewer: 'Enfilade',
  trappedPiece: 'Pièce piégée',
  xRayAttack: 'Attaque aux rayons X',
  zugzwang: 'Zugzwang',

  // --- Coups spéciaux ---
  castling: 'Roque',
  enPassant: 'Prise en passant',
  promotion: 'Promotion',
  underPromotion: 'Sous-promotion',

  // --- Mats ---
  mate: 'Mat',
  mateIn1: 'Mat en 1',
  mateIn2: 'Mat en 2',
  mateIn3: 'Mat en 3',
  mateIn4: 'Mat en 4',
  mateIn5: 'Mat en 5 ou plus',
  anastasiaMate: "Mat d'Anastasie",
  arabianMate: 'Mat arabe',
  backRankMate: 'Mat du couloir',
  balestraMate: "Mat de l'arbalète",
  blindSwineMate: 'Mat des deux tours',
  bodenMate: 'Mat de Boden',
  cornerMate: 'Mat en coin',
  doubleBishopMate: 'Mat des deux fous',
  dovetailMate: 'Mat de Cozio',
  epauletteMate: 'Mat des épaulettes',
  hookMate: 'Mat du hameçon',
  killBoxMate: 'Mat par mise en boîte',
  morphysMate: 'Mat de Morphy',
  operaMate: "Mat de l'Opéra",
  pillsburysMate: 'Mat de Pillsbury',
  smotheredMate: 'Mat étouffé',
  swallowstailMate: 'Mat du guéridon',
  triangleMate: 'Mat du triangle',
  vukovicMate: 'Mat de Vuković',

  // --- Issue de la position ---
  equality: 'Égalité',
  advantage: 'Avantage',
  crushing: 'Écrasant',

  // --- Méta : longueur et origine, masqués dans les pastilles ---
  oneMove: 'Un coup',
  short: 'Court',
  long: 'Long',
  veryLong: 'Très long',
  master: 'Partie de maîtres',
  masterVsMaster: 'Maître contre maître',
  superGM: 'Super grand maître',
}

// Thèmes qui ne décrivent pas un motif : à masquer dans les pastilles sous l'échiquier
// (chess.com masque de même la longueur et l'origine).
const META_THEMES = new Set(['oneMove', 'short', 'long', 'veryLong', 'master', 'masterVsMaster', 'superGM'])

export function isMetaTheme(tag: string): boolean {
  return META_THEMES.has(tag)
}

/** Libellé français court. Repli lisible pour un tag inconnu : « someNewTheme » -> « Some new theme ». */
export function puzzleThemeLabel(tag: string): string {
  const hit = PUZZLE_THEMES_FR[tag]
  if (hit) return hit
  const words = tag.replace(/([a-z])([A-Z0-9])/g, '$1 $2').toLowerCase()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

// Les tags de puzzles.json sont triés alphabétiquement : sans ordre de priorité, « advantage »,
// « crushing », « endgame » et « middlegame » occuperaient les pastilles et éjecteraient les motifs.
// Rang 0 : le but (mat en N) ; 1 : motifs, mats nommés, coups spéciaux ; 2 : phase ; 3 : issue.
const PHASES = new Set(['opening', 'middlegame', 'endgame', 'rookEndgame', 'bishopEndgame', 'knightEndgame', 'pawnEndgame', 'queenEndgame', 'queenRookEndgame'])
const ISSUES = new Set(['equality', 'advantage', 'crushing'])

function rang(tag: string): number {
  if (/^mateIn\d$/.test(tag)) return 0
  if (PHASES.has(tag)) return 2
  if (ISSUES.has(tag)) return 3
  return 1
}

/**
 * Pastilles à afficher pour un puzzle : en français, méta exclus, `max` au plus, par ordre de priorité
 * (but, motifs, phase, issue). « mate » seul ne dit rien de plus qu'un « mateInN » ou un mat nommé
 * présent à côté : il est absorbé.
 */
export function displayThemes(tags: string[], max = 3): string[] {
  const utiles = tags.filter((t) => !isMetaTheme(t))
  const autreMat = utiles.some((t) => t !== 'mate' && /[mM]ate/.test(t))
  return utiles
    .filter((t) => t !== 'mate' || !autreMat)
    .map((t, i) => [t, i] as const)
    .sort((a, b) => rang(a[0]) - rang(b[0]) || a[1] - b[1])
    .slice(0, max)
    .map(([t]) => puzzleThemeLabel(t))
}
