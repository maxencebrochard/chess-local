// Section « Moments critiques » du résumé du bilan : les positions où la partie a basculé
// (lib/criticalMoments.ts). Pour chacune, une question avant de rejouer (« Plan, menace ou coup
// forcé ? »), la bonne réponse justifiée, puis la position rejouée contre Stockfish
// (`/moment-critique`), le bilan se rouvrant au retour sans être recalculé.
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Board } from './Board'
import { ClassIcon } from './ClassIcon'
import { Cta } from './Cta'
import {
  ANSWER_LABEL, ANSWER_RULE, ANSWERS, criticalMoments, momentExplanation, momentHistory, momentState, recordMomentAnswer,
  type CriticalMoment, type MomentAnswer, type MomentHistory,
} from '../lib/criticalMoments'
import { figurine, type GameReview } from '../lib/review'

interface CriticalMomentsProps {
  review: GameReview
  playerColor: 'w' | 'b' | null
  names: { w: string; b: string }
  label: string | null
  gameKey: string | null
  returnTo: string | null
  returnLabel: string
}

// Types du state de `/moment-critique`, construits par `momentState` (lib/criticalMoments.ts).
export type { BilanBack, MomentTarget } from '../lib/criticalMoments'

export function CriticalMoments(props: CriticalMomentsProps) {
  const { review, playerColor } = props
  const navigate = useNavigate()
  const moments = useMemo(() => criticalMoments(review, playerColor), [review, playerColor])
  const [history, setHistory] = useState<Map<string, MomentHistory>>(new Map())

  useEffect(() => {
    let alive = true
    void momentHistory(moments.map((m) => m.fen)).then((h) => alive && setHistory(h))
    return () => {
      alive = false
    }
  }, [moments])

  function answer(m: CriticalMoment, chosen: MomentAnswer) {
    setHistory((h) => new Map(h).set(m.fen, { chosen, move: h.get(m.fen)?.move ?? null }))
    void recordMomentAnswer(m.fen, m.answer, chosen)
  }

  function replay(m: CriticalMoment) {
    const state = momentState(review, m, props)
    // `replace` : l'analyse ne garde pas son state ; un retour arrière ramènerait une analyse vide.
    navigate('/moment-critique', { replace: true, state })
  }

  // Analyse ouverte depuis un moment rejoué : pas de moments imbriqués, qui écraseraient la
  // partie persistée du moment et son retour au bilan d'origine.
  if (props.returnTo === '/moment-critique') return null

  return (
    <section data-testid="critical-moments" className="space-y-3 border-t border-white/10 pt-3">
      <div>
        <h2 className="text-lg font-black">Moments critiques</h2>
        <p className="text-sm text-neutral-400">
          {moments.length
            ? "Les positions où la partie a basculé. Devine ce qu'elles demandaient, puis rejoue-les."
            : "La partie n'a pas basculé sur un coup : rien à rejouer."}
        </p>
      </div>
      {moments.map((m) => (
        <MomentCard
          key={m.index}
          moment={m}
          mine={playerColor !== null}
          history={history.get(m.fen) ?? null}
          onAnswer={(a) => answer(m, a)}
          onReplay={() => replay(m)}
        />
      ))}
    </section>
  )
}

interface MomentCardProps {
  moment: CriticalMoment
  mine: boolean // camp du joueur connu : « tu as joué »
  history: MomentHistory | null
  onAnswer: (a: MomentAnswer) => void
  onReplay: () => void
}

function MomentCard({ moment: m, mine, history, onAnswer, onReplay }: MomentCardProps) {
  const chosen = history?.chosen ?? null
  const fig = (san: string) => figurine(san, m.color)
  const side = m.color === 'w' ? 'Blancs' : 'Noirs'
  const played = mine ? 'tu as joué' : `les ${side} ont joué`
  const arrow = !m.found ? [{ startSquare: m.playedUci.slice(0, 2), endSquare: m.playedUci.slice(2, 4), color: '#ca3431' }] : undefined

  return (
    <div
      data-testid="critical-moment"
      data-index={m.index}
      data-fen={m.fen}
      data-best={m.bestUci}
      data-answer={m.answer}
      data-gap={m.winSecond === null ? '' : (m.winBefore - m.winSecond).toFixed(1)}
      data-threat={m.threat?.kind ?? ''}
      className="rounded-xl bg-surface-2 p-3"
    >
      <div className="flex gap-3">
        <div className="w-28 shrink-0 overflow-hidden rounded-md">
          <Board fen={m.fen} orientation={m.color} interactive={false} arrows={arrow} silent notation={false} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-bold">Coup {m.moveNo}</span>
            {history?.move === 'found' && (
              <span data-testid="moment-status" className="ml-auto text-sm font-bold text-accent">✓ Retrouvé</span>
            )}
            {history?.move === 'missed' && (
              <span data-testid="moment-status" className="ml-auto text-sm font-bold text-red-300">✗ Manqué</span>
            )}
          </div>
          {m.found ? (
            // Coup unique trouvé pendant la partie : le coup n'est pas montré, il reste à retrouver.
            <p className="mt-1 text-sm text-neutral-300">
              {mine ? 'Tu as trouvé' : `Les ${side} ont trouvé`} le seul coup qui tenait.
            </p>
          ) : (
            <>
              <p className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm text-neutral-300">
                <span>{played}</span>
                <span className="font-semibold text-neutral-100">{fig(m.playedSan)}</span>
                <ClassIcon cls={m.cls} size={18} />
              </p>
              <p className="mt-1 text-sm text-neutral-400">
                Chances de gain : {Math.round(m.winBefore)} % → {Math.round(m.winBefore - m.drop)} %
              </p>
            </>
          )}
        </div>
      </div>

      {chosen === null ? (
        <div className="mt-3">
          <p className="mb-2 text-[15px] font-semibold text-neutral-100">Plan, menace ou coup forcé ?</p>
          <div className="grid grid-cols-3 gap-2">
            {ANSWERS.map((a) => (
              <button
                key={a}
                data-testid="moment-choice"
                data-choice={a}
                onClick={() => onAnswer(a)}
                className="min-h-11 cursor-pointer rounded-lg bg-surface-3 px-2 text-sm font-bold text-neutral-100 hover:bg-surface-3/70"
              >
                {ANSWER_LABEL[a]}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="mt-3 space-y-3">
          <div data-testid="moment-verdict" data-correct={chosen === m.answer ? '1' : '0'} className="rounded-lg bg-surface-3/60 px-3 py-2 text-sm">
            <p className={`font-bold ${chosen === m.answer ? 'text-accent' : 'text-amber-300'}`}>
              {chosen === m.answer ? `Bien vu : ${ANSWER_LABEL[m.answer].toLowerCase()}.` : `Pas tout à fait : ${ANSWER_LABEL[m.answer].toLowerCase()}.`}
            </p>
            <p className="mt-1 text-neutral-200">{momentExplanation(m)}</p>
            <p className="mt-1 text-xs text-neutral-400">{ANSWER_RULE}</p>
          </div>
          <Cta data-testid="moment-replay" className="w-full !py-2.5 !text-base" onClick={onReplay}>
            {history?.move ? 'Rejouer encore' : 'Rejouer la position'}
          </Cta>
        </div>
      )}
    </div>
  )
}
