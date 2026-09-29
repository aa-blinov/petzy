import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'antd-mobile/es/global'
import { reduceMotion, restoreMotion, setDefaultConfig } from 'antd-mobile'
import ruRU from 'antd-mobile/es/locales/ru-RU'
// Latin only: Outfit has no Cyrillic (Russian text uses the system face;
// Outfit sets the digits and Latin), and DynaPuff sets only the «Petzy»
// wordmark, at 700.
import '@fontsource/outfit/latin-400.css'
import '@fontsource/outfit/latin-500.css'
import '@fontsource/outfit/latin-600.css'
import '@fontsource/outfit/latin-700.css'
import '@fontsource/dynapuff/latin-700.css'
import './styles/globals.css'
import App from './App.tsx'
import { installAntdA11y } from './utils/antdA11y'
import { installKeyboardWatch } from './utils/keyboard'
import { watchForUpdates } from './utils/swUpdate'
import { initSentry } from './utils/observability'

// antd-mobile ships zh-CN as its default locale, and the app never set
// one — so every string the app didn't pass explicitly rendered in
// Chinese: the pull-to-refresh hint ("下拉刷新"), the infinite-scroll
// footer, Dialog's OK button, Form validation messages, ErrorBlock.
//
// setDefaultConfig rather than <ConfigProvider>: components resolve the
// locale through useConfig(), which falls back to this default, and the
// imperative APIs (Toast.show, Dialog.confirm) render outside the React
// tree and read getDefaultConfig() — a provider would miss those.
setDefaultConfig({ locale: ruRU })

// antd-mobile animates its sheets, dialogs and image viewer with
// react-spring in JS, which the CSS prefers-reduced-motion override can't
// reach — tell the library directly, and follow the OS setting live.
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
const syncMotion = () => (reducedMotion.matches ? reduceMotion() : restoreMotion())
syncMotion()
reducedMotion.addEventListener('change', syncMotion)

installAntdA11y()
installKeyboardWatch()

initSentry()
watchForUpdates()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
