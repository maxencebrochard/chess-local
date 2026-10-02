import { memo, useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { db, type SavedGame } from '../lib/db'
import { botById } from '../lib/bots'

const PAGE = 50 // parties par page : 3 000 parties rendues d'un coup, c'est 27 000 noeuds DOM
const UNDO_MS = 5000 // délai pendant lequel une suppression peut être annulée

const newestFirst = () => db.games.orderBy('date').reverse()

function resultForPlayer(g: SavedGame): { label: string; color: string; small: boolean } {
  if (g.result === '1/2-1/2') return { label: '½', color: 'text-neutral-300', small: false }
  if (g.mode === 'local') return { label: g.result, color: 'text-neutral-300', small: true }
  const won = (g.result === '1-0') === (g.playerColor === 'w')
  return won ? { label: 'G', color: 'text-accent', small: false } : { label: 'P', color: 'text-red-400', small: false }
}

interface RowProps {
  g: SavedGame
  pending: boolean
  onRemove: (id: number) => void
  // Absent quand la suppression est déjà lancée en base : plus rien à annuler.
  onUndo?: () => void
}

// Carte d'une partie, mémoïsée : seule celle dont l'état change se re-rend.
// Mobile : ligne 1 = résultat + infos, ligne 2 = actions ; une seule rangée à partir de md.
const CARD = 'rounded bg-surface-2 px-3 py-2 md:flex md:items-center md:gap-4 md:px-4 md:py-2.5'
const ACTIONS = 'mt-1 flex items-center justify-end gap-2 md:mt-0'
const TITLE = 'truncate text-sm font-semibold leading-5 md:text-base md:leading-6'
const META = 'truncate text-xs leading-4 text-neutral-400 md:text-sm md:leading-5'

const GameRow = memo(function GameRow({ g, pending, onRemove, onUndo }: RowProps) {
  const id = g.id!
  if (pending) {
    // Même squelette que la carte (deux lignes de texte, une rangée d'action) : même hauteur, pas de saut.
    return (
      <li className={CARD}>
        <div role="status" className="min-w-0 md:flex-1">
          <div className={TITLE}>Partie supprimée</div>
          <div className={META}>Elle sera effacée dans 5 secondes.</div>
        </div>
        <div className={ACTIONS}>
          <button
            autoFocus
            onClick={onUndo}
            disabled={!onUndo}
            className="-my-1.5 h-11 cursor-pointer rounded px-4 text-sm font-semibold text-accent hover:bg-accent/20 disabled:cursor-default disabled:opacity-40"
          >
            Annuler
          </button>
        </div>
      </li>
    )
  }
  const res = resultForPlayer(g)
  const bot = g.mode === 'bot' && g.botId ? botById(g.botId) : null
  const title = g.mode === 'bot' ? `${bot?.emoji ?? ''} contre ${bot?.name ?? g.botId} (${bot?.elo ?? '?'})` : 'Partie locale'
  // Le classement passe avant le motif : si la ligne est tronquée, c'est le motif (redondant
  // avec la lettre) qui disparaît, et le texte complet reste dans le title.
  const meta = [
    new Date(g.date).toLocaleDateString('fr-FR', { dateStyle: 'medium' }),
    g.timeControl,
    g.playerRatingAfter ? `classement ${g.playerRatingAfter}` : '',
    `${g.result} ${g.termination}`,
  ]
    .filter(Boolean)
    .join(' · ')
  return (
    <li className={`${CARD} hover:bg-surface-3`}>
      <div className="flex min-w-0 items-center gap-3 md:flex-1">
        <span className={`w-8 shrink-0 text-center font-black leading-5 ${res.small ? 'text-sm' : 'text-lg'} ${res.color}`}>
          {res.label}
        </span>
        <div className="min-w-0 flex-1">
          <div className={TITLE}>
            {title}
            {g.mode === 'bot' && (
              <span className="ml-2 text-xs font-normal text-neutral-500">{g.playerColor === 'w' ? 'Blancs' : 'Noirs'}</span>
            )}
          </div>
          <div className={META} title={meta}>
            {meta}
          </div>
        </div>
      </div>
      <div className={ACTIONS}>
        <Link
          to={`/analyse?game=${id}&review=1`}
          className="rounded bg-accent/20 px-3 py-1.5 text-sm font-semibold text-accent hover:bg-accent/30"
        >
          🔍 Bilan
        </Link>
        <Link to={`/analyse?game=${id}`} className="rounded bg-surface-3 px-3 py-1.5 text-sm font-semibold hover:bg-surface/60">
          Analyser
        </Link>
        <button
          onClick={() => onRemove(id)}
          aria-label="Supprimer la partie"
          className="-my-1.5 flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded text-neutral-500 hover:text-red-400"
        >
          ✕
        </button>
      </div>
    </li>
  )
})

export default function Archive() {
  const [games, setGames] = useState<SavedGame[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [pendingId, setPendingId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  // Parties dont la suppression en base est en cours : elles restent en barre, sans actions,
  // même quand un second ✕ a déjà mis une autre partie en attente.
  const [deleting, setDeleting] = useState<ReadonlySet<number>>(new Set())
  // Suppression en attente, lue par les nettoyages (sortie de page, page cachée) sans fermeture périmée.
  const pendingRef = useRef<{ id: number; timer: number } | null>(null)

  useEffect(() => {
    // Compteur et première page ensemble : un seul rendu, jamais un titre sans ses lignes.
    void Promise.all([db.games.count(), newestFirst().limit(PAGE).toArray()]).then(([n, rows]) => {
      setTotal(n)
      setGames(rows)
    })
  }, [])

  async function loadMore() {
    setLoadingMore(true)
    try {
      const rows = await newestFirst().offset(games.length).limit(PAGE).toArray()
      setGames((gs) => [...gs, ...rows])
    } finally {
      setLoadingMore(false)
    }
  }

  const commit = useCallback(async (id: number) => {
    setBusy(true)
    setDeleting((s) => new Set(s).add(id))
    try {
      await db.games.delete(id)
      setGames((gs) => gs.filter((g) => g.id !== id))
      setTotal((n) => (n === null ? n : n - 1))
    } finally {
      setPendingId((cur) => (cur === id ? null : cur))
      setDeleting((s) => {
        const next = new Set(s)
        next.delete(id)
        return next
      })
      setBusy(false)
    }
  }, [])

  // Valide tout de suite la suppression en attente (second ✕, export, sortie de page).
  const flush = useCallback(() => {
    const p = pendingRef.current
    if (!p) return
    window.clearTimeout(p.timer)
    pendingRef.current = null
    void commit(p.id)
  }, [commit])

  const remove = useCallback(
    (id: number) => {
      flush()
      const timer = window.setTimeout(() => {
        pendingRef.current = null
        void commit(id)
      }, UNDO_MS)
      pendingRef.current = { id, timer }
      setPendingId(id)
    },
    [flush, commit],
  )

  const undo = useCallback(() => {
    const p = pendingRef.current
    if (!p) return
    window.clearTimeout(p.timer)
    pendingRef.current = null
    setPendingId(null)
  }, [])

  // Quitter la page, la cacher (changement d'app iOS) ou la fermer valide la suppression.
  // Si l'app est tuée avant, la partie réapparaît : jamais l'inverse.
  useEffect(() => {
    const onHide = () => {
      if (document.visibilityState === 'hidden') flush()
    }
    document.addEventListener('visibilitychange', onHide)
    window.addEventListener('pagehide', flush)
    return () => {
      document.removeEventListener('visibilitychange', onHide)
      window.removeEventListener('pagehide', flush)
      flush()
    }
  }, [flush])

  async function exportAll() {
    // Toute la base, pas la page affichée ; une partie « supprimée » à l'écran n'en fait pas partie.
    const pending = pendingRef.current?.id
    flush()
    const all = (await newestFirst().toArray()).filter((g) => g.id !== pending)
    const blob = new Blob([all.map((g) => g.pgn).join('\n\n')], { type: 'application/x-chess-pgn' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'mes-parties.pgn'
    a.click()
    URL.revokeObjectURL(url)
  }

  const remaining = total === null ? 0 : total - games.length

  return (
    <div className="mx-auto max-w-4xl p-3 md:p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{total === null ? 'Archive' : `Archive (${total})`}</h1>
        {total !== null && total > 0 && (
          <button
            onClick={() => void exportAll()}
            className="shrink-0 cursor-pointer rounded bg-surface-3 px-4 py-2 text-sm font-semibold hover:bg-surface-3/70"
          >
            ⬇ Exporter tout (PGN)
          </button>
        )}
      </div>

      {total === 0 && <p className="text-neutral-400">Aucune partie enregistrée. Va jouer !</p>}

      <ul className="space-y-1">
        {games.map((g) => {
          const del = deleting.has(g.id!)
          return <GameRow key={g.id} g={g} pending={del || g.id === pendingId} onRemove={remove} onUndo={del ? undefined : undo} />
        })}
      </ul>

      {remaining > 0 && (
        <button
          onClick={() => void loadMore()}
          disabled={busy || loadingMore}
          className="mt-3 w-full cursor-pointer rounded bg-surface-2 py-3 text-sm font-semibold text-neutral-300 hover:bg-surface-3 disabled:opacity-40"
        >
          Voir plus ({remaining} restante{remaining > 1 ? 's' : ''})
        </button>
      )}
    </div>
  )
}
