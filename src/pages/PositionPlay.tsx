// « Jouer contre le moteur » depuis l'analyse (`/analyse/jouer`), comme « Jouer contre
// l'ordinateur depuis la position » de chess.com : la position affichée devient une partie
// contre Stockfish à pleine force, le joueur prenant le camp au trait. Sans objectif.
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { PositionGame } from '../components/PositionGame'
import { loadStoredGame, validFen } from '../lib/positionGame'

const KEY = 'position'

export default function PositionPlay() {
  const navigate = useNavigate()
  const location = useLocation()
  // Position reçue de l'analyse (nouvelle partie), sinon la dernière partie libre persistée
  // (rechargement, retour de l'analyse après « Analyser »).
  const [source] = useState(() => {
    const st = location.state as { fen?: string; label?: string | null; back?: unknown } | null
    if (st?.fen) return validFen(st.fen) ? { fen: st.fen, label: st.label ?? null, back: st.back, fresh: true } : ('invalid' as const)
    const stored = loadStoredGame()
    if (stored?.key === KEY) return { fen: stored.startFen, label: stored.label, back: stored.back, fresh: false }
    return null
  })

  // State consommé : un rechargement reprend la partie persistée au lieu d'en recommencer une.
  useEffect(() => {
    if (location.state) navigate('.', { replace: true, state: null })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!source || source === 'invalid') {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 p-6 text-center">
        <p className="text-neutral-300">{source ? 'Cette position ne peut pas être jouée (position illégale).' : 'Aucune position à jouer.'}</p>
        <p className="text-sm text-neutral-400">
          Dans l'analyse, ouvre les options puis « Jouer contre le moteur » pour affronter Stockfish depuis la position affichée.
        </p>
        <Link to="/analyse" replace className="rounded-lg bg-surface-3 px-4 py-2 font-semibold hover:bg-surface-3/70">
          Aller à l'analyse
        </Link>
      </div>
    )
  }

  return (
    <PositionGame
      gameKey={KEY}
      startFen={source.fen}
      title={source.label ?? 'Contre Stockfish'}
      objective={null}
      resume={!source.fresh}
      restoreFinished={!source.fresh}
      returnTo="/analyse/jouer"
      returnLabel="Retour à la partie"
      back={source.back}
      // Retour à l'analyse d'origine, rouverte depuis son state (elle ne persiste rien).
      onExit={() => navigate('/analyse', { replace: true, state: source.back ?? null })}
    />
  )
}
