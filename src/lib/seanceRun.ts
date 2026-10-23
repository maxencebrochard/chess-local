// Séance du jour : chargement de ce qu'il y a à travailler (IndexedDB, rapport Insights en cache,
// banques bundlées) et matérialisation du plan de seance.ts en étapes sérialisables. La séance en
// cours (sessionStorage) et les séances terminées (`learnSessions`, domaine `seance`) vivent dans
// seanceSession.ts, réexporté ici.
import { ATTACKS, attackStats, statsKey } from './attack'
import { db, getRating } from './db'
import { computeInsights } from './insights'
import { readInsights, rowFitsRun } from './insightsStore'
import { ENDGAMES } from './learn'
import { openingFr } from './openingNames'
import { DRILL_DOMAIN, getFamily, loadProgress, pickVariant, variantStatus } from './openingTrainer'
import { solvedEndgames, validFen } from './positionGame'
import { loadPuzzles, pendingPuzzleId, pickRatedPuzzle, recentPuzzleIds } from './puzzles'
import { buildReviewSession, loadReviewQueue, resolveSession, resolveVariant, variantKey, type ReviewPayload } from './revision'
import {
  planSeance, weakOpenings, type BlockKind, type InsightsFinding, type PlannedBlock, type SeancePlan, type VariantCandidate,
} from './seance'
import type { PuzzleData } from '../components/PuzzlePlayer'
import type { Step } from './seanceSession'

// Séance en cours et séances terminées : seanceSession.ts, léger, que l'accueil lit seul.
export { SEANCE_DOMAIN, SEANCE_SESSION_KEY, RESUME_MS, readStoredSeance, writeStoredSeance, recordSeance, seanceDates } from './seanceSession'
export type { Step, StepPhase, SeanceResult, StoredSeance } from './seanceSession'

// Positions jouables : FEN légale et trait au camp du joueur (mêmes gardes que les pages).
export const playableAttacks = () => ATTACKS.filter((a) => validFen(a.fen) && a.fen.split(' ')[1] === a.attacker)
export const playableEndgames = () => ENDGAMES.filter((e) => validFen(e.fen) && e.fen.split(' ')[1] === e.side)

// ---------- Rapport Insights en cache ----------

// Un rapport ne pèse que s'il couvre assez de parties et reste récent : trois parties, ou un
// rapport de l'été, diraient moins que les exercices des deux dernières semaines.
export const INSIGHTS_MIN_GAMES = 5
export const INSIGHTS_MAX_AGE_DAYS = 30

let findingsMemo: { at: number; keys: string; findings: InsightsFinding[] | null } | null = null

// Faiblesses du dernier rapport Insights, relu depuis le cache comme /insights le restaure (même
// profondeur, même compte) ; null sans rapport exploitable. Calcul mis en cache par rapport.
async function cachedFindings(now: number): Promise<InsightsFinding[] | null> {
  const last = readInsights().lastRun
  if (!last || last.keys.length === 0 || now - last.at > INSIGHTS_MAX_AGE_DAYS * 86_400_000) return null
  const keys = last.keys.join('|')
  if (findingsMemo && findingsMemo.at === last.at && findingsMemo.keys === keys) return findingsMemo.findings
  try {
    const rows = await db.reviews.bulkGet(last.keys)
    if (!rows.every((r) => r && rowFitsRun(r, last))) return null
    const report = computeInsights(rows.filter((r) => r !== undefined))
    const findings = report.games.n >= INSIGHTS_MIN_GAMES ? report.findings.candidates.weaknesses : null
    findingsMemo = { at: last.at, keys, findings }
    return findings
  } catch {
    return null
  }
}

// ---------- Construction ----------

export interface BuiltSeance {
  plan: SeancePlan
  steps: Step[]
  puzzlesUnavailable: boolean
  rating: number // classement puzzles au départ
}

interface Ctx {
  payloads: ReviewPayload[] // file de révision due, résolue
  puzzles: PuzzleData[] | null // null : puzzles.json indisponible
  rating: number
  exclude: Set<string> // puzzles à ne pas tirer : récents, de la révision, en attente sur /puzzles
  inSeance: Set<string> // puzzles déjà dans la séance (ou en attente sur /puzzles)
  rng: () => number
}

// Étapes d'un bloc planifié, par type : un type ajouté sans sa matérialisation ne compile pas.
// Exporté pour le banc Node de la suite `seance`.
export const MATERIALIZE: Record<BlockKind, (b: PlannedBlock, c: Ctx) => Step[]> = {
  revision: (b, c) => {
    const byKey = new Map(c.payloads.map((p) => [`${p.item.kind}:${p.item.key}`, p]))
    return buildReviewSession(c.payloads.map((p) => p.item), b.count).map((i) => ({ kind: 'revision', payload: byKey.get(`${i.kind}:${i.key}`)! }))
  },
  puzzles: (b, c) => {
    const out: Step[] = []
    for (let i = 0; c.puzzles && i < b.count; i++) {
      const puzzle = pickRatedPuzzle(c.puzzles, c.rating, c.exclude, { theme: b.ref, rng: c.rng })
      // Vivier du niveau épuisé, thème et hors thème (le dernier repli ignore les exclusions) : jamais deux fois le même puzzle.
      if (!puzzle || c.inSeance.has(puzzle.id)) break
      c.exclude.add(puzzle.id)
      c.inSeance.add(puzzle.id)
      out.push({ kind: 'puzzles', puzzle })
    }
    return out
  },
  opening: (b) => {
    const v = b.ref ? resolveVariant(b.ref) : null
    return v ? [{ kind: 'opening', color: v.color, uci: v.variant.line.uci, label: openingFr(v.variant.line.name) }] : []
  },
  endgame: (b) => (b.ref ? [{ kind: 'endgame', id: b.ref }] : []),
  attack: (b) => (b.ref ? [{ kind: 'attack', id: b.ref }] : []),
}

// Plan et étapes de la séance. Ne lève pas pour des puzzles indisponibles : puzzles.json en échec
// retire les puzzles (classés et de révision), le reste de la séance tient.
export async function buildSeance(now = Date.now(), rng: () => number = Math.random): Promise<BuiltSeance> {
  const [attempts, sessions, rating, findings, queue, aStats, solved, progress] = await Promise.all([
    db.puzzleAttempts.toArray(),
    db.learnSessions.toArray(),
    getRating('puzzle'),
    cachedFindings(now),
    loadReviewQueue(now),
    attackStats(),
    solvedEndgames(),
    loadProgress(),
  ])

  // Toute la file due est résolue d'abord : un item introuvable ne prend pas la place d'un valide.
  const resolved = await resolveSession(queue.due)
  let puzzlesUnavailable = resolved.puzzlesUnavailable
  let all: PuzzleData[] | null = null
  if (!puzzlesUnavailable) {
    try {
      all = await loadPuzzles()
    } catch {
      puzzlesUnavailable = true
    }
  }
  const payloads = resolved.payloads.filter((p) => !(puzzlesUnavailable && p.kind === 'puzzle'))

  // Variantes : dernière tentative `full` ratée ; puis une variante non maîtrisée de chaque famille
  // signalée par Insights. Le planificateur les classe (famille signalée, puis la plus récente).
  const lastFull = new Map<string, { success: 0 | 1; date: number }>()
  for (const s of [...sessions].sort((a, b) => a.date - b.date)) {
    if (s.domain === DRILL_DOMAIN && s.itemId.startsWith('full:')) lastFull.set(s.itemId.slice('full:'.length), { success: s.success, date: s.date })
  }
  const variants: VariantCandidate[] = []
  for (const [key, l] of lastFull) if (l.success === 0 && resolveVariant(key)) variants.push({ key, last: l.date, family: null })
  for (const o of weakOpenings(findings)) {
    const fam = getFamily(o.family)
    if (!fam) continue
    const v = pickVariant(fam, o.color, progress)
    const key = variantKey(o.color, v.line.uci)
    if (variantStatus(progress, o.color, v) !== 'mastered' && resolveVariant(key)) variants.push({ key, last: lastFull.get(key)?.date ?? 0, family: o.family })
  }

  const plan = planSeance(
    {
      now,
      due: payloads.map((p) => p.item),
      puzzleRating: rating.value,
      puzzles: attempts,
      sessions,
      findings,
      attacks: playableAttacks().map((a) => ({ id: a.id, solved: (aStats.get(statsKey(a))?.successes ?? 0) > 0 })),
      endgames: playableEndgames().map((e) => ({ id: e.id, solved: solved.has(`${e.id}|${e.fen}`) })),
      variants,
      puzzlesAvailable: !puzzlesUnavailable,
    },
    rng,
  )

  const revisionPuzzles = payloads.filter((p) => p.kind === 'puzzle').map((p) => p.item.key)
  const pending = pendingPuzzleId()
  const held = [...revisionPuzzles, ...(pending ? [pending] : [])]
  const ctx: Ctx = {
    payloads,
    puzzles: all,
    rating: rating.value,
    exclude: new Set([...(await recentPuzzleIds()), ...held]),
    inSeance: new Set(held),
    rng,
  }
  const steps = plan.blocks.flatMap((b) => MATERIALIZE[b.kind](b, ctx))
  return { plan, steps, puzzlesUnavailable, rating: rating.value }
}

