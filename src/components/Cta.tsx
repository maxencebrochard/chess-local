// Boutons du design system, style chess.com : CTA vert massif arrondi,
// secondaire gris. Utilisés sur toutes les pages.
interface CtaProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary'
}

export function Cta({ variant = 'primary', className = '', children, ...rest }: CtaProps) {
  const base =
    variant === 'primary'
      ? 'bg-accent text-white shadow-[0_4px_0_#5d9948] hover:bg-accent-hover active:translate-y-0.5 active:shadow-[0_2px_0_#5d9948]'
      : 'bg-surface-3 text-neutral-200 shadow-[0_4px_0_rgba(0,0,0,0.35)] hover:bg-surface-3/80 active:translate-y-0.5 active:shadow-[0_2px_0_rgba(0,0,0,0.35)]'
  return (
    <button
      {...rest}
      className={`cursor-pointer rounded-xl px-5 py-3 text-lg font-black transition disabled:cursor-default disabled:opacity-40 ${base} ${className}`}
    >
      {children}
    </button>
  )
}
