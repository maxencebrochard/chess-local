import { Suspense, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { HashRouter, Link, Navigate, Route, Routes, useLocation, useNavigate, useNavigationType } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import { lazyPage } from './lib/lazyPage'
import { lazyCourse } from './pages/CoursePages'
import Home from './pages/Home'
import { NavIcon, type NavIconName } from './components/NavIcon'
import { isSelected, PLUS_DESTINATIONS, PLUS_MATCH } from './lib/navigation'

// Découpage par route : l'accueil reste dans le bundle initial, chaque autre page (et ses données
// JSON, son moteur, ses dépendances) arrive avec sa route. Toutes les chunks sont précachées par le
// service worker (globPatterns de vite.config.ts) : hors ligne, chaque route s'ouvre comme avant.
const Play = lazyPage(() => import('./pages/Play'))
const Analysis = lazyPage(() => import('./pages/Analysis'))
const Puzzles = lazyPage(() => import('./pages/Puzzles'))
const PuzzleRush = lazyPage(() => import('./pages/PuzzleRush'))
const Archive = lazyPage(() => import('./pages/Archive'))
const Stats = lazyPage(() => import('./pages/Stats'))
const Import = lazyPage(() => import('./pages/Import'))
const Learn = lazyPage(() => import('./pages/Learn'))
const OpeningTrainer = lazyPage(() => import('./pages/OpeningTrainer'))
const MyRepertoire = lazyPage(() => import('./pages/MyRepertoire'))
const Endgames = lazyPage(() => import('./pages/Endgames'))
const EndgameClock = lazyPage(() => import('./pages/EndgameClock'))
const PositionPlay = lazyPage(() => import('./pages/PositionPlay'))
const CriticalMoment = lazyPage(() => import('./pages/CriticalMoment'))
const Mates = lazyPage(() => import('./pages/Mates'))
const MissedAttacks = lazyPage(() => import('./pages/MissedAttacks'))
const MissedDefenses = lazyPage(() => import('./pages/MissedDefenses'))
const LearningPathMap = lazyPage(() => import('./pages/LearningPath'))
const PathStepRoute = lazyPage(() => import('./pages/LearningPath').then((m) => ({ default: m.PathStepRoute })))
const MyStructures = lazyPage(() => import('./pages/MyStructures'))
const Revision = lazyPage(() => import('./pages/Revision'))
const Attack = lazyPage(() => import('./pages/Attack'))
const Convert = lazyPage(() => import('./pages/Convert'))
const Defense = lazyPage(() => import('./pages/Defense'))
const Visualisation = lazyPage(() => import('./pages/Visualisation'))
const Insights = lazyPage(() => import('./pages/Insights'))
const Seance = lazyPage(() => import('./pages/Seance'))
const More = lazyPage(() => import('./pages/More'))
const Settings = lazyPage(() => import('./pages/Settings'))
const MyData = lazyPage(() => import('./pages/MyData'))
const Finales = lazyCourse(() => import('./lib/endgameCourse').then((m) => m.FINALES))
const Roque = lazyCourse(() => import('./lib/attackCourse').then((m) => m.ROQUE))
const DefenseCourse = lazyCourse(() => import('./lib/defenseCourse').then((m) => m.DEFENSE))
const Bases = lazyCourse(() => import('./lib/basicsCourse').then((m) => m.BASES))
const StructuresCourse = lazyCourse(
  () => import('./lib/structuresCourse').then((m) => m.STRUCTURES_COURSE),
  () => import('./pages/MyStructures').then(({ MyStructuresCard }) => <MyStructuresCard />),
)

// `match` : routes rattachées à l'onglet (allumé, sans être la page du lien), sous-chemins compris.
// Rattachements du « Placement cible de chaque route » (docs/ux-refonte.md, lot 0) : Mats éclair
// sous Puzzles, moments critiques sous Apprendre (Réviser mes parties), parties, outils,
// statistiques et réglages sous Plus.
const NAV: { to: string; icon: NavIconName; label: string; match: string[] }[] = [
  { to: '/', icon: 'accueil', label: 'Accueil', match: ['/seance'] },
  { to: '/jouer', icon: 'jouer', label: 'Jouer', match: [] },
  { to: '/puzzles', icon: 'puzzles', label: 'Puzzles', match: ['/rush', '/mats'] },
  { to: '/apprendre', icon: 'apprendre', label: 'Apprendre', match: ['/apprendre', '/ouvertures', '/repertoire', '/finales', '/revision', '/attaques-manquees', '/attaque', '/convertir', '/defenses-ratees', '/defense', '/visualisation', '/structures', '/moment-critique'] },
  { to: '/plus', icon: 'plus', label: 'Plus', match: PLUS_MATCH },
]

const under = (pathname: string, root: string) => pathname === root || pathname.startsWith(`${root}/`)

// `aria-current` : "page" sur la racine de l'onglet, "true" sur une route rattachée, absent sinon.
function ariaCurrent(n: (typeof NAV)[number], pathname: string): 'page' | 'true' | undefined {
  if (pathname === n.to) return 'page'
  if (n.match.some((m) => under(pathname, m))) return 'true'
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
      {/* Bande opaque sous l'heure et la Dynamic Island (index.css) : en PWA standalone, ce qui
          défile n'y passe plus en transparence. Hauteur nulle hors iPhone. */}
      <div aria-hidden="true" className="safe-top-band" />
      <nav aria-label="Navigation principale" className="hidden w-44 shrink-0 flex-col gap-1 overflow-y-auto overscroll-contain border-r border-black/30 bg-surface-2 p-3 md:flex">
        <div className="mb-3 px-2 text-lg font-black">
          Chess<span className="text-accent">Local</span>
        </div>
        {NAV.map((n) => {
          const current = ariaCurrent(n, pathname)
          return (
            // `replace` : une navigation vers une racine d'onglet n'empile jamais d'entrée
            // d'historique, sinon le swipe-back iOS (bord gauche) a toujours une cible et
            // sort de la partie en cours. Les descentes (`navigate('/analyse', { state })`,
            // tuiles Puzzle Rush et chess.com de l'accueil, liens du hub Plus) restent des push.
            <div key={n.to} className="contents">
              <Link
                to={n.to}
                replace
                onClick={() => onTabClick(n.to)}
                aria-current={current}
                data-nav-tab={n.icon}
                className={`flex min-h-11 items-center gap-3 rounded-lg px-3 py-2 font-semibold transition ${
                  current ? 'bg-accent/20 text-accent-light' : 'text-neutral-300 hover:bg-surface-3'
                }`}
              >
                <NavIcon name={n.icon} active={!!current} className="h-5 w-5" />
                {n.label}
              </Link>
              {/* Sous-destinations de Plus, dépliées dès que l'onglet est allumé (au clic sur
                  Plus ou sur une route rattachée) : dérivées de la route, sans état à garder.
                  Sans `aria-current`, réservé à l'onglet ; la sélection est visuelle. La nav
                  défile seule si une fenêtre basse ne la contient plus. */}
              {n.icon === 'plus' && current && (
                <ul aria-label="Plus" data-nav-sub className="mb-1 ml-5 flex flex-col gap-0.5 border-l border-white/10 pl-1.5">
                  {PLUS_DESTINATIONS.map((d) => {
                    const selected = isSelected(d, pathname)
                    return (
                      <li key={d.label}>
                        <Link
                          to={d.to}
                          replace
                          onClick={() => onTabClick(d.to)}
                          data-selected={selected || undefined}
                          className={`flex min-h-11 items-center rounded-lg px-3 text-sm font-semibold transition ${
                            selected ? 'bg-surface-3 text-white' : 'text-neutral-400 hover:bg-surface-3 hover:text-neutral-200'
                          }`}
                        >
                          {d.short ?? d.label}
                        </Link>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          )
        })}
        <div className="mt-auto whitespace-nowrap px-2 text-[11px] text-neutral-400">100 % local · SF 18</div>
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
          {/* Le secours ne se voit qu'à l'ouverture directe d'une route paresseuse (rechargement,
              lien) : une navigation dans l'app est une transition (HashRouter), qui garde la page
              affichée jusqu'à ce que la suivante soit prête. */}
          <Suspense fallback={<PageLoading />}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/jouer" element={<Play />} />
              <Route path="/puzzles" element={<Puzzles />} />
              <Route path="/rush" element={<PuzzleRush />} />
              <Route path="/apprendre" element={<Learn />} />
              <Route path="/ouvertures" element={<OpeningTrainer />} />
              <Route path="/repertoire" element={<MyRepertoire />} />
              <Route path="/apprendre/finales" element={<Finales.Index />} />
              <Route path="/apprendre/finales/:id" element={<Finales.Lesson />} />
              <Route path="/apprendre/roque" element={<Roque.Index />} />
              <Route path="/apprendre/roque/:id" element={<Roque.Lesson />} />
              <Route path="/apprendre/bases" element={<Bases.Index />} />
              <Route path="/apprendre/bases/:id" element={<Bases.Lesson />} />
              <Route path="/apprendre/parcours" element={<LearningPathMap />} />
              <Route path="/apprendre/parcours/:id" element={<PathStepRoute />} />
              <Route path="/apprendre/structures" element={<StructuresCourse.Index />} />
              <Route path="/apprendre/structures/:id" element={<StructuresCourse.Lesson />} />
              <Route path="/structures" element={<MyStructures />} />
              <Route path="/structures/:key" element={<MyStructures />} />
              <Route path="/apprendre/defense" element={<DefenseCourse.Index />} />
              <Route path="/apprendre/defense/:id" element={<DefenseCourse.Lesson />} />
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
              {/* Statique : classée devant `/finales/:id` par le routeur, aucun id de finale ne vaut `chrono`. */}
              <Route path="/finales/chrono" element={<EndgameClock />} />
              <Route path="/finales/:id" element={<Endgames />} />
              <Route path="/attaque" element={<Attack />} />
              <Route path="/attaque/:id" element={<Attack />} />
              <Route path="/defense" element={<Defense />} />
              <Route path="/defense/:id" element={<Defense />} />
              <Route path="/visualisation" element={<Visualisation />} />
              <Route path="/convertir" element={<Convert />} />
              <Route path="/convertir/:id" element={<Convert />} />
              <Route path="/archive" element={<Archive />} />
              <Route path="/stats" element={<Stats />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="/seance" element={<Seance />} />
              <Route path="/import" element={<Import />} />
              <Route path="/plus" element={<More />} />
              <Route path="/reglages" element={<Settings />} />
              <Route path="/donnees" element={<MyData />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
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
              data-nav-tab={n.icon}
              className={`flex min-h-11 min-w-0 flex-1 flex-col items-center justify-center gap-px py-1 text-xs leading-3.5 font-semibold ${
                current ? 'text-accent' : 'text-neutral-400'
              }`}
            >
              <NavIcon name={n.icon} active={!!current} />
              {n.label}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}

// Secours de chargement d'une page : vide d'abord (une chunk précachée arrive en quelques
// dizaines de millisecondes, un texte qui clignote serait pire), un indicateur discret ensuite.
function PageLoading() {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 400)
    return () => clearTimeout(t)
  }, [])
  return (
    <div aria-busy="true" className="flex h-full items-center justify-center p-6">
      {slow && <p className="text-sm text-neutral-400">Chargement…</p>}
    </div>
  )
}
