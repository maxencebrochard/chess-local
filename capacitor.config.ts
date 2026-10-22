import type { CapacitorConfig } from '@capacitor/cli'

// Coquille iOS de la PWA (docs/ios-app.md) : la même app web, empaquetée depuis `dist/`.
// `npm run ios:sync` construit le web puis le copie dans ios/App/App/public.
const config: CapacitorConfig = {
  appId: 'io.github.maxencebrochard.chesslocal',
  appName: 'ChessLocal',
  webDir: 'dist',
  // Fond de l'app (theme_color du manifeste) : pas d'éclair blanc au lancement ni au défilement.
  backgroundColor: '#262421',
  ios: {
    // Les safe areas restent gérées par la page (viewport-fit=cover, pt-safe/pb-safe), comme en PWA.
    contentInset: 'never',
    // Appui long sur une pièce : pas d'aperçu de lien ni de menu WebKit pendant un glissé.
    allowsLinkPreview: false,
  },
  plugins: {
    // Texte clair sur le fond sombre : le plugin cœur SystemBars applique son style au démarrage et
    // écraserait sinon UIStatusBarStyle d'Info.plist (DARK = contenu clair).
    SystemBars: { style: 'DARK' },
  },
}

export default config
