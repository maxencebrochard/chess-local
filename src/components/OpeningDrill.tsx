// Drill de l'entraîneur d'ouvertures, en plein écran, façon chess.com Drills : le joueur joue
// son camp, l'adversaire répond la ligne, une faute montre le coup attendu (flèche bleue) et il
// faut le rejouer. Au-delà de la ligne lichess, Stockfish prolonge la variante (profondeur fixe,
// résultat mémorisé par position : « Réessayer » redemande les mêmes coups).
import { useEffect, useMemo, useRef, useState } from 'react'
import { Chess, type Move } from 'chess.js'
import { Board, type BoardArrow } from './Board'
import { ExerciseFeedback, ExerciseHeader, ExercisePromptActions, ExerciseScreen, ExerciseStage, type ExerciseVerdict } from './Exercise'
import { sounds } from '../lib/sounds'
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

// Drill jugé, tel qu'affiché : l'appelant le garde avec sa séance avant d'ouvrir l'analyseur et le
// rend au retour (prop `snapshot`), qui reprend le verdict à l'identique sans nouvelle écriture.
export interface DrillSnapshot {
  plies: { uci: string; src: Source }[]
  faults: number
  engineMisses: number
  result: { success: boolean; empty?: boolean }
  msg: { tone: Tone; text: string } | null
  arrows: BoardArrow[]
}

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
  onAnalyse: (moves: string[], snapshot: DrillSnapshot) => void
  snapshot?: DrillSnapshot | null // retour de l'analyseur : verdict restauré, déjà enregistré
  session: { ok: number; total: number }
  // Habillage de séance (révision espacée) : titre à la place du mode et compteur masqué, ligne
  // d'état sous l'en-tête, libellé du bouton suivant, ligne sous le verdict (« Revient dans 3 jours »).
  title?: string
  subtitle?: string
  // Série (révision, séance du jour, parcours) : « n/N » et barre dans l'en-tête.
  progress?: { index: number; total: number; done: number; counterProps?: Record<string, string> }
  nextLabel?: string
  resultNote?: string | null
}

const SUITE_COUNT = 5
// Zone de décision du drill : trois lignes de message (théorie attendue, coups théoriques) plus
// la ligne d'état et la rangée d'actions.
const DRILL_ZONE_REM = 9.75
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

  const restored = props.snapshot ?? null
  const [plies, setPlies] = useState<{ uci: string; src: Source }[]>(() => restored?.plies ?? initial.map((uci) => ({ uci, src: 'given' })))
  const [pending, setPending] = useState<string | null>(null) // coup du joueur en cours de vérification
  const [thinking, setThinking] = useState(false)
  const [msg, setMsg] = useState<{ tone: Tone; text: string } | null>(restored?.msg ?? null)
  const [arrows, setArrows] = useState<BoardArrow[]>(restored?.arrows ?? [])
  const [hint, setHint] = useState<string | null>(null)
  const [faults, setFaults] = useState(restored?.faults ?? 0) // fautes de théorie et indices
  const [engineMisses, setEngineMisses] = useState(restored?.engineMisses ?? 0) // écarts avec Stockfish, hors maîtrise
  const [result, setResult] = useState<{ success: boolean; empty?: boolean } | null>(restored?.result ?? null)
  const alive = useRef(true)
  const recorded = useRef(restored !== null) // verdict restauré : déjà écrit avant l'analyse
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
    ;(success ? sounds.success : sounds.fail)()
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

  function handleMove(from: string, to: string, promotion?: string): Move | false {
    if (result || pending || thinking || !myTurn) return false
    let mv: Move
    try {
      mv = new Chess(fen).move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    const played = mv.from + mv.to + (mv.promotion ?? '')
    if (mode === 'next') return judgeNext(played, mv.san) && mv
    if (!inEngine) return judgeBook(played, mv.san) && mv
    judgeEngine(played, mv.san)
    return mv
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
    ok: 'text-accent-light',
    bad: 'text-red-200',
    info: 'text-sky-200',
    engine: 'text-neutral-300',
  }
  const last = pending ?? moves[moves.length - 1]
  const lastMove = last ? { from: last.slice(0, 2), to: last.slice(2, 4) } : null
  const interactive = !result && !pending && !thinking && myTurn
  const nextLabel = props.nextLabel ?? (mode === 'next' ? 'Position suivante' : mode === 'suite' ? 'Suite suivante' : 'Variante suivante')
  const stats = `${engineMisses > 0 ? `${engineMisses} écart${engineMisses > 1 ? 's' : ''} avec Stockfish · ` : ''}${
    mode !== 'next' && plyTarget === null && moves.length >= variant!.moves.length ? 'Fin de la théorie connue' : `${moves.length} demi-coups`}`
  // Explication du verdict : le dernier message (coup trouvé, théorie attendue, Stockfish muet),
  // sinon le bilan de la ligne. La note de droite porte l'échéance d'une révision ou le compte.
  const reason = result && (msg?.text ?? (result.success ? 'Ligne déroulée sans faute.' : 'Rejoue la ligne pour la fixer.'))
  const verdict: ExerciseVerdict | null = result
    ? {
        tone: result.empty ? 'neutral' : result.success ? 'success' : 'review',
        label: result.empty ? 'Non comptée' : result.success
          ? mode === 'full' ? 'Variante maîtrisée' : mode === 'suite' ? 'Suite réussie' : 'Trouvé du premier coup'
          : `À revoir${faults > 0 ? ` · ${faults} faute${faults > 1 ? 's' : ''}` : ''}`,
        reason,
        note: props.resultNote && !result.empty ? <span data-result-note>{props.resultNote}</span> : <span>{stats}</span>,
      }
    : null

  return (
    <ExerciseScreen
      data-drill
      data-mode={mode}
      data-uci={moves.join(' ')}
      data-hint={hint ?? undefined}
      data-variant-uci={variant?.line.uci}
    >
      <ExerciseHeader
        title={<>{props.title ?? MODE_LABEL[mode]}<span className="ml-2 text-sm font-semibold text-neutral-400">{fam.label}</span></>}
        index={props.progress?.index}
        total={props.progress?.total}
        done={props.progress?.done}
        counterProps={props.progress?.counterProps}
        onClose={props.onClose}
        closeLabel="Fermer le drill"
        action={
          <span className="text-sm font-bold text-accent" title="Réussites de la séance">
            {props.title === undefined && props.session.total > 0 ? `${props.session.ok}/${props.session.total}` : ''}
          </span>
        }
      />
      <ExerciseStage
        zone={DRILL_ZONE_REM}
        above={
          <div className="flex h-7 items-center gap-2">
            <span data-variant-name className="min-w-0 flex-1 truncate text-sm font-semibold text-neutral-200">
              {title}
            </span>
            {extended && inEngine && (
              <span className="shrink-0 rounded-full bg-surface-3 px-2 py-0.5 text-xs font-bold text-neutral-300">
                ⚙ Stockfish{thinking ? '…' : ''}
              </span>
            )}
          </div>
        }
        feedback={
          <ExerciseFeedback
            verdict={verdict}
            reasonLines={3}
            zoneProps={{ 'data-result': result ? (result.empty ? 'empty' : result.success ? 'ok' : 'review') : undefined }}
            prompt={
              <>
                <span className={`line-clamp-2 ${msg ? toneClass[msg.tone] : ''}`}>{msg?.text ?? prompt}</span>
                {props.subtitle && <span className="mt-1 block truncate text-xs font-semibold text-neutral-400">{props.subtitle}</span>}
              </>
            }
            promptActions={
              <ExercisePromptActions
                secondary={[
                  { label: 'Indice', icon: '💡', onClick: showHint, disabled: !!hint || !!pending || thinking || !myTurn },
                  ...(mode === 'next' ? [{ label: props.nextLabel ?? 'Position suivante', icon: '→', onClick: props.onNext }] : []),
                ]}
              />
            }
            onNext={props.onNext}
            nextLabel={nextLabel}
            onRetry={props.onRetry}
            onAnalyse={() => result && props.onAnalyse(moves, { plies, faults, engineMisses, result, msg, arrows })}
          />
        }
        below={
          <div ref={stripRef} data-moves className="flex min-h-9 items-center gap-1 overflow-x-auto px-1.5 py-1.5 whitespace-nowrap [scrollbar-width:none]">
            {plies.map((p, i) => (
              <span key={i} className="flex shrink-0 items-center gap-1">
                {i % 2 === 0 && <span className="text-sm text-neutral-400">{i / 2 + 1}.</span>}
                <span
                  data-engine={p.src === 'engine' ? '' : undefined}
                  className={`rounded px-1 text-[15px] font-bold ${p.src === 'given' ? 'text-neutral-400' : p.src === 'engine' ? 'text-neutral-300' : 'text-neutral-100'}`}
                >
                  {figurine(sans[i] ?? p.uci, i % 2 === 0 ? 'w' : 'b')}
                  {p.src === 'engine' && <span className="ml-0.5 text-xs text-neutral-400" title="Coup de Stockfish">⚙</span>}
                </span>
              </span>
            ))}
          </div>
        }
      >
        <Board
          fen={displayFen}
          orientation={color}
          interactive={interactive}
          movableColor={color}
          onMove={handleMove}
          lastMove={lastMove}
          arrows={arrows}
        />
      </ExerciseStage>
    </ExerciseScreen>
  )
}
