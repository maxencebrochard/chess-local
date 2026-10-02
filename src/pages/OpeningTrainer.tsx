// Entraîneur d'ouvertures (/ouvertures), façon chess.com Openings / Drills : choix d'une
// famille (populaires + recherche), fiche avec camp, longueur, trois modes et liste des
// variantes avec leur état. La fiche vit dans l'URL (?famille=&camp=&longueur=) : retour du
// navigateur, rechargement et retour depuis l'analyse retrouvent la même fiche.
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Chess } from 'chess.js'
import { OpeningDrill, type DrillItem } from '../components/OpeningDrill'
import { Engine } from '../lib/engine'
import { openingFr } from '../lib/openingNames'
import {
  EMPTY_PROGRESS, MODE_LABEL, getFamily, loadProgress, modeStats, nextMovePositions, pickSuite, pickVariant,
  popularFamilies, recordDrill, searchFamilies, uciMoves, variantStatus,
  type Color, type DrillMode, type Family, type Progress, type Variant, type VariantStatus,
} from '../lib/openingTrainer'
import { figurine } from '../lib/review'

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
const LENGTHS = [
  { id: 'theorie', label: 'Théorie seule', plies: null },
  { id: '10', label: '10 coups', plies: 20 },
  { id: '15', label: '15 coups', plies: 30 },
] as const
type LengthId = (typeof LENGTHS)[number]['id']
const DEFAULT_LENGTH: LengthId = '15'
const PAGE_SIZE = 20

type Filter = 'all' | 'review' | 'new'

export default function OpeningTrainer() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const fam = getFamily(params.get('famille') ?? '')
  const campParam = params.get('camp')
  const color: Color = campParam === 'w' || campParam === 'b' ? campParam : (fam?.defaultColor ?? 'w')
  const lengthId = (LENGTHS.find((l) => l.id === params.get('longueur'))?.id ?? DEFAULT_LENGTH) as LengthId
  const plyTarget = LENGTHS.find((l) => l.id === lengthId)!.plies

  const [query, setQuery] = useState('')
  const [progress, setProgress] = useState<Progress>(EMPTY_PROGRESS)
  // retry : « Réessayer » d'une même position ; en « Prochain coup », seule la 1re tentative compte.
  const [drill, setDrill] = useState<{ item: DrillItem; key: number; retry: boolean } | null>(null)
  const [saveError, setSaveError] = useState(false)
  const [session, setSession] = useState({ ok: 0, total: 0 })
  const [filter, setFilter] = useState<Filter>('all')
  const [showAll, setShowAll] = useState(false)
  const engineRef = useRef<Engine | null>(null)

  useEffect(() => {
    void loadProgress().then(setProgress)
  }, [])

  useEffect(
    () => () => {
      engineRef.current?.quit()
      engineRef.current = null
    },
    [],
  )

  // Nouvelle fiche (ou retour navigateur pendant un drill) : drill fermé, en haut de page, liste
  // repliée, filtre et compteur de séance remis à zéro. Le camp fait partie de la séance.
  useEffect(() => {
    setDrill(null)
    setShowAll(false)
    setFilter('all')
    setSession({ ok: 0, total: 0 })
  }, [fam?.key, color])
  useEffect(() => {
    document.querySelector('main')?.scrollTo(0, 0)
  }, [fam?.key])

  const positions = useMemo(() => (fam ? nextMovePositions(fam, color) : []), [fam, color])
  // État des variantes et réussites par mode : recalculés seulement quand la progression change.
  const familyStats = useMemo(() => {
    if (!fam) return null
    const statuses = new Map<Variant, VariantStatus>(fam.variants.map((v) => [v, variantStatus(progress, color, v)]))
    const values = [...statuses.values()]
    return {
      statuses,
      mastered: values.filter((v) => v === 'mastered').length,
      review: values.filter((v) => v === 'review').length,
      next: modeStats(progress, fam, color, 'next'),
      suite: modeStats(progress, fam, color, 'suite'),
    }
  }, [fam, color, progress])

  function getEngine(): Engine {
    engineRef.current ??= new Engine()
    return engineRef.current
  }

  function openFamily(key: string) {
    setQuery('')
    setParams({ famille: key })
  }

  function setOption(name: 'camp' | 'longueur', value: string) {
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        next.set(name, value)
        return next
      },
      { replace: true },
    )
  }

  function makeItem(f: Family, mode: DrillMode, chosen?: Variant, prev?: DrillItem): DrillItem | null {
    if (mode === 'full') {
      return { mode, variant: chosen ?? pickVariant(f, color, progress, prev?.variant ?? undefined), start: 0, position: null }
    }
    if (mode === 'suite') {
      const { variant, start } = pickSuite(f, color, 5, plyTarget, progress, prev?.variant ?? undefined)
      return { mode, variant, start, position: null }
    }
    if (positions.length === 0) return null
    const prevKey = prev?.position?.join(' ')
    let pos = positions[Math.floor(Math.random() * positions.length)]
    for (let i = 0; i < 5 && positions.length > 1 && pos.join(' ') === prevKey; i++) {
      pos = positions[Math.floor(Math.random() * positions.length)]
    }
    return { mode, variant: null, start: pos.length, position: pos }
  }

  function startDrill(mode: DrillMode, chosen?: Variant) {
    if (!fam) return
    const item = makeItem(fam, mode, chosen)
    if (item) setDrill((d) => ({ item, key: (d?.key ?? 0) + 1, retry: false }))
  }

  async function onResult(item: DrillItem, retry: boolean, success: boolean) {
    if (item.mode === 'next' && retry) return
    const moves = item.mode === 'next' ? (item.position ?? []) : (item.variant?.moves ?? [])
    setSession((s) => ({ ok: s.ok + (success ? 1 : 0), total: s.total + 1 }))
    try {
      await recordDrill(item.mode, color, moves, success)
      setProgress(await loadProgress())
      setSaveError(false)
    } catch {
      setSaveError(true)
    }
  }

  // ---------- Drill (par-dessus la fiche, qui garde son défilement) ----------
  const drillView = fam && drill && (
    <OpeningDrill
      key={drill.key}
      fam={fam}
      color={color}
      item={drill.item}
      plyTarget={plyTarget}
      getEngine={getEngine}
      session={session}
      onResult={(ok) => void onResult(drill.item, drill.retry, ok)}
      onRetry={() => setDrill({ item: drill.item, key: drill.key + 1, retry: true })}
      onNext={() => {
        const next = makeItem(fam, drill.item.mode, undefined, drill.item)
        if (next) setDrill({ item: next, key: drill.key + 1, retry: false })
      }}
      onClose={() => setDrill(null)}
      onAnalyse={(moves) =>
        navigate('/analyse', {
          state: {
            fen: START_FEN,
            uci: moves,
            orientation: color,
            label: drill.item.variant ? openingFr(drill.item.variant.line.name) : fam.label,
            returnTo: `/ouvertures?${params.toString()}`,
          },
        })
      }
    />
  )

  // ---------- Fiche d'une ouverture ----------
  if (fam) {
    const { statuses, mastered, review, next, suite } = familyStats!
    const filtered = fam.variants.filter((v) => filter === 'all' || statuses.get(v) === filter)
    const shown = showAll ? filtered : filtered.slice(0, PAGE_SIZE)
    const lengthText = plyTarget === null ? "jusqu'à la fin de la théorie" : `jusqu'au coup ${plyTarget / 2}, prolongée par Stockfish`

    const modes: { mode: DrillMode; icon: string; desc: string; stat: string; disabled?: boolean }[] = [
      { mode: 'next', icon: '🎯', desc: "Une position de l'ouverture : trouve un coup théorique.", stat: next.total ? `${next.ok}/${next.total}` : '', disabled: positions.length === 0 },
      { mode: 'suite', icon: '➡️', desc: "Une position en cours de variante : ses 5 coups d'après.", stat: suite.total ? `${suite.ok}/${suite.total}` : '' },
      { mode: 'full', icon: '🔁', desc: `Une variante au hasard, du premier coup ${lengthText}.`, stat: mastered ? `${mastered} ✓` : '' },
    ]

    return (
      <>
        <div className="mx-auto max-w-2xl p-4 md:p-6">
          <button
            onClick={() => setParams({}, { replace: true })}
            className="mb-2 -ml-1 cursor-pointer px-1 py-1 text-sm font-semibold text-neutral-400 hover:text-white"
          >
            ‹ Ouvertures
          </button>
          <h1 className="text-2xl font-black">{fam.label}</h1>
          <p className="mb-1 text-sm text-neutral-400">
            {fam.mainLine.eco} · <MoveText moves={uciMoves(fam.mainLine.uci)} />
          </p>
          <p data-progress className="mb-4 text-sm text-neutral-300">
            <b className={mastered ? 'text-accent' : ''}>{mastered} maîtrisée{mastered > 1 ? 's' : ''}</b>
            {' · '}
            <b className={review ? 'text-red-300' : ''}>{review} à revoir</b>
            {' · '}
            {fam.variants.length} variante{fam.variants.length > 1 ? 's' : ''}
          </p>
          {saveError && (
            <p role="alert" className="mb-4 rounded bg-red-900/40 px-3 py-2 text-sm text-red-200">
              La dernière tentative n'a pas pu être enregistrée (stockage indisponible).
            </p>
          )}

          <div className="mb-4 flex flex-col gap-2">
            <Segmented
              label="Camp"
              options={[{ id: 'w', label: 'Blancs' }, { id: 'b', label: 'Noirs' }]}
              value={color}
              onChange={(v) => setOption('camp', v)}
            />
            <Segmented label="Longueur" options={LENGTHS.map((l) => ({ id: l.id, label: l.label }))} value={lengthId} onChange={(v) => setOption('longueur', v)} />
          </div>

          <div className="mb-6 flex flex-col gap-2">
            {modes.map((m) => (
              <button
                key={m.mode}
                data-mode={m.mode}
                onClick={() => startDrill(m.mode)}
                disabled={m.disabled}
                className="flex cursor-pointer items-center gap-3 rounded-xl bg-surface-2 p-3 text-left hover:bg-surface-3 disabled:cursor-default disabled:opacity-40"
              >
                <span className="text-2xl" aria-hidden="true">{m.icon}</span>
                <span className="min-w-0 flex-1">
                  <span className="block font-bold">{MODE_LABEL[m.mode]}</span>
                  <span className="block text-xs text-neutral-400">{m.disabled ? 'Aucune position pour ce camp.' : m.desc}</span>
                </span>
                {m.stat && <span className="shrink-0 text-sm font-bold text-accent">{m.stat}</span>}
              </button>
            ))}
          </div>

          <div className="mb-2 flex flex-wrap items-center gap-2">
            <h2 className="mr-auto text-lg font-black">Variantes</h2>
            {(
              [
                { id: 'all', label: 'Toutes', n: fam.variants.length },
                { id: 'review', label: 'À revoir', n: review },
                { id: 'new', label: 'Nouvelles', n: fam.variants.length - mastered - review },
              ] as const
            ).map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  setFilter(c.id)
                  setShowAll(false)
                }}
                aria-pressed={filter === c.id}
                className={`cursor-pointer rounded-full px-3 py-1 text-xs font-bold ${filter === c.id ? 'bg-neutral-100 text-neutral-900' : 'bg-surface-2 text-neutral-300 hover:bg-surface-3'}`}
              >
                {c.label} {c.n}
              </button>
            ))}
          </div>
          <ul className="flex flex-col gap-1.5">
            {shown.map((v) => (
              <li key={v.line.uci}>
                <VariantRow variant={v} status={statuses.get(v)!} onClick={() => startDrill('full', v)} />
              </li>
            ))}
          </ul>
          {filtered.length === 0 && <p className="py-4 text-center text-sm text-neutral-500">Aucune variante dans ce filtre.</p>}
          {!showAll && filtered.length > PAGE_SIZE && (
            <button
              onClick={() => setShowAll(true)}
              className="mt-2 w-full cursor-pointer rounded-xl bg-surface-2 py-2.5 text-sm font-bold text-neutral-300 hover:bg-surface-3"
            >
              Afficher les {filtered.length - PAGE_SIZE} autres
            </button>
          )}
        </div>
        {drillView}
      </>
    )
  }

  // ---------- Accueil ----------
  const hits = searchFamilies(query)
  const mastered = (f: Family) => f.variants.filter((v) => variantStatus(progress, f.defaultColor, v) === 'mastered').length
  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <Link to="/apprendre" className="mb-2 -ml-1 inline-block px-1 py-1 text-sm font-semibold text-neutral-400 hover:text-white">
        ‹ Apprendre
      </Link>
      <h1 className="mb-1 text-2xl font-black">📖 Entraîneur d'ouvertures</h1>
      <p className="mb-4 text-sm text-neutral-400">
        Choisis une ouverture, puis trouve le prochain coup, la suite ou toute une variante, jusqu'au coup 15.
      </p>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Rechercher une ouverture"
        aria-label="Rechercher une ouverture"
        className="mb-4 w-full rounded-xl bg-surface-2 px-4 py-3 text-base text-white placeholder:text-neutral-500 focus:ring-2 focus:ring-accent focus:outline-none"
      />
      {query.trim() ? (
        hits.length ? (
          <ul className="flex flex-col gap-1.5">
            {hits.slice(0, 40).map(({ family: f, via }) => (
              <li key={f.key}>
                <button
                  data-family={f.key}
                  onClick={() => openFamily(f.key)}
                  className="flex w-full cursor-pointer items-center gap-3 rounded-xl bg-surface-2 px-3 py-2.5 text-left hover:bg-surface-3"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-bold">{f.label}</span>
                    {via && <span className="block truncate text-xs text-neutral-400">{via}</span>}
                  </span>
                  <span className="shrink-0 text-xs text-neutral-500">
                    {f.variants.length} variante{f.variants.length > 1 ? 's' : ''}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="py-6 text-center text-sm text-neutral-500">Aucune ouverture trouvée.</p>
        )
      ) : (
        <>
          <h2 className="mb-2 text-sm font-semibold text-neutral-400">Les plus courantes</h2>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
            {popularFamilies().map((f) => {
              const m = mastered(f)
              return (
                <button
                  key={f.key}
                  data-family={f.key}
                  onClick={() => openFamily(f.key)}
                  className="flex min-h-[4.25rem] cursor-pointer flex-col justify-center rounded-xl bg-surface-2 px-3 py-2 text-left hover:bg-surface-3"
                >
                  <span className="block leading-tight font-bold">{f.label}</span>
                  <span className="mt-0.5 block text-xs text-neutral-400">
                    {f.variants.length} variantes{m > 0 && <span className="font-bold text-accent"> · {m} ✓</span>}
                  </span>
                </button>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

function Segmented<T extends string>({ label, options, value, onChange }: {
  label: string
  options: { id: T; label: string }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-[4.5rem] shrink-0 text-sm font-semibold text-neutral-400">{label}</span>
      <div role="group" aria-label={label} className="flex min-w-0 flex-1 gap-1 rounded-lg bg-surface-2 p-1">
        {options.map((o) => (
          <button
            key={o.id}
            onClick={() => onChange(o.id)}
            aria-pressed={value === o.id}
            className={`flex-1 cursor-pointer rounded-md px-1 py-1.5 text-[13px] font-bold whitespace-nowrap ${value === o.id ? 'bg-surface-3 text-white shadow' : 'text-neutral-400 hover:text-white'}`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// Coups en notation figurine : « 1.e4 e5 2.♘f3 ♘c6 3.d4 ».
function MoveText({ moves, from = 0 }: { moves: string[]; from?: number }) {
  const text = useMemo(() => {
    const c = new Chess()
    const parts: string[] = []
    moves.forEach((m, i) => {
      const san = c.move({ from: m.slice(0, 2), to: m.slice(2, 4), promotion: m[4] }).san
      if (i < from) return
      const fig = figurine(san, i % 2 === 0 ? 'w' : 'b')
      parts.push(i % 2 === 0 ? `${i / 2 + 1}.${fig}` : i === from ? `${Math.ceil(i / 2)}…${fig}` : fig)
    })
    return parts.join(' ')
  }, [moves, from])
  return <>{text}</>
}

function VariantRow({ variant, status, onClick }: { variant: Variant; status: VariantStatus; onClick: () => void }) {
  // Les 4 derniers demi-coups distinguent les variantes homonymes.
  const from = Math.max(0, variant.moves.length - 4)
  return (
    <button
      data-variant={variant.line.uci}
      onClick={onClick}
      className="flex w-full cursor-pointer items-center gap-3 rounded-xl bg-surface-2 px-3 py-2 text-left hover:bg-surface-3"
    >
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-bold">{variant.label}</span>
        <span className="block truncate text-xs text-neutral-400">
          <MoveText moves={variant.moves} from={from} />
        </span>
      </span>
      {status === 'mastered' && <span className="shrink-0 rounded-full bg-accent/20 px-2 py-0.5 text-xs font-bold text-accent">Maîtrisée</span>}
      {status === 'review' && <span className="shrink-0 rounded-full bg-red-900/50 px-2 py-0.5 text-xs font-bold text-red-300">À revoir</span>}
    </button>
  )
}
