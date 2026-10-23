// Ce que l'accueil affiche après son premier rendu et qui tire des modules lourds : compteur de
// révision (revision.ts tire l'entraîneur d'ouvertures et ses 470 Ko d'ouvertures) et progression du
// parcours (learningPath.ts tire les cours bundlés). Home l'importe dynamiquement, en une seule
// chunk à charger : l'accueil s'affiche sans attendre ces données.
export { describeKinds, loadReviewQueue } from './revision'
export { computePath, EMPTY_FACTS } from './learningPath'
export { loadPathFacts } from './learningPathStore'
