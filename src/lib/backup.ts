// Sauvegarde/restauration complète des données locales (IndexedDB + réglages).
// Seul filet de l'utilisateur : ses données ne vivent que sur son appareil, et supprimer l'icône
// de la PWA efface tout. La restauration est la seule opération destructive de l'app, donc :
// validation du fichier ENTIER d'abord (inspectBackup, pur), puis UNE transaction Dexie.
import { db } from './db'
import { BOARD_THEMES, REVIEW_DEPTHS, useSettings } from '../store/settings'

// Version du format de fichier = version du schéma Dexie : une table ajoutée = nouveau bloc
// `db.version(n)` = nouvelle version de sauvegarde, avec son `since` dans SPECS.
export const BACKUP_VERSION = db.verno
export const MAX_BACKUP_BYTES = 50 * 1024 * 1024
const MAX_SETTING_STRING = 100 // un pseudo chess.com fait moins de 30 caractères
// Clé additive, hors sauvegarde et hors réglages : date du dernier export réussi.
const LAST_EXPORT_KEY = 'chess-local-last-export'
// Clés de l'app dans localStorage (le persist Zustand et la date du dernier export) et clé de la
// séance d'Apprendre dans sessionStorage : les seules que la réinitialisation a le droit de toucher.
const APP_LOCAL_KEYS = ['chess-local-settings', LAST_EXPORT_KEY]
const LEARN_SESSION_KEY = 'learn-session-v1'

export const TABLES = ['games', 'ratings', 'puzzleAttempts', 'rushScores', 'mistakes', 'learnSessions'] as const
export type TableName = (typeof TABLES)[number]
export type Counts = Record<TableName, number>
type Row = Record<string, unknown>

const isStr = (v: unknown): v is string => typeof v === 'string'
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isPlain = (v: unknown): v is Row => typeof v === 'object' && v !== null && !Array.isArray(v)

interface TableSpec {
  since: number // version du schéma qui introduit la table : absente d'un fichier plus ancien, elle est vidée
  pk: string
  labels: [string, string] // singulier, pluriel
  valid: (r: Row) => boolean // forme minimale : les champs présents depuis la création de la table
}

const SPECS: Record<TableName, TableSpec> = {
  games: { since: 1, pk: 'id', labels: ['partie', 'parties'], valid: (r) => isStr(r.pgn) && isNum(r.date) },
  ratings: {
    since: 1,
    pk: 'key',
    labels: ['classement', 'classements'],
    valid: (r) => isStr(r.key) && r.key !== '' && isNum(r.value) && isNum(r.games),
  },
  puzzleAttempts: {
    since: 1,
    pk: 'id',
    labels: ['puzzle tenté', 'puzzles tentés'],
    valid: (r) => isStr(r.puzzleId) && isNum(r.date),
  },
  rushScores: { since: 1, pk: 'id', labels: ['score Rush', 'scores Rush'], valid: (r) => isNum(r.score) && isNum(r.date) },
  mistakes: {
    since: 2,
    pk: 'id',
    labels: ['erreur à revoir', 'erreurs à revoir'],
    valid: (r) => isStr(r.fenBefore) && isStr(r.bestUci),
  },
  learnSessions: {
    since: 2,
    pk: 'id',
    labels: ['séance Apprendre', 'séances Apprendre'],
    valid: (r) => isStr(r.domain) && isStr(r.itemId),
  },
}

export function countLabel(t: TableName, n: number): string {
  return `${n} ${SPECS[t].labels[n > 1 ? 1 : 0]}`
}

export function tableLabel(t: TableName): string {
  return SPECS[t].labels[1]
}

// « 12 parties, 5 classements et 30 puzzles tentés » : seulement les tables non vides.
export function describeCounts(counts: Counts, tables: readonly TableName[] = TABLES): string {
  const parts = tables.filter((t) => counts[t] > 0).map((t) => countLabel(t, counts[t]))
  if (parts.length === 0) return 'aucune donnée'
  if (parts.length === 1) return parts[0]
  return `${parts.slice(0, -1).join(', ')} et ${parts[parts.length - 1]}`
}

export async function currentCounts(): Promise<Counts> {
  const counts = {} as Counts
  for (const t of TABLES) counts[t] = await db.table(t).count()
  return counts
}

// ---------- Export ----------

// Lecture des six tables dans UNE transaction : l'instantané est cohérent même si une écriture
// (fin de partie, puzzle, restauration) arrive pendant l'export. Les comptes viennent des
// tableaux lus : aucune requête de plus avant la feuille de partage.
export async function exportBackup(): Promise<{ json: string; counts: Counts }> {
  const data: Record<string, unknown> = { _app: 'chess-local', _version: BACKUP_VERSION, _date: new Date().toISOString() }
  const counts = {} as Counts
  await db.transaction('r', TABLES.map((t) => db.table(t)), async () => {
    for (const t of TABLES) {
      const rows: unknown[] = await db.table(t).toArray()
      data[t] = rows
      counts[t] = rows.length
    }
  })
  data.settings = localStorage.getItem(useSettings.persist.getOptions().name ?? 'chess-local-settings')
  return { json: JSON.stringify(data), counts }
}

// Nom daté en heure LOCALE (toISOString est en UTC : entre 0 h et 2 h, c'était encore la veille).
export function backupFileName(d = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `chesslocal-sauvegarde-${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}.json`
}

// shared / downloaded : le fichier est sorti ; cancelled : l'utilisateur a fermé la feuille de
// partage ; failed : le partage a été refusé (activation utilisateur expirée, par exemple).
export type SaveOutcome = 'shared' | 'downloaded' | 'cancelled' | 'failed'

// Partage du fichier. À appeler SANS await préalable dans un gestionnaire de tap : WebKit exige
// une activation utilisateur encore fraîche.
function shareFile(file: File): Promise<SaveOutcome> {
  return navigator.share({ files: [file] }).then(
    () => 'shared' as const,
    (err: unknown) => {
      if ((err as DOMException).name === 'AbortError') return 'cancelled'
      console.error('partage de la sauvegarde refusé', err)
      return 'failed'
    },
  )
}

// Sort le fichier de l'app. En PWA iOS standalone il n'y a pas de gestionnaire de
// téléchargements : la feuille de partage (Enregistrer dans Fichiers, AirDrop, Mail) est le
// seul chemin fiable, et un repli vers un lien de téléchargement y serait un faux succès. Sans
// feuille de partage (bureau), lien attaché au DOM, blob révoqué plus tard.
export function saveBackupFile(file: File): Promise<SaveOutcome> {
  if (navigator.canShare?.({ files: [file] })) return shareFile(file)
  const url = URL.createObjectURL(file)
  const a = document.createElement('a')
  a.href = url
  a.download = file.name
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    a.remove()
    URL.revokeObjectURL(url)
  }, 60_000)
  return Promise.resolve('downloaded')
}

export interface LastExport {
  at: number
  games: number
}

export function readLastExport(): LastExport | null {
  try {
    const v: unknown = JSON.parse(localStorage.getItem(LAST_EXPORT_KEY) ?? 'null')
    return isPlain(v) && isNum(v.at) && isNum(v.games) ? { at: v.at, games: v.games } : null
  } catch {
    return null
  }
}

function recordExport(games: number) {
  localStorage.setItem(LAST_EXPORT_KEY, JSON.stringify({ at: Date.now(), games } satisfies LastExport))
}

export interface ExportResult {
  outcome: SaveOutcome
  counts: Counts
  file: File // gardé pour un nouvel essai de partage synchrone
}

// Exporte tout et mémorise la date, seulement si le fichier est vraiment sorti.
export async function runExport(): Promise<ExportResult> {
  const { json, counts } = await exportBackup()
  const file = new File([json], backupFileName(), { type: 'application/json' })
  const outcome = await saveBackupFile(file)
  if (outcome === 'shared' || outcome === 'downloaded') recordExport(counts.games)
  return { outcome, counts, file }
}

// Nouvel essai après un partage refusé : rien d'asynchrone avant `share()`.
export function retryShare(file: File, games: number): Promise<SaveOutcome> {
  return shareFile(file).then((outcome) => {
    if (outcome === 'shared') recordExport(games)
    return outcome
  })
}

// true : le navigateur s'engage à ne pas purger ; false : purge possible ; null : API absente.
// Lecture seule : la demande `persist()` est faite au démarrage (main.tsx).
export async function storageProtected(): Promise<boolean | null> {
  try {
    return navigator.storage?.persisted ? await navigator.storage.persisted() : null
  } catch {
    return null
  }
}

// ---------- Restauration ----------

export type SettingsFate = 'restored' | 'absent' | 'unreadable'
type SettingsValues = Record<string, unknown>

export interface BackupPlan {
  version: number
  date: number | null // horodatage de la sauvegarde, null si absent ou illisible
  rows: Record<TableName, Row[]>
  counts: Counts
  missingTables: TableName[] // tables inconnues du format du fichier : elles seront VIDÉES
  settings: SettingsFate
  settingsState: SettingsValues | null // réglages nettoyés, prêts pour useSettings.setState
}

const FORBIDDEN_KEYS = new Set(['__proto__', 'constructor', 'prototype'])

// Valeurs par défaut du store, sans ses actions.
function settingsDefaults(): SettingsValues {
  const out: SettingsValues = {}
  for (const [k, v] of Object.entries(useSettings.getInitialState())) if (typeof v !== 'function') out[k] = v
  return out
}

// Ne garde que les réglages connus du store, du bon type, de taille raisonnable et parmi les
// valeurs que l'interface sait afficher : un blob abîmé ou trafiqué ne peut ni écraser une action
// (`setTheme: "x"`), ni poser un thème ou une profondeur inconnus, ni saturer le localStorage.
// Retourne null si le blob n'est pas lisible.
function cleanSettings(raw: unknown): SettingsValues | null {
  if (!isStr(raw)) return null
  let blob: unknown
  try {
    blob = JSON.parse(raw)
  } catch {
    return null
  }
  if (!isPlain(blob) || !isPlain(blob.state)) return null
  const defaults = settingsDefaults()
  const state: SettingsValues = { ...defaults }
  for (const k of Object.keys(defaults)) {
    const v = blob.state[k]
    if (typeof v !== typeof defaults[k]) continue
    if (isStr(v) && v.length > MAX_SETTING_STRING) continue
    state[k] = v
  }
  if (!BOARD_THEMES.some((t) => t.id === state.themeId)) state.themeId = defaults.themeId
  if (!Object.hasOwn(REVIEW_DEPTHS, String(state.reviewDepth))) state.reviewDepth = defaults.reviewDepth
  return state
}

// Valide le fichier ENTIER sans toucher à la base. Lève une Error au message français,
// affichable tel quel. Tout refus ici garantit que rien n'a changé.
export function inspectBackup(json: string): BackupPlan {
  if (json.length > MAX_BACKUP_BYTES) throw new Error('Fichier trop volumineux : 50 Mo maximum.')
  let data: unknown
  let forbidden = ''
  try {
    data = JSON.parse(json, (k, v: unknown) => {
      if (FORBIDDEN_KEYS.has(k)) forbidden = k
      return v
    })
  } catch {
    throw new Error("Fichier illisible : ce n'est pas un JSON valide (fichier tronqué ou abîmé ?).")
  }
  if (forbidden) throw new Error(`Sauvegarde refusée : elle contient une clé interdite (« ${forbidden} »).`)
  if (!isPlain(data) || data._app !== 'chess-local') throw new Error("Ce fichier n'est pas une sauvegarde ChessLocal.")
  const version = data._version
  if (!isNum(version) || !Number.isInteger(version) || version < 1) {
    throw new Error('Sauvegarde refusée : sa version est absente ou illisible.')
  }
  if (version > BACKUP_VERSION) {
    throw new Error("Cette sauvegarde vient d'une version plus récente de ChessLocal. Mets l'app à jour, puis réessaie.")
  }

  const rows = {} as Record<TableName, Row[]>
  const counts = {} as Counts
  const missingTables: TableName[] = []
  for (const t of TABLES) {
    const spec = SPECS[t]
    const list = data[t]
    if (list === undefined && spec.since > version) {
      missingTables.push(t)
      rows[t] = []
      counts[t] = 0
      continue
    }
    if (!Array.isArray(list)) throw new Error(`Sauvegarde incomplète ou abîmée : la liste « ${spec.labels[1]} » est absente ou illisible.`)
    const seen = new Set<unknown>()
    let withId = 0
    list.forEach((r: unknown, i) => {
      const where = `Sauvegarde abîmée (« ${spec.labels[1]} », ligne ${i + 1})`
      if (!isPlain(r) || !spec.valid(r)) throw new Error(`${where} : forme inattendue.`)
      const key = r[spec.pk]
      if (spec.pk === 'id' && key === undefined) return
      if (spec.pk === 'id' && !(isNum(key) && Number.isInteger(key) && key > 0)) throw new Error(`${where} : identifiant invalide.`)
      if (seen.has(key)) throw new Error(`${where} : identifiant en double.`)
      seen.add(key)
      withId++
    })
    // Tout ou rien par table : mêlées à des lignes numérotées, des lignes sans identifiant
    // recevraient un numéro déjà pris et feraient échouer la transaction après validation.
    if (spec.pk === 'id' && withId > 0 && withId < list.length) {
      throw new Error(`Sauvegarde abîmée (« ${spec.labels[1]} ») : identifiants incohérents (certaines lignes n'en ont pas).`)
    }
    rows[t] = list as Row[]
    counts[t] = list.length
  }
  // Une sauvegarde vide ne doit jamais servir de bouton « tout effacer » : il y a Réinitialiser pour ça.
  if (TABLES.every((t) => counts[t] === 0)) throw new Error('Cette sauvegarde est vide : rien à restaurer.')

  const at = isStr(data._date) ? Date.parse(data._date) : NaN
  const settingsState = cleanSettings(data.settings)
  const settings: SettingsFate = settingsState ? 'restored' : data.settings == null ? 'absent' : 'unreadable'
  return { version, date: Number.isNaN(at) ? null : at, rows, counts, missingTables, settings, settingsState }
}

export interface ImportResult {
  counts: Counts // recomptés en base après la transaction : le succès annoncé est mesuré, pas déduit
  settingsApplied: boolean
}

// Applique un plan validé : TOUTES les tables sont remplacées dans une seule transaction (une
// table absente d'une ancienne sauvegarde est vidée : jamais d'état mixte). Au moindre échec
// Dexie annule tout. Les réglages passent ensuite par le store lui-même : le middleware persist
// écrit le blob, et le store en mémoire ne réécrira plus l'ancien état au premier réglage touché.
export async function importBackup(plan: BackupPlan): Promise<ImportResult> {
  try {
    await db.transaction('rw', TABLES.map((t) => db.table(t)), async () => {
      for (const t of TABLES) {
        await db.table(t).clear()
        await db.table(t).bulkAdd(plan.rows[t])
      }
    })
  } catch (err) {
    console.error('restauration annulée', err)
    const name = err instanceof Error ? ` (${err.name})` : ''
    throw new Error(`La restauration a échoué${name} : rien n'a été modifié, tes données actuelles sont intactes.`)
  }
  // La séance d'Apprendre en cours pourrait pointer vers des erreurs disparues. On ne retire que
  // sa clé : l'origine GitHub Pages est partagée par tous les sites du compte, un clear() global
  // effacerait le stockage d'autres projets.
  sessionStorage.removeItem(LEARN_SESSION_KEY)
  let settingsApplied = false
  if (plan.settingsState) {
    try {
      useSettings.setState(plan.settingsState as Partial<ReturnType<typeof useSettings.getState>>)
      settingsApplied = true
    } catch (err) {
      console.error('réglages non appliqués', err)
    }
  }
  return { counts: await currentCounts(), settingsApplied }
}

// Sortie de secours : efface TOUT sur cet appareil (données, réglages, date d'export) puis
// redémarre l'app. Les tables sont vidées depuis notre propre connexion, déjà ouverte : rien ne
// peut bloquer, alors qu'un `deleteDatabase` attendrait qu'un autre onglet ferme la base et
// ferait patienter derrière lui toute réouverture. Le service worker et ses caches sont gardés :
// ils portent le code, pas les données, et sans eux la PWA ne démarrerait plus hors ligne.
export async function resetApp(): Promise<void> {
  await db.transaction('rw', TABLES.map((t) => db.table(t)), async () => {
    for (const t of TABLES) await db.table(t).clear()
  })
  // Seulement les clés de l'app, jamais clear() : l'origine GitHub Pages est partagée par tous les
  // sites du compte.
  for (const key of APP_LOCAL_KEYS) localStorage.removeItem(key)
  sessionStorage.removeItem(LEARN_SESSION_KEY)
  location.hash = '#/'
  location.reload()
}
