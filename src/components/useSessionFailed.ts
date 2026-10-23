// Séance d'Apprendre demandée depuis un hub (groupe d'Entraînement, Réviser mes parties) et
// impossible à construire : `/apprendre` revient ici avec `state.sessionFailed` (Learn.tsx). Le
// state est lu une fois puis effacé : un rechargement n'affiche plus le message.
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

export function useSessionFailed(): boolean {
  const location = useLocation()
  const navigate = useNavigate()
  const [failed] = useState(() => Boolean((location.state as { sessionFailed?: boolean } | null)?.sessionFailed))
  useEffect(() => {
    if (failed) navigate('.', { replace: true, state: null })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return failed
}
