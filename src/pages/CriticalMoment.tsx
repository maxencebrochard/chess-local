// Un moment critique du bilan rejoué contre Stockfish à pleine force (`/moment-critique`) :
// retrouver le coup du bilan (keyMove, noté dans `learnSessions` domaine 'critical-moment'), puis
// jouer la suite. La sortie rouvre l'analyse sur le même bilan, sans le recalculer.
import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import type { BilanBack, MomentTarget } from '../components/CriticalMoments'
import { PositionGame } from '../components/PositionGame'
import { recordReplaced } from '../lib/attempts'
import { ANSWER_LABEL, recordMomentMove } from '../lib/criticalMoments'
import { loadStoredGame, validFen } from '../lib/positionGame'
import { figurine } from '../lib/review'
import { useSettings } from '../store/settings'

const KEY = 'moment'

// Gardé avec la partie persistée (`back` de PositionGame) : rechargement et retour de l'analyse.
interface MomentBack {
  moment: MomentTarget
  analysis: BilanBack
}

function isMomentBack(v: unknown): v is MomentBack {
  const b = v as MomentBack | null
  return !!b && typeof b.moment?.fen === 'string' && typeof b.moment.bestUci === 'string' && typeof b.analysis?.pgn === 'string'
}

export default function CriticalMoment() {
  const navigate = useNavigate()
  const location = useLocation()
  const { showAttackers } = useSettings()
  // Moment reçu du bilan (nouvelle tentative), sinon la partie persistée de ce moment
  // (rechargement, retour de l'analyse après « Analyser »).
  const [source] = useState(() => {
    const st = location.state as { moment?: MomentTarget; back?: BilanBack } | null
    if (st?.moment) {
      const back = { moment: st.moment, analysis: st.back }
      return isMomentBack(back) && validFen(back.moment.fen) ? { back, fresh: true } : ('invalid' as const)
    }
    const stored = loadStoredGame()
    if (stored?.key === KEY && isMomentBack(stored.back) && stored.back.moment.fen === stored.startFen) {
      return { back: stored.back, fresh: false }
    }
    return null
  })

  if (!source || source === 'invalid') {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 p-6 text-center">
        <p data-testid="moment-missing" className="text-neutral-300">
          {source ? 'Ce moment ne peut pas être rejoué (position illégale).' : 'Aucun moment critique à rejouer.'}
        </p>
        <p className="text-sm text-neutral-400">
          Lance le bilan d'une partie dans l'analyse : ses moments critiques s'affichent en bas du résumé.
        </p>
        <Link to="/analyse" replace className="rounded-lg bg-surface-3 px-4 py-2 font-semibold hover:bg-surface-3/70">
          Aller à l'analyse
        </Link>
      </div>
    )
  }

  const { moment, analysis } = source.back
  const color = moment.fen.split(' ')[1] === 'b' ? 'b' : 'w'
  const played = figurine(moment.playedSan, color)
  const exit = () => navigate('/analyse', { replace: true, state: analysis })
  return (
    <PositionGame
      gameKey={KEY}
      startFen={moment.fen}
      title={`Moment critique · coup ${moment.moveNo}`}
      objective={null}
      objectiveLabel="Objectif : trouve le bon coup"
      goalHint={moment.found ? 'Pendant la partie, le seul coup qui tenait a été trouvé : retrouve-le.' : `Au bilan, ${played} a fait basculer la partie : trouve mieux.`}
      lesson={`${ANSWER_LABEL[moment.answer]}. ${moment.explanation}`}
      resume={!source.fresh}
      restoreFinished={!source.fresh}
      returnTo="/moment-critique"
      returnLabel="Retour au moment critique"
      back={source.back}
      showAttackers={showAttackers}
      onReplace={recordReplaced}
      onPersisted={() => {
        if (location.state) navigate('.', { replace: true, state: null })
      }}
      keyMove={{ uci: moment.bestUci, san: moment.bestSan, followUp: 'Joue la suite', onJudged: (found) => void recordMomentMove(moment.fen, moment.answer, found) }}
      otherLabel="Retour au bilan"
      onExit={exit}
      onOther={exit}
    />
  )
}
