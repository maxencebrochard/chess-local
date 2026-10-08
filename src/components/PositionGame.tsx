// Partie contre Stockfish depuis une position, sans plafond de coups : seules les règles du jeu
// (mat, pat, répétition, 50 coups, matériel insuffisant), l'abandon ou une nulle acceptée
// l'arrêtent. Sert aux finales jouées jusqu'au bout et au bouton « Jouer contre le moteur » de
// l'analyse (pleine force), et à l'entraîneur d'attaque (défenseur à l'Elo choisi, avantage
// décisif qui permet de conclure). Le joueur a le trait au départ ; la partie est persistée à
// chaque coup.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Chess, type Color, type Move } from 'chess.js'
import { useNavigate } from 'react-router-dom'
import { AttackLegend } from './AttackLegend'
import { Board, type BoardArrow } from './Board'
import { ConfirmSheet } from './ConfirmSheet'
import { CourseSheet } from './CourseSheet'
import { Cta } from './Cta'
import { EngineContinuation } from './EngineContinuation'
import { MoveStrip } from './MoveStrip'
import { courseFor } from '../lib/courses'
import { Engine } from '../lib/engine'
import {
  boardEnd, decisiveEnd, decisiveStreak, DECISIVE_TURNS, engineAcceptsDraw, halfmoveClock, judge, loadStoredGame,
  repetitions, replay, resignEnd, resumedGame, storeGame, verdictText, type GameEnd, type Objective, type Opponent, type StoredGame,
} from '../lib/positionGame'
import { figurine, winPct } from '../lib/review'
import { sounds } from '../lib/sounds'
import { useSettings } from '../store/settings'

// Temps de réflexion de Stockfish par coup : pleine force, sans faire attendre.
const ENGINE_MOVETIME_MS = 700
// Suivi de l'avantage décisif : éval courte de chaque position au trait du joueur.
const DECISIVE_EVAL_MS = 300

// Fin d'une tentative, remontée une seule fois : `end.kind === 'decisive'` quand l'avantage
// décisif est atteint, même si le joueur choisit ensuite de continuer.
export interface FinishInfo {
  end: GameEnd
  assisted: boolean
}

// Coup attendu au premier coup du joueur (« Mes attaques manquées » : le coup du bilan). Un autre
// coup est vérifié par Stockfish : il « tient aussi » s'il perd moins de 5 points de win%
// (même règle que « Mes erreurs »). `onJudged` suit le contrat `LearnSession` dans db.ts, au plus
// une fois par tentative ; Annuler, Recommencer ou abandonner pendant la vérification compte
// comme un échec. Une erreur moteur ou un départ de la page pendant la vérification ne note rien.
export interface KeyMove {
  uci: string
  san: string
  onJudged: (found: boolean) => void
}
// `other` : partie reprise après rechargement, premier coup différent du coup attendu et verdict
// perdu : on rappelle le coup du bilan sans juger. `unverified` : Stockfish n'a pas pu juger le
// coup : rien n'est noté, Recommencer relance une tentative propre.
type KeyResult = 'checking' | 'found' | 'close' | 'missed' | 'other' | 'unverified'

// Verdict dérivé d'une partie reprise : seul le coup exact se reconnaît sans moteur.
function restoredKeyResult(chess: Chess, player: Color, key: KeyMove | undefined): KeyResult | null {
  const first = key ? chess.history({ verbose: true }).find((m) => m.color === player) : undefined
  return first ? (first.lan === key!.uci ? 'found' : 'other') : null
}

export interface PositionGameProps {
  gameKey: string // clé de persistance fournie par l'écran appelant, distincte selon l'exercice
  startFen: string
  title: string
  objective: Objective
  goalHint?: string | null // précision sous l'objectif (finales)
  lesson?: string | null
  courseId?: string | null
  resume?: boolean // reprendre la partie persistée de cette clé (vrai par défaut)
  restoreFinished?: boolean // retour de l'analyse : reprendre aussi une partie terminée
  returnTo: string // où « Retour » de l'analyse ramène
  returnLabel: string
  onExit: () => void
  onOther?: () => void // « Autre finale »
  otherLabel?: string // libellé du bouton de onOther
  onFinished?: (success: boolean, info: FinishInfo) => void // première fin de chaque tentative
  onAbandon?: (info: { assisted: boolean }) => void // Recommencer en cours de tentative, après au moins un coup du joueur
  // Première action dans cette partie alors qu'une autre partie persistée était en cours : elle va
  // être écrasée (seul emplacement de persistance).
  onReplace?: (replaced: StoredGame) => void
  back?: unknown // gardé avec la partie persistée (partie libre)
  showAttackers?: boolean // calque « Compte les attaquants » (cadres sur l'échiquier + légende)
  objectiveLabel?: string // titre du bandeau quand il n'y a pas d'objectif (défaut « Partie libre »)
  keyMove?: KeyMove
  opponent?: Opponent // absent : Stockfish à pleine force, sans option
  decisiveCp?: number // seuil d'avantage décisif (centipions) ; absent : pas de suivi
  lessonLabel?: string // libellé du bouton qui déplie `lesson`
  successTitle?: string // titre du verdict réussi
  headerAction?: ReactNode // à droite du titre, à la place du bouton du cours
  planButton?: boolean // fin de partie : « Plan », la suite de Stockfish depuis la position de départ
  allowDraw?: boolean // bouton Nulle (vrai par défaut)
}

interface Init {
  chess: Chess
  end: GameEnd | null
  assisted: boolean
  recorded: boolean
  decisive: StoredGame['decisive'] | null
}

function initialGame(p: PositionGameProps): Init {
  const stored = p.resume !== false ? resumedGame(p.gameKey, p.startFen, !!p.restoreFinished) : null
  if (stored) {
    const chess = replay(p.startFen, stored.uci)
    return {
      chess,
      end: stored.end ?? boardEnd(chess),
      assisted: stored.assisted,
      recorded: stored.recorded ?? !!stored.end,
      decisive: stored.decisive ?? null,
    }
  }
  const chess = new Chess(p.startFen)
  return { chess, end: boardEnd(chess), assisted: false, recorded: false, decisive: null }
}

export function PositionGame(props: PositionGameProps) {
  const { startFen, title, objective, goalHint, lesson, courseId, onExit, onOther, opponent, decisiveCp } = props
  const navigate = useNavigate()
  const { playSounds } = useSettings()
  const [init] = useState(() => initialGame(props))
  const player = new Chess(startFen).turn()

  const chessRef = useRef(init.chess)
  const [fen, setFen] = useState(init.chess.fen())
  const [history, setHistory] = useState<Move[]>(init.chess.history({ verbose: true }))
  const [viewIndex, setViewIndex] = useState(-1) // -1 = position courante
  const [end, setEnd] = useState<GameEnd | null>(init.end)
  const [assisted, setAssisted] = useState(init.assisted)
  const recordedRef = useRef(init.recorded)
  // Stockfish joue (dès le montage si une partie reprise lui laisse le trait).
  const [thinking, setThinking] = useState(() => !init.end && init.chess.turn() !== new Chess(startFen).turn())
  const [busy, setBusy] = useState<'hint' | 'draw' | null>(null) // indice ou nulle en calcul
  const [hint, setHint] = useState<BoardArrow | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [showLesson, setShowLesson] = useState(false)
  const [showCourse, setShowCourse] = useState(false)
  const [confirmResign, setConfirmResign] = useState(false)
  const [showPlan, setShowPlan] = useState(false)
  // Avantage décisif atteint : choix proposé, ou poursuite choisie (plus de proposition).
  const [decisive, setDecisive] = useState<StoredGame['decisive'] | null>(init.decisive)
  // Série de tours au-dessus du seuil, et dernier demi-coup évalué (une éval n'est comptée qu'une fois).
  const streakRef = useRef({ count: 0, ply: -1 })
  const engineRef = useRef<Engine | null>(null)
  // Moteur à pleine force pour l'indice, la nulle et le suivi de l'avantage quand l'adversaire est
  // bridé : un moteur limité ne sert jamais d'oracle.
  const oracleRef = useRef<Engine | null>(null)
  // Génération de la partie : un coup moteur, un indice ou une nulle calculés pour une partie
  // remplacée (Recommencer, démontage) sont ignorés à leur retour.
  const genRef = useRef(0)
  // Verdict sur le premier coup du joueur (keyMove) ; `judgedRef` : déjà noté pour cette tentative
  // (une partie reprise avec un coup joué ne se note pas une seconde fois).
  const [keyResult, setKeyResult] = useState<KeyResult | null>(() => restoredKeyResult(init.chess, player, props.keyMove))
  const judgedRef = useRef(keyResult !== null)
  // Vérification Stockfish en cours : note la tentative ratée si Annuler, Recommencer ou un abandon
  // l'interrompt (appelée par l'action elle-même, avant que la tentative suivante ne commence).
  const pendingJudgeRef = useRef<(() => void) | null>(null)

  const course = courseId ? courseFor(courseId) : null
  // Miroirs pour les callbacks asynchrones (éval de l'oracle rendue après un rendu).
  const assistedRef = useRef(assisted)
  const decisiveRef = useRef(decisive)
  useEffect(() => {
    assistedRef.current = assisted
    decisiveRef.current = decisive
  }, [assisted, decisive])

  function getEngine(): Engine {
    if (!engineRef.current) {
      engineRef.current = new Engine()
      // Sous mutex : appliquées avant la première recherche.
      if (opponent) void engineRef.current.setOptions(opponent.options)
    }
    return engineRef.current
  }

  function getOracle(): Engine {
    if (!opponent) return getEngine()
    oracleRef.current ??= new Engine()
    return oracleRef.current
  }

  // Persistance à chaque changement : coups rejoués depuis la FEN de départ à la reprise. Une
  // partie vierge n'écrase pas la partie en cours d'une autre position (simple coup d'œil).
  useEffect(() => {
    const stored = loadStoredGame()
    const other = stored && (stored.key !== props.gameKey || stored.startFen !== startFen)
    if (history.length === 0 && !end && other) return
    if (other && !stored.end && !stored.recorded && stored.uci.length > 0) props.onReplace?.(stored)
    storeGame({
      key: props.gameKey,
      startFen,
      player,
      label: title,
      uci: history.map((m) => m.lan),
      end,
      assisted,
      recorded: recordedRef.current,
      back: props.back,
      level: opponent?.level,
      decisive: decisive ?? undefined,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history, end, assisted, decisive])

  const finish = useCallback((e: GameEnd) => {
    setEnd(e)
    const verdict = judge(e, player, objective)
    if (playSounds) (verdict === 'fail' ? sounds.fail : verdict === 'success' ? sounds.success : sounds.gameEnd)()
    if (!recordedRef.current) {
      recordedRef.current = true
      props.onFinished?.(verdict === 'success' && !assisted, { end: e, assisted })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [player, objective, playSounds, assisted, props.onFinished])

  // Après chaque coup (joueur ou moteur) : affichage, son, fin de partie éventuelle.
  const afterMove = useCallback((move: Move): GameEnd | null => {
    const c = chessRef.current
    if (playSounds) {
      if (c.inCheck()) sounds.check()
      else if (move.captured) sounds.capture()
      else sounds.move()
    }
    setFen(c.fen())
    setHistory(c.history({ verbose: true }))
    setViewIndex(-1)
    setHint(null)
    setNotice(null)
    const e = boardEnd(c)
    if (e) finish(e)
    return e
  }, [playSounds, finish])

  // Avantage décisif : à chaque tour du joueur, l'oracle évalue la position (de son point de vue,
  // il a le trait). Tenu DECISIVE_TURNS tours de suite, la tentative est réussie (notée tout de
  // suite) et le joueur choisit de conclure ou de continuer. Les évals passent dans l'ordre des
  // tours (mutex du moteur) ; une éval d'une partie remplacée (Recommencer, Annuler) est ignorée.
  const trackDecisive = useCallback(async () => {
    if (!decisiveCp || decisiveRef.current) return
    const gen = genRef.current
    const ply = chessRef.current.history().length
    let line
    try {
      line = (await getOracle().search({ fen: chessRef.current.fen(), movetimeMs: DECISIVE_EVAL_MS, multipv: 1 })).lines[0]
    } catch {
      return
    }
    if (gen !== genRef.current || decisiveRef.current || ply <= streakRef.current.ply) return
    const count = decisiveStreak(streakRef.current.count, line?.scoreCp ?? null, line?.scoreMate ?? null, decisiveCp)
    streakRef.current = { count, ply }
    // Proposition seulement sur la position évaluée : si le joueur a déjà rejoué (ou fini la
    // partie) pendant l'éval, la série est notée mais le choix attend le tour suivant.
    const c = chessRef.current
    if (count < DECISIVE_TURNS || c.history().length !== ply || boardEnd(c)) return
    decisiveRef.current = 'offered'
    setDecisive('offered')
    if (playSounds) sounds.success()
    if (!recordedRef.current) {
      recordedRef.current = true
      props.onFinished?.(!assistedRef.current, { end: decisiveEnd(player), assisted: assistedRef.current })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decisiveCp, playSounds, player, props.onFinished])

  const engineMove = useCallback(async () => {
    const gen = genRef.current
    const c = chessRef.current
    setThinking(true)
    try {
      const res = await getEngine().search({ fen: c.fen(), movetimeMs: ENGINE_MOVETIME_MS, multipv: 1 })
      if (gen !== genRef.current) return
      const move = c.move({ from: res.bestMove.slice(0, 2), to: res.bestMove.slice(2, 4), promotion: res.bestMove[4] })
      if (!afterMove(move)) void trackDecisive()
    } catch {
      // Pas de coup exploitable (ne devrait pas arriver) : dit-le, « Relancer » réessaie.
      if (gen === genRef.current) setNotice("Stockfish n'a pas répondu.")
    } finally {
      if (gen === genRef.current) setThinking(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [afterMove])

  // Reprise d'une partie interrompue pendant que Stockfish réfléchissait, et arrêt du moteur au
  // démontage (null obligatoire : StrictMode rejoue les effets).
  useEffect(() => {
    const c = chessRef.current
    if (!boardEnd(c) && !init.end && c.turn() !== player) void engineMove()
    return () => {
      // Page quittée pendant la vérification : rien n'est noté.
      pendingJudgeRef.current = null
      // Compteur, pas un nœud du DOM : c'est bien la valeur courante qu'il faut incrémenter.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      genRef.current++
      engineRef.current?.quit()
      engineRef.current = null
      oracleRef.current?.quit()
      oracleRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const live = viewIndex === -1
  const myTurn = !end && !thinking && chessRef.current.turn() === player

  function handleMove(from: string, to: string, promotion?: string): boolean {
    if (!myTurn || !live || busy) return false
    const first = chessRef.current.history({ verbose: true }).every((m) => m.color !== player)
    let move: Move
    try {
      move = chessRef.current.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    if (first && props.keyMove) void judgeKeyMove(move, props.keyMove, assisted)
    // Jouer après « Attaque réussie », c'est choisir de continuer.
    if (decisive === 'offered') setDecisive('continued')
    if (!afterMove(move)) void engineMove()
    return true
  }

  // Premier coup du joueur contre le coup attendu : égal, ou vérifié par Stockfish (profondeur 12,
  // avant / après, point de vue du joueur). Le mutex du moteur enchaîne cette vérification et la
  // réponse de Stockfish sans se gêner. `assistedNow` : un indice avant le coup l'a révélé.
  async function judgeKeyMove(move: Move, key: KeyMove, assistedNow: boolean) {
    const gen = genRef.current
    const fenBefore = move.before
    const note = (found: boolean) => {
      if (judgedRef.current) return
      judgedRef.current = true
      key.onJudged(found)
    }
    const conclude = (r: KeyResult) => {
      // Tentative reprise ou relancée avant le verdict : déjà notée par `abandonJudge`.
      if (gen !== genRef.current) return
      pendingJudgeRef.current = null
      setKeyResult(r)
      note((r === 'found' || r === 'close') && !assistedNow)
    }
    if (move.lan === key.uci) {
      conclude('found')
      return
    }
    setKeyResult('checking')
    pendingJudgeRef.current = () => note(false)
    try {
      const engine = getEngine()
      const cp = (l?: { scoreMate: number | null; scoreCp: number | null }) =>
        l ? (l.scoreMate !== null ? (l.scoreMate > 0 ? 10000 : -10000) : (l.scoreCp ?? 0)) : 0
      const before = await engine.search({ fen: fenBefore, depth: 12, multipv: 1 })
      if (gen !== genRef.current) return
      const after = await engine.search({ fen: move.after, depth: 12, multipv: 1 })
      const wBefore = winPct(cp(before.lines[0]))
      const wAfter = new Chess(move.after).isCheckmate() ? 100 : winPct(-cp(after.lines[0]))
      conclude(wBefore - wAfter < 5 ? 'close' : 'missed')
    } catch {
      if (gen !== genRef.current) return
      pendingJudgeRef.current = null
      setKeyResult('unverified')
    }
  }

  // Annuler, Recommencer ou abandon avant le verdict : la tentative en cours est ratée.
  function abandonJudge() {
    const pending = pendingJudgeRef.current
    pendingJudgeRef.current = null
    pending?.()
  }

  function restart() {
    abandonJudge()
    if (!end && !recordedRef.current && playerMoves > 0) props.onAbandon?.({ assisted })
    genRef.current++
    streakRef.current = { count: 0, ply: -1 }
    setDecisive(null)
    chessRef.current = new Chess(startFen)
    recordedRef.current = false
    judgedRef.current = false
    setKeyResult(null)
    setFen(startFen)
    setHistory([])
    setViewIndex(-1)
    setEnd(boardEnd(chessRef.current))
    setAssisted(false)
    setThinking(false)
    setBusy(null)
    setHint(null)
    setNotice(null)
  }

  // Reprend le dernier coup du joueur (et la réponse de Stockfish). Possible après une fin sur
  // l'échiquier : le pat accidentel est l'erreur type des mats élémentaires.
  function takeback() {
    const c = chessRef.current
    if (thinking || busy) return
    const mine = c.history({ verbose: true }).filter((m) => m.color === player).length
    if (mine === 0) return
    if (c.turn() === player) c.undo() // la réponse de Stockfish
    c.undo() // mon coup
    abandonJudge()
    genRef.current++
    if (mine === 1) setKeyResult(null) // premier coup repris : le verdict repart avec lui
    streakRef.current = { count: 0, ply: -1 }
    setFen(c.fen())
    setHistory(c.history({ verbose: true }))
    setViewIndex(-1)
    setEnd(null)
    setAssisted(true)
    setHint(null)
    setNotice(null)
  }

  async function requestHint() {
    if (!myTurn || busy) return
    const gen = genRef.current
    setBusy('hint')
    setAssisted(true)
    try {
      const res = await getOracle().search({ fen: chessRef.current.fen(), depth: 14, multipv: 1 })
      if (gen !== genRef.current) return
      const uci = res.bestMove
      if (uci && uci.length >= 4) setHint({ startSquare: uci.slice(0, 2), endSquare: uci.slice(2, 4), color: '#81b64c' })
    } finally {
      if (gen === genRef.current) setBusy(null)
    }
  }

  async function offerDraw() {
    if (!myTurn || busy) return
    const gen = genRef.current
    setBusy('draw')
    try {
      const res = await getOracle().search({ fen: chessRef.current.fen(), depth: 12, multipv: 1 })
      if (gen !== genRef.current) return
      const line = res.lines[0]
      if (engineAcceptsDraw(line?.scoreCp ?? null, line?.scoreMate ?? null)) finish({ result: '1/2-1/2', kind: 'agreed' })
      else setNotice('Stockfish refuse la nulle.')
    } finally {
      if (gen === genRef.current) setBusy(null)
    }
  }

  // « Conclure » après un avantage décisif : la partie s'arrête, gagnée.
  function conclude() {
    if (end) return
    genRef.current++
    setThinking(false)
    setBusy(null)
    setDecisive('continued')
    finish(decisiveEnd(player))
  }

  function resign() {
    setConfirmResign(false)
    if (end) return
    abandonJudge()
    genRef.current++
    setThinking(false)
    setBusy(null)
    finish(resignEnd(player))
  }

  // `replace` : l'analyse prend la place de la partie, son bouton retour la remet en place.
  function analyse() {
    navigate('/analyse', {
      replace: true,
      state: {
        fen: startFen,
        uci: history.map((m) => m.lan),
        orientation: player,
        label: title,
        returnTo: props.returnTo,
        returnLabel: props.returnLabel,
      },
    })
  }

  // ---------- Rendu ----------
  const playerMoves = history.filter((m) => m.color === player).length
  // Avantage décisif atteint : la tentative est réussie, quelle que soit la suite.
  const verdict = end ? (decisive && objective ? 'success' : judge(end, player, objective)) : null
  const baseText = end ? verdictText(end, player, objective, playerMoves) : null
  const text = baseText && verdict === 'success' && props.successTitle ? { ...baseText, title: props.successTitle } : baseText
  const offered = !end && decisive === 'offered'
  const clock = halfmoveClock(fen)
  const showClock = !end && (objective === 'draw' || clock >= 60)
  // `fen` signale le changement de la partie (mutable, dans une ref).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reps = useMemo(() => (end ? 0 : repetitions(chessRef.current)), [fen, end])
  // Retour sur le premier coup : le verdict au premier coup, puis un rappel plus sobre tant que la
  // partie continue (plus d'« Annuler pour réessayer » une fois l'attaque engagée).
  const keyFig = props.keyMove ? figurine(props.keyMove.san, player) : ''
  const playerMovesSoFar = history.filter((m) => m.color === player).length
  const keyLine =
    keyResult === 'checking' ? 'Je vérifie ton coup…'
    : keyResult === 'found' || keyResult === 'close'
      ? playerMovesSoFar <= 1
        ? (keyResult === 'found' ? "C'est le coup du bilan : mène l'attaque !" : `Ça tient aussi (au bilan : ${keyFig}). Mène l'attaque !`)
        : "Mène l'attaque jusqu'au bout."
    : keyResult === 'unverified' && playerMovesSoFar <= 1
      ? "Stockfish n'a pas pu vérifier ton coup : Recommencer pour réessayer."
    : keyResult === 'missed' || keyResult === 'other' || keyResult === 'unverified'
      ? playerMovesSoFar <= 1 && keyResult === 'missed' ? `Au bilan : ${keyFig}. Annuler pour réessayer.` : `Au bilan : ${keyFig}. La partie continue.`
    : null
  const subline =
    notice ??
    (reps === 2 ? 'Position déjà vue 2 fois : une fois de plus et c\'est nulle.' : null) ??
    keyLine ??
    goalHint ??
    (objective ? null : `Tu joues les ${player === 'w' ? 'Blancs' : 'Noirs'}, sans limite de coups.`)
  const sublineClass =
    end || offered ? ''
    : notice || reps === 2 || keyResult === 'missed' || keyResult === 'unverified' ? 'text-amber-300'
    : keyResult === 'found' || keyResult === 'close' ? 'text-accent'
    : 'text-neutral-400'
  const viewFen = live ? fen : history[viewIndex].after
  const lastMove = live ? history[history.length - 1] : history[viewIndex]
  const boardEndKind = end && end.kind !== 'resign' && end.kind !== 'agreed' && end.kind !== 'decisive'

  return (
    <div
      data-testid="position-game"
      data-fen={fen}
      data-status={end ? 'over' : 'playing'}
      data-verdict={verdict ?? 'none'}
      data-decisive={decisive ?? 'none'}
      data-thinking={thinking || busy ? '1' : '0'}
      className="mx-auto flex h-full max-w-2xl flex-col"
    >
      <header className="flex items-center gap-1 px-2 pt-1">
        {/* Avec une action à droite plus large qu'un bouton rond, deux côtés de même largeur
            gardent le titre centré. */}
        <div className={`flex shrink-0 ${props.headerAction ? 'w-20' : ''}`}>
          <button
            onClick={onExit}
            aria-label="Retour"
            className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-full text-2xl text-neutral-400 hover:text-white"
          >
            ←
          </button>
        </div>
        <h1 className="min-w-0 flex-1 truncate text-center text-lg font-black">{title}</h1>
        {props.headerAction ? <div className="flex w-20 shrink-0 justify-end">{props.headerAction}</div> : (course ? (
          <button
            onClick={() => setShowCourse(true)}
            title="Voir le cours"
            aria-label="Voir le cours"
            className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-full text-lg font-black text-neutral-400 hover:text-white"
          >
            ?
          </button>
        ) : (
          <span className="w-10" />
        ))}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div
          data-testid="objective"
          className={`mx-3 mt-1 rounded px-3 py-1.5 ${
            verdict === 'success' || offered ? 'bg-accent/15 text-accent'
            : verdict === 'fail' ? 'bg-red-900/40 text-red-200'
            : 'bg-surface-2'
          }`}
        >
          <div className="flex items-center gap-2">
            <p className="min-w-0 flex-1 truncate text-sm font-bold">
              {text
                ? <>{verdict === 'success' ? '✓ ' : verdict === 'fail' ? '✗ ' : ''}{text.title}</>
                : offered ? <>✓ {props.successTitle ?? 'Objectif atteint'}</>
                : objective === 'win' ? 'Objectif : gagner'
                : objective === 'draw' ? 'Objectif : tenir la nulle'
                : (props.objectiveLabel ?? 'Partie libre')}
            </p>
            {lesson && (
              <button
                onClick={() => setShowLesson((s) => !s)}
                aria-expanded={showLesson}
                className="shrink-0 cursor-pointer rounded-full bg-surface-3/80 px-2.5 py-0.5 text-xs font-semibold text-neutral-200 hover:bg-surface-3"
              >
                {props.lessonLabel ?? 'Leçon'} {showLesson ? '▴' : '▾'}
              </button>
            )}
          </div>
          <p data-testid="objective-subline" className={`truncate text-xs ${sublineClass}`}>
            {text ? <>{text.reason}{assisted && ' (avec aide)'}</>
              : offered ? <>Avantage décisif tenu : conclus, ou joue jusqu'au mat.{assisted && ' (avec aide)'}</>
              : (subline ?? ' ')}
          </p>
        </div>
        {showLesson && lesson && (
          <p className="mx-3 mt-1 rounded bg-surface-2 px-3 py-2 text-sm leading-snug text-neutral-200">{lesson}</p>
        )}

        <div className="flex h-7 items-center gap-2 px-3 text-xs text-neutral-400">
          <span className="font-semibold text-neutral-300">🤖 Stockfish 18</span>
          <span>{thinking ? 'réfléchit…' : busy === 'hint' ? 'cherche un indice…' : busy === 'draw' ? 'étudie ta proposition…' : opponent ? opponent.label : 'pleine force'}</span>
          <span className="ml-auto flex items-center gap-2">
            {assisted && !end && <span className="rounded bg-surface-3 px-1.5 py-0.5">avec aide</span>}
            {showClock && (
              <span className={`rounded px-1.5 py-0.5 ${clock >= 80 ? 'bg-amber-900/50 text-amber-200' : 'bg-surface-3'}`}>
                50 coups : {Math.floor(clock / 2)}/50
              </span>
            )}
          </span>
        </div>

        <div className="flex justify-center">
          <div className="boardbox md:w-[min(62vh,560px)]">
            <Board
              fen={viewFen}
              orientation={player}
              interactive={myTurn && live && !busy}
              movableColor={player}
              onMove={handleMove}
              lastMove={lastMove ? { from: lastMove.from, to: lastMove.to } : null}
              arrows={hint && live ? [hint] : []}
              showAttackers={props.showAttackers}
            />
          </div>
        </div>
        {props.showAttackers && <AttackLegend fen={viewFen} className="px-3 pt-1" compact />}
        <div className="min-h-10">
          <MoveStrip
            sans={history.map((m) => m.san)}
            classes={history.map(() => null)}
            currentIndex={live ? history.length - 1 : viewIndex}
            onSelect={(i) => setViewIndex(i === history.length - 1 ? -1 : i)}
            startTurn={player}
          />
        </div>
      </div>

      <div className="flex items-center gap-1 border-t border-black/40 px-1 py-1.5">
        {offered ? (
          <>
            <Action label="Continuer" icon="▶" onClick={() => setDecisive('continued')} />
            <Action label="Recommencer" icon="↺" onClick={restart} />
            <div className="flex-1" />
            <Cta className="mr-1 px-5 py-2 text-base" onClick={conclude}>Conclure</Cta>
          </>
        ) : !end ? (
          <>
            <Action label="Abandonner" icon="🏳" onClick={() => setConfirmResign(true)} />
            {objective !== 'draw' && props.allowDraw !== false && (
              <Action label="Nulle" icon="½" onClick={() => void offerDraw()} disabled={!myTurn || !!busy} />
            )}
            {!thinking && chessRef.current.turn() !== player ? (
              <Action label="Relancer" icon="🤖" onClick={() => void engineMove()} />
            ) : (
              <Action label="Indice" icon="💡" onClick={() => void requestHint()} disabled={!myTurn || !!busy} />
            )}
            <Action label="Annuler" icon="↩" onClick={takeback} disabled={thinking || !!busy || playerMoves === 0} />
            <Action label="Recommencer" icon="↺" onClick={restart} disabled={history.length === 0} />
          </>
        ) : (
          <>
            {boardEndKind && <Action label="Annuler" icon="↩" onClick={takeback} disabled={playerMoves === 0} />}
            <Action label="Analyser" icon="♞" onClick={analyse} disabled={history.length === 0} />
            {props.planButton && <Action label="Plan" icon="💡" onClick={() => setShowPlan(true)} />}
            {onOther && <Action label="Rejouer" icon="↺" onClick={restart} />}
            <div className="flex-1" />
            {onOther ? (
              <Cta className="mr-1 px-5 py-2 text-base" onClick={onOther}>{props.otherLabel ?? 'Autre finale'}</Cta>
            ) : (
              <Cta className="mr-1 px-5 py-2 text-base" onClick={restart}>Rejouer</Cta>
            )}
          </>
        )}
      </div>

      {confirmResign && (
        <ConfirmSheet
          title="Abandonner la partie ?"
          confirmLabel="Abandonner"
          danger
          testId="resign"
          onConfirm={resign}
          onCancel={() => setConfirmResign(false)}
        >
          <p>{objective ? 'La partie sera comptée comme un objectif manqué.' : 'La partie sera perdue.'} Tu pourras la rejouer ou l'analyser ensuite.</p>
        </ConfirmSheet>
      )}
      {showCourse && course && <CourseSheet course={course} onClose={() => setShowCourse(false)} />}
      {showPlan && (
        <EngineContinuation startFen={startFen} playerColor={player} mode="plan" label={title} onClose={() => setShowPlan(false)} />
      )}
    </div>
  )
}

// Action de la barre du bas : icône + libellé, comme le mode entraîneur de Jouer.
function Action({ label, icon, onClick, disabled }: { label: string; icon: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex min-w-0 flex-1 cursor-pointer flex-col items-center gap-0.5 rounded px-0.5 py-1 text-[11px] font-semibold whitespace-nowrap text-neutral-300 hover:text-white disabled:cursor-default disabled:opacity-35"
    >
      <span aria-hidden="true" className="text-xl leading-none">{icon}</span>
      {label}
    </button>
  )
}
