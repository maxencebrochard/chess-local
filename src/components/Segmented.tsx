// Contrôle segmenté (camp, longueur, cadence) partagé par l'entraîneur d'ouvertures et Mon répertoire.
export function Segmented<T extends string>({ label, options, value, onChange }: {
  label: string
  options: { id: T; label: string }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-[4.5rem] shrink-0 text-sm font-semibold text-neutral-400">{label}</span>
      <div role="group" aria-label={label} className="flex min-w-0 flex-1 gap-1 rounded-lg bg-surface-2 p-1">
        {options.map((o) => (
          <button
            key={o.id}
            onClick={() => onChange(o.id)}
            aria-pressed={value === o.id}
            className={`flex-1 cursor-pointer rounded-md px-1 py-1.5 text-[13px] font-bold whitespace-nowrap ${value === o.id ? 'bg-surface-3 text-white shadow' : 'text-neutral-400 hover:text-white'}`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}
