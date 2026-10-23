// Séance du jour (/seance) : un entraînement guidé de 10 à 15 minutes qui enchaîne quelques blocs
// courts tirés de ce qu'il y a à travailler. Pur (sans React ni lecture de Dexie) : registre des
// types de blocs, poids des faiblesses, planificateur, série de jours et libellés du bilan.
// Exécuté aussi sous Node par la suite E2E `seance` (banc) : seuls des types viennent de revision.ts et
// d'insights.ts, qui tirent Dexie et le moteur. Le chargement des données et la
// matérialisation du plan vivent dans seanceRun.ts.
//
// Ajouter un type de bloc : une entrée dans BLOCK_META, une règle dans planSeance, une
// matérialisation dans seanceRun.ts et un rendu dans RENDERERS de pages/Seance.tsx.
import type { Finding } from './insights'
import { puzzleThemeLabel } from './puzzleThemes'
import { addDays, startOfDay } from './days'
import type { ReviewKind } from './revision'

export type BlockKind = 'revision' | 'puzzles' | 'opening' | 'endgame' | 'attack'

// Minutes estimées par étape : le budget de la séance se compte avec elles.
export const BLOCK_META: Record<BlockKind, { label: string; emoji: string; minutes: number }> = {
  revision: { label: 'Révision', emoji: '🔁', minutes: 1 },
  puzzles: { label: 'Puzzles à ton niveau', emoji: '🧩', minutes: 1 },
  opening: { label: "Variante d'ouverture", emoji: '📖', minutes: 2 },
  endgame: { label: 'Finale à jouer', emoji: '🏁', minutes: 4 },
  attack: { label: "Position d'attaque", emoji: '⚔️', minutes: 5 },
}

// Budget visé : 12 minutes, jamais plus de 15 ; 10 au moins dès qu'un bloc long a un candidat.
export const BUDGET = { target: 12, min: 10, max: 15 } as const
export const REVISION_MAX = 4

// Révisions dues qu'une nouvelle séance reprend (les plus urgentes, choisies par
// buildReviewSession). L'accueil lit la même règle pour ne pas compter deux fois ces révisions.
export function revisionBlockSize(due: number): number {
  return Math.max(0, Math.min(due, REVISION_MAX))
}
export const PUZZLES_MIN = 3
export const PUZZLES_MAX = 6
// Poids des ouvertures à partir duquel une variante entre dans la séance même si le budget est atteint.
export const OPENING_THRESHOLD = 0.4
// Fenêtre de l'historique récent, en jours civils (aujourd'hui compris).
export const HISTORY_DAYS = 14
// Avec un rapport Insights, part de ses sévérités dans le poids (le reste vient de l'historique).
export const INSIGHTS_SHARE = 0.7

// ---------- Faiblesses ----------

export type Domain = 'tactics' | 'attack' | 'endgame' | 'opening'
export const DOMAINS: Domain[] = ['tactics', 'attack', 'endgame', 'opening']

// Faiblesses d'Insights (ids de computeInsights) rattachées aux domaines de la séance. Les ids
// préfixés (`ouverture-<famille>-<camp>`, `phase-<phase>`) se reconnaissent par préfixe.
const FINDING_DOMAIN: Record<string, Domain> = {
  gaffes: 'tactics',
  'pieces-en-prise': 'tactics',
  'menaces-ignorees': 'tactics',
  'tactiques-manquees': 'tactics',
  opportunisme: 'tactics',
  defense: 'tactics',
  'temps-pression': 'tactics',
  'defaites-au-temps': 'tactics',
  tendance: 'tactics',
  tilt: 'tactics',
  'phase-middlegame': 'tactics',
  'mats-manques': 'attack',
  attaque: 'attack',
  'phase-endgame': 'endgame',
  conversion: 'endgame',
  'phase-opening': 'opening',
  couleur: 'opening',
}

export function findingDomain(id: string): Domain | null {
  if (id.startsWith('ouverture-')) return 'opening'
  return FINDING_DOMAIN[id] ?? null
}

export type InsightsFinding = Pick<Finding, 'id' | 'title' | 'severity' | 'plan'>

// Ligne d'historique, au format `learnSessions` (seuls les champs lus).
export interface HistoryRow {
  date: number
  domain: string
  itemId: string
  success: 0 | 1
  outcome?: string
}

export interface DomainWeight {
  weight: number // [0, 1] : plus c'est haut, plus le domaine est à travailler
  n: number // tentatives des 14 derniers jours
  ok: number
  finding: InsightsFinding | null // faiblesse d'Insights la plus sévère du domaine
}

function historyDomain(row: HistoryRow): Domain | null {
  if (row.domain === 'tactic' || (row.domain === 'revision' && row.itemId.startsWith('puzzle:'))) return 'tactics'
  if (row.domain === 'attack') return row.outcome === 'abandon' ? null : 'attack'
  if (row.domain === 'endgame-play') return 'endgame'
  if (row.domain === 'opening-drill') return 'opening'
  return null
}

// Poids par domaine. Historique : 1 - (réussites + 1) / (tentatives + 2) sur les 14 derniers jours
// civils (lissage de Laplace : 0,5 sans données). Avec un rapport Insights (`findings` non nul),
// 70 % viennent de la sévérité de sa faiblesse la plus forte dans le domaine (0 sans faiblesse) :
// de vraies parties disent mieux où l'on pèche que des exercices.
export function domainWeights(
  input: { now: number; puzzles: { date: number; success: boolean }[]; sessions: HistoryRow[]; findings: InsightsFinding[] | null },
): Record<Domain, DomainWeight> {
  const from = addDays(startOfDay(input.now), -(HISTORY_DAYS - 1))
  const stats = Object.fromEntries(DOMAINS.map((d) => [d, { n: 0, ok: 0 }])) as Record<Domain, { n: number; ok: number }>
  for (const a of input.puzzles) {
    if (a.date < from || a.date > input.now) continue
    stats.tactics.n++
    if (a.success) stats.tactics.ok++
  }
  for (const r of input.sessions) {
    if (r.date < from || r.date > input.now) continue
    const d = historyDomain(r)
    if (!d) continue
    stats[d].n++
    stats[d].ok += r.success
  }
  const best = new Map<Domain, InsightsFinding>()
  for (const f of input.findings ?? []) {
    const d = findingDomain(f.id)
    if (!d || !Number.isFinite(f.severity)) continue
    const cur = best.get(d)
    if (!cur || f.severity > cur.severity) best.set(d, f)
  }
  const out = {} as Record<Domain, DomainWeight>
  for (const d of DOMAINS) {
    const { n, ok } = stats[d]
    const hist = 1 - (ok + 1) / (n + 2)
    const finding = best.get(d) ?? null
    const ins = finding ? Math.max(0, Math.min(1, finding.severity)) : 0
    const weight = input.findings ? INSIGHTS_SHARE * ins + (1 - INSIGHTS_SHARE) * hist : hist
    out[d] = { weight: Math.round(weight * 1000) / 1000, n, ok, finding }
  }
  return out
}

// Thème lichess de la faiblesse tactique la plus sévère qui en propose un (séance Tactiques ciblée
// de son plan), ou null.
export function tacticTheme(findings: InsightsFinding[] | null): string | null {
  const tactical = (findings ?? []).filter((f) => findingDomain(f.id) === 'tactics').sort((a, b) => b.severity - a.severity)
  for (const f of tactical) {
    const theme = f.plan.find((p) => p.state?.tactic)?.state?.tactic
    if (theme) return theme
  }
  return null
}

// Familles d'ouvertures signalées par Insights (`ouverture-<famille>-<camp>`), de la plus sévère
// à la moins sévère. La clé de famille peut contenir des tirets : le camp est le dernier segment.
export function weakOpenings(findings: InsightsFinding[] | null): { family: string; color: 'w' | 'b' }[] {
  return (findings ?? [])
    .filter((f) => f.id.startsWith('ouverture-'))
    .sort((a, b) => b.severity - a.severity)
    .map((f) => {
      const rest = f.id.slice('ouverture-'.length)
      const color = rest.slice(rest.lastIndexOf('-') + 1)
      return { family: rest.slice(0, rest.lastIndexOf('-')), color: color as 'w' | 'b' }
    })
    .filter((o) => o.family !== '' && (o.color === 'w' || o.color === 'b'))
}

// ---------- Planificateur ----------

export interface VariantCandidate {
  key: string // `<w|b>:<UCI>` (variantKey de revision.ts)
  last: number // dernière tentative en mode `full` (0 : jamais tentée)
  family: string | null // famille signalée par Insights d'où vient le candidat, sinon null
}

export interface PlanInput {
  now: number
  due: { kind: ReviewKind; key: string }[] // file de révision due, items résolus, du plus en retard au moins en retard
  puzzleRating: number
  puzzles: { date: number; success: boolean }[] // puzzleAttempts
  sessions: HistoryRow[] // learnSessions
  findings: InsightsFinding[] | null // faiblesses candidates du rapport Insights en cache, null sans rapport
  attacks: { id: string; solved: boolean }[]
  endgames: { id: string; solved: boolean }[]
  variants: VariantCandidate[] // variantes ratées (dernière tentative `full` échouée) ou d'une famille signalée, non maîtrisées
  puzzlesAvailable?: boolean // false : puzzles.json ne charge pas, aucun bloc puzzles (vrai par défaut)
}

export interface PlannedBlock {
  kind: BlockKind
  count: number // étapes du bloc
  reason: string
  // Paramètre propre au type : thème lichess (puzzles), id de la position (attack, endgame),
  // clé de variante `<w|b>:<UCI>` (opening).
  ref?: string
}

export interface SeancePlan {
  blocks: PlannedBlock[]
  minutes: number
  weights: Record<Domain, DomainWeight>
}

const plural = (n: number, one: string, many: string) => `${n} ${n > 1 ? many : one}`

function reasonFor(w: DomainWeight): string {
  if (w.finding) return `Point faible d'après Insights : ${w.finding.title}`
  if (w.n > 0) return `${plural(w.ok, 'réussite', 'réussites')} sur ${w.n} ces ${HISTORY_DAYS} derniers jours`
  return `Pas travaillé ces ${HISTORY_DAYS} derniers jours`
}

function pickOne<T extends { solved: boolean }>(items: T[], rng: () => number): T | null {
  const fresh = items.filter((i) => !i.solved)
  const pool = fresh.length ? fresh : items
  return pool.length ? pool[Math.min(pool.length - 1, Math.floor(rng() * pool.length))] : null
}

// Plan de la séance. Composition (minutes de BLOCK_META) :
// 1. révision : les items dus, 4 au plus ;
// 2. bloc long : attaque ou finale, le domaine de poids le plus fort (égalité : attaque), parmi les
//    positions jamais réussies d'abord ;
// 3. variante : une variante ratée (ou d'une famille signalée par Insights), si le poids des
//    ouvertures atteint 0,4 ou si la séance resterait sous 10 minutes avec le minimum de puzzles ;
// 4. puzzles : de 3 à 6, de quoi viser 12 minutes, un de plus si la tactique est le domaine le
//    plus faible ; jamais au-delà de 15 minutes.
// Ordre d'affichage : révision, puzzles, variante, bloc long (le plus long en dernier).
export function planSeance(input: PlanInput, rng: () => number = Math.random): SeancePlan {
  const weights = domainWeights(input)
  let minutes = 0
  const add = (b: PlannedBlock) => {
    minutes += BLOCK_META[b.kind].minutes * b.count
    return b
  }

  const revisionCount = revisionBlockSize(input.due.length)
  const revision = revisionCount > 0
    ? add({ kind: 'revision', count: revisionCount, reason: input.due.length > revisionCount ? `${revisionCount} des ${input.due.length} éléments dus aujourd'hui` : `${plural(revisionCount, 'élément dû', 'éléments dus')} aujourd'hui` })
    : null

  const longOrder: ('attack' | 'endgame')[] = weights.endgame.weight > weights.attack.weight ? ['endgame', 'attack'] : ['attack', 'endgame']
  let long: PlannedBlock | null = null
  for (const kind of longOrder) {
    const chosen = pickOne(kind === 'attack' ? input.attacks : input.endgames, rng)
    if (!chosen) continue
    long = add({ kind, count: 1, ref: chosen.id, reason: reasonFor(weights[kind]) })
    break
  }

  const puzzlesOn = input.puzzlesAvailable !== false
  const due = new Set(input.due.filter((d) => d.kind === 'variant').map((d) => d.key))
  const variants = input.variants.filter((v) => !due.has(v.key))
  let opening: PlannedBlock | null = null
  const projected = minutes + (puzzlesOn ? PUZZLES_MIN * BLOCK_META.puzzles.minutes : 0)
  if (variants.length && (weights.opening.weight >= OPENING_THRESHOLD || projected < BUDGET.min)) {
    // Famille signalée par Insights d'abord, puis la variante ratée la plus récente.
    const flagged = weakOpenings(input.findings).map((o) => o.family)
    const rank = (v: VariantCandidate) => (v.family ? flagged.indexOf(v.family) : Infinity)
    const sorted = [...variants].sort((a, b) => rank(a) - rank(b) || b.last - a.last)
    const v = sorted[0]
    if (projected + BLOCK_META.opening.minutes <= BUDGET.max) {
      opening = add({ kind: 'opening', count: 1, ref: v.key, reason: v.family ? reasonFor(weights.opening) : 'Ratée à ta dernière tentative' })
    }
  }

  let puzzles: PlannedBlock | null = null
  if (puzzlesOn) {
    const top = DOMAINS.reduce((a, b) => (weights[b].weight > weights[a].weight ? b : a))
    let count = Math.max(PUZZLES_MIN, Math.min(PUZZLES_MAX, BUDGET.target - minutes))
    if (top === 'tactics') count = Math.min(PUZZLES_MAX, count + 1)
    count = Math.max(0, Math.min(count, BUDGET.max - minutes))
    const theme = tacticTheme(input.findings)
    if (count > 0) {
      puzzles = add({
        kind: 'puzzles',
        count,
        reason: theme ? `${puzzleThemeLabel(theme)} : point faible d'après Insights` : `Autour de ton classement (${input.puzzleRating})`,
        ...(theme ? { ref: theme } : {}),
      })
    }
  }

  const blocks = [revision, puzzles, opening, long].filter((b): b is PlannedBlock => b !== null)
  return { blocks, minutes, weights }
}

// ---------- Série de jours ----------

// Jours civils locaux consécutifs portant une séance terminée, jusqu'à aujourd'hui, ou jusqu'à
// hier si celle du jour n'est pas encore faite (`today` faux : la série est à prolonger).
export function streak(dates: number[], now = Date.now()): { days: number; today: boolean } {
  const days = new Set(dates.filter((d) => Number.isFinite(d) && d <= now).map(startOfDay))
  const today0 = startOfDay(now)
  const today = days.has(today0)
  let day = today ? today0 : addDays(today0, -1)
  let n = 0
  while (days.has(day)) {
    n++
    day = addDays(day, -1)
  }
  return { days: n, today }
}

export function streakLabel(days: number): string {
  return `🔥 ${plural(days, 'jour', 'jours')}`
}

// ---------- Temps et bilan ----------

// Une étape compte au plus 10 minutes : une pause, ou la PWA laissée en arrière-plan, ne gonfle
// pas le bilan.
export const STEP_CAP_MS = 10 * 60_000

export function stepDuration(start: number, end: number): number {
  return Math.max(0, Math.min(STEP_CAP_MS, end - start))
}

export function minutesLabel(ms: number): string {
  return `${Math.max(1, Math.round(ms / 60_000))} min`
}

export interface StepResult {
  idx: number // index de l'étape
  kind: BlockKind
  ok: boolean
  ms: number // durée comptée (plafonnée)
}

export interface BlockSummary {
  kind: BlockKind
  ok: number
  total: number // étapes jugées
  steps: number // étapes prévues
}

// Résumé par bloc, dans l'ordre de la séance : les étapes consécutives d'un même type forment un bloc.
export function summarize(kinds: BlockKind[], results: StepResult[]): BlockSummary[] {
  const out: BlockSummary[] = []
  kinds.forEach((kind, idx) => {
    let cur = out[out.length - 1]
    if (!cur || cur.kind !== kind) out.push((cur = { kind, ok: 0, total: 0, steps: 0 }))
    cur.steps++
    const r = results.find((x) => x.idx === idx)
    if (r) {
      cur.total++
      if (r.ok) cur.ok++
    }
  })
  return out
}

// Durée estimée d'une liste d'étapes (« ≈ 12 min »).
export function estimateMinutes(kinds: BlockKind[]): number {
  return kinds.reduce((s, k) => s + BLOCK_META[k].minutes, 0)
}
