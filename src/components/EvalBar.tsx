// Barre d'évaluation verticale, point de vue blanc (blanc en bas si orientation blanche).
interface EvalBarProps {
  cp: number | null // centipawns point de vue blanc
  mate: number | null // point de vue blanc, 0 = mat sur l'échiquier
  orientation: 'w' | 'b'
}

export function EvalBar({ cp, mate, orientation }: EvalBarProps) {
  let whiteShare: number
  let label: string
  if (mate !== null) {
    whiteShare = mate === 0 ? (cp && cp > 0 ? 100 : 0) : mate > 0 ? 100 : 0
    label = mate === 0 ? '#' : `M${Math.abs(mate)}`
  } else if (cp === null) {
    whiteShare = 50
    label = ''
  } else {
    // Sigmoïde douce : ±400cp ≈ 90/10.
    whiteShare = 100 / (1 + Math.exp(-cp / 190))
    label = (Math.abs(cp) / 100).toFixed(1).replace('.', ',')
  }
  const topIsWhite = orientation === 'b'
  const topShare = topIsWhite ? whiteShare : 100 - whiteShare
  const labelOnWhite = mate !== null ? mate >= 0 : (cp ?? 0) >= 0

  return (
    <div className="relative h-full w-6 overflow-hidden rounded bg-neutral-800" title={label}>
      <div
        className="absolute inset-x-0 top-0 transition-all duration-300"
        style={{ height: `${topShare}%`, background: topIsWhite ? '#f8f8f8' : '#403d39' }}
      />
      <div
        className="absolute inset-x-0 bottom-0 transition-all duration-300"
        style={{ height: `${100 - topShare}%`, background: topIsWhite ? '#403d39' : '#f8f8f8' }}
      />
      <span
        className={`absolute inset-x-0 text-center text-[9px] font-bold ${
          labelOnWhite ? 'text-neutral-800' : 'text-neutral-100'
        }`}
        style={labelOnWhite === topIsWhite ? { top: 2 } : { bottom: 2 }}
      >
        {label}
      </span>
    </div>
  )
}
