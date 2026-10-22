// Réponse d'un asset local de l'app (`public/`, même origine) jugée exploitable.
// Dans la coquille iOS, le gestionnaire du schéma capacitor:// répond avec un statut 0 au lieu de 200 :
// un fetch de même origine qui aboutit ne peut pas être opaque, donc 0 y signifie « servi ».
// Un vrai 404 garde son statut et reste refusé, comme une page HTML servie à la place du fichier.
export function assetResponseOk(res: Response): boolean {
  return res.ok || (res.status === 0 && res.type !== 'opaque')
}
