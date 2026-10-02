import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Chess } from 'chess.js'
import { useNavigate } from 'react-router-dom'
import { Board, type BoardArrow } from '../components/Board'
import { Clock } from '../components/Clock'
import { CoachBubble } from '../components/CoachBubble'
import { Cta } from '../components/Cta'
import { HEvalBar } from '../components/HEvalBar'
import { MoveList } from '../components/MoveList'
import { MoveStrip } from '../components/MoveStrip'
import { greeting, liveComment, quickClass, type LiveComment } from '../lib/liveCoach'
import { isBookPosition } from '../lib/openings'
import { openingFr } from '../lib/openingNames'
import { BOTS, botById, botEngineOptions, botThinkBudget, type Bot } from '../lib/bots'
import { Engine } from '../lib/engine'
import { applyRating, db, getRating, type SavedGame } from '../lib/db'
import { openingForMoves } from '../lib/openings'
import { sounds } from '../lib/sounds'
import { useSettings, type PlayColor, type PlayMode } from '../store/settings'

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
const UNLIMITED = TIME_CONTROLS[7]

type GameStatus = 'setup' | 'playing' | 'over'

interface GameOver {
  result: '1-0' | '0-1' | '1/2-1/2'
  termination: string
  cancelled?: boolean // moins de deux demi-coups : ni classement ni archive
  saveFailed?: boolean // transaction refusée (stockage plein ou indisponible) : ni classement ni archive
  ratingBefore?: number
  ratingAfter?: number
}

// Partie en cours vue par les callbacks et les minuteurs : posée une fois par partie,
// elle ne dépend d'aucune closure React périmée. `seq` est le jeton de partie.
interface LiveGame {
  seq: number
  mode: PlayMode
  bot: Bot
  playerColor: 'w' | 'b'
  tc: TimeControl // cadence effective (toujours Illimité en mode entraîneur)
  tcLabel: string // cadence choisie sur l'écran de configuration, mémorisée telle quelle
}

// Partie en cours mémorisée pour survivre à un changement d'onglet, au retour arrière iOS et
// à une PWA tuée en arrière-plan (sessionStorage ne survit pas à cette dernière). Transitoire :
// hors sauvegarde, expirée après 24 h, pendules figées pendant l'absence.
const GAME_KEY = 'chess-local-play-game'
const GAME_TTL_MS = 24 * 3600_000

interface StoredGame {
  mode: PlayMode
  botId: string
  playerColor: 'w' | 'b'
  tcLabel: string
  sans: string[]
  clocks: { w: number; b: number }
  unrated: boolean
  lastWhiteCp: number
  savedAt: number
}

function readStoredGame(): StoredGame | null {
  try {
    const raw = localStorage.getItem(GAME_KEY)
    if (!raw) return null
    const g = JSON.parse(raw) as StoredGame
    if (!Array.isArray(g.sans) || typeof g.savedAt !== 'number' || Date.now() - g.savedAt > GAME_TTL_MS) return null
    return g
  } catch {
    return null
  }
}

function writeStoredGame(g: StoredGame | null) {
  try {
    if (g) localStorage.setItem(GAME_KEY, JSON.stringify(g))
    else localStorage.removeItem(GAME_KEY)
  } catch {
    // stockage indisponible (navigation privée) : la partie vit seulement en mémoire
  }
}

// Matériel suffisant pour mater, règle chess.com pour un drapeau : le camp qui ne tombe pas
// gagne seulement s'il peut encore mater. Roi seul, roi + fou, roi + cavalier, roi + deux
// cavaliers : insuffisant (nulle). Fou + cavalier, deux fous, tout pion, tour ou dame :
// suffisant. FIDE 6.9 et lichess comptent les deux cavaliers comme suffisants ; on suit chess.com.
function hasMatingMaterial(chess: Chess, color: 'w' | 'b'): boolean {
  let bishops = 0
  let knights = 0
  for (const row of chess.board()) {
    for (const sq of row) {
      if (!sq || sq.color !== color) continue
      if (sq.type === 'p' || sq.type === 'r' || sq.type === 'q') return true
      if (sq.type === 'b') bishops++
      if (sq.type === 'n') knights++
    }
  }
  return bishops >= 1 && bishops + knights >= 2
}

// Joue un coup UCI si le moteur l'a mal formé ou s'il est illégal, renvoie null.
function applyUci(chess: Chess, uci: string) {
  try {
    return chess.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
  } catch {
    return null
  }
}

export default function Play() {
  const navigate = useNavigate()
  const { playSounds, playMode, playBotId, playColor, playTcLabel, setPlayConfig } = useSettings()

  // --- Configuration (mémorisée dans les réglages) ---
  const [mode, setMode] = useState<PlayMode>(playMode)
  const [bot, setBot] = useState<Bot>(() => botById(playBotId) ?? BOTS[3])
  const [colorChoice, setColorChoice] = useState<PlayColor>(playColor)
  const [tc, setTc] = useState<TimeControl>(() => TIME_CONTROLS.find((t) => t.label === playTcLabel) ?? TIME_CONTROLS[4])
  const [myRating, setMyRating] = useState<number | null>(null)
  const myRatingClass = useRef<SavedGame['timeClass'] | null>(null) // cadence dont myRating affiche le classement
  // Le mode entraîneur joue sans pendule, sans écraser la cadence choisie pour les bots.
  const effectiveTc = mode === 'coach' ? UNLIMITED : tc

  // --- Partie ---
  const chessRef = useRef(new Chess())
  const [fen, setFen] = useState(chessRef.current.fen())
  const [sans, setSans] = useState<string[]>([])
  const [viewIndex, setViewIndex] = useState(-1) // -1 = direct
  const [status, setStatus] = useState<GameStatus>('setup')
  const statusRef = useRef<GameStatus>('setup') // miroir synchrone pour les minuteurs et les callbacks
  const [playerColor, setPlayerColor] = useState<'w' | 'b'>('w')
  const [clocks, setClocks] = useState<{ w: number; b: number }>({ w: 0, b: 0 })
  const clocksRef = useRef(clocks) // source de vérité de la pendule : le tick ne fait aucun effet de bord dans un updater
  const [gameOver, setGameOver] = useState<GameOver | null>(null)
  const [savedGameId, setSavedGameId] = useState<number | null>(null)
  // Feuille de confirmation d'abandon ; `cancel` fige l'intention à l'ouverture (sous deux demi-coups
  // = annuler), même si le coup du bot tombe pendant que la feuille est ouverte.
  const [confirmResign, setConfirmResign] = useState<{ cancel: boolean } | null>(null)
  const engineRef = useRef<Engine | null>(null)
  const gameRef = useRef<LiveGame | null>(null)
  // Jeton de partie : incrémenté à chaque début, fin, retour à la configuration et démontage. Tout résultat asynchrone
  // (coup du bot, éval, indication) le compare avant d'agir : une partie finie ou remplacée
  // ne reçoit plus rien, même si sa recherche moteur se termine après coup.
  const gameSeq = useRef(0)
  const thinkingSeq = useRef<number | null>(null) // jeton de la partie dont le bot réfléchit
  const lowTimeWarned = useRef(false)

  // --- Mode entraîneur ---
  const coachEngineRef = useRef<Engine | null>(null) // pleine force, dédié à l'éval
  const [coachMsg, setCoachMsg] = useState<LiveComment | null>(null)
  const [liveCp, setLiveCp] = useState<number | null>(null) // point de vue blanc
  const [unrated, setUnrated] = useState(false)
  const [hintArrow, setHintArrow] = useState<BoardArrow | null>(null)
  const [hintBusy, setHintBusy] = useState(false)
  const [bookBadge, setBookBadge] = useState<string | null>(null)
  const lastWhiteCp = useRef(20) // éval blanche avant le dernier coup
  const unratedRef = useRef(false)
  const takebackGen = useRef(0) // incrémenté par Annuler : une éval lancée avant est jetée

  // Instantané de la partie en cours (voir GAME_KEY).
  const saveGame = useCallback(() => {
    const g = gameRef.current
    if (!g || statusRef.current !== 'playing') return
    writeStoredGame({
      mode: g.mode,
      botId: g.bot.id,
      playerColor: g.playerColor,
      tcLabel: g.tcLabel,
      sans: chessRef.current.history(),
      clocks: clocksRef.current,
      unrated: unratedRef.current,
      lastWhiteCp: lastWhiteCp.current,
      savedAt: Date.now(),
    })
  }, [])

  function markUnrated() {
    unratedRef.current = true
    setUnrated(true)
    saveGame()
  }

  const releaseEngines = useCallback(() => {
    // Null obligatoire : StrictMode rejoue les effets, un worker terminé ne doit pas être réutilisé.
    engineRef.current?.quit()
    engineRef.current = null
    coachEngineRef.current?.quit()
    coachEngineRef.current = null
  }, [])

  // Éval + commentaire live après chaque demi-coup (mode entraîneur).
  // Chaîne sérialisée : l'éval du coup N doit finir avant celle du coup N+1
  // (sinon la classification du coup du bot lirait une éval « avant » périmée).
  const liveChain = useRef(Promise.resolve())
  const liveEval = useCallback((san: string, byPlayer: boolean) => {
    const game = chessRef.current
    const seq = gameSeq.current
    const gen = takebackGen.current
    const fen = game.fen()
    const moverColor: 'w' | 'b' = game.turn() === 'w' ? 'b' : 'w'
    const turnAfter = game.turn()
    const uciMoves = game.history({ verbose: true }).map((m) => m.lan)
    const isBook = isBookPosition(uciMoves)
    const mate = game.isCheckmate()
    const over = game.isGameOver()
    setBookBadge(isBook ? uciMoves[uciMoves.length - 1].slice(2, 4) : null)

    liveChain.current = liveChain.current.then(async () => {
      if (seq !== gameSeq.current || gen !== takebackGen.current) return // partie finie ou coup annulé
      let whiteCp: number
      if (mate) {
        whiteCp = moverColor === 'w' ? 10000 : -10000
      } else if (over) {
        whiteCp = 0
      } else {
        coachEngineRef.current ??= new Engine()
        const res = await coachEngineRef.current.search({ fen, depth: 10, multipv: 1 })
        const line = res.lines[0]
        const cpPovTurn = line ? (line.scoreMate !== null ? (line.scoreMate > 0 ? 10000 : -10000) : (line.scoreCp ?? 0)) : 0
        whiteCp = turnAfter === 'w' ? cpPovTurn : -cpPovTurn
      }
      if (seq !== gameSeq.current || gen !== takebackGen.current) return
      const cpBeforeMover = moverColor === 'w' ? lastWhiteCp.current : -lastWhiteCp.current
      const cpAfterMover = moverColor === 'w' ? whiteCp : -whiteCp
      lastWhiteCp.current = whiteCp
      setLiveCp(whiteCp)
      const cls = quickClass(cpBeforeMover, cpAfterMover, isBook)
      setCoachMsg(liveComment({ san, moverColor, byPlayer, cls, uciMoves }))
    })
  }, [])

  useEffect(() => {
    myRatingClass.current = effectiveTc.timeClass
    getRating(effectiveTc.timeClass).then((r) => setMyRating(r.value))
  }, [effectiveTc])

  useEffect(
    () => () => {
      gameSeq.current++ // plus aucun résultat asynchrone ne touchera cet écran
      saveGame() // partie en cours conservée (changement d'onglet, retour arrière)
      releaseEngines()
    },
    [saveGame, releaseEngines],
  )

  // PWA tuée en arrière-plan ou page rechargée : aucun démontage, l'instantané part ici.
  useEffect(() => {
    const onHide = () => {
      if (document.visibilityState === 'hidden') saveGame()
    }
    document.addEventListener('visibilitychange', onHide)
    window.addEventListener('pagehide', saveGame)
    return () => {
      document.removeEventListener('visibilitychange', onHide)
      window.removeEventListener('pagehide', saveGame)
    }
  }, [saveGame])

  const chess = chessRef.current
  const uciMoves = useMemo(
    () => chess.history({ verbose: true }).map((m) => m.lan),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fen],
  )
  const opening = useMemo(() => openingForMoves(uciMoves), [uciMoves])

  // Position affichée (navigation dans l'historique). L'index est borné : sans coup, ou
  // au-delà du dernier, on montre le direct.
  const viewFen = useMemo(() => {
    const verbose = chess.history({ verbose: true })
    const idx = viewIndex === -1 ? -1 : Math.min(viewIndex, verbose.length - 1)
    if (idx < 0 || idx === verbose.length - 1) return fen
    const c = new Chess()
    for (let i = 0; i <= idx; i++) c.move(verbose[i].san)
    return c.fen()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewIndex, fen])

  const lastMove = useMemo(() => {
    const verbose = chess.history({ verbose: true })
    const idx = Math.min(viewIndex === -1 ? verbose.length - 1 : viewIndex, verbose.length - 1)
    if (idx < 0) return null
    return { from: verbose[idx].from, to: verbose[idx].to }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewIndex, fen])

  const endGame = useCallback(
    async (result: GameOver['result'], termination: string, cancel = false) => {
      const g = gameRef.current
      if (!g || statusRef.current !== 'playing') return // déjà finie (double tick, StrictMode)
      // Synchrone d'abord : plus aucun coup ni résultat moteur ne sera accepté.
      statusRef.current = 'over'
      const seq = ++gameSeq.current
      thinkingSeq.current = null
      setStatus('over')
      setConfirmResign(null)
      writeStoredGame(null)
      releaseEngines()
      if (playSounds) sounds.gameEnd()
      const c = chessRef.current
      if (cancel || c.history().length < 2) {
        // Partie annulée (comme chess.com) : ni classement ni archive. `cancel` : l'utilisateur a
        // confirmé « Annuler la partie ? », même si un coup du bot est tombé entre-temps.
        setGameOver({ result, termination, cancelled: true })
        return
      }
      c.header('Event', g.mode !== 'local' ? `Partie vs ${g.bot.name}` : 'Partie locale')
      c.header('Site', 'chess-local')
      c.header('Date', new Date().toISOString().slice(0, 10).replaceAll('-', '.'))
      c.header('White', g.mode !== 'local' ? (g.playerColor === 'w' ? 'Moi' : g.bot.name) : 'Blancs')
      c.header('Black', g.mode !== 'local' ? (g.playerColor === 'b' ? 'Moi' : g.bot.name) : 'Noirs')
      c.header('Result', result)
      const rated = g.mode !== 'local' && !unratedRef.current
      const score = result === '1/2-1/2' ? 0.5 : (result === '1-0') === (g.playerColor === 'w') ? 1 : 0
      let ratingBefore: number | undefined
      let ratingAfter: number | undefined
      let id: number | undefined
      // Partie et classement dans une seule transaction : jamais l'un sans l'autre.
      // Seules des promesses Dexie sont attendues ici, sinon la transaction se ferme trop tôt.
      try {
        await db.transaction('rw', db.games, db.ratings, async () => {
          if (rated) {
            ratingBefore = (await getRating(g.tc.timeClass)).value
            ratingAfter = await applyRating(g.tc.timeClass, g.bot.elo, score as 0 | 0.5 | 1)
          }
          id = await db.games.add({
            date: Date.now(),
            mode: g.mode === 'local' ? 'local' : 'bot',
            botId: g.mode !== 'local' ? g.bot.id : undefined,
            playerColor: g.playerColor,
            timeControl: g.tc.label,
            timeClass: g.tc.timeClass,
            pgn: c.pgn(),
            result,
            termination,
            playerRatingAfter: ratingAfter,
          })
        })
      } catch (err) {
        console.warn('Partie non enregistrée :', err)
        if (seq === gameSeq.current) setGameOver({ result, termination, saveFailed: true })
        return
      }
      if (ratingAfter !== undefined && myRatingClass.current === g.tc.timeClass) setMyRating(ratingAfter)
      if (seq !== gameSeq.current) return // nouvelle partie ou retour à la configuration entre-temps
      setSavedGameId(id ?? null)
      setGameOver({ result, termination, ratingBefore, ratingAfter })
    },
    [playSounds, releaseEngines],
  )

  // Drapeau : le camp adverse ne gagne que s'il a de quoi mater, sinon nulle.
  const onFlag = useCallback(
    (turn: 'w' | 'b') => {
      const winner = turn === 'w' ? 'b' : 'w'
      if (hasMatingMaterial(chessRef.current, winner)) void endGame(winner === 'w' ? '1-0' : '0-1', 'au temps')
      else void endGame('1/2-1/2', 'au temps, matériel insuffisant pour mater')
    },
    [endGame],
  )

  // --- Pendule ---
  useEffect(() => {
    if (status !== 'playing' || effectiveTc.baseMs === null) return
    const interval = setInterval(() => {
      const turn = chessRef.current.turn()
      const next = { ...clocksRef.current, [turn]: Math.max(0, clocksRef.current[turn] - 100) }
      clocksRef.current = next
      setClocks(next)
      if (next[turn] <= 0) {
        onFlag(turn)
      } else if (!lowTimeWarned.current && next[turn] <= 15_000 && (mode !== 'bot' || turn === playerColor)) {
        lowTimeWarned.current = true
        if (playSounds) sounds.lowTime()
      }
    }, 100)
    return () => clearInterval(interval)
  }, [status, effectiveTc, mode, playerColor, playSounds, onFlag])

  const checkGameEnd = useCallback((): boolean => {
    const c = chessRef.current
    if (!c.isGameOver()) return false
    if (c.isCheckmate()) void endGame(c.turn() === 'w' ? '0-1' : '1-0', 'par échec et mat')
    else if (c.isStalemate()) void endGame('1/2-1/2', 'par pat')
    else if (c.isThreefoldRepetition()) void endGame('1/2-1/2', 'par triple répétition')
    else if (c.isInsufficientMaterial()) void endGame('1/2-1/2', 'par matériel insuffisant')
    else void endGame('1/2-1/2', 'par la règle des 50 coups')
    return true
  }, [endGame])

  const afterMove = useCallback(
    (san: string, byPlayer = false) => {
      const c = chessRef.current
      const g = gameRef.current
      if (!g) return false
      if (playSounds) {
        if (c.inCheck()) sounds.check()
        else if (san.includes('x')) sounds.capture()
        else sounds.move()
      }
      if (g.tc.baseMs !== null) {
        const justMoved = c.turn() === 'w' ? 'b' : 'w'
        clocksRef.current = { ...clocksRef.current, [justMoved]: clocksRef.current[justMoved] + g.tc.incMs }
        setClocks(clocksRef.current)
      }
      setFen(c.fen())
      setSans(c.history())
      setViewIndex(-1)
      if (g.mode === 'coach') {
        setHintArrow(null)
        void liveEval(san, byPlayer)
      }
      const ended = checkGameEnd()
      if (!ended) saveGame() // jamais une position terminée dans l'instantané
      return !ended
    },
    [playSounds, checkGameEnd, liveEval, saveGame],
  )

  const playBotMove = useCallback(async () => {
    const c = chessRef.current
    const g = gameRef.current
    if (!g) return
    const seq = g.seq
    if (thinkingSeq.current === seq || statusRef.current !== 'playing' || c.isGameOver()) return
    thinkingSeq.current = seq
    try {
      if (!engineRef.current) {
        engineRef.current = new Engine()
        void engineRef.current.setOptions(botEngineOptions(g.bot))
      }
      const engine = engineRef.current
      const remaining = g.tc.baseMs === null ? null : clocksRef.current[c.turn()]
      const budget = botThinkBudget(g.bot, remaining, g.tc.incMs)
      let uci: string
      if (g.bot.randomness > 0 && Math.random() < g.bot.randomness) {
        const moves = c.moves({ verbose: true })
        uci = moves[Math.floor(Math.random() * moves.length)].lan
      } else {
        const res = await engine.search({ fen: c.fen(), movetimeMs: budget.movetimeMs, multipv: 1 })
        uci = res.bestMove
      }
      // Latence artificielle pour un rythme naturel, réduite quand la pendule presse.
      const latency = (300 + Math.random() * 500) * budget.latencyScale
      if (latency > 0) await new Promise((r) => setTimeout(r, latency))
      if (seq !== gameSeq.current) return // partie finie ou remplacée pendant la réflexion
      const move = applyUci(c, uci)
      if (move) afterMove(move.san)
    } finally {
      if (thinkingSeq.current === seq) thinkingSeq.current = null
    }
  }, [afterMove])

  function handlePlayerMove(from: string, to: string, promotion?: string): boolean {
    const c = chessRef.current
    if (status !== 'playing') return false
    if (viewIndex !== -1) return false
    try {
      const move = c.move({ from, to, promotion: promotion ?? 'q' })
      const cont = afterMove(move.san, true)
      if (cont && mode !== 'local') void playBotMove()
      return true
    } catch {
      return false
    }
  }

  // Démarre une partie (neuve, ou restaurée depuis l'instantané avec ses coups et ses pendules).
  function beginGame(
    next: { mode: PlayMode; bot: Bot; color: 'w' | 'b'; tc: TimeControl },
    restored: { chess: Chess; clocks: { w: number; b: number }; unrated: boolean; lastWhiteCp: number } | null,
  ) {
    const gameTc = next.mode === 'coach' ? UNLIMITED : next.tc
    const c = restored?.chess ?? new Chess()
    chessRef.current = c
    gameSeq.current++
    gameRef.current = { seq: gameSeq.current, mode: next.mode, bot: next.bot, playerColor: next.color, tc: gameTc, tcLabel: next.tc.label }
    thinkingSeq.current = null
    liveChain.current = Promise.resolve()
    takebackGen.current = 0
    setMode(next.mode)
    setBot(next.bot)
    if (next.mode !== 'coach') setTc(next.tc)
    setPlayerColor(next.color)
    setFen(c.fen())
    setSans(c.history())
    setViewIndex(-1)
    setGameOver(null)
    setSavedGameId(null)
    setConfirmResign(null)
    clocksRef.current = restored?.clocks ?? { w: gameTc.baseMs ?? 0, b: gameTc.baseMs ?? 0 }
    setClocks(clocksRef.current)
    lowTimeWarned.current = false
    unratedRef.current = restored?.unrated ?? false
    setUnrated(unratedRef.current)
    setHintArrow(null)
    setHintBusy(false)
    setBookBadge(null)
    lastWhiteCp.current = restored?.lastWhiteCp ?? 20
    setLiveCp(next.mode === 'coach' ? lastWhiteCp.current : null)
    setCoachMsg(next.mode === 'coach' ? (restored ? { text: 'On reprend la partie.', cls: null, mood: 'thinking' } : greeting()) : null)
    statusRef.current = 'playing'
    setStatus('playing')
    if (next.mode !== 'local') {
      // Moteur créé et options posées dès maintenant : le WASM se charge pendant le premier coup du joueur.
      engineRef.current ??= new Engine()
      void engineRef.current.setOptions(botEngineOptions(next.bot))
      if (next.mode === 'coach') coachEngineRef.current ??= new Engine()
      if (c.turn() !== next.color) {
        const seq = gameSeq.current
        setTimeout(() => {
          if (seq === gameSeq.current) void playBotMove()
        }, 400)
      }
    }
  }

  function startGame() {
    const color = colorChoice === 'random' ? (Math.random() < 0.5 ? 'w' : 'b') : colorChoice
    beginGame({ mode, bot, color, tc }, null)
  }

  // Restaure la partie en cours au montage (changement d'onglet, retour arrière, rechargement).
  // Avant la peinture : l'écran de configuration n'apparaît jamais, même brièvement.
  useLayoutEffect(() => {
    const stored = readStoredGame()
    if (!stored) return
    const c = new Chess()
    try {
      for (const san of stored.sans) c.move(san)
    } catch {
      writeStoredGame(null) // coups illisibles : on repart de la configuration
      return
    }
    if (c.isGameOver() || !['bot', 'local', 'coach'].includes(stored.mode)) {
      writeStoredGame(null)
      return
    }
    beginGame(
      {
        mode: stored.mode,
        bot: botById(stored.botId) ?? BOTS[3],
        color: stored.playerColor === 'b' ? 'b' : 'w',
        tc: TIME_CONTROLS.find((t) => t.label === stored.tcLabel) ?? TIME_CONTROLS[4],
      },
      { chess: c, clocks: stored.clocks, unrated: !!stored.unrated, lastWhiteCp: stored.lastWhiteCp ?? 20 },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function goSetup() {
    statusRef.current = 'setup'
    gameSeq.current++
    gameRef.current = null
    writeStoredGame(null)
    setStatus('setup')
  }

  function resign() {
    if (status === 'playing') setConfirmResign({ cancel: chessRef.current.history().length < 2 })
  }

  function confirmResignNow() {
    const cancel = confirmResign?.cancel === true
    setConfirmResign(null)
    const g = gameRef.current
    if (!g || statusRef.current !== 'playing') return
    const loser = g.mode !== 'local' ? g.playerColor : chessRef.current.turn()
    void endGame(loser === 'w' ? '0-1' : '1-0', 'par abandon', cancel)
  }

  // --- Actions du mode entraîneur ---
  async function requestHint() {
    const g = gameRef.current
    if (!g || hintBusy || status !== 'playing' || chessRef.current.turn() !== g.playerColor) return
    markUnrated()
    setHintBusy(true)
    const seq = g.seq
    const fenNow = chessRef.current.fen()
    try {
      coachEngineRef.current ??= new Engine()
      const res = await coachEngineRef.current.search({ fen: fenNow, depth: 12, multipv: 1 })
      if (seq !== gameSeq.current || chessRef.current.fen() !== fenNow) return // la position a changé entre-temps
      const uci = res.bestMove
      if (uci && uci.length >= 4) {
        setHintArrow({ startSquare: uci.slice(0, 2), endSquare: uci.slice(2, 4), color: '#81b64c' })
      }
    } finally {
      setHintBusy(false)
    }
  }

  function takeback() {
    const c = chessRef.current
    const g = gameRef.current
    if (!g || status !== 'playing' || c.history().length < 2 || c.turn() !== g.playerColor || thinkingSeq.current === g.seq) return
    markUnrated()
    c.undo()
    c.undo()
    takebackGen.current++ // les évals des coups annulés sont jetées
    setFen(c.fen())
    setSans(c.history())
    setViewIndex(-1)
    setHintArrow(null)
    setBookBadge(null)
    saveGame()
    // Recale l'éval sur la position restaurée.
    const seq = g.seq
    const gen = takebackGen.current
    const fenNow = c.fen()
    void (async () => {
      coachEngineRef.current ??= new Engine()
      const res = await coachEngineRef.current.search({ fen: fenNow, depth: 10, multipv: 1 })
      if (seq !== gameSeq.current || gen !== takebackGen.current) return
      const line = res.lines[0]
      const cpPovTurn = line ? (line.scoreMate !== null ? (line.scoreMate > 0 ? 10000 : -10000) : (line.scoreCp ?? 0)) : 0
      const whiteCp = c.turn() === 'w' ? cpPovTurn : -cpPovTurn
      lastWhiteCp.current = whiteCp
      setLiveCp(whiteCp)
      setCoachMsg({ text: 'On reprend ici. Cherche un meilleur plan.', cls: null, mood: 'thinking' })
    })()
  }

  // --- Configuration : chaque choix est mémorisé dans les réglages ---
  function chooseMode(m: PlayMode) {
    setMode(m)
    setPlayConfig({ playMode: m })
  }
  function chooseBot(b: Bot) {
    setBot(b)
    setPlayConfig({ playBotId: b.id })
  }
  function chooseColor(c: PlayColor) {
    setColorChoice(c)
    setPlayConfig({ playColor: c })
  }
  function chooseTc(t: TimeControl) {
    setTc(t)
    setPlayConfig({ playTcLabel: t.label })
  }

  // --- Rendu ---
  if (status === 'setup') {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <h1 className="mb-6 text-2xl font-bold">Jouer</h1>
        <div className="mb-5 flex flex-wrap gap-2">
          <ModeButton active={mode === 'bot'} onClick={() => chooseMode('bot')} label="🤖 Contre un bot" />
          <ModeButton active={mode === 'coach'} onClick={() => chooseMode('coach')} label="🎓 Entraîneur" />
          <ModeButton active={mode === 'local'} onClick={() => chooseMode('local')} label="👥 2 joueurs (local)" />
        </div>

        {mode === 'coach' && (
          <p className="mb-4 rounded bg-surface-2 p-3 text-sm text-neutral-300">
            Le coach évalue chaque coup en direct, commente la partie, et t'offre Indication et Annuler.
            Sans pendule. La partie reste classée tant que tu n'utilises pas d'aide.
          </p>
        )}

        {mode !== 'local' && (
          <>
            <h2 className="mb-2 text-sm font-semibold text-neutral-400">Adversaire</h2>
            <div className="mb-5 grid grid-cols-3 gap-2">
              {BOTS.map((b) => (
                <button
                  key={b.id}
                  onClick={() => chooseBot(b)}
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
              <ModeButton active={colorChoice === 'w'} onClick={() => chooseColor('w')} label="♔ Blancs" />
              <ModeButton active={colorChoice === 'b'} onClick={() => chooseColor('b')} label="♚ Noirs" />
              <ModeButton active={colorChoice === 'random'} onClick={() => chooseColor('random')} label="🎲 Aléatoire" />
            </div>
          </>
        )}

        {mode !== 'coach' && (
          <>
            <h2 className="mb-2 text-sm font-semibold text-neutral-400">Cadence</h2>
            <div className="mb-6 grid grid-cols-4 gap-2">
              {TIME_CONTROLS.map((t) => (
                <button
                  key={t.label}
                  onClick={() => chooseTc(t)}
                  className={`cursor-pointer rounded-lg border-2 py-2 font-semibold transition ${
                    tc.label === t.label ? 'border-accent bg-accent/10' : 'border-transparent bg-surface-2 hover:bg-surface-3'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </>
        )}

        {mode !== 'local' && myRating !== null && (
          <p className="mb-4 text-sm text-neutral-400">
            Mon classement {effectiveTc.timeClass} : <b className="text-white">{myRating}</b>
          </p>
        )}

        <Cta className="w-full" onClick={startGame}>
          Jouer
        </Cta>
      </div>
    )
  }

  const orientation = mode !== 'local' ? playerColor : 'w'
  const topColor = orientation === 'w' ? 'b' : 'w'
  const nameOf = (c: 'w' | 'b') =>
    mode === 'local' ? (c === 'w' ? 'Blancs' : 'Noirs') : c === playerColor ? `Moi${myRating ? ` (${myRating})` : ''}` : `${bot.emoji} ${bot.name} (${bot.elo})`
  const selectMove = (i: number) => setViewIndex(i >= sans.length - 1 ? -1 : i) // le dernier coup = le direct

  const gameOverModal = gameOver && (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/70" onClick={() => setGameOver(null)}>
      <div className="w-96 rounded-xl bg-surface-2 p-6 text-center shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-1 text-2xl font-bold">
          {gameOver.cancelled
            ? 'Partie annulée'
            : gameOver.result === '1/2-1/2'
              ? 'Nulle'
              : gameOver.result === '1-0'
                ? 'Les Blancs gagnent'
                : 'Les Noirs gagnent'}
        </h2>
        <p className="mb-4 text-neutral-400">
          {gameOver.cancelled ? 'Moins de deux coups joués : ni classement ni archive.' : gameOver.termination}
        </p>
        {gameOver.ratingAfter !== undefined && gameOver.ratingBefore !== undefined && (
          <p className="mb-4 text-lg">
            Classement : <b>{gameOver.ratingAfter}</b>{' '}
            <span className={gameOver.ratingAfter >= gameOver.ratingBefore ? 'text-accent' : 'text-red-400'}>
              ({gameOver.ratingAfter >= gameOver.ratingBefore ? '+' : ''}
              {gameOver.ratingAfter - gameOver.ratingBefore})
            </span>
          </p>
        )}
        {gameOver.saveFailed && (
          <p className="mb-4 text-sm text-red-400">Partie non enregistrée : stockage du navigateur plein ou indisponible.</p>
        )}
        {mode === 'coach' && unrated && !gameOver.cancelled && (
          <p className="mb-4 text-sm text-neutral-400">Partie non classée (aide du coach utilisée).</p>
        )}
        <div className="flex flex-col gap-2">
          {savedGameId !== null && (
            <Cta className="w-full" onClick={() => navigate(`/analyse?game=${savedGameId}&review=1`)}>
              Bilan de la partie
            </Cta>
          )}
          <Cta variant="secondary" className="w-full" onClick={goSetup}>
            Nouvelle partie
          </Cta>
        </div>
      </div>
    </div>
  )

  // Confirmation d'abandon. Sous deux demi-coups, la partie est annulée plutôt que perdue.
  const tooShort = confirmResign?.cancel === true
  const confirmSheet = confirmResign && status === 'playing' && (
    <div className="fixed inset-0 z-30 flex items-end justify-center bg-black/60 md:items-center" onClick={() => setConfirmResign(null)}>
      <div className="pb-safe w-full max-w-md rounded-t-2xl bg-surface-2 p-5 shadow-2xl md:rounded-2xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-1 text-lg font-bold">{tooShort ? 'Annuler la partie ?' : 'Abandonner la partie ?'}</h2>
        <p className="mb-4 text-sm text-neutral-400">
          {tooShort
            ? 'Moins de deux coups joués : la partie ne sera ni classée ni archivée.'
            : mode === 'local'
              ? 'Le camp au trait perd la partie.'
              : unrated
                ? 'Ton adversaire gagne. Partie non classée.'
                : 'Ton adversaire gagne et ton classement en tient compte.'}
        </p>
        <div className="flex flex-col gap-2">
          <button onClick={confirmResignNow} className="cursor-pointer rounded-xl bg-red-800 py-3 text-lg font-black text-white hover:bg-red-700">
            {tooShort ? 'Oui, annuler' : 'Oui, abandonner'}
          </button>
          <Cta variant="secondary" className="w-full" onClick={() => setConfirmResign(null)}>
            Continuer la partie
          </Cta>
        </div>
      </div>
    </div>
  )

  // --- Rendu mode entraîneur : éval bar, coach, board plein, barre d'actions ---
  if (mode === 'coach') {
    return (
      <div className="mx-auto flex h-full max-w-2xl flex-col">
        <div className="px-3 pt-2">
          <HEvalBar cp={liveCp} mate={null} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="flex items-center justify-between px-3 pt-2 text-sm">
            <span className="font-semibold">{nameOf(topColor)}</span>
            {unrated && <span className="rounded bg-surface-3 px-2 py-0.5 text-xs text-neutral-400">non classée</span>}
          </div>
          <div className="px-3 py-2">
            <CoachBubble mood={coachMsg?.mood ?? 'thinking'} cls={coachMsg?.cls ?? undefined} headline={coachMsg?.headline} fixed>
              {coachMsg?.text ?? '…'}
            </CoachBubble>
          </div>
          <div className="flex justify-center">
            <div className="boardbox md:w-[min(56vh,520px)]">
              <Board
                fen={viewFen}
                orientation={orientation}
                interactive={status === 'playing' && viewIndex === -1}
                movableColor={playerColor}
                onMove={handlePlayerMove}
                lastMove={lastMove}
                arrows={hintArrow ? [hintArrow] : []}
                badge={bookBadge && viewIndex === -1 ? { square: bookBadge, cls: 'book' } : null}
              />
            </div>
          </div>
          <MoveStrip
            sans={sans}
            classes={sans.map(() => null)}
            currentIndex={viewIndex === -1 ? sans.length - 1 : viewIndex}
            onSelect={selectMove}
          />
        </div>
        <div className="flex items-center gap-1 border-t border-black/40 p-2">
          <CoachAction label="Abandonner" icon="🏳" onClick={resign} disabled={status !== 'playing'} />
          <CoachAction
            label={hintBusy ? '…' : 'Indication'}
            icon="💡"
            onClick={() => void requestHint()}
            disabled={status !== 'playing' || hintBusy || chess.turn() !== playerColor}
          />
          <CoachAction
            label="Annuler"
            icon="↩"
            onClick={takeback}
            disabled={status !== 'playing' || sans.length < 2 || chess.turn() !== playerColor}
          />
          <div className="flex-1" />
          {status !== 'playing' && (
            <Cta className="px-6 py-2 text-base" onClick={goSetup}>
              Nouvelle partie
            </Cta>
          )}
        </div>
        {confirmSheet}
        {gameOverModal}
      </div>
    )
  }

  const noMoves = sans.length === 0
  return (
    <div className="flex h-full flex-col items-center justify-start gap-2 p-2 md:flex-row md:justify-center md:gap-6 md:p-4">
      <div className="flex flex-col gap-2">
        <div className="flex w-full items-center justify-between">
          <span className="font-semibold">{nameOf(topColor)}</span>
          {effectiveTc.baseMs !== null && <Clock ms={clocks[topColor]} active={status === 'playing' && chess.turn() === topColor} label="" />}
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
          {effectiveTc.baseMs !== null && <Clock ms={clocks[orientation]} active={status === 'playing' && chess.turn() === orientation} label="" />}
        </div>
      </div>

      <div className="flex w-full flex-col gap-2 px-1 pb-2 md:h-[min(76vh,640px)] md:w-72 md:gap-3 md:px-0 md:pb-0">
        <div className="rounded bg-surface-2 px-3 py-2 text-sm text-neutral-300">
          {opening ? (
            <>
              <span className="font-mono text-xs text-neutral-500">{opening.eco}</span> {openingFr(opening.name)}
            </>
          ) : (
            <span className="text-neutral-500">Ouverture inconnue</span>
          )}
        </div>
        <div className="h-32 md:min-h-0 md:h-auto md:flex-1">
          <MoveList sans={sans} currentIndex={viewIndex === -1 ? sans.length - 1 : viewIndex} onSelect={selectMove} />
        </div>
        <div className="flex gap-2">
          <NavButton label="⏮" disabled={noMoves} onClick={() => setViewIndex(0)} />
          <NavButton label="◀" disabled={noMoves} onClick={() => setViewIndex((v) => Math.max(0, (v === -1 ? sans.length - 1 : v) - 1))} />
          <NavButton label="▶" disabled={noMoves} onClick={() => setViewIndex((v) => (v === -1 ? -1 : v + 1 >= sans.length - 1 ? -1 : v + 1))} />
          <NavButton label="⏭" disabled={noMoves} onClick={() => setViewIndex(-1)} />
        </div>
        {status === 'playing' ? (
          <button onClick={resign} className="cursor-pointer rounded bg-surface-3 py-2 font-semibold hover:bg-red-900">
            🏳 Abandonner
          </button>
        ) : (
          <button onClick={goSetup} className="cursor-pointer rounded bg-accent py-2 font-bold text-white hover:bg-accent-hover">
            Nouvelle partie
          </button>
        )}
      </div>

      {confirmSheet}
      {gameOverModal}
    </div>
  )
}

// Action de la barre du mode entraîneur.
function CoachAction({ label, icon, onClick, disabled }: {
  label: string
  icon: string
  onClick: () => void
  disabled?: boolean
}) {
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

function NavButton({ label, onClick, disabled }: { label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex-1 cursor-pointer rounded bg-surface-3 py-1.5 hover:bg-surface-3/70 disabled:cursor-default disabled:opacity-40 disabled:hover:bg-surface-3"
    >
      {label}
    </button>
  )
}
