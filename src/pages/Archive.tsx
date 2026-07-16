import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { db, type SavedGame } from '../lib/db'
import { botById } from '../lib/bots'

export default function Archive() {
  const [games, setGames] = useState<SavedGame[]>([])

  useEffect(() => {
    void db.games.orderBy('date').reverse().toArray().then(setGames)
  }, [])

  function exportAll() {
    const pgn = games.map((g) => g.pgn).join('\n\n')
    const blob = new Blob([pgn], { type: 'application/x-chess-pgn' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'mes-parties.pgn'
    a.click()
    URL.revokeObjectURL(url)
  }

  async function remove(id: number) {
    await db.games.delete(id)
    setGames((gs) => gs.filter((g) => g.id !== id))
  }

  function resultForPlayer(g: SavedGame): { label: string; color: string } {
    if (g.mode === 'local') return { label: g.result, color: 'text-neutral-300' }
    if (g.result === '1/2-1/2') return { label: '½', color: 'text-neutral-300' }
    const won = (g.result === '1-0') === (g.playerColor === 'w')
    return won ? { label: 'G', color: 'text-accent' } : { label: 'P', color: 'text-red-400' }
  }

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Archive ({games.length})</h1>
        {games.length > 0 && (
          <button onClick={exportAll} className="cursor-pointer rounded bg-surface-3 px-4 py-2 text-sm font-semibold hover:bg-surface-3/70">
            ⬇ Exporter tout (PGN)
          </button>
        )}
      </div>

      {games.length === 0 && <p className="text-neutral-400">Aucune partie enregistrée. Va jouer !</p>}

      <div className="space-y-1">
        {games.map((g) => {
          const res = resultForPlayer(g)
          const bot = g.botId ? botById(g.botId) : null
          return (
            <div key={g.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded bg-surface-2 px-3 py-2.5 hover:bg-surface-3 md:flex-nowrap md:px-4">
              <span className={`w-6 text-center text-lg font-black ${res.color}`}>{res.label}</span>
              <div className="flex-1">
                <div className="font-semibold">
                  {g.mode === 'bot' ? `${bot?.emoji ?? ''} vs ${bot?.name ?? g.botId} (${bot?.elo ?? '?'})` : 'Partie locale'}
                  <span className="ml-2 text-sm font-normal text-neutral-500">
                    {g.mode === 'bot' && (g.playerColor === 'w' ? '· Blancs' : '· Noirs')}
                  </span>
                </div>
                <div className="text-sm text-neutral-400">
                  {new Date(g.date).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })} · {g.timeControl} · {g.result} {g.termination}
                  {g.playerRatingAfter && ` · classement ${g.playerRatingAfter}`}
                </div>
              </div>
              <Link
                to={`/analyse?game=${g.id}&review=1`}
                className="rounded bg-accent/20 px-3 py-1.5 text-sm font-semibold text-accent hover:bg-accent/30"
              >
                🔍 Bilan
              </Link>
              <Link to={`/analyse?game=${g.id}`} className="rounded bg-surface-3 px-3 py-1.5 text-sm font-semibold hover:bg-surface/60">
                Analyser
              </Link>
              <button onClick={() => void remove(g.id!)} className="cursor-pointer rounded px-2 py-1.5 text-neutral-500 hover:text-red-400">
                ✕
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
