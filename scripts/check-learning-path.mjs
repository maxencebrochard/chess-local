// Contrôle hors ligne du parcours d'apprentissage (src/data/learningPath.json) : ids figés et
// ordre des niveaux, références existantes (leçons des cours, cours détaillés, finales, familles
// d'ouvertures, thèmes de puzzles avec un vivier suffisant), bandes d'Elo dans l'ordre, seuils
// cohérents, textes en français.
// Les références se résolvent avec la vraie logique de l'app (src/lib/learningPath.ts,
// openingTrainer.ts...), bundlée par rolldown depuis scripts/learning-path-entry.ts.
// Lancé par e2e/test_parcours.py (donc par le gate) :
//   node scripts/check-learning-path.mjs [json]   (par défaut : src/data/learningPath.json)
// N'imprime que les manquements ([KO]) et un bilan ; code de sortie 1 au moindre [KO].
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { rolldown } from 'rolldown'
import { checkText, createChecker } from './course-rules.mjs'

const DATA = process.argv[2] ?? 'src/data/learningPath.json'
const path = JSON.parse(readFileSync(DATA, 'utf8'))
const { check, finish } = createChecker()

const dir = mkdtempSync(join(tmpdir(), 'learning-path-'))
let app
try {
  const bundle = await rolldown({ input: 'scripts/learning-path-entry.ts', platform: 'node', logLevel: 'silent' })
  await bundle.write({ file: join(dir, 'entry.mjs'), format: 'esm' })
  app = await import(pathToFileURL(join(dir, 'entry.mjs')).href)
} finally {
  rmSync(dir, { recursive: true, force: true })
}

// Ids publiés : la progression est stockée par id (learnSessions `path`, itemId = id d'étape ;
// le test de placement compte les niveaux dans cet ordre). Un id ne se renomme ni ne se supprime
// jamais, un niveau ne change pas de place ; on peut seulement en ajouter.
const FROZEN_LEVELS = ['debutant', 'intermediaire', 'confirme', 'avance']
const FROZEN_STEPS = [
  'valeur-des-pieces', 'pieces-en-prise', 'menaces', 'mat-en-un', 'developpement', 'partie-italienne',
  'mat-deux-tours', 'mat-dame', 'mat-du-couloir', 'mat-tour',
  'fourchette', 'clouage', 'enfilade', 'carre-du-pion', 'opposition', 'tours-septieme', 'mat-en-deux', 'gambit-dame',
  'attaque-decouverte', 'deviation', 'sacrifice-grec', 'cases-cles', 'attraction', 'pion-de-tour', 'sacrifice', 'sicilienne',
  'compter-les-pieces',
  'coup-intermediaire', 'manoeuvre-de-reti', 'coup-tranquille', 'lucena', 'eliminer-le-defenseur', 'philidor', 'zugzwang',
  'defense', 'dame-contre-tour', 'mat-en-trois',
]
const ID = /^[a-z0-9-]+$/
const BAND_SPAN = 400 // une bande de puzzles reste à ±400 de l'Elo du niveau
const POOL_FACTOR = 4 // vivier minimal : 4 fois le nombre de puzzles d'une série

// Vivier de puzzles : public/puzzles.json, format compact [id, fen, moves, rating, themes].
const PUZZLES = JSON.parse(readFileSync('public/puzzles.json', 'utf8')).map(([, , , rating, themes]) => ({ rating, themes: themes.split(' ') }))
function pool(themes, [lo, hi]) {
  return PUZZLES.filter((p) => p.rating >= lo && p.rating <= hi && (!themes || themes.some((t) => p.themes.includes(t)))).length
}
const mid = ([lo, hi]) => (lo + hi) / 2
function band(r, label) {
  const ok = Array.isArray(r) && r.length === 2 && r.every(Number.isInteger) && r[0] < r[1]
  check(ok, `${label} : bande d'Elo invalide ${JSON.stringify(r)}`)
  return ok
}

const levels = Array.isArray(path.levels) ? path.levels : []
check(levels.length > 0, 'aucun niveau')
FROZEN_LEVELS.forEach((id, i) => check(levels[i]?.id === id, `niveau ${i + 1} : ${id} attendu (ordre figé), trouvé ${levels[i]?.id}`))
for (const l of levels) check(FROZEN_LEVELS.includes(l.id), `niveau ${l.id} : nouvel id à ajouter à FROZEN_LEVELS`)

const ids = new Set()
const lessonsUsed = new Map() // cours -> index de la dernière leçon citée
const refsUsed = new Set()
let prevElo = -Infinity
let prevPlacement = -Infinity
let prevLevelBand = -Infinity
for (const level of levels) {
  const L = `niveau ${level.id}`
  check(ID.test(level.id ?? ''), `${L} : id hors [a-z0-9-]`)
  checkText(check, level.title, `${L} titre`, 24)
  checkText(check, level.intro, `${L} intro`, 220)
  check(/^#[0-9a-f]{6}$/i.test(level.color ?? ''), `${L} : couleur invalide`)
  check(Number.isInteger(level.elo) && level.elo > prevElo, `${L} : Elo ${level.elo} non croissant`)
  prevElo = level.elo
  const pr = level.placement?.rating
  if (band(pr, `${L} placement`)) {
    check(Math.abs(mid(pr) - level.elo) <= 300, `${L} : bande de placement loin de l'Elo du niveau`)
    check(mid(pr) > prevPlacement, `${L} : bande de placement pas plus haute que celle du niveau précédent`)
    prevPlacement = mid(pr)
    check(pool(null, pr) >= app.PLACEMENT_PER_LEVEL * 10, `${L} : trop peu de puzzles pour le test de placement`)
  }
  const steps = Array.isArray(level.steps) ? level.steps : []
  check(steps.length > 0, `${L} : aucune étape`)
  let levelMin = Infinity
  let levelMax = -Infinity
  for (const step of steps) {
    const S = `étape ${step.id}`
    check(ID.test(step.id ?? ''), `${S} : id hors [a-z0-9-]`)
    check(step.id !== app.PLACEMENT_ID, `${S} : id réservé au test de placement`)
    check(!ids.has(step.id), `${S} : id en double`)
    ids.add(step.id)
    checkText(check, step.title, `${S} titre`, 40)
    checkText(check, step.summary, `${S} résumé`, 110)
    check(typeof step.icon === 'string' && step.icon.length > 0 && step.icon.length <= 6, `${S} : icône absente ou trop longue`)
    const ex = step.exercise
    check(Boolean(step.lesson || ex), `${S} : ni leçon ni exercice`)
    if (step.lesson !== undefined) {
      const ref = app.lessonRef(step.lesson)
      check(ref !== null, `${S} : leçon inconnue ${step.lesson}`)
      check(!refsUsed.has(step.lesson), `${S} : leçon ${step.lesson} déjà utilisée par une autre étape`)
      refsUsed.add(step.lesson)
      if (ref) {
        const idx = ref.course.lessonIds.indexOf(ref.id)
        check(idx > (lessonsUsed.get(ref.course.slug) ?? -1), `${S} : leçon ${step.lesson} avant une leçon qui la suit dans son cours`)
        lessonsUsed.set(ref.course.slug, idx)
      }
    }
    if (step.read !== undefined) {
      check(app.courseFor(step.read) !== null, `${S} : cours détaillé inconnu ${step.read}`)
      check(ex?.kind === 'puzzles' || ex?.kind === 'opening', `${S} : read sans série notée à la suite`)
    }
    if (!ex) continue
    if (ex.kind === 'puzzles' || ex.kind === 'opening') {
      check(Number.isInteger(ex.count) && ex.count >= 2 && ex.count <= 10, `${S} : count ${ex.count} hors de 2 à 10`)
      check(Number.isInteger(ex.pass) && ex.pass >= 1 && ex.pass <= ex.count && ex.pass * 2 >= ex.count, `${S} : seuil ${ex.pass}/${ex.count} incohérent`)
    }
    if (ex.kind === 'puzzles') {
      check(Array.isArray(ex.themes) && ex.themes.length > 0, `${S} : aucun thème`)
      for (const t of ex.themes ?? []) {
        check(Object.hasOwn(app.PUZZLE_THEMES_FR, t), `${S} : thème inconnu ${t}`)
        check(PUZZLES.some((p) => p.themes.includes(t)), `${S} : thème ${t} absent de puzzles.json`)
      }
      if (band(ex.rating, S)) {
        check(Math.abs(mid(ex.rating) - level.elo) <= BAND_SPAN, `${S} : bande ${ex.rating} loin de l'Elo du niveau (${level.elo})`)
        const n = pool(ex.themes ?? [], ex.rating)
        check(n >= POOL_FACTOR * ex.count, `${S} : ${n} puzzles dans la bande, ${POOL_FACTOR * ex.count} au moins`)
        levelMin = Math.min(levelMin, mid(ex.rating))
        levelMax = Math.max(levelMax, mid(ex.rating))
      }
    } else if (ex.kind === 'opening') {
      const fam = app.getFamily(ex.family ?? '')
      check(fam !== null, `${S} : famille d'ouverture inconnue ${ex.family}`)
      check(ex.color === 'w' || ex.color === 'b', `${S} : couleur invalide ${ex.color}`)
      if (fam) {
        const meaty = fam.variants.filter((v) => app.playerMoveCount(v, ex.color) >= 3).length
        check(meaty >= ex.count, `${S} : ${meaty} variantes où le joueur joue 3 coups, ${ex.count} au moins`)
      }
    } else if (ex.kind === 'endgame') {
      const eg = app.ENDGAMES.find((e) => e.id === ex.id)
      check(eg !== undefined, `${S} : finale inconnue ${ex.id}`)
      if (eg) check(eg.difficulty <= level.elo + BAND_SPAN, `${S} : finale ${ex.id} (${eg.difficulty}) trop difficile pour le niveau`)
    } else {
      check(false, `${S} : type d'exercice inconnu ${ex.kind}`)
    }
  }
  if (levelMin !== Infinity) {
    check(levelMin > prevLevelBand, `${L} : une série de puzzles est plus basse que celles du niveau précédent`)
    prevLevelBand = levelMax
  }
}
for (const id of FROZEN_STEPS) check(ids.has(id), `étape ${id} supprimée ou renommée : la progression des élèves en dépend`)
for (const id of ids) check(FROZEN_STEPS.includes(id), `étape ${id} : nouvel id à ajouter à FROZEN_STEPS`)

// Le parcours de l'app est bien celui-ci, et son point de départ est sa première étape.
const live = app.computePath(app.EMPTY_FACTS, path.levels ?? [])
check(live.current?.step.id === levels[0]?.steps?.[0]?.id, 'parcours neuf : la première étape devrait être courante')

finish()
