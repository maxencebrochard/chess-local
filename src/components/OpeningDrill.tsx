// Drill de l'entraîneur d'ouvertures, en plein écran, façon chess.com Drills : le joueur joue
// son camp, l'adversaire répond la ligne, une faute montre le coup attendu (flèche bleue) et il
// faut le rejouer. Au-delà de la ligne lichess, Stockfish prolonge la variante (profondeur fixe,
// résultat mémorisé par position : « Réessayer » redemande les mêmes coups).
import { useEffect, useMemo, useRef, useState } from 'react'
import { Chess } from 'chess.js'
import { Board, type BoardArrow } from './Board'
import { Cta } from './Cta'
import type { Engine, EngineLine } from '../lib/engine'
import { isBookPosition, openingForMoves } from '../lib/openings'
import { openingFr } from '../lib/openingNames'
import {
  ENGINE_TOLERANCE_CP, MODE_LABEL, familyContinuations, lineScore, positionName, variantLabel,
  type Color, type DrillMode, type Family, type Variant,
} from '../lib/openingTrainer'
import { figurine } from '../lib/review'

export interface DrillItem {
  mode: DrillMode
  variant: Variant | null // suite, full
  start: number // demi-coups déjà joués au départ
  position: string[] | null // next
}

type Source = 'given' | 'book' | 'engine'
type Tone = 'ok' | 'bad' | 'info' | 'engine'

interface Props {
  fam: Family
  color: Color
  item: DrillItem
  plyTarget: number | null // null : théorie seule
  getEngine: () => Engine
  onResult: (success: boolean) => void // appelé une seule fois par drill
  onRetry: () => void
  onNext: () => void
  onClose: () => void
  onAnalyse: (moves: string[]) => void
  session: { ok: number; total: number }
  // Habillage de séance (révision espacée) : titre à la place du mode et compteur masqué, ligne
  // d'état sous l'en-tête, libellé du bouton suivant, ligne sous le verdict (« Revient dans 3 jours »).
  title?: string
  subtitle?: string
  nextLabel?: string
  resultNote?: string | null
}

const SUITE_COUNT = 5
const ENGINE_DEPTH = 14
const REPLY_DELAY_MS = 450
const BLUE = '#69c3f2'
const ARROW_COLORS = [BLUE, '#81b64c', '#f2b04c']

interface Analysis {
  lines: EngineLine[] // multipv, meilleure d'abord (peut être vide)
  best: string | null // meilleur coup : lines[0], sinon le bestmove brut du moteur
}

// Analyses mémorisées par moteur puis par FEN : la première réussie fait foi pour la session de
// la page. Une recherche en échec sort du cache pour être relancée au prochain appel.
const analyses = new WeakMap<Engine, Map<string, Promise<Analysis>>>()

function analyse(engine: Engine, fen: string): Promise<Analysis> {
  let byFen = analyses.get(engine)
  if (!byFen) analyses.set(engine, (byFen = new Map()))
  const cache = byFen
  let p = cache.get(fen)
  if (!p) {
    p = engine.search({ fen, depth: ENGINE_DEPTH, multipv: 3 }).then(
      (r) => {
        const lines = r.lines.filter((l) => l.pv.length > 0)
        const raw = r.bestMove && r.bestMove !== '(none)' ? r.bestMove : null
        return { lines, best: lines[0]?.pv[0] ?? raw }
      },
      (e: unknown) => {
        cache.delete(fen)
        throw e
      },
    )
    cache.set(fen, p)
  }
  return p
}

function play(moves: string[]): Chess {
  const c = new Chess()
  for (const m of moves) c.move({ from: m.slice(0, 2), to: m.slice(2, 4), promotion: m[4] })
  return c
}

function sanOf(moves: string[], uci: string): string {
  try {
    return play(moves).move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] }).san
  } catch {
    return uci
  }
}

const arrow = (uci: string, color = BLUE): BoardArrow => ({ startSquare: uci.slice(0, 2), endSquare: uci.slice(2, 4), color })

export function OpeningDrill(props: Props) {
  const { fam, color, item, plyTarget, getEngine, onResult } = props
  const mode = item.mode
  const variant = item.variant
  const initial = mode === 'next' ? (item.position ?? []) : (variant?.moves.slice(0, item.start) ?? [])

  const [plies, setPlies] = useState<{ uci: string; src: Source }[]>(() => initial.map((uci) => ({ uci, src: 'given' })))
  const [pending, setPending] = useState<string | null>(null) // coup du joueur en cours de vérification
  const [thinking, setThinking] = useState(false)
  const [msg, setMsg] = useState<{ tone: Tone; text: string } | null>(null)
  const [arrows, setArrows] = useState<BoardArrow[]>([])
  const [hint, setHint] = useState<string | null>(null)
  const [faults, setFaults] = useState(0) // fautes de théorie et indices
  const [engineMisses, setEngineMisses] = useState(0) // écarts avec Stockfish, hors maîtrise
  const [result, setResult] = useState<{ success: boolean; empty?: boolean } | null>(null)
  const alive = useRef(true)
  const recorded = useRef(false)
  const plannedReply = useRef<{ after: string; move: string } | null>(null)
  const stripRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  const moves = useMemo(() => plies.map((p) => p.uci), [plies])
  const chess = useMemo(() => play(moves), [moves])
  const fen = chess.fen()
  const displayFen = useMemo(() => (pending ? play([...moves, pending]).fen() : fen), [moves, pending, fen])
  const sans = useMemo(() => chess.history(), [chess])

  // Bornes de la ligne : fin de la théorie lichess utilisée, puis fin du drill.
  const lineEnd = variant ? (plyTarget ?? variant.moves.length) : 0
  const bookLen = variant ? Math.min(variant.moves.length, lineEnd) : 0
  const end = mode === 'suite' ? Math.min(item.start + 2 * SUITE_COUNT - 1, lineEnd) : lineEnd
  const extended = mode !== 'next' && bookLen < end
  const inEngine = mode !== 'next' && moves.length >= bookLen && extended
  const turn: Color = moves.length % 2 === 0 ? 'w' : 'b'
  const myTurn = turn === color
  const fig = (san: string, ply = moves.length) => figurine(san, ply % 2 === 0 ? 'w' : 'b')

  function record(success: boolean) {
    if (recorded.current) return
    recorded.current = true
    onResult(success)
  }

  // Stockfish muet (aucun coup) ou en échec : la variante s'arrête là, sans être comptée.
  function engineFailed() {
    setThinking(false)
    setPending(null)
    setResult({ success: false, empty: true })
    setMsg({ tone: 'engine', text: 'Stockfish ne répond pas : la variante s\'arrête ici. Réessaie.' })
  }

  function finish(success: boolean) {
    record(success)
    setResult({ success })
  }

  function commit(uci: string, src: Source) {
    const next = [...moves, uci]
    setPlies((p) => [...p, { uci, src }])
    setArrows([])
    setHint(null)
    return next
  }

  // Fin de ligne (variante, suite) : longueur atteinte ou partie terminée. Une ligne où le
  // joueur n'a rien joué (ex. 1.c3 côté Noirs) ne compte pas : ni réussite ni échec.
  useEffect(() => {
    if (mode === 'next' || result || pending) return
    if (moves.length < end && !chess.isGameOver()) return
    const played = plies.some((p, i) => p.src !== 'given' && (i % 2 === 0) === (color === 'w'))
    if (played) finish(faults === 0)
    else {
      setResult({ success: false, empty: true })
      setMsg({ tone: 'engine', text: `Rien à jouer pour les ${color === 'w' ? 'Blancs' : 'Noirs'} dans cette ligne.` })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moves])

  // Coup adverse : la ligne lichess, puis Stockfish.
  useEffect(() => {
    if (mode === 'next' || result || pending || myTurn || moves.length >= end || chess.isGameOver()) return
    const i = moves.length
    if (i < bookLen) {
      const t = setTimeout(() => commit(variant!.moves[i], 'book'), REPLY_DELAY_MS)
      return () => clearTimeout(t)
    }
    const planned = plannedReply.current
    if (planned && planned.after === moves.join(' ')) {
      const t = setTimeout(() => commit(planned.move, 'engine'), REPLY_DELAY_MS)
      return () => clearTimeout(t)
    }
    let cancelled = false
    setThinking(true)
    void analyse(getEngine(), fen).then(
      ({ best }) => {
        if (cancelled || !alive.current) return
        setThinking(false)
        if (best) commit(best, 'engine')
        else engineFailed()
      },
      () => {
        if (cancelled || !alive.current) return
        engineFailed()
      },
    )
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moves, result, pending])

  // Annonce du relais Stockfish, et analyse lancée dès que la position apparaît (le joueur
  // réfléchit pendant ce temps).
  useEffect(() => {
    if (!inEngine || result) return
    if (moves.length === bookLen) {
      setMsg({ tone: 'engine', text: `⚙ Fin de la théorie lichess au coup ${Math.max(1, Math.ceil(bookLen / 2))} : la suite est celle de Stockfish.` })
    }
    if (myTurn && !chess.isGameOver()) analyse(getEngine(), fen).catch(() => undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moves, inEngine])

  // Liste des coups : toujours le dernier en vue.
  useEffect(() => {
    const s = stripRef.current
    if (s) s.scrollLeft = s.scrollWidth
  }, [plies])

  // ---------- Coups du joueur ----------

  function handleMove(from: string, to: string, promotion?: string): boolean {
    if (result || pending || thinking || !myTurn) return false
    let san: string
    let played: string
    try {
      const mv = new Chess(fen).move({ from, to, promotion: promotion ?? 'q' })
      san = mv.san
      played = mv.from + mv.to + (mv.promotion ?? '')
    } catch {
      return false
    }
    if (mode === 'next') return judgeNext(played, san)
    if (!inEngine) return judgeBook(played, san)
    judgeEngine(played, san)
    return true
  }

  function judgeNext(played: string, san: string): boolean {
    const conts = familyContinuations(fam, moves)
    const hit = conts.find((c) => c.move === played)
    if (hit) {
      const first = !recorded.current
      commit(played, 'book')
      const others = conts.filter((c) => c.move !== played).slice(0, 3).map((c) => fig(sanOf(moves, c.move)))
      setMsg({
        tone: 'ok',
        text: `✓ Théorique : ${fig(san)} · ${variantLabel(hit.line.name, fam.label)}${others.length ? `. Autres coups théoriques : ${others.join(', ')}` : ''}`,
      })
      finish(first && faults === 0)
      return true
    }
    if (isBookPosition([...moves, played])) {
      const other = openingForMoves([...moves, played])
      setMsg({ tone: 'info', text: `Coup théorique${other ? ` (${openingFr(other.name)})` : ''}, mais il sort de l'ouverture travaillée. Réessaie.` })
      return false
    }
    setFaults((f) => f + 1)
    record(false)
    showTheory(conts, '✗ Hors théorie. La théorie joue')
    return false
  }

  // Flèches (3 au plus) et légende des coups théoriques de la position.
  function showTheory(conts: ReturnType<typeof familyContinuations>, prefix: string) {
    const top = conts.slice(0, 3)
    setArrows(top.map((c, i) => arrow(c.move, ARROW_COLORS[i])))
    setHint(top[0]?.move ?? null)
    const list = top.map((c) => `${fig(sanOf(moves, c.move))} (${variantLabel(c.line.name, fam.label)})`).join(', ')
    setMsg({ tone: 'bad', text: `${prefix} : ${list}.` })
  }

  function judgeBook(played: string, san: string): boolean {
    const expected = variant!.moves[moves.length]
    if (played === expected) {
      const next = commit(played, 'book')
      const named = positionName(fam, next)
      setMsg({ tone: 'ok', text: `✓ ${fig(san)}${named ? ` · ${openingFr(named.name)}` : ''}` })
      return true
    }
    const alt = familyContinuations(fam, moves).find((c) => c.move === played)
    if (alt) {
      setMsg({ tone: 'info', text: `Coup théorique aussi (${openingFr(alt.line.name)}), mais cette variante continue autrement. Réessaie.` })
      return false
    }
    if (isBookPosition([...moves, played])) {
      const other = openingForMoves([...moves, played])
      setMsg({ tone: 'info', text: `Coup théorique${other ? ` (${openingFr(other.name)})` : ''}, mais il sort de l'ouverture travaillée. Réessaie.` })
      return false
    }
    setFaults((f) => f + 1)
    setArrows([arrow(expected)])
    setHint(expected)
    const named = positionName(fam, [...moves, expected])
    setMsg({
      tone: 'bad',
      text: `✗ Hors théorie : ici la théorie joue ${fig(sanOf(moves, expected))}${named ? ` (${openingFr(named.name)})` : ''}. Rejoue-le.`,
    })
    return false
  }

  function judgeEngine(played: string, san: string) {
    setPending(played)
    setThinking(true)
    setMsg({ tone: 'engine', text: 'Stockfish vérifie…' })
    const before = moves
    analyse(getEngine(), fen).then(({ lines, best: bestMove }) => {
      if (!alive.current) return
      setPending(null)
      setThinking(false)
      if (!bestMove) return engineFailed()
      const best = lines[0]
      if (played === bestMove) {
        commit(played, 'engine')
        if (best?.pv[1]) plannedReply.current = { after: [...before, played].join(' '), move: best.pv[1] }
        setMsg({ tone: 'ok', text: `✓ ${fig(san)} : le coup de Stockfish.` })
        return
      }
      const bestSan = fig(sanOf(before, bestMove))
      const mine = lines.find((l) => l.pv[0] === played)
      setArrows([arrow(bestMove)])
      setHint(bestMove)
      // Autre bon coup : à 30 cp du meilleur, et jamais un mat subi par le joueur.
      const close = best && mine && !(mine.scoreMate !== null && mine.scoreMate < 0) && lineScore(best) - lineScore(mine) <= ENGINE_TOLERANCE_CP
      if (close) {
        setMsg({ tone: 'info', text: `${fig(san)} est bon aussi selon Stockfish, mais la ligne continue par ${bestSan} : rejoue-le.` })
        return
      }
      setEngineMisses((n) => n + 1)
      setMsg({ tone: 'bad', text: `✗ Stockfish préfère ${bestSan}. Rejoue-le.` })
    }, () => {
      if (alive.current) engineFailed()
    })
  }

  function showHint() {
    if (hint || result || pending || thinking || !myTurn) return
    if (mode === 'next') {
      setFaults((f) => f + 1)
      record(false)
      showTheory(familyContinuations(fam, moves), 'Indice. La théorie joue')
      return
    }
    if (!inEngine) {
      const expected = variant!.moves[moves.length]
      setFaults((f) => f + 1)
      setArrows([arrow(expected)])
      setHint(expected)
      setMsg({ tone: 'info', text: 'Indice : joue le coup de la flèche.' })
      return
    }
    setThinking(true)
    setMsg({ tone: 'engine', text: 'Stockfish cherche…' })
    analyse(getEngine(), fen).then(({ best }) => {
      if (!alive.current) return
      setThinking(false)
      if (!best) return engineFailed()
      setEngineMisses((n) => n + 1)
      setArrows([arrow(best)])
      setHint(best)
      setMsg({ tone: 'info', text: 'Indice : le coup de Stockfish est sur la flèche.' })
    }, () => {
      if (alive.current) engineFailed()
    })
  }

  // ---------- Rendu ----------

  const sideFr = color === 'w' ? 'Blancs' : 'Noirs'
  const title = mode === 'next'
    ? openingFr(positionName(fam, initial)?.name ?? fam.mainLine.name)
    : openingFr(variant!.line.name)
  const prompt = mode === 'next'
    ? `Trait aux ${sideFr} : trouve un coup de la théorie.`
    : myTurn ? `Tu joues les ${sideFr} : à toi.` : 'L\'adversaire répond…'
  const toneClass: Record<Tone, string> = {
    ok: 'bg-accent/15 text-[#b5dc8c]',
    bad: 'bg-red-900/40 text-red-200',
    info: 'bg-sky-900/40 text-sky-200',
    engine: 'bg-surface-2 text-neutral-300',
  }
  const last = pending ?? moves[moves.length - 1]
  const lastMove = last ? { from: last.slice(0, 2), to: last.slice(2, 4) } : null
  const interactive = !result && !pending && !thinking && myTurn
  const nextLabel = props.nextLabel ?? (mode === 'next' ? 'Position suivante' : mode === 'suite' ? 'Suite suivante' : 'Variante suivante')

  return (
    <div className="pt-safe pb-safe fixed inset-0 z-40 overflow-y-auto bg-surface">
      <div
        data-drill
        data-mode={mode}
        data-uci={moves.join(' ')}
        data-hint={hint ?? undefined}
        data-variant-uci={variant?.line.uci}
        className="mx-auto flex min-h-full max-w-2xl flex-col"
      >
        <header className="flex items-center gap-2 px-3 py-1">
          <button
            onClick={props.onClose}
            aria-label="Fermer le drill"
            className="cursor-pointer p-1.5 text-2xl text-neutral-400 hover:text-white"
          >
            ✕
          </button>
          <h1 className="min-w-0 flex-1 truncate text-center text-lg font-black">
            {props.title ?? MODE_LABEL[mode]}
            <span className="ml-2 text-sm font-semibold text-neutral-500">{fam.label}</span>
          </h1>
          <span className="w-9 text-right text-sm font-bold text-accent" title="Réussites de la séance">
            {props.title === undefined && props.session.total > 0 ? `${props.session.ok}/${props.session.total}` : ''}
          </span>
        </header>
        {props.subtitle && <p className="px-3 pb-1 text-center text-xs font-semibold text-neutral-400">{props.subtitle}</p>}

        <div className="flex items-center gap-2 px-3 pb-1">
          <span data-variant-name className="min-w-0 flex-1 truncate text-sm font-semibold text-neutral-200">
            {title}
          </span>
          {extended && inEngine && (
            <span className="shrink-0 rounded-full bg-surface-3 px-2 py-0.5 text-xs font-bold text-neutral-300">
              ⚙ Stockfish{thinking ? '…' : ''}
            </span>
          )}
        </div>

        {/* Hauteur réservée (2 lignes) : le board ne saute pas quand un message apparaît. */}
        <p className={`mx-3 mb-2 flex h-[3.25rem] items-center overflow-hidden rounded px-3 py-1 text-sm leading-snug ${msg ? toneClass[msg.tone] : 'text-neutral-400'}`}>
          <span className="line-clamp-2">{msg?.text ?? prompt}</span>
        </p>

        <div className="flex justify-center">
          <div className="boardbox md:w-[min(56vh,520px)]">
            <Board
              fen={displayFen}
              orientation={color}
              interactive={interactive}
              movableColor={color}
              onMove={handleMove}
              lastMove={lastMove}
              arrows={arrows}
            />
          </div>
        </div>

        <div ref={stripRef} data-moves className="flex min-h-9 items-center gap-1 overflow-x-auto px-3 py-1.5 whitespace-nowrap [scrollbar-width:none]">
          {plies.map((p, i) => (
            <span key={i} className="flex shrink-0 items-center gap-1">
              {i % 2 === 0 && <span className="text-sm text-neutral-500">{i / 2 + 1}.</span>}
              <span
                data-engine={p.src === 'engine' ? '' : undefined}
                className={`rounded px-1 text-[15px] font-bold ${p.src === 'given' ? 'text-neutral-400' : p.src === 'engine' ? 'text-neutral-300' : 'text-neutral-100'}`}
              >
                {figurine(sans[i] ?? p.uci, i % 2 === 0 ? 'w' : 'b')}
                {p.src === 'engine' && <span className="ml-0.5 text-xs text-neutral-500" title="Coup de Stockfish">⚙</span>}
              </span>
            </span>
          ))}
        </div>

        {result ? (
          <div data-result={result.empty ? 'empty' : result.success ? 'ok' : 'review'} className="flex flex-col gap-2 px-3 py-2">
            <div className="flex items-baseline gap-2">
              <span className={`text-lg leading-tight font-black ${result.empty ? 'text-neutral-300' : result.success ? 'text-accent' : 'text-red-400'}`}>
                {result.empty ? 'Non comptée' : result.success
                  ? mode === 'full' ? '✓ Variante maîtrisée' : mode === 'suite' ? '✓ Suite réussie' : '✓ Trouvé du premier coup'
                  : `À revoir${faults > 0 ? ` · ${faults} faute${faults > 1 ? 's' : ''}` : ''}`}
              </span>
              <span className="min-w-0 flex-1 truncate text-right text-xs text-neutral-400">
                {engineMisses > 0 && `${engineMisses} écart${engineMisses > 1 ? 's' : ''} avec Stockfish · `}
                {mode !== 'next' && plyTarget === null && moves.length >= variant!.moves.length ? 'Fin de la théorie connue' : `${moves.length} demi-coups`}
              </span>
            </div>
            {props.resultNote && !result.empty && (
              <p data-result-note className="text-sm font-semibold text-neutral-300">
                {props.resultNote}
              </p>
            )}
            <div className="flex items-center gap-2">
              <button
                onClick={props.onRetry}
                className="flex cursor-pointer flex-col items-center rounded px-2 py-1 text-xs font-semibold text-neutral-300 hover:text-white"
              >
                <span className="text-lg leading-none">↺</span>
                Réessayer
              </button>
              <button
                onClick={() => props.onAnalyse(moves)}
                className="flex cursor-pointer flex-col items-center rounded px-2 py-1 text-xs font-semibold text-neutral-300 hover:text-white"
              >
                <span className="text-lg leading-none">♞</span>
                Analyser
              </button>
              <Cta className="ml-auto flex-1 px-4 py-2 text-base" onClick={props.onNext}>
                {nextLabel}
              </Cta>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-3 py-2">
            <button
              onClick={showHint}
              disabled={!!hint || !!pending || thinking || !myTurn}
              className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-surface-2 px-3 py-2 text-sm font-bold text-neutral-200 hover:bg-surface-3 disabled:cursor-default disabled:opacity-40"
            >
              💡 Indice
            </button>
            {mode === 'next' && (
              <button
                onClick={props.onNext}
                className="ml-auto cursor-pointer rounded-lg bg-surface-2 px-3 py-2 text-sm font-bold text-neutral-200 hover:bg-surface-3"
              >
                Position suivante
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
