import { HashRouter, NavLink, Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import Play from './pages/Play'
import Analysis from './pages/Analysis'
import Puzzles from './pages/Puzzles'
import PuzzleRush from './pages/PuzzleRush'
import Archive from './pages/Archive'
import Stats from './pages/Stats'

const NAV = [
  { to: '/', icon: '♞', label: 'Accueil' },
  { to: '/jouer', icon: '♟', label: 'Jouer' },
  { to: '/puzzles', icon: '🧩', label: 'Puzzles' },
  { to: '/rush', icon: '⚡', label: 'Rush' },
  { to: '/analyse', icon: '🔍', label: 'Analyse' },
  { to: '/archive', icon: '📚', label: 'Archive' },
  { to: '/stats', icon: '📊', label: 'Stats' },
]

export default function App() {
  return (
    <HashRouter>
      <div className="flex h-dvh flex-col md:flex-row">
        <nav className="hidden w-44 shrink-0 flex-col gap-1 border-r border-black/30 bg-surface-2 p-3 md:flex">
          <div className="mb-3 px-2 text-lg font-black">
            Chess<span className="text-accent">Local</span>
          </div>
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) =>
                `rounded px-3 py-2 font-semibold transition ${
                  isActive ? 'bg-accent/20 text-accent' : 'text-neutral-300 hover:bg-surface-3'
                }`
              }
            >
              <span className="mr-2">{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
          <div className="mt-auto whitespace-nowrap px-2 text-[11px] text-neutral-600">100 % local · SF 18</div>
        </nav>
        <main className="pt-safe min-w-0 flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/jouer" element={<Play />} />
            <Route path="/puzzles" element={<Puzzles />} />
            <Route path="/rush" element={<PuzzleRush />} />
            <Route path="/analyse" element={<Analysis />} />
            <Route path="/archive" element={<Archive />} />
            <Route path="/stats" element={<Stats />} />
          </Routes>
        </main>
        <nav className="pb-safe flex shrink-0 border-t border-black/40 bg-surface-2 md:hidden">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) =>
                `flex flex-1 flex-col items-center gap-0.5 py-1.5 text-[10px] font-semibold ${
                  isActive ? 'text-accent' : 'text-neutral-400'
                }`
              }
            >
              <span className="text-lg leading-none">{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </HashRouter>
  )
}
