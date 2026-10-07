// Contrôle hors ligne du cours de finales (src/data/endgameCourse.json) avec chess.js : structure,
// positions légales, lignes jouables, flèches, textes en français, et tampon de vérification.
// Le verdict des positions (gain, nulle, « seul coup ») est prouvé par scripts/verify-endgame-course.py
// contre les tables de finales ; ce contrôle exige que le JSON soit exactement celui qu'il a tamponné.
// Lancé par e2e/test_endgame_course.py (donc par le gate) : `node scripts/check-endgame-course.mjs`.
// Règles communes (positions, flèches, textes, tampon) : scripts/course-rules.mjs.
// N'imprime que les manquements ([KO]) et un bilan ; code de sortie 1 au moindre [KO].
import { readFileSync } from 'node:fs'
import { SQUARE, checkAnnouncedMate, checkArrows as arrowsRule, checkCited as citedRule, checkText as textRule, createChecker, load, oppositeCheck, stampMatches } from './course-rules.mjs'

const RAW = readFileSync('src/data/endgameCourse.json', 'utf8')
const course = JSON.parse(RAW)
const endgames = JSON.parse(readFileSync('src/data/endgames.json', 'utf8'))

// Ids publiés : la progression des élèves est stockée par id (learnSessions `finales:<id>`).
// Un id ne se renomme ni ne se supprime jamais ; on peut seulement en ajouter.
const FROZEN_IDS = [
  'mat-deux-tours', 'mat-dame', 'mat-tour',
  'carre-du-pion', 'opposition', 'cases-cles', 'pion-de-tour', 'manoeuvre-de-reti',
  'lucena', 'philidor', 'tour-derriere-le-pion',
  'dame-contre-pion',
  'roi-actif', 'pion-passe',
]

const { check, finish } = createChecker()
const checkArrows = (fen, arrows, label) => arrowsRule(check, fen, arrows, label)
const checkText = (text, label, max) => textRule(check, text, label, max)
const checkCited = (text, fens, label) => citedRule(check, text, fens, label)

// ---------- Tampon ----------
check(stampMatches(RAW, readFileSync('scripts/endgame-course.verified', 'utf8')), 'endgameCourse.json a changé depuis sa vérification par les tables : lance python3 scripts/verify-endgame-course.py')

// ---------- Positions ----------
function legalPosition(fen, label) {
  const c = load(fen)
  check(c !== null, `${label} : FEN refusée par chess.js (${fen})`)
  if (!c) return null
  check(!oppositeCheck(fen), `${label} : le camp qui n'a pas le trait est en échec (${fen})`)
  const pieces = c.board().flat().filter(Boolean).length
  check(pieces <= 7, `${label} : plus de 7 pièces, invérifiable par les tables`)
  check(fen.split(' ')[4] === '0', `${label} : compteur des 50 coups non nul`)
  return c
}

// ---------- Chapitres et leçons ----------
const lessons = course.lessons ?? {}
const ids = Object.keys(lessons)
const inChapters = []
const chapterIds = new Set()
for (const ch of course.chapters ?? []) {
  check(!chapterIds.has(ch.id), `chapitre ${ch.id} en double`)
  chapterIds.add(ch.id)
  checkText(ch.title, `chapitre ${ch.id} titre`, 40)
  check(Array.isArray(ch.lessons) && ch.lessons.length > 0, `chapitre ${ch.id} vide`)
  inChapters.push(...(ch.lessons ?? []))
}
for (const id of ids) check(inChapters.filter((x) => x === id).length === 1, `leçon ${id} : doit figurer dans exactement un chapitre`)
for (const id of inChapters) check(ids.includes(id), `chapitre : leçon inconnue ${id}`)
for (const id of FROZEN_IDS) check(ids.includes(id), `leçon ${id} supprimée ou renommée : la progression des élèves en dépend`)
for (const id of ids) check(FROZEN_IDS.includes(id), `leçon ${id} : nouvel id à ajouter à FROZEN_IDS`)

const exerciseOwner = new Map()
for (const [id, lesson] of Object.entries(lessons)) {
  const L = `leçon ${id}`
  check(/^[a-z0-9-]+$/.test(id), `${L} : id hors [a-z0-9-]`)
  checkText(lesson.title, `${L} titre`, 40)
  checkText(lesson.summary, `${L} résumé`, 110)
  check(Array.isArray(lesson.keyPoints) && lesson.keyPoints.length >= 2, `${L} : au moins deux points clés`)
  for (const k of lesson.keyPoints ?? []) checkText(k, `${L} point clé`, 120)
  if (lesson.exercise !== undefined) {
    check(endgames.some((e) => e.id === lesson.exercise), `${L} : exercice ${lesson.exercise} absent de endgames.json`)
    check(!exerciseOwner.has(lesson.exercise), `${L} : exercice ${lesson.exercise} déjà lié à ${exerciseOwner.get(lesson.exercise)}`)
    exerciseOwner.set(lesson.exercise, id)
  }
  const steps = lesson.steps ?? []
  check(steps.length >= 2, `${L} : au moins deux étapes`)
  check(steps.some((s) => s.kind === 'line'), `${L} : au moins une ligne à jouer`)
  steps.forEach((step, si) => {
    const S = `${L} étape ${si + 1}`
    if (step.kind === 'diagram') {
      checkText(step.text, S, 300)
      const c = legalPosition(step.fen, S)
      if (!c) return
      check(!c.isCheckmate() && !c.isStalemate(), `${S} : diagramme déjà mat ou pat`)
      check(step.orientation === undefined || step.orientation === 'w' || step.orientation === 'b', `${S} : orientation invalide`)
      check(step.claim === undefined || ['w', 'b', 'draw'].includes(step.claim), `${S} : claim invalide`)
      checkArrows(step.fen, step.arrows ?? [], S)
      for (const [sq, color] of Object.entries(step.marks ?? {})) {
        check(SQUARE.test(sq) && ['green', 'red', 'blue', 'yellow'].includes(color), `${S} : marque invalide ${sq}=${color}`)
      }
      checkCited(step.text, [step.fen], S)
      check(!/seul coup/i.test(step.text), `${S} : « seul coup » n'est vérifiable que sur un coup de ligne (only)`)
      // Un diagramme qui annonce un résultat le fait vérifier par les tables (claim).
      check(!/\b(gagn\w*|nulle|perd\w*)\b/i.test(step.text) || step.claim !== undefined, `${S} : le texte annonce un résultat sans claim vérifié`)
    } else if (step.kind === 'line') {
      checkText(step.text, S, 260)
      checkText(step.end, `${S} fin`, 220)
      check(step.result === 'win' || step.result === 'draw', `${S} : result invalide`)
      const c = legalPosition(step.fen, S)
      if (!c) return
      const player = c.turn()
      const moves = step.moves ?? []
      check(moves.length > 0, `${S} : ligne vide`)
      const fens = [c.fen()]
      for (const [mi, m] of moves.entries()) {
        const M = `${S} coup ${mi + 1} (${m.san})`
        const mine = c.turn() === player
        let mv
        try {
          mv = c.move(m.san)
        } catch {
          check(false, `${M} : injouable`)
          return
        }
        check(mv.san === m.san, `${M} : SAN non canonique (${mv.san})`)
        const uci = mv.from + mv.to + (mv.promotion ?? '')
        if (m.text !== undefined) checkText(m.text, M, 220)
        if (mine) {
          check(Array.isArray(m.keeps) && m.keeps.includes(uci), `${M} : keeps absent ou sans le coup (relance la vérification)`)
          if (m.only) check(m.keeps?.length === 1, `${M} : only mais ${m.keeps?.length} coups gardent le résultat`)
        } else {
          check(m.only === undefined && m.keeps === undefined, `${M} : only/keeps sur un coup adverse`)
        }
        if (/seul coup/i.test(m.text ?? '')) check(m.only === true, `${M} : « seul coup » dans le texte sans only vérifié`)
        checkAnnouncedMate(check, c, m.text, M)
        fens.push(c.fen())
      }
      checkAnnouncedMate(check, c, step.end, `${S} fin`)
      check(!/seul coup/i.test(step.text) && !/seul coup/i.test(step.end ?? ''), `${S} : « seul coup » se dit sur le coup concerné, avec only`)
      for (const m of moves) checkCited(m.text ?? '', fens, `${S} coup ${m.san}`)
      checkCited(step.text, fens, S)
      checkCited(step.end ?? '', fens, `${S} fin`)
    } else {
      check(false, `${S} : type d'étape inconnu ${step.kind}`)
    }
  })
}

finish()
