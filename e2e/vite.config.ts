import { mergeConfig } from 'vite'
import config from '../vite.config'

// Les E2E de développement gardent StrictMode, mais un journal ou une documentation modifiée
// pendant la campagne ne doit pas recharger les pages en plein geste.
export default mergeConfig(config, { server: { watch: null, hmr: false } })
