const iconPaths = {
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  bolt: '<path d="m13 2-9 12h7l-1 8 9-12h-7l1-8Z"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  clipboard: '<rect x="5" y="5" width="14" height="16" rx="2"/><path d="M9 5V3h6v2"/>',
  code: '<path d="m8 9-3 3 3 3m8-6 3 3-3 3m-5 3 2-12"/>',
  copy: '<rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
  document: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6m-6 4h6"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M5 21h14"/>',
  external: '<path d="M14 3h7v7m0-7-10 10"/><path d="M18 13v7H4V6h7"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.2 2.5 3.3 5.5 3.3 9S14.2 18.5 12 21c-2.2-2.5-3.3-5.5-3.3-9S9.8 5.5 12 3Z"/>',
  layers: '<path d="m12 3-9 5 9 5 9-5-9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.2 1.2"/><path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.2-1.2"/>',
  nodes: '<circle cx="12" cy="5" r="2.5"/><circle cx="5" cy="18" r="2.5"/><circle cx="19" cy="18" r="2.5"/><path d="m10.8 7.2-4.6 8.6m7-8.6 4.6 8.6M7.5 18h9"/>',
  ranking: '<path d="M4 20v-5h4v5M10 20V10h4v10M16 20V5h4v15"/><path d="m4 10 5-5 4 3 6-6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  send: '<path d="m22 2-7 20-4-9-9-4 20-7Z"/><path d="M22 2 11 13"/>',
  thumbsDown: '<path d="M7 3H3v11h4m0-11h10l2 2v6l-4 7h-3l1-4H7V3Z"/>',
  thumbsUp: '<path d="M7 21H3V10h4m0 11h10l2-2v-6l-4-7h-3l1 4H7v11Z"/>',
  translate: '<path d="M4 5h8M8 3v2m3 0c-1 4-4 7-7 8m2-5c1 2 3 4 6 5m2-6h3l4 14m-2-5h-7"/>',
}

export function icon(name, className = '') {
  const paths = iconPaths[name] || iconPaths.search
  return `<svg class="icon ${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`
}

export function escapeHtml(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

export function header(active = 'start') {
  const navItem = (path, label, key) => `
    <a class="site-nav__link ${active === key ? 'is-active' : ''}" href="${path}" data-route>
      ${label}
    </a>`

  return `
    <header class="site-header">
      <div class="site-header__inner">
        <a class="brand" href="/" data-route aria-label="Wikidata Vector Database home">
          <img class="brand__logo" src="/assets/wikidata-vector-logo.png" alt="" width="32" height="35" />
          <span class="brand__copy">
            <strong>Wikidata Vector Database</strong>
            <span>Semantic search across millions of Wikidata entities</span>
          </span>
        </a>
        <nav class="site-nav" aria-label="Primary navigation">
          ${navItem('/', 'Start', 'start')}
          ${navItem('/search', 'Search', 'search')}
          ${navItem('/use-cases', 'Use Cases', 'use-cases')}
        </nav>
      </div>
    </header>`
}

export function searchBar(value = '', inputId = 'search-query') {
  return `
    <form class="search-bar" data-search-form role="search">
      ${icon('search', 'search-bar__leading')}
      <label class="sr-only" for="${inputId}">Search Wikidata</label>
      <input id="${inputId}" name="q" value="${escapeHtml(value)}" placeholder="Start typing to see suggestions…" autocomplete="off" />
      <button class="button button--primary search-bar__button" type="submit">
        ${icon('search')}<span>Search</span>
      </button>
    </form>`
}

export function wikidataUrl(id) {
  const path = String(id).startsWith('P') ? `Property:${id}` : id
  return `https://www.wikidata.org/wiki/${encodeURIComponent(path)}`
}

export function bindInternalLinks(container, navigate) {
  container.querySelectorAll('[data-route]').forEach((link) => {
    link.addEventListener('click', (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
      event.preventDefault()
      navigate(link.getAttribute('href'))
    })
  })
}
