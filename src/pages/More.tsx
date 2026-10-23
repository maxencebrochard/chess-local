import { ActivityCard } from '../components/ActivityCard'
import { NavIcon } from '../components/NavIcon'
import { PageHeader } from '../components/PageHeader'
import { PLUS_GROUPS } from '../lib/navigation'

// Hub de l'onglet Plus : tes parties, les outils et tes données. Racine d'onglet, donc sans retour ;
// ses liens sont des descentes empilées (le retour arrière ramène ici).
export default function More() {
  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader title="Plus" description="Tes parties, l’analyse, ta progression et tes réglages." />
      {PLUS_GROUPS.map((g) => (
        <section key={g.title} aria-labelledby={`plus-${g.items[0].icon}`} className="mb-6 last:mb-0">
          <h2 id={`plus-${g.items[0].icon}`} className="mb-2 text-lg font-semibold">{g.title}</h2>
          <div className="grid gap-2">
            {g.items.map((d) => (
              <ActivityCard
                key={d.label}
                to={d.to}
                state={d.section ? { section: d.section } : undefined}
                data-plus={d.icon}
                icon={<NavIcon name={d.icon} className="h-6 w-6 text-accent" />}
                title={d.label}
                description={d.description}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
