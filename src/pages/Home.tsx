import { Link, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Cta } from '../components/Cta'
import { db, DEFAULT_RATING } from '../lib/db'

export default function Home() {
  const navigate = useNavigate()
  const [ratings, setRatings] = useState<Record<string, number>>({})
  const [solved, setSolved] = useState(0)
  const [nbGames, setNbGames] = useState(0)

  useEffect(() => {
    void db.ratings.toArray().then((rs) => setRatings(Object.fromEntries(rs.map((r) => [r.key, r.value]))))
    void db.puzzleAttempts.where('date').above(0).toArray().then((a) => setSolved(a.filter((x) => x.success).length))
    void db.games.count().then(setNbGames)
  }, [])

  const r = (key: string) => ratings[key] ?? DEFAULT_RATING

  const statCards = [
    { icon: '⏱', label: 'Rapide', value: r('rapid') },
    { icon: '⚡', label: 'Blitz', value: r('blitz') },
    { icon: '🚀', label: 'Bullet', value: r('bullet') },
    { icon: '🧩', label: 'Puzzles', value: r('puzzle') },
  ]

  const tiles = [
    { to: '/analyse', icon: '🔍', title: 'Analyse', desc: 'Stockfish 18, bilan, coach' },
    { to: '/rush', icon: '⚡', title: 'Puzzle Rush', desc: '3 min, 5 min ou survie' },
    { to: '/archive', icon: '📚', title: 'Archive', desc: `${nbGames} partie${nbGames > 1 ? 's' : ''}` },
    { to: '/import', icon: '♟', title: 'chess.com', desc: 'Importer tes parties' },
  ]

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col p-4 md:justify-center md:p-8">
      <h1 className="mb-4 text-3xl font-black">
        ♞ Chess<span className="text-accent">Local</span>
      </h1>

      {/* Carte Problèmes, façon chess.com */}
      <Link
        to="/puzzles"
        className="mb-4 block rounded-2xl bg-gradient-to-br from-[#4e7837] to-[#2e4a20] p-5 shadow-lg transition hover:brightness-110"
      >
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-2xl font-black text-white">🧩 Problèmes</div>
            <div className="mt-1 text-sm text-white/80">
              {solved} résolus · classement {r('puzzle')}
            </div>
          </div>
          <span className="shrink-0 rounded-xl bg-accent px-5 py-2.5 text-lg font-black text-white shadow-[0_3px_0_#5d9948]">
            Résolvez !
          </span>
        </div>
      </Link>

      {/* Cartes stats horizontales */}
      <div className="mb-4 grid grid-cols-4 gap-2">
        {statCards.map((s) => (
          <Link key={s.label} to="/stats" className="rounded-xl bg-surface-2 p-3 text-center transition hover:bg-surface-3">
            <div className="text-2xl">{s.icon}</div>
            <div className="text-xl font-black">{s.value}</div>
            <div className="text-xs text-neutral-400">{s.label}</div>
          </Link>
        ))}
      </div>

      {/* Tuiles secondaires */}
      <div className="mb-4 grid grid-cols-2 gap-2">
        {tiles.map((t) => (
          <Link key={t.to} to={t.to} className="flex items-center gap-3 rounded-xl bg-surface-2 p-3 transition hover:bg-surface-3">
            <span className="text-2xl">{t.icon}</span>
            <span>
              <span className="block font-bold">{t.title}</span>
              <span className="block text-xs text-neutral-400">{t.desc}</span>
            </span>
          </Link>
        ))}
      </div>

      {/* CTA Jouer géant, collé en bas */}
      <div className="mt-auto md:mt-4">
        <Cta className="w-full py-4 text-2xl" onClick={() => navigate('/jouer')}>
          Jouer
        </Cta>
      </div>
    </div>
  )
}
