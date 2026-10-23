// Interrupteur des réglages (page Réglages, écran de configuration de Jouer), style chess.com.
// Les classes `h-6 w-11` sont repérées par les suites E2E : ne pas les changer.
// Toute la ligne (libellé compris, 44 px de haut) est la cible tactile : le pseudo-élément du
// bouton la recouvre, comme une ligne de réglage iOS.
interface ToggleProps {
  label: string
  value: boolean
  onChange: (v: boolean) => void
  testId?: string
}

export function Toggle({ label, value, onChange, testId }: ToggleProps) {
  return (
    <div className="relative flex min-h-11 items-center justify-between gap-3">
      <span className="text-sm text-neutral-300">{label}</span>
      <button
        role="switch"
        aria-checked={value}
        aria-label={label}
        data-testid={testId}
        onClick={() => onChange(!value)}
        className={`h-6 w-11 shrink-0 cursor-pointer rounded-full p-0.5 transition after:absolute after:inset-0 after:content-[''] ${value ? 'bg-accent' : 'bg-surface-3'}`}
      >
        <div className={`h-5 w-5 rounded-full bg-white transition ${value ? 'translate-x-5' : ''}`} />
      </button>
    </div>
  )
}
