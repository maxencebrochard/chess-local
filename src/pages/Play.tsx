import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Chess } from 'chess.js'
import { useNavigate } from 'react-router-dom'
import { Board } from '../components/Board'
import { Clock } from '../components/Clock'
import { MoveList } from '../components/MoveList'
import { BOTS, botEngineOptions, type Bot } from '../lib/bots'
import { Engine } from '../lib/engine'
import { applyRating, db, getRating, type SavedGame } from '../lib/db'
import { openingForMoves } from '../lib/openings'
import { sounds } from '../lib/sounds'
import { useSettings } from '../store/settings'

interface TimeControl {
  label: string
  baseMs: number | null // null = illimité
  incMs: number
  timeClass: SavedGame['timeClass']
}

const TIME_CONTROLS: TimeControl[] = [
  { label: '1 min', baseMs: 60_000, incMs: 0, timeClass: 'bullet' },
  { label: '3 min', baseMs: 180_000, incMs: 0, timeClass: 'blitz' },
  { label: '3 | 2', baseMs: 180_000, incMs: 2000, timeClass: 'blitz' },
  { label: '5 min', baseMs: 300_000, incMs: 0, timeClass: 'blitz' },
  { label: '10 min', baseMs: 600_000, incMs: 0, timeClass: 'rapid' },
  { label: '15 | 10', baseMs: 900_000, incMs: 10_000, timeClass: 'rapid' },
  { label: '30 min', baseMs: 1_800_000, incMs: 0, timeClass: 'rapid' },
  { label: 'Illimité', baseMs: null, incMs: 0, timeClass: 'unlimited' },
]

type GameStatus = 'setup' | 'playing' | 'over'

interface GameOver {
  result: '1-0' | '0-1' | '1/2-1/2'
  termination: string
  ratingBefore?: number
  ratingAfter?: number
}

export default function Play() {
  const navigate = useNavigate()
  const { playSounds } = useSettings()

  // --- Setup ---
  const [mode, setMode] = useState<'bot' | 'local'>('bot')
  const [bot, setBot] = useState<Bot>(BOTS[3])
  const [colorChoice, setColorChoice] = useState<'w' | 'b' | 'random'>('w')
  const [tc, setTc] = useState<TimeControl>(TIME_CONTROLS[4])
  const [myRating, setMyRating] = useState<number | null>(null)

  // --- Partie ---
  const chessRef = useRef(new Chess())
  const [fen, setFen] = useState(chessRef.current.fen())
  const [sans, setSans] = useState<string[]>([])
  const [viewIndex, setViewIndex] = useState(-1) // -1 = live
  const [status, setStatus] = useState<GameStatus>('setup')
  const [playerColor, setPlayerColor] = useState<'w' | 'b'>('w')
  const [clocks, setClocks] = useState<{ w: number; b: number }>({ w: 0, b: 0 })
  const [gameOver, setGameOver] = useState<GameOver | null>(null)
  const [savedGameId, setSavedGameId] = useState<number | null>(null)
  const engineRef = useRef<Engine | null>(null)
  const botThinking = useRef(false)
  const lowTimeWarned = useRef(false)

  useEffect(() => {
    getRating(tc.timeClass).then((r) => setMyRating(r.value))
  }, [tc])

  useEffect(
    () => () => {
      // Null obligatoire : StrictMode rejoue les effets, un worker terminé ne doit pas être réutilisé.
      engineRef.current?.quit()
      engineRef.current = null
    },
    [],
  )

  const chess = chessRef.current
  const uciMoves = useMemo(
    () => chess.history({ verbose: true }).map((m) => m.lan),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fen],
  )
  const opening = useMemo(() => openingForMoves(uciMoves), [uciMoves])

  // Position affichée (navigation dans l'historique).
  const viewFen = useMemo(() => {
    if (viewIndex === -1) return fen
    const c = new Chess()
    const verbose = chess.history({ verbose: true })
    for (let i = 0; i <= viewIndex; i++) c.move(verbose[i].san)
    return c.fen()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewIndex, fen])

  const lastMove = useMemo(() => {
    const verbose = chess.history({ verbose: true })
    const idx = viewIndex === -1 ? verbose.length - 1 : viewIndex
    if (idx < 0) return null
    return { from: verbose[idx].from, to: verbose[idx].to }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewIndex, fen])

  // --- Pendule ---
  useEffect(() => {
    if (status !== 'playing' || tc.baseMs === null) return
    const interval = setInterval(() => {
      setClocks((prev) => {
        const turn = chessRef.current.turn()
        const next = { ...prev, [turn]: prev[turn] - 100 }
        if (next[turn] <= 0) {
          next[turn] = 0
          endGame(turn === 'w' ? '0-1' : '1-0', 'au temps')
        } else if (!lowTimeWarned.current && next[turn] <= 15_000 && turn === (mode === 'bot' ? playerColor : turn)) {
          lowTimeWarned.current = true
          if (playSounds) sounds.lowTime()
        }
        return next
      })
    }, 100)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, tc])

  const endGame = useCallback(
    async (result: '1-0' | '0-1' | '1/2-1/2', termination: string) => {
      setStatus((s) => {
        if (s !== 'playing') return s
        void (async () => {
          if (playSounds) sounds.gameEnd()
          let ratingBefore: number | undefined
          let ratingAfter: number | undefined
          if (mode === 'bot') {
            const score = result === '1/2-1/2' ? 0.5 : (result === '1-0') === (playerColor === 'w') ? 1 : 0
            const before = await getRating(tc.timeClass)
            ratingBefore = before.value
            ratingAfter = await applyRating(tc.timeClass, bot.elo, score as 0 | 0.5 | 1)
            setMyRating(ratingAfter)
          }
          const c = chessRef.current
          c.header('Event', mode === 'bot' ? `Partie vs ${bot.name}` : 'Partie locale')
          c.header('Site', 'chess-local')
          c.header('Date', new Date().toISOString().slice(0, 10).replaceAll('-', '.'))
          c.header('White', mode === 'bot' ? (playerColor === 'w' ? 'Moi' : bot.name) : 'Blancs')
          c.header('Black', mode === 'bot' ? (playerColor === 'b' ? 'Moi' : bot.name) : 'Noirs')
          c.header('Result', result)
          const id = await db.games.add({
            date: Date.now(),
            mode,
            botId: mode === 'bot' ? bot.id : undefined,
            playerColor,
            timeControl: tc.label,
            timeClass: tc.timeClass,
            pgn: c.pgn(),
            result,
            termination,
            playerRatingAfter: ratingAfter,
          })
          setSavedGameId(id as number)
          setGameOver({ result, termination, ratingBefore, ratingAfter })
        })()
        return 'over'
      })
    },
    [mode, bot, playerColor, tc, playSounds],
  )

  const checkGameEnd = useCallback((): boolean => {
    const c = chessRef.current
    if (!c.isGameOver()) return false
    if (c.isCheckmate()) endGame(c.turn() === 'w' ? '0-1' : '1-0', 'par échec et mat')
    else if (c.isStalemate()) endGame('1/2-1/2', 'par pat')
    else if (c.isThreefoldRepetition()) endGame('1/2-1/2', 'par triple répétition')
    else if (c.isInsufficientMaterial()) endGame('1/2-1/2', 'par matériel insuffisant')
    else endGame('1/2-1/2', 'par la règle des 50 coups')
    return true
  }, [endGame])

  const afterMove = useCallback(
    (san: string) => {
      const c = chessRef.current
      if (playSounds) {
        if (c.inCheck()) sounds.check()
        else if (san.includes('x')) sounds.capture()
        else sounds.move()
      }
      if (tc.baseMs !== null) {
        const justMoved = c.turn() === 'w' ? 'b' : 'w'
        setClocks((prev) => ({ ...prev, [justMoved]: prev[justMoved] + tc.incMs }))
      }
      setFen(c.fen())
      setSans(c.history())
      setViewIndex(-1)
      return !checkGameEnd()
    },
    [tc, playSounds, checkGameEnd],
  )

  const playBotMove = useCallback(async () => {
    const c = chessRef.current
    if (botThinking.current || c.isGameOver()) return
    botThinking.current = true
    try {
      engineRef.current ??= new Engine()
      const engine = engineRef.current
      await engine.setOptions(botEngineOptions(bot))
      let uci: string
      if (bot.randomness > 0 && Math.random() < bot.randomness) {
        const moves = c.moves({ verbose: true })
        uci = moves[Math.floor(Math.random() * moves.length)].lan
      } else {
        const res = await engine.search({ fen: c.fen(), movetimeMs: bot.movetimeMs, multipv: 1 })
        uci = res.bestMove
      }
      // Latence artificielle pour un rythme naturel.
      await new Promise((r) => setTimeout(r, 300 + Math.random() * 500))
      if (chessRef.current.isGameOver()) return
      const move = c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
      afterMove(move.san)
    } finally {
      botThinking.current = false
    }
  }, [bot, afterMove])

  function handlePlayerMove(from: string, to: string, promotion?: string): boolean {
    const c = chessRef.current
    if (status !== 'playing') return false
    if (viewIndex !== -1) return false
    try {
      const move = c.move({ from, to, promotion: promotion ?? 'q' })
      const cont = afterMove(move.san)
      if (cont && mode === 'bot') void playBotMove()
      return true
    } catch {
      return false
    }
  }

  function startGame() {
    const color = colorChoice === 'random' ? (Math.random() < 0.5 ? 'w' : 'b') : colorChoice
    chessRef.current = new Chess()
    setPlayerColor(color)
    setFen(chessRef.current.fen())
    setSans([])
    setViewIndex(-1)
    setGameOver(null)
    setSavedGameId(null)
    setClocks({ w: tc.baseMs ?? 0, b: tc.baseMs ?? 0 })
    lowTimeWarned.current = false
    setStatus('playing')
    if (mode === 'bot' && color === 'b') {
      setTimeout(() => void playBotMove(), 400)
    }
  }

  function resign() {
    if (status !== 'playing') return
    const loser = mode === 'bot' ? playerColor : chess.turn()
    endGame(loser === 'w' ? '0-1' : '1-0', 'par abandon')
  }

  // --- Rendu ---
  if (status === 'setup') {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <h1 className="mb-6 text-2xl font-bold">Jouer</h1>
        <div className="mb-5 flex gap-2">
          <ModeButton active={mode === 'bot'} onClick={() => setMode('bot')} label="🤖 Contre un bot" />
          <ModeButton active={mode === 'local'} onClick={() => setMode('local')} label="👥 2 joueurs (local)" />
        </div>

        {mode === 'bot' && (
          <>
            <h2 className="mb-2 text-sm font-semibold text-neutral-400">Adversaire</h2>
            <div className="mb-5 grid grid-cols-3 gap-2">
              {BOTS.map((b) => (
                <button
                  key={b.id}
                  onClick={() => setBot(b)}
                  className={`cursor-pointer rounded-lg border-2 p-3 text-left transition ${
                    bot.id === b.id ? 'border-accent bg-accent/10' : 'border-transparent bg-surface-2 hover:bg-surface-3'
                  }`}
                >
                  <div className="text-2xl">{b.emoji}</div>
                  <div className="font-semibold">{b.name}</div>
                  <div className="text-sm text-neutral-400">{b.elo}</div>
                </button>
              ))}
            </div>
            <p className="mb-5 text-sm text-neutral-400">{bot.description}</p>

            <h2 className="mb-2 text-sm font-semibold text-neutral-400">Ma couleur</h2>
            <div className="mb-5 flex gap-2">
              <ModeButton active={colorChoice === 'w'} onClick={() => setColorChoice('w')} label="♔ Blancs" />
              <ModeButton active={colorChoice === 'b'} onClick={() => setColorChoice('b')} label="♚ Noirs" />
              <ModeButton active={colorChoice === 'random'} onClick={() => setColorChoice('random')} label="🎲 Aléatoire" />
            </div>
          </>
        )}

        <h2 className="mb-2 text-sm font-semibold text-neutral-400">Cadence</h2>
        <div className="mb-6 grid grid-cols-4 gap-2">
          {TIME_CONTROLS.map((t) => (
            <button
              key={t.label}
              onClick={() => setTc(t)}
              className={`cursor-pointer rounded-lg border-2 py-2 font-semibold transition ${
                tc.label === t.label ? 'border-accent bg-accent/10' : 'border-transparent bg-surface-2 hover:bg-surface-3'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {mode === 'bot' && myRating !== null && (
          <p className="mb-4 text-sm text-neutral-400">
            Mon classement {tc.timeClass} : <b className="text-white">{myRating}</b>
          </p>
        )}

        <button
          onClick={startGame}
          className="w-full cursor-pointer rounded-lg bg-accent py-3 text-lg font-bold text-white shadow hover:bg-accent-hover"
        >
          Jouer
        </button>
      </div>
    )
  }

  const orientation = mode === 'bot' ? playerColor : 'w'
  const topColor = orientation === 'w' ? 'b' : 'w'
  const nameOf = (c: 'w' | 'b') =>
    mode === 'local' ? (c === 'w' ? 'Blancs' : 'Noirs') : c === playerColor ? `Moi${myRating ? ` (${myRating})` : ''}` : `${bot.emoji} ${bot.name} (${bot.elo})`

  return (
    <div className="flex h-full flex-col items-center justify-start gap-2 p-2 md:flex-row md:justify-center md:gap-6 md:p-4">
      <div className="flex flex-col gap-2">
        <div className="flex w-full items-center justify-between">
          <span className="font-semibold">{nameOf(topColor)}</span>
          {tc.baseMs !== null && <Clock ms={clocks[topColor]} active={status === 'playing' && chess.turn() === topColor} label="" />}
        </div>
        <div className="boardbox">
          <Board
            fen={viewFen}
            orientation={orientation}
            interactive={status === 'playing' && viewIndex === -1}
            movableColor={mode === 'bot' ? playerColor : undefined}
            onMove={handlePlayerMove}
            lastMove={lastMove}
          />
        </div>
        <div className="flex w-full items-center justify-between">
          <span className="font-semibold">{nameOf(orientation)}</span>
          {tc.baseMs !== null && <Clock ms={clocks[orientation]} active={status === 'playing' && chess.turn() === orientation} label="" />}
        </div>
      </div>

      <div className="flex w-full flex-col gap-2 px-1 pb-2 md:h-[min(76vh,640px)] md:w-72 md:gap-3 md:px-0 md:pb-0">
        <div className="rounded bg-surface-2 px-3 py-2 text-sm text-neutral-300">
          {opening ? (
            <>
              <span className="font-mono text-xs text-neutral-500">{opening.eco}</span> {opening.name}
            </>
          ) : (
            <span className="text-neutral-500">Ouverture inconnue</span>
          )}
        </div>
        <div className="h-32 md:min-h-0 md:h-auto md:flex-1">
          <MoveList sans={sans} currentIndex={viewIndex === -1 ? sans.length - 1 : viewIndex} onSelect={setViewIndex} />
        </div>
        <div className="flex gap-2">
          <NavButton label="⏮" onClick={() => setViewIndex(sans.length ? 0 : -1)} />
          <NavButton label="◀" onClick={() => setViewIndex((v) => Math.max(0, (v === -1 ? sans.length - 1 : v) - 1))} />
          <NavButton label="▶" onClick={() => setViewIndex((v) => (v === -1 ? -1 : v + 1 >= sans.length - 1 ? -1 : v + 1))} />
          <NavButton label="⏭" onClick={() => setViewIndex(-1)} />
        </div>
        {status === 'playing' ? (
          <button onClick={resign} className="cursor-pointer rounded bg-surface-3 py-2 font-semibold hover:bg-red-900">
            🏳 Abandonner
          </button>
        ) : (
          <button onClick={() => setStatus('setup')} className="cursor-pointer rounded bg-accent py-2 font-bold text-white hover:bg-accent-hover">
            Nouvelle partie
          </button>
        )}
      </div>

      {gameOver && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/70" onClick={() => setGameOver(null)}>
          <div className="w-96 rounded-xl bg-surface-2 p-6 text-center shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-1 text-2xl font-bold">
              {gameOver.result === '1/2-1/2' ? 'Nulle' : gameOver.result === '1-0' ? 'Les Blancs gagnent' : 'Les Noirs gagnent'}
            </h2>
            <p className="mb-4 text-neutral-400">{gameOver.termination}</p>
            {gameOver.ratingAfter !== undefined && gameOver.ratingBefore !== undefined && (
              <p className="mb-4 text-lg">
                Classement : <b>{gameOver.ratingAfter}</b>{' '}
                <span className={gameOver.ratingAfter >= gameOver.ratingBefore ? 'text-accent' : 'text-red-400'}>
                  ({gameOver.ratingAfter >= gameOver.ratingBefore ? '+' : ''}
                  {gameOver.ratingAfter - gameOver.ratingBefore})
                </span>
              </p>
            )}
            <div className="flex gap-2">
              <button
                onClick={() => setStatus('setup')}
                className="flex-1 cursor-pointer rounded bg-accent py-2 font-bold text-white hover:bg-accent-hover"
              >
                Rejouer
              </button>
              {savedGameId !== null && (
                <button
                  onClick={() => navigate(`/analyse?game=${savedGameId}&review=1`)}
                  className="flex-1 cursor-pointer rounded bg-surface-3 py-2 font-semibold hover:bg-surface-3/70"
                >
                  🔍 Analyser
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ModeButton({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`cursor-pointer rounded-lg border-2 px-4 py-2 font-semibold transition ${
        active ? 'border-accent bg-accent/10' : 'border-transparent bg-surface-2 hover:bg-surface-3'
      }`}
    >
      {label}
    </button>
  )
}

function NavButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex-1 cursor-pointer rounded bg-surface-3 py-1.5 hover:bg-surface-3/70">
      {label}
    </button>
  )
}
