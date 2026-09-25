// Frontière d'erreur de la coquille : une exception de rendu dans une page ne doit plus
// vider tout l'écran (PWA à tuer sur iPhone). Les nav restent hors frontière, donc
// utilisables ; un changement de route (`resetKey`) réarme la frontière.
import { Component, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Cta } from './Cta'

interface Props {
  /** Clé de réinitialisation : quand elle change, l'erreur est oubliée et les enfants re-rendus. */
  resetKey: string
  children: ReactNode
}

interface State {
  error: Error | null
  resetKey: string
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, resetKey: this.props.resetKey }

  // Pas de `console.error` manuel : React 19 logue déjà toute erreur attrapée par une
  // frontière (en prod comme en dev), un log de plus doublerait la pile.
  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error }
  }

  // Réinitialisation dérivée des props (pas de `componentDidUpdate` + `setState`, qui
  // afficherait une fois le secours avec l'ancienne erreur avant de re-rendre).
  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    if (props.resetKey !== state.resetKey) return { error: null, resetKey: props.resetKey }
    return null
  }

  render() {
    if (this.state.error) {
      return <Fallback error={this.state.error} onReset={() => this.setState({ error: null })} />
    }
    return this.props.children
  }
}

// Écran de secours. Composant fonction séparé : le bouton a besoin de `useNavigate`.
function Fallback({ error, onReset }: { error: Error; onReset: () => void }) {
  const navigate = useNavigate()
  return (
    <div className="mx-auto flex h-full max-w-md flex-col justify-center gap-4 p-6">
      <div className="text-4xl" aria-hidden="true">
        ⚠️
      </div>
      <h1 className="text-2xl font-bold">Oups</h1>
      <p role="alert" className="text-neutral-300">
        Cette page a rencontré un problème. Tes parties enregistrées, classements et progrès ne sont pas touchés.
      </p>
      <div className="flex flex-col gap-3">
        {/* Reset explicite AVANT de naviguer : un crash sur l'accueil lui-même ne se relèverait pas sinon. */}
        <Cta
          onClick={() => {
            onReset()
            navigate('/', { replace: true })
          }}
        >
          Revenir à l'accueil
        </Cta>
        <Cta variant="secondary" onClick={() => location.reload()}>
          Recharger
        </Cta>
      </div>
      <details className="text-xs text-neutral-500">
        <summary className="cursor-pointer">Détail technique</summary>
        <pre className="mt-2 whitespace-pre-wrap break-words">{error.message}</pre>
      </details>
    </div>
  )
}
