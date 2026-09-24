import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'antd-mobile/es/global'
import { reduceMotion, restoreMotion, setDefaultConfig } from 'antd-mobile'
import ruRU from 'antd-mobile/es/locales/ru-RU'
import './styles/globals.css'
import App from './App.tsx'

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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
