// Contrôle hors ligne du cours « Les bases » (src/data/basicsCourse.json), mêmes règles que
// « Démolir le roque » (scripts/check-stockfish-course.mjs) : positions, lignes, textes et tampon
// de vérification par Stockfish 18 (python3 scripts/verify-basics-course.py).
// Lancé par e2e/test_parcours.py (donc par le gate) :
//   node scripts/check-basics-course.mjs [json] [tampon]   (par défaut : le cours et son tampon)
// N'imprime que les manquements ([KO]) et un bilan ; code de sortie 1 au moindre [KO].
import { checkStockfishCourse } from './check-stockfish-course.mjs'

// Ids publiés : la progression des élèves est stockée par id (learnSessions `bases:<id>`) et le
// parcours d'apprentissage y renvoie. Un id ne se renomme ni ne se supprime jamais.
const FROZEN_IDS = ['valeur-des-pieces', 'menaces', 'developpement', 'tours-septieme']

checkStockfishCourse({
  data: process.argv[2] ?? 'src/data/basicsCourse.json',
  stamp: process.argv[3] ?? 'scripts/basics-course.verified',
  frozenIds: FROZEN_IDS,
  verifyCommand: 'python3 scripts/verify-basics-course.py',
})
