import { escapeHtml } from './components.js'

const WIDTH = 760
const HEIGHT = 500
const PADDING = 54
const EPSILON = 1e-10
const CLUSTER_COLORS = [
  '#3366cc',
  '#d94888',
  '#df8f00',
  '#159570',
  '#7c3aed',
  '#cf3f3f',
  '#07839f',
  '#9a6700',
  '#4f46e5',
  '#b44593',
  '#527a16',
  '#c45b17',
]

function dot(left, right) {
  let total = 0
  for (let index = 0; index < left.length; index += 1) total += left[index] * right[index]
  return total
}

function orthogonalize(vector, basis) {
  for (const direction of basis) {
    const projection = dot(vector, direction)
    for (let index = 0; index < vector.length; index += 1) {
      vector[index] -= projection * direction[index]
    }
  }
}

function normalize(vector) {
  const length = Math.sqrt(dot(vector, vector))
  if (length <= EPSILON) return false
  for (let index = 0; index < vector.length; index += 1) vector[index] /= length
  return true
}

function dominantEigenpair(matrix, basis, seed) {
  const size = matrix.length
  const vector = Float64Array.from(
    { length: size },
    (_, index) => Math.sin((index + 1) * (seed + 1.37)) + Math.cos((index + 1) * (seed + 0.71)),
  )
  orthogonalize(vector, basis)
  if (!normalize(vector)) vector[seed % size] = 1

  for (let iteration = 0; iteration < 100; iteration += 1) {
    const next = new Float64Array(size)
    for (let row = 0; row < size; row += 1) next[row] = dot(matrix[row], vector)
    orthogonalize(next, basis)
    if (!normalize(next)) return { value: 0, vector: new Float64Array(size) }

    let change = 0
    let inverseChange = 0
    for (let index = 0; index < size; index += 1) {
      change += (next[index] - vector[index]) ** 2
      inverseChange += (next[index] + vector[index]) ** 2
      vector[index] = next[index]
    }
    if (Math.min(change, inverseChange) < 1e-16) break
  }

  const multiplied = matrix.map((row) => dot(row, vector))
  return { value: Math.max(0, dot(vector, multiplied)), vector }
}

function scale(values, start, end) {
  const minimum = Math.min(...values)
  const maximum = Math.max(...values)
  const span = maximum - minimum
  if (span <= EPSILON) return values.map(() => (start + end) / 2)
  return values.map((value) => start + ((value - minimum) / span) * (end - start))
}

export function projectResultVectors(results) {
  const firstVector = results.find((result) => Array.isArray(result.vector) && result.vector.length)?.vector
  if (!firstVector) return []

  const dimension = firstVector.length
  const entries = results
    .map((result, index) => ({ result, index }))
    .filter(({ result }) => (
      Array.isArray(result.vector)
      && result.vector.length === dimension
      && result.vector.every((value) => Number.isFinite(Number(value)))
    ))
  if (!entries.length) return []
  if (entries.length === 1) {
    return [{ ...entries[0], x: WIDTH / 2, y: HEIGHT / 2 }]
  }

  const means = new Float64Array(dimension)
  for (const { result } of entries) {
    for (let column = 0; column < dimension; column += 1) means[column] += Number(result.vector[column])
  }
  for (let column = 0; column < dimension; column += 1) means[column] /= entries.length

  const centered = entries.map(({ result }) => Float64Array.from(
    result.vector,
    (value, column) => Number(value) - means[column],
  ))
  const gram = centered.map(() => new Float64Array(entries.length))
  for (let row = 0; row < entries.length; row += 1) {
    for (let column = row; column < entries.length; column += 1) {
      const value = dot(centered[row], centered[column])
      gram[row][column] = value
      gram[column][row] = value
    }
  }

  const first = dominantEigenpair(gram, [], 1)
  const second = dominantEigenpair(gram, [first.vector], 2)
  const firstScale = Math.sqrt(first.value)
  const secondScale = Math.sqrt(second.value)
  const horizontal = scale(
    entries.map((_, index) => first.vector[index] * firstScale),
    PADDING,
    WIDTH - PADDING,
  )
  const vertical = scale(
    entries.map((_, index) => second.vector[index] * secondScale),
    PADDING,
    HEIGHT - PADDING,
  )

  return entries.map((entry, index) => ({
    ...entry,
    x: horizontal[index],
    y: HEIGHT - vertical[index],
  }))
}

function connectionStatus(status) {
  if (status === 'loading') {
    return '<span class="vector-map__status"><span class="loading-spinner" aria-hidden="true"></span>Finding Wikidata connections…</span>'
  }
  if (status === 'error') return '<span class="vector-map__status vector-map__status--error">Connections could not be loaded.</span>'
  return ''
}

function similarityScore(result) {
  const rawScore = Number(result.similarity_score)
  if (!Number.isFinite(rawScore)) return null
  return Math.abs(rawScore) > 1.2 ? rawScore / 100 : rawScore
}

function nodeRadius(result, minimumScore, maximumScore) {
  const score = similarityScore(result)
  if (score === null) return 7
  const scoreRange = maximumScore - minimumScore
  if (scoreRange <= EPSILON) return 11
  return 6 + ((score - minimumScore) / scoreRange) * 10
}

function clusterData(results, valuesByEntity, missingLabel) {
  if (!(valuesByEntity instanceof Map) || !valuesByEntity.size) {
    return { assignmentByItem: new Map(), clusters: [] }
  }

  const valuesById = new Map()
  const counts = new Map()
  for (const result of results) {
    const uniqueValues = new Map((valuesByEntity.get(result.id) || []).map((value) => [value.id, value]))
    for (const value of uniqueValues.values()) {
      valuesById.set(value.id, value)
      counts.set(value.id, (counts.get(value.id) || 0) + 1)
    }
  }

  const assignmentByItem = new Map()
  for (const result of results) {
    const candidates = [...new Map(
      (valuesByEntity.get(result.id) || []).map((value) => [value.id, value]),
    ).values()].sort((left, right) => (
      (counts.get(right.id) || 0) - (counts.get(left.id) || 0)
      || String(left.label || left.id).localeCompare(String(right.label || right.id))
    ))
    assignmentByItem.set(result.id, candidates[0]?.id || null)
  }

  const usedIds = [...new Set(assignmentByItem.values())]
  const orderedIds = usedIds.filter(Boolean).sort((left, right) => (
    (counts.get(right) || 0) - (counts.get(left) || 0)
    || String(valuesById.get(left)?.label || left).localeCompare(String(valuesById.get(right)?.label || right))
  ))
  const clusters = orderedIds.map((id, index) => ({
    id,
    label: valuesById.get(id)?.label || id,
    count: [...assignmentByItem.values()].filter((value) => value === id).length,
    color: CLUSTER_COLORS[index] || `hsl(${Math.round((index * 137.508) % 360)} 62% 44%)`,
  }))
  if (usedIds.includes(null)) {
    clusters.push({
      id: null,
      label: missingLabel,
      count: [...assignmentByItem.values()].filter((value) => value === null).length,
      color: '#7a8494',
    })
  }

  return { assignmentByItem, clusters }
}

export function vectorMapMarkup(
  results,
  connections = [],
  status = 'idle',
  selectedId = null,
  clusterValuesByEntity = new Map(),
  clusterLabel = 'Instance of',
) {
  const points = projectResultVectors(results)
  if (!points.length) {
    return `
      <section class="vector-map-panel">
        <div class="vector-map-panel__heading">
          <div><h2>Vector space (2D projection)</h2></div>
        </div>
        <div class="vector-map__empty">No vectors were returned for these results.</div>
      </section>`
  }

  const pointById = new Map(points.map((point) => [point.result.id, point]))
  const scores = points.map(({ result }) => similarityScore(result)).filter((score) => score !== null)
  const minimumScore = scores.length ? Math.min(...scores) : 0
  const maximumScore = scores.length ? Math.max(...scores) : 0
  const missingClusterLabel = clusterLabel === 'Datatype' ? 'No datatype' : 'No instance of value'
  const { assignmentByItem, clusters } = clusterData(results, clusterValuesByEntity, missingClusterLabel)
  const clusterById = new Map(clusters.map((cluster) => [cluster.id, cluster]))
  const visibleConnections = connections.filter(({ source, target }) => pointById.has(source) && pointById.has(target))
  const visibleConnectionPairs = [...new Map(visibleConnections.map((connection) => [
    [connection.source, connection.target].sort().join(':'),
    connection,
  ])).values()]
  const edges = visibleConnectionPairs.map(({ source, target }) => {
    const from = pointById.get(source)
    const to = pointById.get(target)
    return `<line class="vector-edge" x1="${from.x.toFixed(2)}" y1="${from.y.toFixed(2)}" x2="${to.x.toFixed(2)}" y2="${to.y.toFixed(2)}" />`
  }).join('')
  const nodes = points.map(({ result, x, y }) => {
    const label = `${result.label || result.id} (${result.id})`
    const selectedClass = result.id === selectedId ? ' is-selected' : ''
    const radius = nodeRadius(result, minimumScore, maximumScore)
    const cluster = clusterById.get(assignmentByItem.get(result.id))
    const nodeClusterLabel = cluster ? ` · ${clusterLabel}: ${cluster.label}` : ''
    const colorStyle = cluster ? ` style="--node-color: ${cluster.color}"` : ''
    return `
      <a class="vector-node${selectedClass}" href="#result-${escapeHtml(result.id)}" data-vector-node="${escapeHtml(result.id)}" aria-label="${escapeHtml(label + nodeClusterLabel)}"${colorStyle}>
        <circle cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="${radius.toFixed(2)}"><title>${escapeHtml(label + nodeClusterLabel)}</title></circle>
        <text x="${x.toFixed(2)}" y="${(y - radius - 8).toFixed(2)}" text-anchor="middle">${escapeHtml(result.label || result.id)}</text>
      </a>`
  }).join('')
  const legend = clusters.length ? `
    <div class="vector-map__legend" aria-label="${escapeHtml(clusterLabel)} color groups">
      ${clusters.map((cluster) => `
        <span><i style="--cluster-color: ${cluster.color}" aria-hidden="true"></i>${escapeHtml(cluster.label)} (${cluster.count})</span>`).join('')}
    </div>` : ''

  return `
    <section class="vector-map-panel">
      <div class="vector-map-panel__heading">
        <div><h2>Vector space (2D projection)</h2></div>
        ${connectionStatus(status)}
      </div>
      <div class="vector-map">
        <svg viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img" aria-label="Two-dimensional PCA projection of the search-result vectors">
          <rect class="vector-map__background" x="1" y="1" width="${WIDTH - 2}" height="${HEIGHT - 2}" />
          <g aria-hidden="true">${edges}</g>
          <g>${nodes}</g>
        </svg>
      </div>
      ${legend}
    </section>`
}
