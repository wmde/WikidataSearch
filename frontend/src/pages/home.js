import { bindInternalLinks, escapeHtml, header, icon, searchBar } from '../components.js'

function initializeNewsletterForm(root) {
  const form = root.querySelector('[data-newsletter-form]')

  form?.addEventListener('submit', () => {
    form.querySelector('[name="zc_spmSubmit"]')?.remove()
  })
}

const examples = [
  {
    label: 'Question-based',
    query: "Who wrote The Hitchhiker's Guide to the Galaxy?",
    expected: 'Finds Wikidata items that help answer the question',
  },
  {
    label: 'Context-rich',
    query: 'British science fiction writer and humorist active in the late 20th century',
    expected: 'Finds entities that match the description',
  },
  {
    label: 'ID-based',
    query: 'Q42',
    expected: 'Finds entities that are semantically similar to the given item',
  },
]

const featuredUseCases = [
  {
    icon: 'search',
    title: 'Retrieve likely entities',
    description: 'Describe a concept and find relevant Wikidata entities, even when wording differs.',
    capability: 'Semantic retrieval',
  },
  {
    icon: 'ranking',
    title: 'Rank entities by context',
    description: 'Use surrounding text to sort candidates and bring the intended Wikidata entity to the top.',
    capability: 'Context-aware ranking',
  },
  {
    icon: 'layers',
    title: 'Explore semantic relationships',
    description: 'Find conceptually similar entities, even when Wikidata does not explicitly connect them.',
    capability: 'Similarity exploration',
  },
]

export function renderHome(root, { navigate }) {
  document.title = 'Wikidata Vector Database'
  root.innerHTML = `
    ${header('start')}
    <main id="main-content">
      <section class="search-intro section section--muted">
        <div class="container container--search">
          <aside class="info-panel" data-info-panel>
            <span class="info-panel__icon">${icon('search')}</span>
            <div>
              <h1>How Vector Search Works</h1>
              <p>Vector search uses language models to measure semantic similarity between a natural-language query and Wikidata entities. Unlike SPARQL, which is designed for precise and structured retrieval, vector search supports exploration and discovery.</p>
            </div>
            <button class="icon-button info-panel__close" type="button" aria-label="Dismiss explanation" data-dismiss-info>×</button>
          </aside>

          ${searchBar()}

          <div class="examples" aria-labelledby="example-title">
            <p id="example-title" class="examples__title">Example queries:</p>
            <div class="examples__list">
              ${examples.map((example) => `
                <div class="example-row">
                  <span class="example-row__label">${example.label}</span>
                  <button class="example-query" type="button" data-query="${escapeHtml(example.query)}">“${escapeHtml(example.query)}”</button>
                  <span class="example-row__check">${icon('check')}</span>
                  <span class="example-row__expected">Expected: ${example.expected}</span>
                </div>`).join('')}
            </div>
          </div>
        </div>
      </section>

      <section class="section section--white">
        <div class="container">
          <div class="section-heading">
            <h2>Core Capabilities</h2>
            <p class="section-heading__kicker">Retrieve, rank, and explore</p>
            <p>Use semantic similarity and context to find likely Wikidata entities, identify the intended match, and surface relationships beyond explicit graph connections.</p>
          </div>

          <div class="card-grid card-grid--three featured-cases">
            ${featuredUseCases.map((item) => `
              <article class="feature-card">
                <span class="round-icon round-icon--solid">${icon(item.icon)}</span>
                <div class="feature-card__body">
                  <h3>${item.title}</h3>
                  <p>${item.description}</p>
                  <div class="feature-card__meta"><span class="tag">${item.capability}</span></div>
                </div>
              </article>`).join('')}
          </div>

          <div class="section-action">
            <a class="button button--primary button--rounded" href="/use-cases" data-route>
              See Practical Use Cases ${icon('arrow')}
            </a>
          </div>
        </div>
      </section>

      <section class="section section--soft" id="resources">
        <div class="container">
          <div class="section-heading">
            <h2>Developer Resources</h2>
            <p>Everything you need to integrate and build with the Wikidata Vector Database. Access API documentation, project information, and the full vector dataset.</p>
          </div>

          <div class="card-grid card-grid--three resource-grid">
            <article class="resource-card">
              <span class="round-icon">${icon('document')}</span>
              <h3>API Documentation</h3>
              <p>Complete API reference, endpoints, parameters, and response models</p>
              <a class="button button--primary" href="/docs">Read Docs</a>
            </article>
            <article class="resource-card">
              <span class="round-icon">${icon('code')}</span>
              <h3>Project Page</h3>
              <p>Learn about the project, architecture, and community contributions</p>
              <a class="button button--primary" href="https://www.wikidata.org/wiki/Wikidata:Vector_Database" target="_blank" rel="noreferrer">View Project</a>
            </article>
            <article class="resource-card">
              <span class="round-icon">${icon('download')}</span>
              <h3>Download Dataset</h3>
              <p>Get the full Wikidata entity embedding dataset for local analysis and custom applications</p>
              <a class="button button--primary" href="https://huggingface.co/datasets/philippesaade/Wikidata_Vectors_0.2" target="_blank" rel="noreferrer">View Dataset</a>
            </article>
          </div>
          <p class="section-link"><a href="https://github.com/wmde/WikidataSearch" target="_blank" rel="noreferrer">View on GitHub →</a></p>
        </div>
      </section>

      <section class="section section--white newsletter">
        <div class="container newsletter__inner">
          <span class="round-icon round-icon--primary">${icon('send')}</span>
          <h2>Stay Updated with Our Newsletter</h2>
          <p>Get the latest updates about new features, improvements, community projects, and technical insights delivered to your inbox.</p>
          <form
            class="newsletter__form"
            method="POST"
            id="zcampaignOptinForm"
            action="https://njyha-zcmp.maillist-manage.eu/weboptin.zc"
            target="_zcSignup"
            data-newsletter-form
          >
            <label class="sr-only" for="newsletter-name">Name (optional)</label>
            <input
              id="newsletter-name"
              name="FIRSTNAME"
              type="text"
              autocomplete="given-name"
              placeholder="Name (optional)"
            />
            <label class="sr-only" for="newsletter-email">Email address</label>
            <input
              id="newsletter-email"
              name="CONTACT_EMAIL"
              type="email"
              autocomplete="email"
              placeholder="you@example.org"
              required
            />
            <button class="button button--primary" type="submit" name="SIGNUP_SUBMIT_BUTTON" value="Sign Up">Subscribe</button>

            <input type="hidden" name="submitType" value="optinCustomView" />
            <input type="hidden" name="emailReportId" value="" />
            <input type="hidden" name="formType" value="QuickForm" />
            <input type="hidden" name="zx" value="14aeb08ab4" />
            <input type="hidden" name="zcvers" value="2.0" />
            <input type="hidden" name="oldListIds" value="" />
            <input type="hidden" name="mode" value="OptinCreateView" />
            <input type="hidden" name="zcld" value="11725ed2aaa5a039" />
            <input type="hidden" name="zctd" value="11725ed2a95dab75" />
            <input type="hidden" name="zc_trackCode" value="ZCFORMVIEW" />
            <input type="hidden" name="zc_formIx" value="3zc80e19654d469f237ecd012af329144237f6af6929bc4e260b83da836ba69c95" />
            <input type="hidden" name="scriptless" value="yes" />
            <input type="hidden" name="zc_spmSubmit" value="ZCSPMSUBMIT" />
          </form>
          <p class="newsletter__consent">By subscribing, I agree that Wikimedia may contact me by email based on my consent (Art. 6 para. 1 lit. a GDPR) until revoked. I can revoke my consent at any time with effect for the future.</p>
        </div>
      </section>
    </main>

    <footer class="site-footer">
      <div class="container">
        <strong>Partners</strong>
        <div class="site-footer__partners">
          <a href="https://jina.ai/" target="_blank" rel="noreferrer">Jina AI</a>
          <a href="https://www.datastax.com/" target="_blank" rel="noreferrer"><strong>DATASTAX</strong></a>
        </div>
      </div>
    </footer>

    `

  bindInternalLinks(root, navigate)

  root.querySelector('[data-dismiss-info]')?.addEventListener('click', () => {
    root.querySelector('[data-info-panel]')?.remove()
  })

  const submitSearch = (query) => {
    const cleanedQuery = query.trim()
    if (cleanedQuery) navigate(`/search?q=${encodeURIComponent(cleanedQuery)}`)
  }

  root.querySelector('[data-search-form]')?.addEventListener('submit', (event) => {
    event.preventDefault()
    submitSearch(new FormData(event.currentTarget).get('q') || '')
  })

  root.querySelectorAll('[data-query]').forEach((button) => {
    button.addEventListener('click', () => submitSearch(button.dataset.query || ''))
  })

  initializeNewsletterForm(root)
}
