const DEFAULT_LANGUAGES = { vectordb_langs: ['de', 'en', 'fr'], other_langs: [] }

async function readJson(response) {
  let body
  try {
    body = await response.json()
  } catch {
    body = null
  }

  if (!response.ok) {
    throw new Error(body?.detail || `Request failed with status ${response.status}`)
  }
  return body
}

export async function getLanguages(signal) {
  try {
    return await fetch('/languages', { signal }).then(readJson)
  } catch (error) {
    if (error.name === 'AbortError') throw error
    return DEFAULT_LANGUAGES
  }
}

export async function searchEntities(options, signal) {
  const isProperty = options.type === 'property'
  const params = new URLSearchParams({
    query: options.query,
    lang: options.language || 'all',
    K: String(options.limit || 10),
    rerank: String(Boolean(options.rerank)),
  })

  if (isProperty) {
    params.set('exclude_external_ids', String(Boolean(options.excludeExternalIds)))
  } else {
    params.set('scope', options.scope || 'with_sitelinks')
  }

  const endpoint = isProperty ? '/property/query/' : '/item/query/'
  const data = await fetch(`${endpoint}?${params}`, { signal }).then(readJson)
  return data.map((item) => ({ ...item, id: item.QID || item.PID }))
}

export async function enrichEntities(results, language = 'en', signal) {
  if (!results.length) return []
  const ids = results.map((result) => result.id).filter(Boolean)
  const languages = [...new Set([language === 'all' ? 'en' : language, 'mul', 'en'])]
  const params = new URLSearchParams({
    action: 'wbgetentities',
    format: 'json',
    origin: '*',
    ids: ids.join('|'),
    props: 'labels|descriptions',
    languages: languages.join('|'),
  })

  try {
    const data = await fetch(`https://www.wikidata.org/w/api.php?${params}`, { signal }).then(readJson)
    return results.map((result) => {
      const entity = data.entities?.[result.id]
      const label = languages.map((lang) => entity?.labels?.[lang]?.value).find(Boolean)
      const description = languages.map((lang) => entity?.descriptions?.[lang]?.value).find(Boolean)
      return {
        ...result,
        label: label || result.id,
        description: description || 'No description is available for this entity.',
      }
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    return results.map((result) => ({
      ...result,
      label: result.id,
      description: 'Entity details could not be loaded from Wikidata.',
    }))
  }
}

export async function findItemPropertyMatches(itemIds, propertyIds, signal) {
  const items = [...new Set(itemIds)].filter((id) => /^Q\d+$/.test(id))
  const properties = [...new Set(propertyIds)].filter((id) => /^P\d+$/.test(id))
  if (!items.length || !properties.length) return new Map()

  const query = `
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wikibase: <http://wikiba.se/ontology#>
    SELECT DISTINCT ?item ?property WHERE {
      VALUES ?item { ${items.map((id) => `wd:${id}`).join(' ')} }
      VALUES ?property { ${properties.map((id) => `wd:${id}`).join(' ')} }
      ?property wikibase:directClaim ?predicate.
      ?item ?predicate ?value.
    }
  `
  const params = new URLSearchParams({ query, format: 'json' })
  const data = await fetch(`https://query.wikidata.org/sparql?${params}`, {
    headers: { Accept: 'application/sparql-results+json' },
    signal,
  }).then(readJson)
  const matches = new Map()

  for (const binding of data.results?.bindings || []) {
    const itemId = binding.item?.value?.match(/Q\d+$/)?.[0]
    const propertyId = binding.property?.value?.match(/P\d+$/)?.[0]
    if (!itemId || !propertyId) continue
    if (!matches.has(itemId)) matches.set(itemId, new Set())
    matches.get(itemId).add(propertyId)
  }

  return matches
}

export async function sendFeedback({ query, id, sentiment, index }) {
  const params = new URLSearchParams({ query, id, sentiment, index: String(index) })
  return fetch(`/feedback?${params}`, { method: 'POST' }).then(readJson)
}
