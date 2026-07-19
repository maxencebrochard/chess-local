// Sauvegarde/restauration complète des données locales (IndexedDB + réglages).
// Filet de sécurité contre toute purge de stockage par iOS/Safari.
import { db } from './db'

const TABLES = ['games', 'ratings', 'puzzleAttempts', 'rushScores', 'mistakes', 'learnSessions'] as const

export async function exportBackup(): Promise<string> {
  const data: Record<string, unknown> = { _app: 'chess-local', _version: 2, _date: new Date().toISOString() }
  for (const t of TABLES) {
    data[t] = await db.table(t).toArray()
  }
  data.settings = localStorage.getItem('chess-local-settings')
  return JSON.stringify(data)
}

export function downloadBackup(json: string) {
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `chesslocal-sauvegarde-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// Restaure une sauvegarde. Remplace les données existantes table par table.
export async function importBackup(json: string): Promise<void> {
  const data = JSON.parse(json) as Record<string, unknown>
  if (data._app !== 'chess-local') throw new Error("Ce fichier n'est pas une sauvegarde ChessLocal.")
  await db.transaction('rw', TABLES.map((t) => db.table(t)), async () => {
    for (const t of TABLES) {
      const rows = data[t]
      if (!Array.isArray(rows)) continue
      await db.table(t).clear()
      await db.table(t).bulkAdd(rows)
    }
  })
  if (typeof data.settings === 'string') localStorage.setItem('chess-local-settings', data.settings)
}
