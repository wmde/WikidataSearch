import {
  enrichEntities,
  findItemConnections,
  findItemPropertyMatches,
  getItemInstanceOf,
  getLanguages,
  getPropertyDatatypes,
  searchEntities,
  sendFeedback,
} from '../api.js'
import { bindInternalLinks, escapeHtml, header, icon, searchBar, wikidataUrl } from '../components.js'
import { vectorMapMarkup } from '../vector-view.js'

function formatSimilarity(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return null
  const percent = Math.abs(number) <= 1.2 ? number * 100 : number
  return Math.max(0, Math.min(100, percent))
}

function scoreClass(score, useReranker) {
  if (score === null) return 'score--unavailable'
  const highThreshold = useReranker ? 75 : 80
  const mediumThreshold = useReranker ? 50 : 70
  if (score >= highThreshold) return 'score--high'
  if (score >= mediumThreshold) return 'score--medium'
  return 'score--low'
}

function headingQuery(query, maxLength = 48) {
  if (query.length <= maxLength) return query
  const shortened = query.slice(0, maxLength).trimEnd()
  const lastSpace = shortened.lastIndexOf(' ')
  const wordSafe = lastSpace >= Math.floor(maxLength * 0.65)
    ? shortened.slice(0, lastSpace)
    : shortened
  return `${wordSafe} ...`
}

function resultsTitle(query) {
  return `<h1 title="${escapeHtml(query)}">Results for “${escapeHtml(headingQuery(query))}”</h1>`
}

function resultCard(result, index, useReranker, relatedType, vectorDetailType = null) {
  const score = formatSimilarity(useReranker ? result.reranker_score : result.similarity_score)
  const scoreLabel = score === null ? 'Not available' : `${score.toFixed(score % 1 ? 1 : 0)}%`
  const scoreName = useReranker ? 'Reranker' : 'Similarity'
  const relatedTitle = vectorDetailType === 'instanceOf'
    ? 'Instance of'
    : vectorDetailType === 'datatype'
      ? 'Datatype'
      : relatedType === 'property'
        ? 'Search-matched properties'
        : 'Search-matched items'
  const loadingLabel = vectorDetailType === 'instanceOf'
    ? 'Loading instance of values…'
    : vectorDetailType === 'datatype'
      ? 'Loading datatype…'
      : relatedType === 'property'
        ? 'Finding matching properties…'
        : 'Finding matching items…'
  const connectedResults = vectorDetailType === 'instanceOf'
    ? `<div class="result-card__connections" data-connected-results="${index}" hidden></div>`
    : ''

  return `
    <article id="result-${escapeHtml(result.id)}" class="result-card" data-result-index="${index}">
      <div class="result-card__heading">
        <h3><a href="${wikidataUrl(result.id)}" target="_blank" rel="noreferrer">${escapeHtml(result.label)}</a> <span>(${escapeHtml(result.id)})</span></h3>
        <span class="score ${scoreClass(score, useReranker)}">${scoreName}: ${scoreLabel}</span>
      </div>
      <p class="result-card__description">${escapeHtml(result.description)}</p>
      <div class="result-card__relations">
        <span class="result-card__relations-icon">${icon('nodes')}</span>
        <div>
          <p>${relatedTitle}</p>
          <div class="related-results" data-related-results="${index}" aria-live="polite">
            <span class="related-loading"><span class="loading-spinner" aria-hidden="true"></span>${loadingLabel}</span>
          </div>
          ${connectedResults}
        </div>
      </div>
      <div class="result-card__footer">
        <div class="feedback" data-feedback>
          <button type="button" aria-label="Mark result helpful" title="Helpful" data-sentiment="up">${icon('thumbsUp')}</button>
          <button type="button" aria-label="Mark result not helpful" title="Not helpful" data-sentiment="down">${icon('thumbsDown')}</button>
          <span>Was this result helpful?</span>
        </div>
        <a href="${wikidataUrl(result.id)}" target="_blank" rel="noreferrer">View on Wikidata ${icon('external')}</a>
      </div>
    </article>`
}

function loadingCards() {
  return Array.from({ length: 3 }, () => `
    <div class="result-card result-card--loading" aria-hidden="true">
      <span></span><span></span><span></span>
    </div>`).join('')
}

function relatedEntitiesMarkup(entities, relatedType, primaryId) {
  if (!entities.length) {
    return `<span class="related-empty">No matching ${relatedType === 'property' ? 'properties' : 'items'} found.</span>`
  }

  return `<div class="related-chips">${entities.map((entity) => {
    const itemId = relatedType === 'property' ? primaryId : entity.id
    const propertyId = relatedType === 'property' ? entity.id : primaryId
    return `
      <a class="related-chip" href="${wikidataUrl(itemId)}#${propertyId}" target="_blank" rel="noreferrer">
        ${escapeHtml(entity.label)} <span>${escapeHtml(entity.id)}</span>
      </a>`
  }).join('')}</div>`
}

function instanceOfMarkup(instances) {
  if (!instances.length) {
    return '<span class="related-empty">No instance of values found.</span>'
  }

  return `<div class="related-chips">${instances.map((instance) => `
    <a class="related-chip" href="${wikidataUrl(instance.id)}" target="_blank" rel="noreferrer">
      ${escapeHtml(instance.label || instance.id)} <span>${escapeHtml(instance.id)}</span>
    </a>`).join('')}</div>`
}

function datatypeMarkup(datatypes) {
  if (!datatypes.length) {
    return '<span class="related-empty">No datatype is available.</span>'
  }

  return `<div class="related-chips">${datatypes.map((datatype) => `
    <span class="related-chip">${escapeHtml(datatype.label || datatype.id)}</span>`).join('')}</div>`
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const area = document.createElement('textarea')
  area.value = text
  area.style.position = 'fixed'
  area.style.opacity = '0'
  document.body.append(area)
  area.select()
  document.execCommand('copy')
  area.remove()
}

export function renderSearch(root, { navigate }) {
  const pageUrl = new URL(window.location.href)
  const pageParams = pageUrl.searchParams
  const query = pageParams.get('q') || ''
  const initialType = pageParams.get('type') === 'property' ? 'property' : 'item'
  const initialLanguage = pageParams.get('lang') || 'all'
  const initialScope = ['with_sitelinks', 'no_sitelinks', 'all'].includes(pageParams.get('scope'))
    ? pageParams.get('scope')
    : 'with_sitelinks'
  const requestedLimit = Number(pageParams.get('limit'))
  const initialLimit = pageParams.has('limit') && Number.isFinite(requestedLimit)
    ? String(Math.min(50, Math.max(1, Math.round(requestedLimit))))
    : '50'
  const initialRerank = pageParams.has('rerank') ? pageParams.get('rerank') === 'true' : true
  const initialExcludeExternalIds = pageParams.has('exclude_external_ids')
    ? pageParams.get('exclude_external_ids') === 'true'
    : true
  const initialView = pageParams.get('view') === 'vector' ? 'vector' : 'list'
  document.title = query ? `${query} · Wikidata Vector Search` : 'Search · Wikidata Vector Database'

  let results = []
  let resultOptions = null
  let activeController = new AbortController()
  const languagesController = new AbortController()
  let currentQuery = query
  let viewMode = initialView
  let selectedVectorResultId = null
  let instanceOfByItem = new Map()
  let instanceOfLoaded = false
  let instanceOfLoadFailed = false
  let datatypeByProperty = new Map()
  let datatypeLoaded = false
  let datatypeLoadFailed = false
  let vectorConnections = []
  let vectorConnectionStatus = 'idle'
  let destroyed = false

  root.innerHTML = `
    ${header('search')}
    <main id="main-content" class="search-page">
      <div class="container container--content">
        ${searchBar(query, 'results-query')}

        <div class="search-layout">
          <section class="results" aria-live="polite" aria-busy="false">
            <div class="results__heading">
              <div data-results-heading>
                ${query ? `${resultsTitle(query)}<p>Searching…</p>` : '<h1>Search Wikidata by meaning</h1><p>Enter a natural-language query, description, or Wikidata ID.</p>'}
              </div>
              <div class="view-switch" data-view-switch ${query ? '' : 'hidden'} aria-label="Result view">
                <span>View:</span>
                <button type="button" data-view="list" aria-pressed="true">List</button>
                <button type="button" data-view="vector" aria-pressed="false">Vector</button>
              </div>
            </div>
            <div class="vector-view" data-vector-view hidden></div>
            <div class="results__list" data-results-list>
              ${query ? loadingCards() : `
                <div class="empty-state">
                  <span class="round-icon">${icon('search')}</span>
                  <h2>Discover related Wikidata entities</h2>
                  <p>Try a question, a contextual description, or an ID such as Q42.</p>
                </div>`}
            </div>
          </section>

          <div class="search-sidebar">
            <aside class="filters" aria-label="Search filters">
              <h2>Filters</h2>
              <label for="search-type">Search type</label>
              <select id="search-type" data-search-type>
                <option value="item">Items</option>
                <option value="property">Properties</option>
              </select>

              <label for="search-language">Language</label>
              <select id="search-language" data-language>
                <option value="all">All languages</option>
              </select>

              <div data-item-options>
                <label for="item-scope">Item scope</label>
                <select id="item-scope" data-scope>
                  <option value="with_sitelinks">With sitelinks</option>
                  <option value="no_sitelinks">Without sitelinks</option>
                  <option value="all">All items</option>
                </select>
              </div>

              <div class="checkbox-row" data-property-options hidden>
                <input id="exclude-external-ids" type="checkbox" data-exclude-external checked />
                <label for="exclude-external-ids">Exclude external IDs</label>
              </div>

              <div class="range-label">
                <label for="result-limit">Results</label>
                <output for="result-limit" data-limit-value>50</output>
              </div>
              <input id="result-limit" class="range-control" type="range" min="1" max="50" step="1" value="50" data-limit />
              <div class="range-limits" aria-hidden="true"><span>1</span><span>50</span></div>

              <div class="checkbox-row" data-rerank-option>
                <input id="use-rerank" type="checkbox" data-rerank checked />
                <label for="use-rerank">Improve order with reranking</label>
              </div>
            </aside>

            <aside class="result-actions" aria-label="Use these results" hidden>
              <h2>Use these results for:</h2>
              <button type="button" data-action="copy">${icon('copy')} Copy API link</button>
              <button type="button" data-action="export">${icon('document')} Export data</button>
              <button type="button" data-action="api" aria-expanded="false">${icon('code')} API example</button>
              <p class="result-actions__status" data-action-status>Search results can be used as grounding context for LLMs or integrated through the API.</p>
              <div class="api-example-panel" data-api-example-panel hidden>
                <div class="api-example-toolbar">
                  <select id="api-example-language" aria-label="API example language" data-api-language>
                    <option value="python">Python</option>
                    <option value="bash">Bash</option>
                    <option value="javascript">Node.js</option>
                    <option value="php">PHP</option>
                    <option value="go">Go</option>
                    <option value="java">Java</option>
                    <option value="csharp">C#</option>
                    <option value="ruby">Ruby</option>
                  </select>
                  <button type="button" class="api-copy-button" data-copy-api>${icon('copy')} Copy code</button>
                </div>
                <pre class="api-example" data-api-example></pre>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </main>`

  bindInternalLinks(root, navigate)

  const form = root.querySelector('[data-search-form]')
  const list = root.querySelector('[data-results-list]')
  const heading = root.querySelector('[data-results-heading]')
  const viewSwitch = root.querySelector('[data-view-switch]')
  const vectorView = root.querySelector('[data-vector-view]')
  const resultsSection = root.querySelector('.results')
  const typeSelect = root.querySelector('[data-search-type]')
  const languageSelect = root.querySelector('[data-language]')
  const scopeSelect = root.querySelector('[data-scope]')
  const limitInput = root.querySelector('[data-limit]')
  const limitValue = root.querySelector('[data-limit-value]')
  const rerankInput = root.querySelector('[data-rerank]')
  const rerankOption = root.querySelector('[data-rerank-option]')
  const excludeExternalInput = root.querySelector('[data-exclude-external]')
  const itemOptions = root.querySelector('[data-item-options]')
  const propertyOptions = root.querySelector('[data-property-options]')
  const resultActions = root.querySelector('.result-actions')
  const actionStatus = root.querySelector('[data-action-status]')
  const apiButton = root.querySelector('[data-action="api"]')
  const apiExamplePanel = root.querySelector('[data-api-example-panel]')
  const apiLanguage = root.querySelector('[data-api-language]')
  const apiCopyButton = root.querySelector('[data-copy-api]')
  const apiExample = root.querySelector('[data-api-example]')

  typeSelect.value = initialType
  scopeSelect.value = initialScope
  limitInput.value = initialLimit
  limitValue.value = initialLimit
  rerankInput.checked = initialRerank
  excludeExternalInput.checked = initialExcludeExternalIds
  if (initialLanguage !== 'all') {
    const initialLanguageOption = document.createElement('option')
    initialLanguageOption.value = initialLanguage
    initialLanguageOption.textContent = initialLanguage.toUpperCase()
    languageSelect.append(initialLanguageOption)
    languageSelect.value = initialLanguage
  }

  const options = () => ({
    query: form.elements.q.value.trim(),
    type: typeSelect.value,
    language: languageSelect.value,
    scope: scopeSelect.value,
    limit: Number(limitInput.value),
    rerank: viewMode === 'vector' ? false : rerankInput.checked,
    excludeExternalIds: excludeExternalInput.checked,
    view: viewMode,
    returnVectors: viewMode === 'vector',
  })

  const searchPageUrl = (searchOptions) => {
    const url = new URL('/search', window.location.origin)
    url.searchParams.set('q', searchOptions.query)
    url.searchParams.set('type', searchOptions.type)
    url.searchParams.set('lang', searchOptions.language)
    url.searchParams.set('limit', String(searchOptions.limit))
    url.searchParams.set('rerank', String(searchOptions.rerank))
    url.searchParams.set('view', searchOptions.view)
    if (searchOptions.type === 'property') {
      url.searchParams.set('exclude_external_ids', String(searchOptions.excludeExternalIds))
    } else {
      url.searchParams.set('scope', searchOptions.scope)
    }
    return url.href
  }

  const apiRequest = (searchOptions) => {
    const endpoint = searchOptions.type === 'property' ? '/property/query/' : '/item/query/'
    const params = {
      query: searchOptions.query,
      lang: searchOptions.language,
      K: String(searchOptions.limit),
      rerank: String(searchOptions.rerank),
    }
    if (searchOptions.returnVectors) params.return_vectors = 'true'
    if (searchOptions.type === 'property') {
      params.exclude_external_ids = String(searchOptions.excludeExternalIds)
    } else {
      params.scope = searchOptions.scope
    }
    return { endpoint: new URL(endpoint, window.location.origin).href, params }
  }

  const apiRequestUrl = (searchOptions) => {
    const { endpoint, params } = apiRequest(searchOptions)
    const url = new URL(endpoint)
    url.search = new URLSearchParams(params).toString()
    return url.href
  }

  const apiExampleFor = (language, searchOptions) => {
    const { endpoint, params } = apiRequest(searchOptions)
    const entries = Object.entries(params)
    const defaultUserAgent = 'ProjectName/1.0 (email@example.com)'
    const url = new URL(endpoint)
    url.search = new URLSearchParams(params).toString()
    const requestUrl = url.href

    if (language === 'python') {
      const lines = entries.map(([key, value]) => `    ${JSON.stringify(key)}: ${JSON.stringify(value)},`).join('\n')
      return `import requests\n\n# Required: change this User-Agent before making requests.\nheaders = {\n    "User-Agent": ${JSON.stringify(defaultUserAgent)},\n}\nparams = {\n${lines}\n}\nresponse = requests.get(${JSON.stringify(endpoint)}, params=params, headers=headers)\nresponse.raise_for_status()\nprint(response.json())`
    }

    if (language === 'javascript') {
      const lines = entries.map(([key, value]) => `  ${JSON.stringify(key)}: ${JSON.stringify(value)},`).join('\n')
      return `// Required: change this User-Agent before making requests.\nconst headers = {\n  "User-Agent": ${JSON.stringify(defaultUserAgent)},\n}\nconst params = new URLSearchParams({\n${lines}\n})\nconst response = await fetch(\`${endpoint}?\${params}\`, { headers })\nif (!response.ok) throw new Error(\`Request failed: \${response.status}\`)\nconst data = await response.json()\nconsole.log(data)`
    }

    if (language === 'php') {
      const phpString = (value) => `'${String(value).replaceAll('\\', '\\\\').replaceAll("'", "\\'")}'`
      const lines = entries.map(([key, value]) => `    ${phpString(key)} => ${phpString(value)},`).join('\n')
      return `<?php\n// Required: change this User-Agent before making requests.\n$options = [\n    'http' => [\n        'header' => ${phpString(`User-Agent: ${defaultUserAgent}`)},\n    ],\n];\n$context = stream_context_create($options);\n$params = [\n${lines}\n];\n$url = ${phpString(endpoint)} . '?' . http_build_query($params);\n$response = file_get_contents($url, false, $context);\nif ($response === false) {\n    throw new RuntimeException('API request failed');\n}\nprint_r(json_decode($response, true));`
    }

    if (language === 'go') {
      return `package main\n\nimport (\n    "fmt"\n    "io"\n    "net/http"\n)\n\nfunc main() {\n    request, err := http.NewRequest(http.MethodGet, ${JSON.stringify(requestUrl)}, nil)\n    if err != nil {\n        panic(err)\n    }\n    // Required: change this User-Agent before making requests.\n    request.Header.Set("User-Agent", ${JSON.stringify(defaultUserAgent)})\n\n    response, err := http.DefaultClient.Do(request)\n    if err != nil {\n        panic(err)\n    }\n    defer response.Body.Close()\n\n    body, err := io.ReadAll(response.Body)\n    if err != nil {\n        panic(err)\n    }\n    if response.StatusCode >= 400 {\n        panic(response.Status)\n    }\n    fmt.Println(string(body))\n}`
    }

    if (language === 'java') {
      return `import java.net.URI;\nimport java.net.http.HttpClient;\nimport java.net.http.HttpRequest;\nimport java.net.http.HttpResponse;\n\npublic class Example {\n    public static void main(String[] args) throws Exception {\n        var client = HttpClient.newHttpClient();\n        // Required: change this User-Agent before making requests.\n        var request = HttpRequest.newBuilder()\n            .uri(URI.create(${JSON.stringify(requestUrl)}))\n            .header("User-Agent", ${JSON.stringify(defaultUserAgent)})\n            .GET()\n            .build();\n        var response = client.send(request, HttpResponse.BodyHandlers.ofString());\n        if (response.statusCode() >= 400) {\n            throw new RuntimeException("Request failed: " + response.statusCode());\n        }\n        System.out.println(response.body());\n    }\n}`
    }

    if (language === 'csharp') {
      return `using System.Net.Http;\n\nusing var client = new HttpClient();\n// Required: change this User-Agent before making requests.\nclient.DefaultRequestHeaders.UserAgent.ParseAdd(${JSON.stringify(defaultUserAgent)});\nvar response = await client.GetAsync(${JSON.stringify(requestUrl)});\nresponse.EnsureSuccessStatusCode();\nvar data = await response.Content.ReadAsStringAsync();\nConsole.WriteLine(data);`
    }

    if (language === 'ruby') {
      return `require "json"\nrequire "net/http"\n\nuri = URI(${JSON.stringify(requestUrl)})\nrequest = Net::HTTP::Get.new(uri)\n# Required: change this User-Agent before making requests.\nrequest["User-Agent"] = ${JSON.stringify(defaultUserAgent)}\nresponse = Net::HTTP.start(uri.hostname, uri.port, use_ssl: uri.scheme == "https") do |http|\n  http.request(request)\nend\nraise "Request failed: #{response.code}" unless response.is_a?(Net::HTTPSuccess)\nputs JSON.pretty_generate(JSON.parse(response.body))`
    }

    return `# Required: change this User-Agent before making requests.\ncurl -H ${JSON.stringify(`User-Agent: ${defaultUserAgent}`)} ${JSON.stringify(requestUrl)}`
  }

  const renderApiExample = () => {
    if (!resultOptions) return
    apiExample.textContent = apiExampleFor(apiLanguage.value, resultOptions)
  }

  const updateTypeControls = () => {
    const showItems = typeSelect.value === 'item'
    itemOptions.hidden = !showItems
    propertyOptions.hidden = showItems
  }

  const updateViewControls = () => {
    viewSwitch.querySelectorAll('[data-view]').forEach((button) => {
      const active = button.dataset.view === viewMode
      button.classList.toggle('is-active', active)
      button.setAttribute('aria-pressed', String(active))
    })
    vectorView.hidden = viewMode !== 'vector'
    rerankOption.hidden = viewMode === 'vector'
  }

  const bindVectorNodes = () => {
    vectorView.querySelectorAll('[data-vector-node]').forEach((node) => {
      node.addEventListener('click', (event) => {
        event.preventDefault()
        showVectorResult(node.dataset.vectorNode, { scroll: true })
      })
    })
  }

  const renderVectorView = () => {
    const isPropertySearch = resultOptions?.type === 'property'
    vectorView.innerHTML = vectorMapMarkup(
      results,
      vectorConnections,
      vectorConnectionStatus,
      selectedVectorResultId,
      isPropertySearch ? datatypeByProperty : instanceOfByItem,
      isPropertySearch ? 'Datatype' : 'Instance of',
    )
    bindVectorNodes()
  }

  const bindFeedback = () => {
    list.querySelectorAll('[data-result-index]').forEach((card) => {
      card.querySelectorAll('[data-sentiment]').forEach((button) => {
        button.addEventListener('click', async () => {
          const index = Number(card.dataset.resultIndex)
          const feedback = card.querySelector('[data-feedback]')
          feedback.querySelectorAll('button').forEach((item) => { item.disabled = true })
          try {
            await sendFeedback({
              query: currentQuery,
              id: results[index].id,
              sentiment: button.dataset.sentiment,
              index,
            })
            feedback.innerHTML = `<span class="feedback__thanks">${icon('check')} Thanks for your feedback!</span>`
          } catch {
            feedback.querySelectorAll('button').forEach((item) => { item.disabled = false })
            feedback.querySelector('span').textContent = 'Feedback could not be sent.'
          }
        })
      })
    })
  }

  const loadRelatedResults = async (searchOptions, primaryResults, controller, resultIndexes = null) => {
    const relatedType = searchOptions.type === 'item' ? 'property' : 'item'
    const relatedOptions = {
      ...searchOptions,
      type: relatedType,
      rerank: false,
      returnVectors: false,
    }

    try {
      const relatedRawResults = await searchEntities(relatedOptions, controller.signal)
      if (destroyed || activeController !== controller) return

      const itemIds = (searchOptions.type === 'item' ? primaryResults : relatedRawResults).map((result) => result.id)
      const propertyIds = (searchOptions.type === 'property' ? primaryResults : relatedRawResults).map((result) => result.id)
      const [relatedResults, matches] = await Promise.all([
        enrichEntities(relatedRawResults, searchOptions.language, controller.signal),
        findItemPropertyMatches(itemIds, propertyIds, controller.signal),
      ])
      if (destroyed || activeController !== controller) return

      primaryResults.forEach((primaryResult, index) => {
        const related = relatedType === 'property'
          ? relatedResults.filter((property) => matches.get(primaryResult.id)?.has(property.id))
          : relatedResults.filter((item) => matches.get(item.id)?.has(primaryResult.id))
        const resultIndex = resultIndexes?.[index] ?? index
        const container = list.querySelector(`[data-related-results="${resultIndex}"]`)
        if (container) container.innerHTML = relatedEntitiesMarkup(related, relatedType, primaryResult.id)
      })
    } catch (error) {
      if (error.name === 'AbortError' || destroyed || activeController !== controller) return
      const label = relatedType === 'property' ? 'properties' : 'items'
      list.querySelectorAll('[data-related-results]').forEach((container) => {
        container.innerHTML = `<span class="related-error">Matching ${label} could not be loaded.</span>`
      })
    }
  }

  const renderInstanceOfDetails = (primaryResults, resultIndexes = null) => {
    primaryResults.forEach((primaryResult, index) => {
      const resultIndex = resultIndexes?.[index] ?? index
      const container = list.querySelector(`[data-related-results="${resultIndex}"]`)
      if (!container) return
      container.innerHTML = instanceOfLoadFailed
        ? '<span class="related-error">Instance of values could not be loaded.</span>'
        : instanceOfMarkup(instanceOfByItem.get(primaryResult.id) || [])
    })
  }

  const renderDatatypeDetails = (primaryResults, resultIndexes = null) => {
    primaryResults.forEach((primaryResult, index) => {
      const resultIndex = resultIndexes?.[index] ?? index
      const container = list.querySelector(`[data-related-results="${resultIndex}"]`)
      if (!container) return
      container.innerHTML = datatypeLoadFailed
        ? '<span class="related-error">Datatype could not be loaded.</span>'
        : datatypeMarkup(datatypeByProperty.get(primaryResult.id) || [])
    })
  }

  const renderConnectedResults = (itemId, resultIndex) => {
    const container = list.querySelector(`[data-connected-results="${resultIndex}"]`)
    if (!container) return
    const outgoingProperties = new Map()
    const incomingProperties = new Map()

    const addConnection = (propertiesByConnectedId, connectedId, connection) => {
      if (!propertiesByConnectedId.has(connectedId)) propertiesByConnectedId.set(connectedId, new Map())
      const propertyKey = `${connection.property.id}:${connection.source}`
      propertiesByConnectedId.get(connectedId).set(propertyKey, {
        ...connection.property,
        statementItemId: connection.source,
      })
    }

    for (const connection of vectorConnections) {
      if (connection.source === itemId) addConnection(outgoingProperties, connection.target, connection)
      if (connection.target === itemId) addConnection(incomingProperties, connection.source, connection)
    }

    const relationshipGroupMarkup = (title, propertiesByConnectedId) => {
      const connectedItems = results.filter((result) => propertiesByConnectedId.has(result.id))
      if (!connectedItems.length) return ''

      return `
        <section class="connected-results-group">
          <p class="connected-results-group__title">${title}</p>
          <div class="connected-results-list">
            ${connectedItems.map((item) => `
              <div class="connected-result-row">
                <button class="related-chip connected-result" type="button" data-connected-item="${escapeHtml(item.id)}">
                  ${escapeHtml(item.label || item.id)} <span>${escapeHtml(item.id)}</span>
                </button>
                <span class="connected-result-row__via">via</span>
                <div class="connected-result-row__properties">
                  ${[...propertiesByConnectedId.get(item.id).values()].map((property) => `
                    <a href="${wikidataUrl(property.statementItemId)}#${escapeHtml(property.id)}" target="_blank" rel="noreferrer" title="View ${escapeHtml(property.id)} statement on ${escapeHtml(property.statementItemId)}">
                      ${escapeHtml(property.label || property.id)} <span>${escapeHtml(property.id)}</span>
                    </a>`).join('')}
                </div>
              </div>`).join('')}
          </div>
        </section>`
    }

    const outgoingMarkup = relationshipGroupMarkup('Outgoing relationships', outgoingProperties)
    const incomingMarkup = relationshipGroupMarkup('Incoming relationships', incomingProperties)
    if (!outgoingMarkup && !incomingMarkup) {
      container.hidden = true
      container.innerHTML = ''
      return
    }

    container.innerHTML = `
      <p>Connected items in these results</p>
      <div class="connected-results-groups">
        ${outgoingMarkup}
        ${incomingMarkup}
      </div>`
    container.hidden = false
  }

  const loadInstanceOfDetails = async (searchOptions, primaryResults, controller, resultIndexes = null) => {
    try {
      const loadedInstanceOf = await getItemInstanceOf(
        primaryResults.map((result) => result.id),
        searchOptions.language,
        controller.signal,
      )
      if (destroyed || activeController !== controller) return
      instanceOfByItem = loadedInstanceOf
      instanceOfLoaded = true
      renderInstanceOfDetails(primaryResults, resultIndexes)
      if (viewMode === 'vector') renderVectorView()
    } catch (error) {
      if (error.name === 'AbortError' || destroyed || activeController !== controller) return
      instanceOfLoaded = true
      instanceOfLoadFailed = true
      renderInstanceOfDetails(primaryResults, resultIndexes)
    }
  }

  const loadDatatypeDetails = async (primaryResults, controller, resultIndexes = null) => {
    try {
      const loadedDatatypes = await getPropertyDatatypes(
        primaryResults.map((result) => result.id),
        controller.signal,
      )
      if (destroyed || activeController !== controller) return
      datatypeByProperty = loadedDatatypes
      datatypeLoaded = true
      renderDatatypeDetails(primaryResults, resultIndexes)
      if (viewMode === 'vector') renderVectorView()
    } catch (error) {
      if (error.name === 'AbortError' || destroyed || activeController !== controller) return
      datatypeLoaded = true
      datatypeLoadFailed = true
      renderDatatypeDetails(primaryResults, resultIndexes)
    }
  }

  const showVectorResult = (id, { scroll = false } = {}) => {
    const index = results.findIndex((result) => result.id === id)
    if (index < 0 || !resultOptions) return
    selectedVectorResultId = id
    vectorView.querySelectorAll('[data-vector-node]').forEach((node) => {
      node.classList.toggle('is-selected', node.dataset.vectorNode === id)
    })
    const relatedType = resultOptions.type === 'item' ? 'property' : 'item'
    list.innerHTML = resultCard(
      results[index],
      index,
      resultOptions.rerank,
      relatedType,
      resultOptions.type === 'item' ? 'instanceOf' : 'datatype',
    )
    bindFeedback()
    if (resultOptions.type === 'item') {
      if (instanceOfLoaded) renderInstanceOfDetails([results[index]], [index])
      renderConnectedResults(id, index)
    } else if (datatypeLoaded) {
      renderDatatypeDetails([results[index]], [index])
    }
    const card = document.getElementById(`result-${id}`)
    if (scroll) {
      card?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      card?.classList.add('result-card--highlighted')
      window.setTimeout(() => card?.classList.remove('result-card--highlighted'), 1600)
    }
  }

  const loadVectorConnections = async (searchOptions, controller) => {
    if (searchOptions.type !== 'item') return
    try {
      const connections = await findItemConnections(
        results.map((result) => result.id),
        searchOptions.language,
        controller.signal,
      )
      if (destroyed || activeController !== controller || viewMode !== 'vector') return
      vectorConnections = connections
      vectorConnectionStatus = 'ready'
      renderVectorView()
      const selectedIndex = results.findIndex((result) => result.id === selectedVectorResultId)
      if (selectedIndex >= 0) renderConnectedResults(selectedVectorResultId, selectedIndex)
    } catch (error) {
      if (error.name === 'AbortError' || destroyed || activeController !== controller || viewMode !== 'vector') return
      vectorConnections = []
      vectorConnectionStatus = 'error'
      renderVectorView()
    }
  }

  const runSearch = async ({ replaceUrl = true } = {}) => {
    const searchOptions = options()
    if (!searchOptions.query) return
    navigate(searchPageUrl(searchOptions), { replace: replaceUrl, render: false, scroll: false })
    activeController.abort()
    const controller = new AbortController()
    activeController = controller
    currentQuery = searchOptions.query
    selectedVectorResultId = null
    instanceOfByItem = new Map()
    instanceOfLoaded = false
    instanceOfLoadFailed = false
    datatypeByProperty = new Map()
    datatypeLoaded = false
    datatypeLoadFailed = false
    vectorConnections = []
    vectorConnectionStatus = 'idle'
    results = []
    resultOptions = null
    resultsSection.setAttribute('aria-busy', 'true')
    heading.innerHTML = `${resultsTitle(currentQuery)}<p>Searching…</p>`
    viewSwitch.hidden = false
    updateViewControls()
    vectorView.innerHTML = viewMode === 'vector'
      ? '<section class="vector-map-panel vector-map-panel--loading"><span class="loading-spinner" aria-hidden="true"></span>Loading vectors…</section>'
      : ''
    list.innerHTML = loadingCards()
    resultActions.hidden = true
    apiExamplePanel.hidden = true
    apiButton.setAttribute('aria-expanded', 'false')

    try {
      const rawResults = await searchEntities(searchOptions, controller.signal)
      results = await enrichEntities(rawResults, searchOptions.language, controller.signal)
      if (destroyed || activeController !== controller) return
      resultOptions = searchOptions
      heading.innerHTML = `${resultsTitle(currentQuery)}<p>${results.length} ${results.length === 1 ? 'result' : 'results'}</p>`
      const relatedType = searchOptions.type === 'item' ? 'property' : 'item'
      if (!results.length) {
        list.innerHTML = '<div class="empty-state"><h2>No results found</h2><p>Try a broader description or another language.</p></div>'
      } else if (viewMode === 'vector') {
        list.innerHTML = ''
      } else {
        list.innerHTML = results.map((result, index) => resultCard(result, index, searchOptions.rerank, relatedType)).join('')
      }
      resultActions.hidden = results.length === 0
      vectorView.hidden = viewMode !== 'vector' || results.length === 0
      if (viewMode === 'vector' && results.length) {
        selectedVectorResultId = results[0].id
        vectorConnectionStatus = searchOptions.type === 'item' ? 'loading' : 'idle'
        renderVectorView()
        showVectorResult(selectedVectorResultId)
        if (searchOptions.type === 'item') {
          void loadVectorConnections(searchOptions, controller)
          void loadInstanceOfDetails(searchOptions, [...results], controller)
        } else {
          void loadDatatypeDetails([...results], controller)
        }
      } else {
        bindFeedback()
        if (results.length) {
          void loadRelatedResults(searchOptions, [...results], controller)
        }
      }
    } catch (error) {
      if (error.name === 'AbortError') return
      heading.innerHTML = `${resultsTitle(currentQuery)}<p>Search failed</p>`
      vectorView.hidden = true
      list.innerHTML = `<div class="error-state" role="alert"><h2>We couldn't retrieve results.</h2><p>${escapeHtml(error.message || 'Please try again shortly.')}</p><button class="button button--primary" type="button" data-retry>Try again</button></div>`
      list.querySelector('[data-retry]')?.addEventListener('click', runSearch)
    } finally {
      if (activeController === controller) resultsSection.setAttribute('aria-busy', 'false')
    }
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault()
    const nextQuery = form.elements.q.value.trim()
    if (nextQuery) {
      document.title = `${nextQuery} · Wikidata Vector Search`
      runSearch({ replaceUrl: false })
    }
  })

  viewSwitch.addEventListener('click', (event) => {
    const button = event.target.closest('[data-view]')
    if (!button || button.dataset.view === viewMode) return
    viewMode = button.dataset.view
    updateViewControls()
    if (currentQuery) runSearch()
  })

  list.addEventListener('click', (event) => {
    const connectedItem = event.target.closest('[data-connected-item]')
    if (!connectedItem || viewMode !== 'vector') return
    showVectorResult(connectedItem.dataset.connectedItem, { scroll: true })
  })

  typeSelect.addEventListener('change', () => {
    updateTypeControls()
    if (currentQuery) runSearch()
  })

  limitInput.addEventListener('input', () => {
    limitValue.value = limitInput.value
  })

  apiLanguage.addEventListener('change', renderApiExample)

  apiCopyButton.addEventListener('click', async () => {
    try {
      await copyText(apiExample.textContent)
      actionStatus.textContent = 'API code copied.'
    } catch {
      actionStatus.textContent = 'Code could not be copied in this browser.'
    }
  })

  root.querySelectorAll('.filters select:not([data-search-type]), .filters input').forEach((control) => {
    control.addEventListener('change', () => {
      if (currentQuery) runSearch()
    })
  })

  root.querySelectorAll('[data-action]').forEach((button) => {
    button.addEventListener('click', async () => {
      if (!results.length) {
        actionStatus.textContent = 'Run a search first.'
        return
      }

      try {
        if (button.dataset.action === 'copy') {
          await copyText(apiRequestUrl(resultOptions || options()))
          actionStatus.textContent = 'API GET link copied.'
        } else if (button.dataset.action === 'export') {
          const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' })
          const url = URL.createObjectURL(blob)
          const download = document.createElement('a')
          download.href = url
          download.download = 'wikidata-vector-results.json'
          download.click()
          URL.revokeObjectURL(url)
          actionStatus.textContent = 'JSON export downloaded.'
        } else if (button.dataset.action === 'api') {
          apiExamplePanel.hidden = !apiExamplePanel.hidden
          button.setAttribute('aria-expanded', String(!apiExamplePanel.hidden))
          if (!apiExamplePanel.hidden) renderApiExample()
          actionStatus.textContent = apiExamplePanel.hidden ? 'API example hidden.' : 'Equivalent API request:'
        }
      } catch {
        actionStatus.textContent = 'That action is not available in this browser.'
      }
    })
  })

  getLanguages(languagesController.signal).then((languages) => {
    if (destroyed) return
    const selectedLanguage = languageSelect.value
    const dedicated = [...new Set(languages.vectordb_langs || [])].sort()
    const translated = [...new Set(languages.other_langs || [])].sort()
    languageSelect.innerHTML = `
      <option value="all">All languages</option>
      <optgroup label="Dedicated vector datasets">
        ${dedicated.map((lang) => `<option value="${escapeHtml(lang)}">${escapeHtml(lang.toUpperCase())}</option>`).join('')}
      </optgroup>
      ${translated.length ? `<optgroup label="Translated queries">${translated.map((lang) => `<option value="${escapeHtml(lang)}">${escapeHtml(lang.toUpperCase())}</option>`).join('')}</optgroup>` : ''}`
    if (Array.from(languageSelect.options).some((option) => option.value === selectedLanguage)) {
      languageSelect.value = selectedLanguage
    }
  }).catch(() => {})

  updateTypeControls()
  updateViewControls()
  if (query) runSearch()

  return () => {
    destroyed = true
    activeController.abort()
    languagesController.abort()
  }
}
