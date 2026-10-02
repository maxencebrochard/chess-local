import { useLayoutEffect, useRef, useState } from 'react'
import { HashRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import Home from './pages/Home'
import Play from './pages/Play'
import Analysis from './pages/Analysis'
import Puzzles from './pages/Puzzles'
import PuzzleRush from './pages/PuzzleRush'
import Archive from './pages/Archive'
import Stats from './pages/Stats'
import Import from './pages/Import'
import Learn from './pages/Learn'
import OpeningTrainer from './pages/OpeningTrainer'
import Endgames from './pages/Endgames'
import PositionPlay from './pages/PositionPlay'
import EndgameCourse, { EndgameLesson } from './pages/EndgameCourse'

// `match` : routes rattachées à l'onglet (allumé, sans être la page du lien), sous-chemins compris.
const NAV = [
  { to: '/', icon: '♞', label: 'Accueil', match: [] as string[] },
  { to: '/jouer', icon: '♟', label: 'Jouer', match: [] as string[] },
  { to: '/puzzles', icon: '🧩', label: 'Puzzles', match: ['/rush'] },
  { to: '/apprendre', icon: '🎓', label: 'Apprendre', match: ['/apprendre', '/ouvertures', '/finales'] },
  { to: '/analyse', icon: '🔍', label: 'Analyse', match: ['/import', '/analyse/jouer'] },
  { to: '/archive', icon: '📚', label: 'Archive', match: [] as string[] },
  { to: '/stats', icon: '📊', label: 'Stats', match: [] as string[] },
]

// `aria-current` : "page" sur la racine de l'onglet, "true" sur une route rattachée, absent sinon.
function ariaCurrent(n: (typeof NAV)[number], pathname: string): 'page' | 'true' | undefined {
  if (pathname === n.to) return 'page'
  if (n.match.some((m) => pathname === m || pathname.startsWith(`${m}/`))) return 'true'
  return undefined
}

export default function App() {
  return (
    <HashRouter>
      <Shell />
    </HashRouter>
  )
}

// Coquille rendue DANS le routeur (il lui faut `useLocation`).
function Shell() {
  const location = useLocation()
  const navigate = useNavigate()
  // Sans barre finale : `#/apprendre/` doit allumer Apprendre.
  const pathname = location.pathname.replace(/\/+$/, '') || '/'
  const mainRef = useRef<HTMLElement>(null)
  // Re-tap de l'onglet de la route courante : seul geste qui réarme la frontière sans
  // changer de chemin.
  const [retaps, setRetaps] = useState(0)
  const onTabClick = (to: string) => {
    if (to === pathname) setRetaps((t) => t + 1)
  }
  // « Revenir à l'accueil » de l'écran de secours : même règle qu'un tap sur l'onglet Accueil.
  const goHome = () => {
    if (pathname === '/') setRetaps((t) => t + 1)
    else navigate('/', { replace: true })
  }

  // Chaque page s'ouvre en haut : `<main>` est le seul conteneur qui défile, et il est
  // partagé entre les routes. Dépend de `pathname` seul : un `navigate('.', { replace })`
  // ou un `setParams` dans une page ne doivent pas remettre le scroll à zéro.
  useLayoutEffect(() => {
    mainRef.current?.scrollTo(0, 0)
  }, [pathname])

  return (
    <div className="flex h-dvh flex-col md:flex-row">
      <nav aria-label="Navigation principale" className="hidden w-44 shrink-0 flex-col gap-1 border-r border-black/30 bg-surface-2 p-3 md:flex">
        <div className="mb-3 px-2 text-lg font-black">
          Chess<span className="text-accent">Local</span>
        </div>
        {NAV.map((n) => {
          const current = ariaCurrent(n, pathname)
          return (
            // `replace` : une navigation vers une racine d'onglet n'empile jamais d'entrée
            // d'historique, sinon le swipe-back iOS (bord gauche) a toujours une cible et
            // sort de la partie en cours. Les descentes (`navigate('/analyse', { state })`,
            // tuiles Puzzle Rush et chess.com de l'accueil) restent des push.
            <Link
              key={n.to}
              to={n.to}
              replace
              onClick={() => onTabClick(n.to)}
              aria-current={current}
              className={`flex min-h-11 items-center rounded px-3 py-2 font-semibold transition ${
                current ? 'bg-accent/20 text-accent' : 'text-neutral-300 hover:bg-surface-3'
              }`}
            >
              <span className="mr-2" aria-hidden="true">
                {n.icon}
              </span>
              {n.label}
            </Link>
          )
        })}
        <div className="mt-auto whitespace-nowrap px-2 text-[11px] text-neutral-600">100 % local · SF 18</div>
      </nav>
      <main ref={mainRef} className="pt-safe min-w-0 flex-1 overflow-y-auto">
        {/* La frontière ne couvre que les pages : les nav restent utilisables pendant le
            secours. Réarmée par un vrai changement de chemin ou un re-tap de l'onglet courant,
            jamais par `location.key` : les `navigate('.', { replace, state: null })` que les
            pages lancent au montage effaceraient un crash survenu juste après le chargement et
            remonteraient la page vide. */}
        <ErrorBoundary resetKey={`${pathname}#${retaps}`} onHome={goHome}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/jouer" element={<Play />} />
            <Route path="/puzzles" element={<Puzzles />} />
            <Route path="/rush" element={<PuzzleRush />} />
            <Route path="/apprendre" element={<Learn />} />
            <Route path="/ouvertures" element={<OpeningTrainer />} />
            <Route path="/apprendre/finales" element={<EndgameCourse />} />
            <Route path="/apprendre/finales/:id" element={<EndgameLesson />} />
            <Route path="/analyse" element={<Analysis />} />
            <Route path="/analyse/jouer" element={<PositionPlay />} />
            <Route path="/finales" element={<Endgames />} />
            <Route path="/finales/:id" element={<Endgames />} />
            <Route path="/archive" element={<Archive />} />
            <Route path="/stats" element={<Stats />} />
            <Route path="/import" element={<Import />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ErrorBoundary>
      </main>
      <nav aria-label="Navigation principale" className="pb-safe flex shrink-0 border-t border-black/40 bg-surface-2 md:hidden">
        {NAV.map((n) => {
          const current = ariaCurrent(n, pathname)
          return (
            <Link
              key={n.to}
              to={n.to}
              replace
              onClick={() => onTabClick(n.to)}
              aria-current={current}
              className={`flex min-h-11 min-w-0 flex-1 flex-col items-center justify-center gap-0.5 py-1.5 text-[10px] font-semibold ${
                current ? 'text-accent' : 'text-neutral-400'
              }`}
            >
              <span className="text-lg leading-none" aria-hidden="true">
                {n.icon}
              </span>
              {n.label}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
