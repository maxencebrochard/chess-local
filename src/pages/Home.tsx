import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { db, DEFAULT_RATING } from '../lib/db'

export default function Home() {
  const [blitz, setBlitz] = useState(DEFAULT_RATING)
  const [puzzle, setPuzzle] = useState(DEFAULT_RATING)
  const [nbGames, setNbGames] = useState(0)

  useEffect(() => {
    void db.ratings.get('blitz').then((r) => r && setBlitz(r.value))
    void db.ratings.get('puzzle').then((r) => r && setPuzzle(r.value))
    void db.games.count().then(setNbGames)
  }, [])

  const tiles = [
    { to: '/jouer', icon: '♟', title: 'Jouer', desc: 'Contre 9 bots de 400 à 3200 Elo, ou à deux sur le même écran.' },
    { to: '/puzzles', icon: '🧩', title: 'Puzzles', desc: `120 000 puzzles notés, adaptés à ton niveau (${puzzle}).` },
    { to: '/rush', icon: '⚡', title: 'Puzzle Rush', desc: '3 min, 5 min ou survie. Trois erreurs et c\'est fini.' },
    { to: '/analyse', icon: '🔍', title: 'Analyse', desc: 'Stockfish 18, bilan de partie, explorer d\'ouvertures.' },
    { to: '/archive', icon: '📚', title: 'Archive', desc: `${nbGames} partie${nbGames > 1 ? 's' : ''} enregistrée${nbGames > 1 ? 's' : ''}, export PGN.` },
    { to: '/stats', icon: '📊', title: 'Stats', desc: `Classements par cadence — blitz ${blitz} — et réglages.` },
  ]

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col justify-center p-8">
      <h1 className="mb-1 text-4xl font-black">
        ♞ Chess<span className="text-accent">Local</span>
      </h1>
      <p className="mb-8 text-neutral-400">Tout chess.com, sans le cloud : 100 % local, 100 % privé, 100 % à toi.</p>
      <div className="grid grid-cols-2 gap-4">
        {tiles.map((t) => (
          <Link key={t.to} to={t.to} className="rounded-xl bg-surface-2 p-5 transition hover:bg-surface-3 hover:shadow-lg">
            <div className="mb-1 text-3xl">{t.icon}</div>
            <div className="text-lg font-bold">{t.title}</div>
            <div className="text-sm text-neutral-400">{t.desc}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}
