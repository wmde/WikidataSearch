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
  if (options.returnVectors) params.set('return_vectors', 'true')

  const endpoint = isProperty ? '/property/query/' : '/item/query/'
  const data = await fetch(`${endpoint}?${params}`, { signal }).then(readJson)
  return data.map((item) => ({ ...item, id: item.QID || item.PID }))
}

export async function findItemConnections(ids, language = 'en', signal) {
  const items = [...new Set(ids)].filter((id) => /^Q\d+$/.test(id))
  if (items.length < 2) return []

  const values = items.map((id) => `wd:${id}`).join(' ')
  const query = `
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wikibase: <http://wikiba.se/ontology#>
    SELECT DISTINCT ?source ?property ?target WHERE {
      VALUES ?source { ${values} }
      VALUES ?target { ${values} }
      ?property wikibase:directClaim ?predicate.
      ?source ?predicate ?target.
      FILTER(?source != ?target)
    }
  `
  const params = new URLSearchParams({ query, format: 'json' })
  const data = await fetch(`https://query.wikidata.org/sparql?${params}`, {
    headers: { Accept: 'application/sparql-results+json' },
    signal,
  }).then(readJson)
  const rawConnections = []
  const propertyIds = new Set()
  const seen = new Set()

  for (const binding of data.results?.bindings || []) {
    const source = binding.source?.value?.match(/Q\d+$/)?.[0]
    const target = binding.target?.value?.match(/Q\d+$/)?.[0]
    const propertyId = binding.property?.value?.match(/P\d+$/)?.[0]
    if (!source || !target || !propertyId) continue
    const key = [source, propertyId, target].join(':')
    if (seen.has(key)) continue
    seen.add(key)
    propertyIds.add(propertyId)
    rawConnections.push({ source, target, propertyId })
  }

  const idsToEnrich = [...propertyIds]
  const batches = []
  for (let index = 0; index < idsToEnrich.length; index += 50) {
    batches.push(idsToEnrich.slice(index, index + 50))
  }
  const enrichedBatches = await Promise.all(batches.map((batch) => enrichEntities(
    batch.map((id) => ({ id })),
    language,
    signal,
  )))
  const propertyById = new Map(enrichedBatches.flat().map((property) => [property.id, property]))

  return rawConnections.map((connection) => ({
    ...connection,
    property: propertyById.get(connection.propertyId) || {
      id: connection.propertyId,
      label: connection.propertyId,
    },
  }))
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

export async function getItemInstanceOf(ids, language = 'en', signal) {
  const items = [...new Set(ids)].filter((id) => /^Q\d+$/.test(id))
  if (!items.length) return new Map()

  const params = new URLSearchParams({
    action: 'wbgetentities',
    format: 'json',
    origin: '*',
    ids: items.join('|'),
    props: 'claims',
  })
  const data = await fetch(`https://www.wikidata.org/w/api.php?${params}`, { signal }).then(readJson)
  const instanceIdsByItem = new Map()
  const allInstanceIds = new Set()

  for (const itemId of items) {
    const instanceIds = []
    const seen = new Set()
    for (const statement of data.entities?.[itemId]?.claims?.P31 || []) {
      if (statement.rank === 'deprecated') continue
      const instanceId = statement.mainsnak?.datavalue?.value?.id
      if (!/^Q\d+$/.test(instanceId || '') || seen.has(instanceId)) continue
      seen.add(instanceId)
      allInstanceIds.add(instanceId)
      instanceIds.push(instanceId)
    }
    instanceIdsByItem.set(itemId, instanceIds)
  }

  const instanceIds = [...allInstanceIds]
  const batches = []
  for (let index = 0; index < instanceIds.length; index += 50) {
    batches.push(instanceIds.slice(index, index + 50))
  }
  const enrichedBatches = await Promise.all(batches.map((batch) => enrichEntities(
    batch.map((id) => ({ id })),
    language,
    signal,
  )))
  const instanceById = new Map(enrichedBatches.flat().map((instance) => [instance.id, instance]))

  return new Map(items.map((itemId) => [
    itemId,
    (instanceIdsByItem.get(itemId) || []).map((id) => instanceById.get(id) || { id, label: id }),
  ]))
}

const DATATYPE_LABELS = {
  'commonsMedia': 'Commons media',
  'entity-schema': 'Entity schema',
  'external-id': 'External identifier',
  'geo-shape': 'Geographic shape',
  'globe-coordinate': 'Geographic coordinates',
  'math': 'Mathematical expression',
  'monolingualtext': 'Monolingual text',
  'musical-notation': 'Musical notation',
  'tabular-data': 'Tabular data',
  'wikibase-form': 'Wikibase form',
  'wikibase-item': 'Wikibase item',
  'wikibase-lexeme': 'Wikibase lexeme',
  'wikibase-property': 'Wikibase property',
  'wikibase-sense': 'Wikibase sense',
}

function datatypeLabel(datatype) {
  if (DATATYPE_LABELS[datatype]) return DATATYPE_LABELS[datatype]
  const words = datatype.replaceAll('-', ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export async function getPropertyDatatypes(ids, signal) {
  const properties = [...new Set(ids)].filter((id) => /^P\d+$/.test(id))
  if (!properties.length) return new Map()

  const params = new URLSearchParams({
    action: 'wbgetentities',
    format: 'json',
    origin: '*',
    ids: properties.join('|'),
    props: 'datatype',
  })
  const data = await fetch(`https://www.wikidata.org/w/api.php?${params}`, { signal }).then(readJson)

  return new Map(properties.map((propertyId) => {
    const datatype = data.entities?.[propertyId]?.datatype
    return [propertyId, datatype ? [{ id: datatype, label: datatypeLabel(datatype) }] : []]
  }))
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
