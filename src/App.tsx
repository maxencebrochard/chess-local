import { useLayoutEffect, useRef, useState } from 'react'
import { HashRouter, Link, Navigate, Route, Routes, useLocation, useNavigate, useNavigationType } from 'react-router-dom'
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
import CriticalMoment from './pages/CriticalMoment'
import Mates from './pages/Mates'
import MissedAttacks from './pages/MissedAttacks'
import MissedDefenses from './pages/MissedDefenses'
import CourseIndex, { CourseLesson } from './pages/LessonCourse'
import { FINALES } from './lib/endgameCourse'
import { ROQUE } from './lib/attackCourse'
import Revision from './pages/Revision'
import Attack from './pages/Attack'
import Defense from './pages/Defense'
import Insights from './pages/Insights'

// `match` : routes rattachées à l'onglet (allumé, sans être la page du lien), sous-chemins compris.
const NAV = [
  { to: '/', icon: '♞', label: 'Accueil', match: [] as string[] },
  { to: '/jouer', icon: '♟', label: 'Jouer', match: [] as string[] },
  { to: '/puzzles', icon: '🧩', label: 'Puzzles', match: ['/rush'] },
  { to: '/apprendre', icon: '🎓', label: 'Apprendre', match: ['/apprendre', '/ouvertures', '/finales', '/mats', '/revision', '/attaques-manquees', '/attaque', '/defenses-ratees', '/defense'] },
  { to: '/analyse', icon: '🔍', label: 'Analyse', match: ['/import', '/analyse/jouer', '/moment-critique'] },
  { to: '/archive', icon: '📚', label: 'Archive', match: [] as string[] },
  { to: '/stats', icon: '📊', label: 'Stats', match: ['/insights'] },
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

  // Chaque écran s'ouvre en haut : `<main>` porte le défilement partagé entre les routes.
  // Un écran nouveau, c'est un autre chemin, ou une autre requête
  // atteinte par push ou par l'historique (fiche `/mats?d=`, ouverture `/ouvertures?famille=`).
  // Un replace de même chemin est un état interne de la page, qui garde son défilement :
  // `navigate('.', { replace, state: null })` au montage, `setParams({ etape }, { replace })`,
  // option d'une fiche.
  const navigationType = useNavigationType()
  const search = location.search
  const shown = useRef({ pathname, search })
  useLayoutEffect(() => {
    const prev = shown.current
    shown.current = { pathname, search }
    if (prev.pathname !== pathname || (prev.search !== search && navigationType !== 'REPLACE')) mainRef.current?.scrollTo(0, 0)
  }, [pathname, search, navigationType])

  // `h-full` : la coquille prend exactement le body, fixé sur le viewport (index.css).
  return (
    <div className="flex h-full flex-col md:flex-row">
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
      {/* `overscroll-contain` : en butée, le geste s'arrête là au lieu de se chaîner vers le
          document (index.css). */}
      <main ref={mainRef} className="pt-safe min-w-0 flex-1 overflow-y-auto overscroll-contain">
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
            <Route path="/apprendre/finales" element={<CourseIndex key={FINALES.slug} course={FINALES} />} />
            <Route path="/apprendre/finales/:id" element={<CourseLesson course={FINALES} />} />
            <Route path="/apprendre/roque" element={<CourseIndex key={ROQUE.slug} course={ROQUE} />} />
            <Route path="/apprendre/roque/:id" element={<CourseLesson course={ROQUE} />} />
            <Route path="/mats" element={<Mates />} />
            <Route path="/revision" element={<Revision />} />
            <Route path="/attaques-manquees" element={<MissedAttacks />} />
            <Route path="/attaques-manquees/:id" element={<MissedAttacks />} />
            <Route path="/defenses-ratees" element={<MissedDefenses />} />
            <Route path="/defenses-ratees/:id" element={<MissedDefenses />} />
            <Route path="/analyse" element={<Analysis />} />
            <Route path="/analyse/jouer" element={<PositionPlay />} />
            <Route path="/moment-critique" element={<CriticalMoment />} />
            <Route path="/finales" element={<Endgames />} />
            <Route path="/finales/:id" element={<Endgames />} />
            <Route path="/attaque" element={<Attack />} />
            <Route path="/attaque/:id" element={<Attack />} />
            <Route path="/defense" element={<Defense />} />
            <Route path="/defense/:id" element={<Defense />} />
            <Route path="/archive" element={<Archive />} />
            <Route path="/stats" element={<Stats />} />
            <Route path="/insights" element={<Insights />} />
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
