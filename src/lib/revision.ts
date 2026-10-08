// Révision espacée commune : ce qui a été raté (puzzles, fautes de parties, variantes
// d'ouverture) revient selon une échelle de Leitner à intervalles fixes. Sans React, et sans
// table dédiée : l'échéance de chaque item se calcule depuis son historique daté dans les tables
// existantes, et un résultat de révision s'écrit là où l'écran d'origine écrit déjà.
import { db, type LearnSession, type Mistake } from './db'
import { scoreItem } from './learn'
import {
  DRILL_DOMAIN, familyKey, families, getFamily, popularFamilies, recordDrill, type Color, type Family, type Variant,
} from './openingTrainer'
import { openingFr } from './openingNames'
import { loadPuzzles } from './puzzles'
import openingsData from '../data/openings.json'
import type { PuzzleData } from '../components/PuzzlePlayer'

export type ReviewKind = 'puzzle' | 'mistake' | 'variant'

// Lignes `learnSessions` propres à la révision : les puzzles revus (`puzzle:<id>`), seuls items
// sans journal de tentatives hors Elo (puzzleAttempts est celui des puzzles classés).
export const REVISION_DOMAIN = 'revision'

// Leitner plutôt que SM-2 : les verdicts sont binaires partout (puzzle, drill, faute vérifiée
// par Stockfish), et rien n'est stocké par item. Boîte = jours de réussite consécutifs depuis le
// dernier jour d'échec ; une réussite en dernière boîte sort l'item de la file (acquis), un échec
// le ramène en première boîte.
export const LADDER_DAYS = [1, 3, 7, 21] as const
// Un item en retard de plus d'un mois sort de la file : un historique de mois de puzzles ratés ne
// doit pas former un arriéré de centaines d'items à l'activation, ni au retour d'une longue pause.
export const MAX_OVERDUE_DAYS = 30
export const SESSION_MAX = 8
const DAY = 86_400_000

export interface ReviewEvent {
  date: number
  success: boolean
}

export interface ReviewItem {
  kind: ReviewKind
  // puzzle : id lichess ; mistake : id de la ligne `mistakes` ; variant : `<w|b>:<UCI>`.
  key: string
  box: number
  due: number // minuit local du jour d'échéance
  last: number // date du dernier événement
}

export interface ReviewQueue {
  due: ReviewItem[] // échéance aujourd'hui ou avant, du plus en retard au moins en retard
  upcoming: ReviewItem[] // échéance future, de la plus proche à la plus lointaine
}

export function startOfDay(ms: number): number {
  const d = new Date(ms)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

// Jours civils locaux (setDate, pas des multiples de 86 400 000 ms : la nuit du passage à l'heure
// d'été compte 23 h, et un minuit calculé en millisecondes tomberait à 1 h du matin).
export function addDays(dayStart: number, days: number): number {
  const d = new Date(dayStart)
  d.setDate(d.getDate() + days)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

export function daysBetween(fromDayStart: number, toDayStart: number): number {
  return Math.round((toDayStart - fromDayStart) / DAY)
}

// Échéance d'un item depuis ses événements, ou null : jamais raté, ou acquis.
// Les événements sont agrégés par jour civil local : un jour avec un échec vaut un échec, un jour
// de réussites seules vaut une réussite. Sinon un réessai réussi dans la minute (le trainer en
// écrit un en mode variante) ou trois séances le même jour feraient monter les boîtes sans aucun
// espacement. Les dates invalides sont ignorées, les dates futures ramenées à maintenant.
export function schedule(events: ReviewEvent[], now = Date.now()): { box: number; due: number; last: number } | null {
  const byDay = new Map<number, { failed: boolean; last: number }>()
  for (const e of events) {
    if (!Number.isFinite(e.date)) continue
    const date = Math.min(e.date, now)
    const day = startOfDay(date)
    const cur = byDay.get(day)
    if (cur) {
      cur.failed ||= !e.success
      cur.last = Math.max(cur.last, date)
    } else byDay.set(day, { failed: !e.success, last: date })
  }
  const days = [...byDay.entries()].sort((a, b) => a[0] - b[0])
  let lastFail = -1
  days.forEach(([, d], i) => {
    if (d.failed) lastFail = i
  })
  if (lastFail === -1) return null
  const box = days.length - 1 - lastFail
  if (box >= LADDER_DAYS.length) return null
  const [lastDay, lastInfo] = days[days.length - 1]
  return { box, due: addDays(lastDay, LADDER_DAYS[box]), last: lastInfo.last }
}

// ---------- Variantes (openings.json, familles de l'entraîneur) ----------

const LINE_BY_UCI = new Map((openingsData as { eco: string; name: string; uci: string }[]).map((o) => [o.uci, o]))

export interface ResolvedVariant {
  fam: Family
  variant: Variant
  color: Color
}

export function variantKey(color: Color, uci: string): string {
  return `${color}:${uci}`
}

// Une variante n'est connue que si une famille la compte parmi ses feuilles : une base régénérée
// peut laisser des tentatives orphelines (gardées, jamais révisées). Une ligne peut appartenir à
// deux familles (la Londres est construite par nom) : familles populaires d'abord (la Londres
// avant « Partie du pion dame »), puis celle du nom lichess, puis les autres.
export function resolveVariant(key: string): ResolvedVariant | null {
  const color = key[0]
  const uci = key.slice(2)
  if ((color !== 'w' && color !== 'b') || key[1] !== ':' || !uci) return null
  const line = LINE_BY_UCI.get(uci)
  if (!line) return null
  const own = getFamily(familyKey(line.name))
  const candidates = [...popularFamilies(), ...(own ? [own] : []), ...families().values()]
  for (const fam of candidates) {
    const variant = fam.variants.find((v) => v.line.uci === uci)
    if (variant) return { fam, variant, color }
  }
  return null
}

// ---------- File de révision ----------

function push<K>(map: Map<K, ReviewEvent[]>, key: K, event: ReviewEvent) {
  const list = map.get(key)
  if (list) list.push(event)
  else map.set(key, [event])
}

// Événements par item, toutes sources confondues :
// - puzzles : `puzzleAttempts` (« Passer » y vaut échec : le puzzle n'a pas été résolu), séances
//   Apprendre Tactiques (`itemId` = id) et Stratégie (`<carte>:<id>`), lignes `revision` (`puzzle:<id>`) ;
// - fautes : création de la ligne `mistakes` (échec initial) + lignes `mistakes` d'Apprendre ;
// - variantes : lignes `opening-drill` du mode `full` (comme l'état « Maîtrisée / À revoir »).
function collectEvents(
  attempts: { puzzleId: string; date: number; success: boolean }[],
  sessions: LearnSession[],
  mistakes: Mistake[],
): { puzzles: Map<string, ReviewEvent[]>; mistakes: Map<number, ReviewEvent[]>; variants: Map<string, ReviewEvent[]> } {
  const puzzles = new Map<string, ReviewEvent[]>()
  const byMistake = new Map<number, ReviewEvent[]>()
  const variants = new Map<string, ReviewEvent[]>()
  for (const a of attempts) push(puzzles, a.puzzleId, { date: a.date, success: a.success })
  for (const s of sessions) {
    const event = { date: s.date, success: s.success === 1 }
    if (s.domain === 'tactic') push(puzzles, s.itemId, event)
    else if (s.domain === 'strategy') push(puzzles, s.itemId.slice(s.itemId.lastIndexOf(':') + 1), event)
    else if (s.domain === REVISION_DOMAIN && s.itemId.startsWith('puzzle:')) push(puzzles, s.itemId.slice('puzzle:'.length), event)
    else if (s.domain === 'mistakes' && /^\d+$/.test(s.itemId)) push(byMistake, Number(s.itemId), event)
    else if (s.domain === DRILL_DOMAIN && s.itemId.startsWith('full:')) push(variants, s.itemId.slice('full:'.length), event)
  }
  const out = new Map<number, ReviewEvent[]>()
  for (const m of mistakes) {
    if (m.id === undefined) continue
    out.set(m.id, [{ date: m.date, success: false }, ...(byMistake.get(m.id) ?? [])])
  }
  return { puzzles, mistakes: out, variants }
}

const byUrgency = (a: ReviewItem, b: ReviewItem) => a.due - b.due || a.last - b.last

// Tout ce qui est en révision, séparé entre dû (aujourd'hui ou avant, et depuis moins de
// MAX_OVERDUE_DAYS) et à venir. Ne charge jamais puzzles.json : seuls IndexedDB et openings.json
// (bundlé) sont lus, et les familles d'ouvertures ne sont construites que s'il y a une variante
// ratée à placer.
export async function loadReviewQueue(now = Date.now()): Promise<ReviewQueue> {
  const [attempts, sessions, mistakes] = await Promise.all([db.puzzleAttempts.toArray(), db.learnSessions.toArray(), db.mistakes.toArray()])
  const events = collectEvents(attempts, sessions, mistakes)
  const items: ReviewItem[] = []
  const add = (kind: ReviewKind, key: string, list: ReviewEvent[], known: () => boolean = () => true) => {
    const s = schedule(list, now)
    if (s && known()) items.push({ kind, key, ...s })
  }
  for (const [id, list] of events.puzzles) add('puzzle', id, list)
  for (const [id, list] of events.mistakes) add('mistake', String(id), list)
  for (const [key, list] of events.variants) add('variant', key, list, () => resolveVariant(key) !== null)
  const today = startOfDay(now)
  const horizon = addDays(today, -MAX_OVERDUE_DAYS)
  return {
    due: items.filter((i) => i.due <= today && i.due >= horizon).sort(byUrgency),
    upcoming: items.filter((i) => i.due > today).sort(byUrgency),
  }
}

// Séance : les items dus entrelacés par type (puzzle, faute, variante), chaque type du plus en
// retard au moins en retard, le type le plus en retard en premier. Courte : SESSION_MAX items.
export function buildReviewSession(due: ReviewItem[], max = SESSION_MAX): ReviewItem[] {
  const groups = new Map<ReviewKind, ReviewItem[]>()
  for (const item of [...due].sort(byUrgency)) {
    const g = groups.get(item.kind)
    if (g) g.push(item)
    else groups.set(item.kind, [item])
  }
  const queues = [...groups.values()] // ordre d'insertion = ordre des têtes, du plus en retard
  const out: ReviewItem[] = []
  for (let i = 0; out.length < max && queues.some((q) => i < q.length); i++) {
    for (const q of queues) if (i < q.length && out.length < max) out.push(q[i])
  }
  return out
}

// ---------- Contenu des items ----------

export type ReviewPayload =
  | { kind: 'puzzle'; item: ReviewItem; puzzle: PuzzleData }
  | { kind: 'mistake'; item: ReviewItem; mistake: Mistake }
  | { kind: 'variant'; item: ReviewItem; color: Color; uci: string; label: string }

// Charge le contenu des items (puzzles.json seulement s'il y a des puzzles). À appeler sur toute
// la file due, avant de composer la séance : un item introuvable (puzzle disparu de la base,
// faute supprimée, variante orpheline) est écarté et compté dans `missing`, et ne doit pas
// occuper une place de la séance ; si puzzles.json ne charge pas, les puzzles sont écartés et
// `puzzlesUnavailable` le dit.
export async function resolveSession(items: ReviewItem[]): Promise<{ payloads: ReviewPayload[]; missing: number; puzzlesUnavailable: boolean }> {
  let puzzles: Map<string, PuzzleData> | null = null
  let puzzlesUnavailable = false
  if (items.some((i) => i.kind === 'puzzle')) {
    try {
      puzzles = new Map((await loadPuzzles()).map((p) => [p.id, p]))
    } catch {
      puzzlesUnavailable = true
    }
  }
  const payloads: ReviewPayload[] = []
  let missing = 0
  for (const item of items) {
    if (item.kind === 'puzzle') {
      const puzzle = puzzles?.get(item.key)
      if (puzzle) payloads.push({ kind: 'puzzle', item, puzzle })
      else if (!puzzlesUnavailable) missing++
    } else if (item.kind === 'mistake') {
      const mistake = await db.mistakes.get(Number(item.key))
      if (mistake) payloads.push({ kind: 'mistake', item, mistake })
      else missing++
    } else {
      const resolved = resolveVariant(item.key)
      if (resolved) payloads.push({ kind: 'variant', item, color: resolved.color, uci: resolved.variant.line.uci, label: openingFr(resolved.variant.line.name) })
      else missing++
    }
  }
  return { payloads, missing, puzzlesUnavailable }
}

// Écrit le résultat là où l'écran d'origine écrit, sans toucher aucun Elo : « Mes erreurs » et
// l'entraîneur d'ouvertures voient la révision ; les puzzles classés (Elo, série) l'ignorent.
// Une faute ratée en révision redevient pendante dans « Mes erreurs » (solved 0), même si elle
// avait été classée.
export async function recordReview(p: ReviewPayload, success: boolean): Promise<void> {
  if (p.kind === 'puzzle') {
    await db.learnSessions.add({ date: Date.now(), domain: REVISION_DOMAIN, itemId: `puzzle:${p.puzzle.id}`, success: success ? 1 : 0, ratingAfter: null })
  } else if (p.kind === 'mistake') {
    // Même écriture que `finishItem` de Learn.tsx (ratingKey nul : aucun Elo).
    await scoreItem('mistakes', String(p.mistake.id), success, 0)
    await db.mistakes.update(p.mistake.id!, { attempts: p.mistake.attempts + 1, solved: success ? 1 : 0 })
  } else {
    await recordDrill('full', p.color, p.uci.split(' '), success)
  }
}

// ---------- Libellés ----------

const KIND_LABEL: Record<ReviewKind, [string, string]> = {
  puzzle: ['puzzle', 'puzzles'],
  mistake: ['erreur', 'erreurs'],
  variant: ['variante', 'variantes'],
}

// « 3 puzzles · 1 erreur · 1 variante » (types présents seulement).
export function describeKinds(items: ReviewItem[]): string {
  return (['puzzle', 'mistake', 'variant'] as ReviewKind[])
    .map((k) => [k, items.filter((i) => i.kind === k).length] as const)
    .filter(([, n]) => n > 0)
    .map(([k, n]) => `${n} ${KIND_LABEL[k][n > 1 ? 1 : 0]}`)
    .join(' · ')
}

// Prochain passage après un résultat : boîte d'arrivée 0 à 3, ou acquis (null).
function nextIntervalLabel(boxAfter: number): string | null {
  if (boxAfter >= LADDER_DAYS.length) return null
  return intervalLabel(LADDER_DAYS[boxAfter])
}

// « demain », « dans N jours », avec « une semaine » et « trois semaines » comme cas particuliers.
export function intervalLabel(days: number): string {
  if (days <= 1) return 'demain'
  if (days === 7) return 'dans une semaine'
  if (days === 21) return 'dans trois semaines'
  return `dans ${days} jours`
}

// « Revient demain », « Revient dans 3 jours », « Acquis : ne reviendra plus ».
export function returnLabel(boxAfter: number): string {
  const l = nextIntervalLabel(boxAfter)
  return l ? `Revient ${l}` : 'Acquis : ne reviendra plus'
}

// Échéance d'un item à venir, en jours civils : « demain », « dans 5 jours ».
export function dueLabel(due: number, now = Date.now()): string {
  return intervalLabel(Math.max(1, daysBetween(startOfDay(now), due)))
}

// « aujourd'hui », « hier », « il y a 5 jours ».
export function agoLabel(date: number, now = Date.now()): string {
  const days = daysBetween(startOfDay(date), startOfDay(now))
  return days <= 0 ? "aujourd'hui" : days === 1 ? 'hier' : `il y a ${days} jours`
}

// Ligne d'état d'un item : « Raté il y a 10 jours · étape 1/4 », « Réussi hier · étape 2/4 ».
export function statusLabel(item: ReviewItem, now = Date.now()): string {
  return `${item.box === 0 ? 'Raté' : 'Réussi'} ${agoLabel(item.last, now)} · étape ${item.box + 1}/${LADDER_DAYS.length}`
}
