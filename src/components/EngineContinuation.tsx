// « Aller plus loin » après un exercice, façon « Play vs computer » de chess.com : un calque
// plein écran qui reprend une position contre Stockfish (pleine force, sans limite de coups,
// jusqu'au mat, à la nulle ou à l'abandon), ou déroule la meilleure suite du moteur (« plan »).
// Hors score : le calque n'écrit rien en base, l'appelant garde son verdict tel quel.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Chess, type Move } from 'chess.js'
import { Board } from './Board'
import { Cta } from './Cta'
import { HEvalBar } from './HEvalBar'
import { Engine } from '../lib/engine'
import {
  endText, fenAfter, isTerminal, playUci, terminalEval, whiteEval,
  type ContinuationMode, type ContinuationOverlay,
} from '../lib/continuation'
import { figurine } from '../lib/review'
import { sounds } from '../lib/sounds'
import { useSettings } from '../store/settings'

const BOT_MOVETIME_MS = 500
const BOT_DELAY_MS = 250 // latence naturelle avant la réponse du moteur
const EVAL_MS = 300 // éval du tour du joueur : bornée en temps, le mutex moteur la fait passer avant la réponse
const PLAN_FIRST_MS = 1500
const PLAN_EXTEND_MS = 600
const PLAN_PLIES = 10 // longueur visée de la ligne du plan (demi-coups)
const PLAN_STEP_MS = 900 // déroulé automatique du plan

type Eval = { cp: number | null; mate: number | null }
const COLOR_FR = { w: 'Blancs', b: 'Noirs' } as const

// ---------- Ligne « Aller plus loin » sous le verdict d'un exercice ----------
export function GoFurtherRow({ planLabel, planFirst, onOpen }: {
  planLabel: string // « Voir la suite » / « Voir le plan »
  planFirst?: boolean
  onOpen: (mode: ContinuationMode) => void
}) {
  const play = (
    <button key="play" onClick={() => onOpen('play')} className={ROW_BUTTON}>
      <span aria-hidden className="text-base leading-none">🤖</span> Jouer contre le moteur
    </button>
  )
  const plan = (
    <button key="plan" onClick={() => onOpen('plan')} className={ROW_BUTTON}>
      <span aria-hidden className="text-base leading-none">💡</span> {planLabel}
    </button>
  )
  return <div className="flex flex-wrap gap-2 px-3 pb-2">{planFirst ? [plan, play] : [play, plan]}</div>
}

const ROW_BUTTON =
  'flex grow basis-auto cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-lg bg-surface-2 px-3 py-2.5 text-sm font-bold text-neutral-200 hover:bg-surface-3'

// ---------- Calque ----------
interface EngineContinuationProps {
  startFen: string
  playerColor: 'w' | 'b'
  mode: ContinuationMode
  initialMoves?: string[] // coups UCI déjà joués depuis startFen (calque restauré)
  initialResigned?: boolean
  label?: string // titre de la position dans l'analyseur
  returnTo?: string // si fourni, bouton « Analyser » (retour vers cette route)
  onBeforeAnalyse?: (overlay: ContinuationOverlay) => void
  onClose: () => void
}

export function EngineContinuation(props: EngineContinuationProps) {
  const { playerColor, onClose } = props
  const navigate = useNavigate()
  const [mode, setMode] = useState<ContinuationMode>(props.mode)
  const [start, setStart] = useState({ fen: props.startFen, moves: props.initialMoves ?? [], resigned: props.initialResigned ?? false, tick: 0 })
  const engineRef = useRef<Engine | null>(null)
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(
    () => () => {
      engineRef.current?.quit()
      engineRef.current = null
    },
    [],
  )

  // Dernier onClose reçu : l'appelant peut en passer un nouveau à chaque rendu.
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  // Focus dans le calque à l'ouverture, Échap pour revenir à l'exercice.
  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCloseRef.current()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  function getEngine(): Engine {
    engineRef.current ??= new Engine()
    return engineRef.current
  }

  function analyse(moves: string[], resigned: boolean) {
    if (!props.returnTo) return
    props.onBeforeAnalyse?.({ mode: 'play', startFen: start.fen, moves, resigned })
    navigate('/analyse', {
      state: { fen: start.fen, uci: moves, orientation: playerColor, label: props.label, returnTo: props.returnTo },
    })
  }

  const title = mode === 'plan' ? 'Le plan de Stockfish' : 'Contre Stockfish'
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      data-continuation={mode}
      className="pt-safe pb-safe fixed inset-0 z-50 overflow-y-auto overscroll-contain bg-surface"
    >
      <div className="mx-auto flex min-h-full max-w-2xl flex-col">
        <header className="flex items-center px-3 py-1">
          <button
            ref={closeRef}
            onClick={onClose}
            className="w-24 cursor-pointer p-1.5 text-left text-sm font-semibold text-neutral-400 hover:text-white"
          >
            ← Exercice
          </button>
          <h1 className="flex-1 truncate text-center text-lg font-black">{title}</h1>
          <span className="w-24" />
        </header>
        {mode === 'play' ? (
          <PlayPane
            key={start.tick}
            startFen={start.fen}
            initialMoves={start.moves}
            initialResigned={start.resigned}
            playerColor={playerColor}
            getEngine={getEngine}
            onAnalyse={props.returnTo ? analyse : undefined}
            onReplay={() => setStart((s) => ({ fen: s.fen, moves: [], resigned: false, tick: s.tick + 1 }))}
            onClose={onClose}
          />
        ) : (
          <PlanPane
            startFen={start.fen}
            playerColor={playerColor}
            getEngine={getEngine}
            onPlayFrom={(fen) => {
              setStart((s) => ({ fen, moves: [], resigned: false, tick: s.tick + 1 }))
              setMode('play')
            }}
          />
        )}
      </div>
    </div>
  )
}

// ---------- Mode jouer ----------
function PlayPane({ startFen, initialMoves, initialResigned, playerColor, getEngine, onAnalyse, onReplay, onClose }: {
  startFen: string
  initialMoves: string[]
  initialResigned: boolean
  playerColor: 'w' | 'b'
  getEngine: () => Engine
  onAnalyse?: (moves: string[], resigned: boolean) => void
  onReplay: () => void
  onClose: () => void
}) {
  const { playSounds } = useSettings()
  const chessRef = useRef<Chess | null>(null)
  chessRef.current ??= playUci(startFen, initialMoves).chess
  const [moves, setMoves] = useState<Move[]>(() => chessRef.current!.history({ verbose: true }))
  const [thinking, setThinking] = useState(false)
  const [resigned, setResigned] = useState(initialResigned)
  const [evalW, setEvalW] = useState<Eval>({ cp: null, mate: null })
  // Toute réponse moteur arrivée après un changement de position (annuler, abandon, démontage)
  // porte une génération périmée et est ignorée.
  const gen = useRef({ n: 0 }).current

  const c = chessRef.current
  const fen = c.fen()
  const ended = endText(c, playerColor)
  const over = resigned || ended !== null
  const last = moves[moves.length - 1]

  function sync() {
    setMoves(chessRef.current!.history({ verbose: true }))
  }

  function moveSound(move: Move) {
    if (!playSounds) return
    if (chessRef.current!.isGameOver()) sounds.gameEnd()
    else if (chessRef.current!.inCheck()) sounds.check()
    else if (move.captured) sounds.capture()
    else sounds.move()
  }

  async function evaluate(g: number) {
    const board = chessRef.current!
    if (board.isGameOver()) {
      setEvalW(terminalEval(board))
      return
    }
    const turn = board.turn()
    const res = await getEngine().search({ fen: board.fen(), movetimeMs: EVAL_MS, multipv: 1 })
    if (g !== gen.n) return
    setEvalW(whiteEval(res.lines[0], turn))
  }

  async function botMove(g: number) {
    const board = chessRef.current!
    if (board.isGameOver() || board.turn() === playerColor) return
    setThinking(true)
    const turn = board.turn()
    const res = await getEngine().search({ fen: board.fen(), movetimeMs: BOT_MOVETIME_MS, multipv: 1 })
    await new Promise((r) => setTimeout(r, BOT_DELAY_MS))
    if (g !== gen.n) return
    setThinking(false)
    if (!res.bestMove || res.bestMove.length < 4) return
    let move: Move
    try {
      move = board.move({ from: res.bestMove.slice(0, 2), to: res.bestMove.slice(2, 4), promotion: res.bestMove[4] })
    } catch {
      return
    }
    // Le score de la recherche vaut pour la position après le meilleur coup, celui qu'on joue ;
    // un mat donné par le moteur est alors plus proche d'un coup.
    const line = res.lines[0]
    const after = line && line.scoreMate !== null && line.scoreMate > 0 ? { ...line, scoreMate: line.scoreMate - 1 } : line
    setEvalW(board.isGameOver() ? terminalEval(board) : whiteEval(after, turn))
    moveSound(move)
    sync()
  }

  // Ouverture (et remontage après « Rejouer ») : le moteur joue s'il a le trait, sinon on évalue.
  useEffect(() => {
    const g = ++gen.n
    if (initialResigned) return
    if (chessRef.current!.turn() === playerColor) void evaluate(g)
    else void botMove(g)
    return () => {
      gen.n++
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function handleMove(from: string, to: string, promotion?: string): boolean {
    const board = chessRef.current!
    if (over || thinking || board.turn() !== playerColor) return false
    let move: Move
    try {
      move = board.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    moveSound(move)
    sync()
    const g = ++gen.n
    if (board.isGameOver()) setEvalW(terminalEval(board))
    else void botMove(g)
    return true
  }

  const canUndo = !over && !thinking && c.turn() === playerColor && moves.some((m) => m.color === playerColor)

  // Reprend le dernier coup du joueur et la réponse du moteur.
  function undo() {
    if (!canUndo) return
    const board = chessRef.current!
    let undone = board.undo()
    while (undone && undone.color !== playerColor) undone = board.undo()
    sync()
    void evaluate(++gen.n)
  }

  function resign() {
    if (over) return
    gen.n++
    setThinking(false)
    setResigned(true)
  }

  const status = resigned ? 'Tu as abandonné' : ended ?? (thinking ? 'Stockfish réfléchit…' : c.turn() === playerColor ? `À toi de jouer (${COLOR_FR[playerColor]})` : '…')
  const won = ended?.includes('tu gagnes')

  return (
    <>
      <div className="px-3 pt-1">
        <HEvalBar cp={evalW.cp} mate={evalW.mate} />
      </div>
      <p
        className={`flex min-h-9 items-center justify-center px-3 text-center text-sm font-semibold ${
          over ? (won ? 'text-accent' : resigned || ended?.startsWith('Échec') ? 'text-red-400' : 'text-neutral-200') : 'text-neutral-300'
        } ${over ? 'text-base font-black' : ''}`}
      >
        {status}
      </p>
      <div className="flex justify-center">
        <div className="boardbox md:w-[min(56vh,520px)]">
          <Board
            fen={fen}
            orientation={playerColor}
            interactive={!over && !thinking && c.turn() === playerColor}
            movableColor={playerColor}
            onMove={handleMove}
            lastMove={last ? { from: last.from, to: last.to } : null}
          />
        </div>
      </div>
      <LineStrip startFen={startFen} sans={moves.map((m) => m.san)} current={moves.length - 1} />
      <div className="mt-auto flex flex-wrap items-center gap-1 border-t border-black/40 p-2">
        {!over ? (
          <>
            <Action label="Abandonner" icon="🏳" onClick={resign} />
            <Action label="Annuler" icon="↩" onClick={undo} disabled={!canUndo} />
            {onAnalyse && <Action label="Analyser" icon="♞" onClick={() => onAnalyse(moves.map((m) => m.lan), resigned)} />}
          </>
        ) : (
          <>
            {onAnalyse && <Action label="Analyser" icon="♞" onClick={() => onAnalyse(moves.map((m) => m.lan), resigned)} />}
            <div className="flex-1" />
            <Cta variant="secondary" className="px-3 py-2 text-sm whitespace-nowrap" onClick={onReplay}>
              ↻ Rejouer
            </Cta>
            <Cta className="px-3 py-2 text-sm whitespace-nowrap" onClick={onClose}>
              Retour à l'exercice
            </Cta>
          </>
        )}
      </div>
    </>
  )
}

// ---------- Mode plan ----------
function PlanPane({ startFen, playerColor, getEngine, onPlayFrom }: {
  startFen: string
  playerColor: 'w' | 'b'
  getEngine: () => Engine
  onPlayFrom: (fen: string) => void
}) {
  const [line, setLine] = useState<string[] | null>(null) // coups UCI ; null = première recherche en cours
  const [extending, setExtending] = useState(false)
  const [evalW, setEvalW] = useState<Eval>({ cp: null, mate: null })
  const [idx, setIdx] = useState(-1) // -1 = position de départ
  const [autoplay, setAutoplay] = useState(true)

  // Calcul de la ligne : une PV, prolongée par recherches courtes quand elle est tronquée.
  useEffect(() => {
    let alive = true
    void (async () => {
      const engine = getEngine()
      const turn = new Chess(startFen).turn()
      const first = await engine.search({ fen: startFen, movetimeMs: PLAN_FIRST_MS, multipv: 1 })
      if (!alive) return
      setEvalW(whiteEval(first.lines[0], turn))
      let { chess, played } = playUci(startFen, (first.lines[0]?.pv ?? [first.bestMove]).slice(0, PLAN_PLIES))
      // La première PV s'affiche tout de suite ; la ligne s'allonge ensuite.
      setLine(played)
      setExtending(true)
      while (alive && played.length < PLAN_PLIES && !chess.isGameOver()) {
        const res = await engine.search({ fen: chess.fen(), movetimeMs: PLAN_EXTEND_MS, multipv: 1 })
        const more = playUci(chess.fen(), (res.lines[0]?.pv ?? [res.bestMove]).slice(0, PLAN_PLIES - played.length))
        if (more.played.length === 0) break
        chess = more.chess
        played = [...played, ...more.played]
        if (alive) setLine(played)
      }
      if (alive) setExtending(false)
    })()
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startFen])

  const n = line?.length ?? 0
  useEffect(() => {
    if (!line || !autoplay || idx >= n - 1) return
    const t = setTimeout(() => setIdx((i) => i + 1), PLAN_STEP_MS)
    return () => clearTimeout(t)
  }, [line, autoplay, idx, n])

  const fen = useMemo(() => (line ? fenAfter(startFen, line, idx + 1) : startFen), [line, startFen, idx])
  const sans = useMemo(() => (line ? playUci(startFen, line).chess.history() : []), [line, startFen])
  const current = line && idx >= 0 ? line[idx] : null

  function go(i: number) {
    setAutoplay(false)
    setIdx(Math.max(-1, Math.min(n - 1, i)))
  }

  const status = line === null
    ? 'Calcul du plan…'
    : n === 0 && !extending
      ? "Stockfish n'a pas trouvé de suite"
      : 'La meilleure suite selon Stockfish (éval. au départ)'

  return (
    <>
      <div className="px-3 pt-1">
        <HEvalBar cp={evalW.cp} mate={evalW.mate} />
      </div>
      <p className="flex min-h-9 items-center justify-center px-3 text-center text-sm font-semibold text-neutral-300">{status}</p>
      <div className="flex justify-center">
        <div className="boardbox md:w-[min(56vh,520px)]">
          <Board
            fen={fen}
            orientation={playerColor}
            interactive={false}
            lastMove={current ? { from: current.slice(0, 2), to: current.slice(2, 4) } : null}
          />
        </div>
      </div>
      <LineStrip startFen={startFen} sans={sans} current={idx} onSelect={go} />
      <div className="mt-auto flex items-center gap-1 border-t border-black/40 p-2">
        <NavButton label="Début" glyph="⏮" onClick={() => go(-1)} disabled={!line} />
        <NavButton label="Coup précédent" glyph="◀" onClick={() => go(idx - 1)} disabled={!line} />
        <NavButton label="Coup suivant" glyph="▶" onClick={() => go(idx + 1)} disabled={!line} />
        <NavButton label="Fin" glyph="⏭" onClick={() => go(n - 1)} disabled={!line} />
        <div className="flex-1" />
        <Cta className="px-3 py-2 text-sm whitespace-nowrap" onClick={() => onPlayFrom(fen)} disabled={!line || isTerminal(fen)}>
          Jouer à partir d'ici
        </Cta>
      </div>
    </>
  )
}

// ---------- Briques ----------

// Bande de coups numérotée à partir du FEN de départ (« 34... ♚d7 » quand les Noirs commencent).
function LineStrip({ startFen, sans, current, onSelect }: {
  startFen: string
  sans: string[]
  current: number
  onSelect?: (i: number) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [, turn, , , , fullmove] = startFen.split(' ')
  const firstPly = (Number(fullmove) - 1) * 2 + (turn === 'b' ? 1 : 0)

  useEffect(() => {
    // Défilement horizontal manuel : scrollIntoView ferait aussi défiler le calque.
    const strip = ref.current
    const el = strip?.querySelector<HTMLElement>('[data-current="true"]')
    if (!strip || !el) return
    strip.scrollTo({ left: el.offsetLeft - strip.clientWidth / 2 + el.clientWidth / 2, behavior: 'smooth' })
  }, [current, sans.length])

  return (
    <div ref={ref} className="flex min-h-11 items-center gap-1.5 overflow-x-auto px-3 py-1.5 [scrollbar-width:none]">
      {sans.map((san, i) => {
        const ply = firstPly + i
        const color = ply % 2 === 0 ? 'w' : 'b'
        const number = Math.floor(ply / 2) + 1
        const prefix = color === 'w' ? `${number}.` : i === 0 ? `${number}...` : null
        const cls = `shrink-0 rounded px-1.5 py-1 text-[15px] font-bold ${
          i === current ? 'bg-neutral-100 text-neutral-900' : 'text-neutral-200'
        }`
        return (
          <span key={i} className="flex shrink-0 items-center gap-1">
            {prefix && <span className="text-sm text-neutral-500">{prefix}</span>}
            {onSelect ? (
              <button data-current={i === current} onClick={() => onSelect(i)} className={`cursor-pointer ${cls}`}>
                {figurine(san, color)}
              </button>
            ) : (
              <span data-current={i === current} className={cls}>
                {figurine(san, color)}
              </span>
            )}
          </span>
        )
      })}
    </div>
  )
}

function Action({ label, icon, onClick, disabled }: { label: string; icon: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex cursor-pointer flex-col items-center gap-0.5 rounded px-3 py-1 text-xs font-semibold text-neutral-300 hover:text-white disabled:cursor-default disabled:opacity-35"
    >
      <span className="text-xl leading-none">{icon}</span>
      {label}
    </button>
  )
}

function NavButton({ label, glyph, onClick, disabled }: { label: string; glyph: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="flex h-10 w-11 cursor-pointer items-center justify-center rounded bg-surface-3 text-lg text-neutral-200 hover:bg-surface-3/80 disabled:cursor-default disabled:opacity-35"
    >
      {glyph}
    </button>
  )
}
