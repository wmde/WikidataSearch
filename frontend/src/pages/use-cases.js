import { bindInternalLinks, header, icon } from '../components.js'

const developerCases = [
  {
    icon: 'nodes',
    title: 'GraphRAG',
    description: "Combine semantic retrieval with Wikidata's structured graph to answer complex questions with references.",
    example: 'A user asks about novels exploring gender themes that won awards. The system uses semantic search to find relevant works, follows graph connections to retrieve award statements, and returns winning novels with citations.',
  },
  {
    icon: 'bolt',
    title: 'Text to Wikidata Entities',
    description: 'Link text mentions to the correct Wikidata items by combining keyword matching with semantic similarity.',
    example: 'A news article mentions “Paris” while discussing events in Texas. The system identifies multiple Paris entities, compares context similarity, and links to Paris, Texas (Q830149) instead of Paris, France (Q90).',
  },
  {
    icon: 'database',
    title: 'Similarity Based Topic Classification',
    description: 'Classify text or Wikidata items by comparing them to predefined topic anchors in semantic space.',
    example: 'A developer defines topics such as “climate science” and “modern literature” using Wikidata items. New text is compared against these anchors, assigned topics based on similarity scores, and can be zero-shot tagged.',
  },
  {
    icon: 'clipboard',
    title: 'Fact Checking with Wikidata',
    description: 'Verify claims by comparing them against Wikidata items and their referenced statements.',
    example: 'A user submits “Marie Curie won two Nobel Prizes in physics.” The system finds the entity, checks referenced facts, and returns which parts are supported, contradicted, or need context.',
  },
]

const editorCases = [
  {
    icon: 'search',
    title: 'Semantic Gap Discovery',
    description: 'Identify Wikidata items that are likely missing important statements by comparing them to similar items in the same domain.',
    example: 'An editor selects “instance of: film” and an item. The tool finds similar films by meaning and highlights commonly present properties that are missing, helping the editor decide what to add.',
  },
  {
    icon: 'link',
    title: 'Connect Wikimedia Content to Wikidata',
    description: 'Match Wikipedia articles and other Wikimedia content to the right Wikidata items using semantic search and similarity.',
    example: 'An editor creates a Wikipedia article that needs to be linked to Wikidata. The tool uses its title and abstract to find and rank candidate items, placing the most likely match first even when labels differ across languages.',
  },
  {
    icon: 'code',
    title: 'Grounded SPARQL Generation',
    description: 'Explore relevant items, properties, and modeling patterns to give an LLM the context it needs to generate proper SPARQL queries.',
    example: 'Given “Which African cities have more than 1 million inhabitants?”, the system first finds relevant Wikidata items and properties, examines how cities, continents, and population values are modeled. It provides those IDs and relationships to the LLM to generate the SPARQL query.',
  },
  {
    icon: 'layers',
    title: 'Semantic and Graph Explorer',
    description: "Interact with Wikidata's data through a combination of semantic similarity and graph relationships.",
    example: 'Vector search groups items by semantic similarity, surfacing conceptually related entities. The Wikidata graph provides structured relationships, letting users move from semantic proximity to explicit links.',
  },
]

function useCaseCard(item) {
  return `
    <article class="use-case-card">
      <span class="round-icon round-icon--solid">${icon(item.icon)}</span>
      <div>
        <h3>${item.title}</h3>
        <p>${item.description}</p>
        <p class="use-case-card__example">${item.example}</p>
      </div>
    </article>`
}

export function renderUseCases(root, { navigate }) {
  document.title = 'Use Cases · Wikidata Vector Database'
  root.innerHTML = `
    ${header('use-cases')}
    <main id="main-content" class="use-cases-page">
      <section class="use-cases-hero">
        <div class="container">
          <h1>Use Cases &amp; Possibilities</h1>
          <p>Explore ideas for what you can build with the Wikidata Vector Database.</p>
        </div>
      </section>

      <section class="use-case-group">
        <div class="container container--content">
          <h2>For AI Developers</h2>
          <div class="use-case-grid">${developerCases.map(useCaseCard).join('')}</div>
        </div>
      </section>

      <section class="use-case-group">
        <div class="container container--content">
          <h2>For Wikidata Editors</h2>
          <div class="use-case-grid">${editorCases.map(useCaseCard).join('')}</div>
        </div>
      </section>

      <section class="community-callout">
        <div class="container container--content">
          <div class="community-callout__inner">
            <h2>Show the community what you've built!</h2>
            <p>Are you using Wikidata Vector Search in a real project?<br />Tell us about your idea, your use case, and how vector search helps you work with Wikidata.</p>
            <a class="button button--primary button--pill" href="https://wikimedia.sslsurvey.de/Wikidata-Vector-DB-Feedback-Alpha-release" target="_blank" rel="noreferrer">＋&nbsp; Share your project</a>
          </div>
        </div>
      </section>

      <section class="section use-cases-cta">
        <div class="container">
          <h2>Ready to start exploring?</h2>
          <p>Try the Wikidata Vector Search and find relevant entities using natural language.</p>
          <a class="button button--primary" href="/search" data-route>Start Searching</a>
        </div>
      </section>
    </main>`

  bindInternalLinks(root, navigate)
}
