import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router-dom'

// `aside` : élément non interactif aligné à droite (compteur, pastille), après le texte.
// `iconWidth` : icône dans une colonne fixe, pour aligner les titres d'une liste d'emojis et de glyphes.
type Content = { title: ReactNode; description?: ReactNode; icon?: ReactNode; children?: ReactNode; aside?: ReactNode; iconWidth?: boolean }
type Props = Content & (
  | (Omit<LinkProps, 'title' | 'children'> & { onClick?: never })
  | (Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'title' | 'children'> & { to?: never })
)

// Une seule racine interactive ; la progression et l'icône restent non interactives.
export function ActivityCard({ title, description, icon, children, aside, iconWidth, className = '', ...props }: Props) {
  const content = <>
    {icon && <span className={`shrink-0 text-2xl ${iconWidth ? 'w-8 text-center' : ''}`} aria-hidden="true">{icon}</span>}
    <span className="min-w-0 flex-1">
      <span className="ui-card-title block text-base leading-snug font-semibold wrap-break-word">{title}</span>
      {description && <span className="ui-card-description mt-1 block text-sm leading-snug text-muted">{description}</span>}
      {children}
    </span>
    {aside}
  </>
  const classes = `ui-card flex min-h-11 min-w-0 cursor-pointer items-center gap-3 rounded-xl bg-surface-2 p-3 text-left transition hover:bg-surface-3 disabled:cursor-default disabled:opacity-40 ${className}`
  if ('to' in props && props.to !== undefined) {
    return <Link {...props as LinkProps} className={classes}>{content}</Link>
  }
  return <button type="button" {...props as ButtonHTMLAttributes<HTMLButtonElement>} className={classes}>{content}</button>
}
