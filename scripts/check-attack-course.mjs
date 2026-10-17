// Contrôle hors ligne du cours « Démolir le roque » (src/data/attackCourse.json) avec chess.js :
// structure, positions légales, lignes jouables, `keeps` et `only` cohérents, flèches, textes en
// français, prudence des formulations, et tampon de vérification.
// Les verdicts (avantage décisif, nette avance, « seul coup », échec d'un sacrifice) sont prouvés par
// Stockfish 18 dans scripts/verify-attack-course.py ; ce contrôle exige que le JSON soit exactement
// celui qu'il a tamponné.
// Lancé par e2e/test_cours_roque.py (donc par le gate) :
//   node scripts/check-attack-course.mjs [json] [tampon]   (par défaut : le cours et son tampon)
// N'imprime que les manquements ([KO]) et un bilan ; code de sortie 1 au moindre [KO].
import { checkStockfishCourse } from './check-stockfish-course.mjs'

// Ids publiés : la progression des élèves est stockée par id (learnSessions `roque:<id>`).
// Un id ne se renomme ni ne se supprime jamais ; on peut seulement en ajouter.
const FROZEN_IDS = [
  'grec-schema', 'grec-echec',
  'lasker-bauer',
  'sacrifice-g7', 'sacrifice-f7', 'breche-g6', 'breche-h6',
  'tempete-de-pions', 'ouvrir-une-colonne',
  'levier-f5', 'attaque-de-pieces',
  'levier-de-tour', 'batterie-dame-fou',
  'ouvrir-le-centre', 'sacrifice-cd5',
  'compter-les-pieces', 'eliminer-le-defenseur', 'faire-venir-les-reserves',
]

checkStockfishCourse({
  data: process.argv[2] ?? 'src/data/attackCourse.json',
  stamp: process.argv[3] ?? 'scripts/attack-course.verified',
  frozenIds: FROZEN_IDS,
  verifyCommand: 'python3 scripts/verify-attack-course.py',
})
