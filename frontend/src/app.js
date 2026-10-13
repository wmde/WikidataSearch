import './styles.css'
import { renderHome } from './pages/home.js'
import { renderSearch } from './pages/search.js'
import { renderUseCases } from './pages/use-cases.js'

const root = document.querySelector('#app')
let cleanupCurrentPage = null

function navigate(target, { replace = false, render = true, scroll = true } = {}) {
  const url = new URL(target, window.location.origin)
  const current = `${window.location.pathname}${window.location.search}`
  const next = `${url.pathname}${url.search}`

  if (current !== next) {
    window.history[replace ? 'replaceState' : 'pushState']({}, '', next)
  }
  if (render) renderRoute()
  if (scroll) window.scrollTo({ top: 0, behavior: 'auto' })
}

function renderRoute() {
  cleanupCurrentPage?.()
  cleanupCurrentPage = null

  const path = window.location.pathname.replace(/\/+$/, '') || '/'
  const context = { navigate }

  if (path === '/') {
    cleanupCurrentPage = renderHome(root, context)
  } else if (path === '/search') {
    cleanupCurrentPage = renderSearch(root, context)
  } else if (path === '/use-cases') {
    cleanupCurrentPage = renderUseCases(root, context)
  } else {
    navigate('/', { replace: true })
  }
}

window.addEventListener('popstate', renderRoute)
renderRoute()
