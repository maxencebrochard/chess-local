// Contrôle hors ligne du cours « Démolir le roque » (src/data/attackCourse.json) avec chess.js :
// structure, positions légales, lignes jouables, `keeps` et `only` cohérents, flèches, textes en
// français, prudence des formulations, et tampon de vérification.
// Les verdicts (avantage décisif, nette avance, « seul coup », échec d'un sacrifice) sont prouvés par
// Stockfish 18 dans scripts/verify-attack-course.py ; ce contrôle exige que le JSON soit exactement
// celui qu'il a tamponné.
// Lancé par e2e/test_cours_roque.py (donc par le gate) :
//   node scripts/check-attack-course.mjs [json] [tampon]   (par défaut : le cours et son tampon)
// N'imprime que les manquements ([KO]) et un bilan ; code de sortie 1 au moindre [KO].
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import {
  SQUARE, checkAnnouncedMate, checkArrows, checkCited, checkText, createChecker, load, oppositeCheck, stampMatches, word,
} from './course-rules.mjs'

const DATA = process.argv[2] ?? 'src/data/attackCourse.json'
const STAMP = process.argv[3] ?? 'scripts/attack-course.verified'
const RAW = readFileSync(DATA, 'utf8')
const course = JSON.parse(RAW)
const { check, finish } = createChecker()

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

const STAMP_TEXT = readFileSync(STAMP, 'utf8')
check(stampMatches(RAW, STAMP_TEXT), `${DATA} a changé depuis sa vérification par Stockfish : lance python3 scripts/verify-attack-course.py`)
// Le tampon lie aussi la version du vérificateur (paliers, profondeurs) : le changer impose de revérifier.
const verifierSha = createHash('sha256').update(readFileSync('scripts/verify-attack-course.py')).digest('hex')
check(STAMP_TEXT.trim().split(/\s+/)[1] === verifierSha, 'scripts/verify-attack-course.py a changé depuis le tampon : relance-le')

// Un texte qui affirme un verdict doit s'appuyer sur une vérification moteur.
const VERDICT = word('gagn\\p{L}*|perd(?:s|ent|u|ant|ante)?|nulle|échou\\p{L}*|réfut\\p{L}*|décisi\\p{L}*|tient|tiennent|marche|fonctionne\\p{L}*|gagnant\\p{L}*|perdant\\p{L}*')
// Mots absolus : jamais, le moteur ne prouve rien de tel à profondeur finie (sauf un mat, voir MATE_WORDS).
const ABSOLUTE = word('forcément|imparable|imparables|inévitable|inévitablement|à coup sûr|sans appel|irrésistible')
const FORCED = word('forcé\\p{L}*')
// « mat » dans un diagramme exige un mat établi par Stockfish (éval tamponnée « #n »).
const MATE = word('mat')
const SUB_PROMOTION = /=[NBR]/

// `mateEval` : un diagramme dont l'éval tamponnée est un mat peut dire « forcé ».
function prudent(text, label, mateEval = false) {
  if (typeof text !== 'string') return
  check(!ABSOLUTE.test(text), `${label} : formulation absolue (${(text.match(ABSOLUTE) || [])[0]}) que Stockfish n'établit pas`)
  check(mateEval || !FORCED.test(text), `${label} : « forcé » sans mat établi par Stockfish`)
}

function legalPosition(fen, label) {
  const c = load(fen)
  check(c !== null, `${label} : FEN refusée par chess.js (${fen})`)
  if (!c) return null
  check(!oppositeCheck(fen), `${label} : le camp qui n'a pas le trait est en échec (${fen})`)
  const board = c.board().flat().filter(Boolean)
  for (const color of ['w', 'b']) {
    const pawns = board.filter((p) => p.color === color && p.type === 'p').length
    const pieces = board.filter((p) => p.color === color).length
    check(pawns <= 8 && pieces <= 16, `${label} : matériel impossible (${color})`)
    check(board.filter((p) => p.color === color && p.type === 'k').length === 1, `${label} : un roi par camp (${color})`)
  }
  check(!/[pP]/.test(fen.split(' ')[0].split('/')[0] + fen.split(' ')[0].split('/')[7]), `${label} : pion sur la 1re ou la 8e rangée`)
  return c
}

const lessons = course.lessons ?? {}
const ids = Object.keys(lessons)
const inChapters = []
const chapterIds = new Set()
for (const ch of course.chapters ?? []) {
  check(!chapterIds.has(ch.id), `chapitre ${ch.id} en double`)
  chapterIds.add(ch.id)
  checkText(check, ch.title, `chapitre ${ch.id} titre`, 40)
  check(Array.isArray(ch.lessons) && ch.lessons.length > 0, `chapitre ${ch.id} vide`)
  inChapters.push(...(ch.lessons ?? []))
}
for (const id of ids) check(inChapters.filter((x) => x === id).length === 1, `leçon ${id} : doit figurer dans exactement un chapitre`)
for (const id of inChapters) check(ids.includes(id), `chapitre : leçon inconnue ${id}`)
for (const id of FROZEN_IDS) check(ids.includes(id), `leçon ${id} supprimée ou renommée : la progression des élèves en dépend`)
for (const id of ids) check(FROZEN_IDS.includes(id), `leçon ${id} : nouvel id à ajouter à FROZEN_IDS`)

for (const [id, lesson] of Object.entries(lessons)) {
  const L = `leçon ${id}`
  check(/^[a-z0-9-]+$/.test(id), `${L} : id hors [a-z0-9-]`)
  checkText(check, lesson.title, `${L} titre`, 40)
  checkText(check, lesson.summary, `${L} résumé`, 110)
  prudent(lesson.summary, `${L} résumé`)
  check(lesson.exercise === undefined, `${L} : pas d'exercice de finale dans ce cours`)
  check(Array.isArray(lesson.keyPoints) && lesson.keyPoints.length >= 2, `${L} : au moins deux points clés`)
  for (const k of lesson.keyPoints ?? []) {
    checkText(check, k, `${L} point clé`, 120)
    prudent(k, `${L} point clé`)
  }
  const steps = lesson.steps ?? []
  check(steps.length >= 2, `${L} : au moins deux étapes`)
  check(steps.some((s) => s.kind === 'line'), `${L} : au moins une ligne à jouer`)
  steps.forEach((step, si) => {
    const S = `${L} étape ${si + 1}`
    if (step.kind === 'diagram') {
      checkText(check, step.text, S, 300)
      prudent(step.text, S, (step.eval ?? '').startsWith('#'))
      const c = legalPosition(step.fen, S)
      if (!c) return
      check(!c.isCheckmate() && !c.isStalemate(), `${S} : diagramme déjà mat ou pat`)
      check(step.orientation === undefined || step.orientation === 'w' || step.orientation === 'b', `${S} : orientation invalide`)
      check(step.claim === undefined || ['w', 'b', 'equal'].includes(step.claim), `${S} : claim invalide (w, b ou equal)`)
      check(typeof step.eval === 'string' && /^(?:[+-]\d+\.\d\d|#-?\d+)$/.test(step.eval), `${S} : éval moteur absente (relance la vérification)`)
      if (step.fails !== undefined) {
        let ok = true
        try {
          load(step.fen).move(step.fails)
        } catch {
          ok = false
        }
        check(ok, `${S} : fails ${step.fails} injouable`)
      }
      checkArrows(check, step.fen, step.arrows ?? [], S)
      for (const [sq, color] of Object.entries(step.marks ?? {})) {
        check(SQUARE.test(sq) && ['green', 'red', 'blue', 'yellow'].includes(color), `${S} : marque invalide ${sq}=${color}`)
      }
      checkCited(check, step.text, [step.fen], S)
      check(!word('seul coup').test(step.text), `${S} : « seul coup » n'est vérifiable que sur un coup de ligne (only)`)
      check(!VERDICT.test(step.text) || step.claim !== undefined || step.fails !== undefined, `${S} : le texte annonce un verdict (${(step.text.match(VERDICT) || [])[0]}) sans claim ni fails vérifié`)
      check(!MATE.test(step.text) || (step.eval ?? '').startsWith('#'), `${S} : le texte parle de mat sans mat établi par Stockfish`)
    } else if (step.kind === 'line') {
      checkText(check, step.text, S, 260)
      checkText(check, step.end, `${S} fin`, 220)
      for (const [t, l] of [[step.text, S], [step.end, `${S} fin`]]) prudent(t, l)
      check(step.result === 'win' || step.result === 'edge', `${S} : result invalide (win ou edge)`)
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
        for (const [t, l] of [[m.text, M], [m.hint, `${M} indice`]]) {
          if (t !== undefined) {
            checkText(check, t, l, 220)
            prudent(t, l)
          }
        }
        if (mine) {
          check(Array.isArray(m.keeps) && m.keeps.includes(uci), `${M} : keeps absent ou sans le coup (relance la vérification)`)
          if (m.only) check(m.keeps?.length === 1, `${M} : only mais ${m.keeps?.length} coups gardent le résultat`)
          check(!SUB_PROMOTION.test(m.san), `${M} : sous-promotion de l'élève (le glisser promeut en dame)`)
          check(m.weak === undefined, `${M} : weak réservé aux réponses adverses`)
          check(!(m.close ?? []).some((u) => (m.keeps ?? []).includes(u)), `${M} : close et keeps se recouvrent`)
        } else {
          check(m.only === undefined && m.keeps === undefined && m.close === undefined && m.hint === undefined, `${M} : only/keeps/close/hint sur un coup adverse`)
          check(m.weak === undefined || m.weak === true, `${M} : weak invalide`)
        }
        if (word('seul coup').test(m.text ?? '')) check(m.only === true, `${M} : « seul coup » dans le texte sans only vérifié`)
        checkAnnouncedMate(check, c, m.text, M)
        fens.push(c.fen())
      }
      checkAnnouncedMate(check, c, step.end, `${S} fin`)
      check(!word('seul coup').test(step.text) && !word('seul coup').test(step.end ?? ''), `${S} : « seul coup » se dit sur le coup concerné, avec only`)
      for (const m of moves) {
        checkCited(check, m.text ?? '', fens, `${S} coup ${m.san}`)
        checkCited(check, m.hint ?? '', fens, `${S} coup ${m.san} indice`)
      }
      checkCited(check, step.text, fens, S)
      checkCited(check, step.end ?? '', fens, `${S} fin`)
    } else {
      check(false, `${S} : type d'étape inconnu ${step.kind}`)
    }
  })
}

finish()
