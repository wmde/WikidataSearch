<template>
  <main class="w-screen min-h-screen bg-light-content dark:bg-dark-content overflow-auto">

    <!-- Settings Modal -->
    <Settings v-if="showSettings" @close="showSettings = false" />

    <!-- Home Icon -->
    <Icon
      class="text-4xl absolute right-4 top-4 cursor-pointer text-light-text dark:text-dark-text hover:text-light-distinct-text dark:hover:text-dark-distinct-text transition-colors"
      icon="mdi:home"
      @click="showSettings = true"
    />

    <div class="max-w-screen-2xl mx-auto px-4 sm:px-8 md:px-12 py-12 space-y-12">

      <!-- Header -->
      <div class="flex flex-col sm:flex-row items-center gap-6 text-center sm:text-left justify-center">
        <a href="https://www.wikidata.org/wiki/Wikidata:Embedding_Project" target="_blank" class="shrink-0">
          <img
            src="https://upload.wikimedia.org/wikipedia/commons/0/01/Wikidata_Embedding_Project_Logo.png"
            alt="Wikidata Embedding Project Logo"
            class="h-24 object-contain"
          />
        </a>
        <div>
          <h1 class="text-5xl font-bold py-2">
              Wikidata Vector Database
          </h1>
        </div>
      </div>

      <div class="flex justify-center w-full">
        <div class="flex flex-col w-full md:w-4/5 space-y-4">

          <!-- Search bar + Info -->
          <div class="flex flex-nowrap items-center gap-3">
            <!-- Search bar (unchanged design) -->
            <div class="relative flex-1 min-w-0 text-2xl rounded-lg bg-light-menu dark:bg-dark-menu elem-shadow-sm">
              <input
                v-model="inputText"
                type="text"
                class="w-full pl-4 pr-24 bg-transparent rounded-lg h-12 placeholder:text-light-distinct-text dark:placeholder:text-dark-distinct-text text-light-text dark:text-dark-text"
                :placeholder="$t('chat-prompt')"
                autocomplete="off"
                @keyup.enter="inputText.length > 0 ? search() : {}"
                @focus="inputFocused = true"
                @blur="inputFocused = false"
              />
              <!-- Send icon stays inside the bar -->
              <Icon
                class="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer"
                :class="{
                  'text-light-text dark:text-dark-text': inputFocused && inputText.length === 0,
                  'text-light-text dark:text-dark-text hover:text-light-distinct-text dark:hover:text-dark-distinct-text':
                    inputFocused && inputText.length > 0,
                  'text-light-distinct-text dark:text-dark-distinct-text': !inputFocused
                }"
                icon="fluent:send-24-filled"
                size="2em"
                @click="inputText.length > 0 ? search() : {}"
              />
            </div>

            <!-- Info icon + How to query -->
            <div class="relative group inline-flex items-center shrink-0" tabindex="0" aria-label="How to search">
              <Icon
                icon="fluent:info-16-regular"
                class="text-blue-600 dark:text-blue-400 cursor-pointer"
                size="2.5em"
              />
              <div
                class="absolute right-0 top-full mt-2 w-[28rem] max-w-[90vw] p-3 bg-light-menu dark:bg-dark-menu
                      text-sm text-light-text dark:text-dark-text rounded shadow-lg z-20 opacity-0
                      group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity pointer-events-none"
                role="tooltip"
              >
                <p class="font-semibold mb-2">How vector search works</p>

                <p class="text-sm mb-1">What it does:</p>
                <ul class="list-disc pl-5 space-y-1">
                  <li>Explore Wikidata entities</li>
                  <li>Fuzzy search by meaning and context</li>
                  <li>Surface similar items</li>
                </ul>

                <p class="text-sm mt-2 mb-1">What it doesn't do:</p>
                <ul class="list-disc pl-5 space-y-1">
                  <li>Answer questions (Use results to investigate further)</li>
                  <li>Return complete lists (Use SPARQL for that)</li>
                </ul>

                <p class="text-sm mt-2 mb-1">Examples:</p>
                <ul class="list-disc pl-5 space-y-1">
                  <li><code>English science-fiction novel</code></li>
                  <li><code>Q42</code></li>
                  <li><code>Who wrote Hitchhiker's Guide to the Galaxy?</code></li>
                </ul>
              </div>
            </div>
          </div>

          <!-- Controls -->
          <div class="flex items-center justify-between gap-4 flex-wrap text-sm text-light-text dark:text-dark-text">

            <!-- Language Selector -->
            <div class="flex flex-col md:flex-row items-start md:items-center gap-4 text-sm text-light-text dark:text-dark-text">
              <span class="font-medium">Language:</span>

              <!-- Radios for vectordb_langs -->
              <div class="flex gap-4 items-center flex-wrap">
                <label
                  v-for="lang in vectordbLangs"
                  :key="lang"
                  class="flex items-center gap-1 cursor-pointer px-2 py-1 border rounded-lg hover:bg-light-menu dark:hover:bg-dark-menu transition-colors"
                >
                  <input type="radio" :value="lang" v-model="selectedLanguage" class="accent-blue-600" />
                  {{ lang.toUpperCase() }}
                </label>
              </div>

              <!-- Dropdown for other languages -->
              <div v-if="otherLanguages.length > 0" class="flex items-center gap-2 relative group">
                <select
                  v-model="selectedLanguage"
                  class="rounded-lg border border-light-distinct-text dark:border-dark-distinct-text bg-light-menu dark:bg-dark-menu text-light-text dark:text-dark-text h-8 px-2"
                >
                  <option v-for="lang in otherLanguages" :key="lang" :value="lang">
                    {{ lang.toUpperCase() }}
                  </option>
                </select>

                <!-- Info Icon Tooltip -->
                <div>
                  <Icon
                    icon="fluent:info-16-regular"
                    class="text-blue-600 dark:text-blue-400 cursor-pointer ml-1"
                  />
                  <div
                    class="absolute left-1/2 -translate-x-1/2 top-full mt-1 w-80 p-3 bg-light-menu dark:bg-dark-menu text-sm text-light-text dark:text-dark-text rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity z-10 pointer-events-none"
                    role="tooltip"
                  >
                    <p class="font-semibold mb-3">Language Selection Info</p>
                    <p class="mb-2">
                      <strong>Radio buttons</strong> represent languages with dedicated vector datasets. Selecting one queries vectors in that language.
                    </p>
                    <p class="mb-2">
                      <strong>Dropdown menu</strong> shows other languages without dedicated vectors. Selecting one will translate your query to English and search the full vector database.
                    </p>
                    <p>
                      The <strong>'ALL'</strong> option queries the full vector database regardless of language. More languages will be added as dedicated vectors in future releases.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <!-- Items / Properties toggle -->
            <div class="flex items-center gap-2 relative group">
              <span class="font-medium">Search type:</span>
              <div class="inline-flex h-8 rounded-lg overflow-hidden border border-light-distinct-text dark:border-dark-distinct-text">
                <button
                  class="px-3 h-full flex items-center text-base font-medium"
                  :class="searchType === 'item'
                    ? 'bg-light-menu dark:bg-dark-menu text-light-text dark:text-dark-text'
                    : 'bg-transparent text-light-distinct-text dark:text-dark-distinct-text'"
                  @click="searchType = 'item'"
                  type="button"
                >
                  Items
                </button>
                <button
                  class="px-3 h-full flex items-center text-base font-medium"
                  :class="searchType === 'property'
                    ? 'bg-light-menu dark:bg-dark-menu text-light-text dark:text-dark-text'
                    : 'bg-transparent text-light-distinct-text dark:text-dark-distinct-text'"
                  @click="searchType = 'property'"
                  type="button"
                >
                  Properties
                </button>
              </div>

              <div>
                <Icon
                  icon="fluent:info-16-regular"
                  class="text-blue-600 dark:text-blue-400 cursor-pointer ml-1"
                />
                <div
                  class="absolute left-1/2 -translate-x-1/2 top-full mt-1 w-80 p-3 bg-light-menu dark:bg-dark-menu text-sm text-light-text dark:text-dark-text rounded shadow-lg opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity z-10 pointer-events-none"
                  role="tooltip"
                >
                  <p class="font-semibold mb-2">Search Type Info</p>
                  <p><strong>Items</strong> searches Wikidata entities (QIDs), while <strong>Properties</strong> searches Wikidata properties (PIDs).</p>
                </div>
              </div>
            </div>

            <!-- Item scope toggle -->
            <div v-if="searchType === 'item'" class="flex items-center gap-2 relative group">
              <span class="font-medium">Scope:</span>
              <div class="inline-flex h-8 rounded-lg overflow-hidden border border-light-distinct-text dark:border-dark-distinct-text">
                <button
                  v-for="option in itemScopeOptions"
                  :key="option.value"
                  class="px-3 h-full flex items-center text-base font-medium"
                  :class="itemScope === option.value
                    ? 'bg-light-menu dark:bg-dark-menu text-light-text dark:text-dark-text'
                    : 'bg-transparent text-light-distinct-text dark:text-dark-distinct-text'"
                  :aria-pressed="itemScope === option.value"
                  @click="itemScope = option.value"
                  type="button"
                >
                  {{ option.label }}
                </button>
              </div>

              <div>
                <Icon
                  icon="fluent:info-16-regular"
                  class="text-blue-600 dark:text-blue-400 cursor-pointer ml-1"
                />
                <div
                  class="absolute left-1/2 -translate-x-1/2 top-full mt-1 w-80 p-3 bg-light-menu dark:bg-dark-menu text-sm text-light-text dark:text-dark-text rounded shadow-lg opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity z-10 pointer-events-none"
                  role="tooltip"
                >
                  <p class="font-semibold mb-2">Item Scope Info</p>
                  <p><strong>With sitelinks</strong> searches items linked to Wikipedia pages.</p>
                  <p><strong>No sitelinks</strong> searches items without linked Wikipedia pages.</p>
                  <p><strong>All</strong> searches both kinds of items.</p>
                </div>
              </div>
            </div>

          </div>

          <!-- Rerank toggle -->
          <div class="flex items-center gap-2 relative group text-sm text-light-text dark:text-dark-text">
            <span class="font-medium">Rerank:</span>
            <button
              class="inline-flex h-8 items-center rounded-lg border px-3 font-medium transition-colors"
              :class="useRerank
                ? 'border-blue-600 bg-blue-600 text-white'
                : 'border-light-distinct-text dark:border-dark-distinct-text bg-transparent text-light-distinct-text dark:text-dark-distinct-text hover:bg-light-menu dark:hover:bg-dark-menu'"
              @click="useRerank = !useRerank"
              type="button"
            >
              {{ useRerank ? 'ON' : 'OFF' }}
            </button>

            <div class="relative">
              <Icon
                icon="fluent:info-16-regular"
                class="text-blue-600 dark:text-blue-400 cursor-pointer ml-1"
              />
              <div
                class="absolute left-1/2 -translate-x-1/2 top-full mt-1 w-80 p-3 bg-light-menu dark:bg-dark-menu text-sm text-light-text dark:text-dark-text rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity z-10 group-focus-within:opacity-100 pointer-events-none"
                role="tooltip"
              >
                <p class="font-semibold mb-2">Rerank Info</p>
                <p>Rerank applies an extra relevance model to reorder top results, which can improve quality but increases response time.</p>
              </div>
            </div>
          </div>

          <!-- Prototype Warning -->
          <p class="text-sm text-light-text dark:text-dark-text">
            ⚠️ This tool is in early testing, and results may be incomplete or inaccurate. Your queries are sent to a third-party service (JinaAI) for processing, and we store them for up to 90 days for quality improvements. We welcome your feedback! Please help us improve by filling out
            <a href="https://wikimedia.sslsurvey.de/Wikidata-Vector-DB-Feedback-Alpha-release" target="_blank"
               class="text-blue-600 dark:text-blue-400 hover:underline">
              our survey
            </a>.
          </p>

          <!-- Error Message -->
          <p v-if="error && error.length" class="mt-0 text-sm text-red-500">{{ error }}</p>

        </div>
      </div>

      <!-- Response -->
      <div v-if="response" class="flex justify-center w-full">
        <div class="flex flex-col w-full md:w-4/5 space-y-7">
          <FieldAnswer :response="response" :isLoading="false" />
        </div>
      </div>

      <!-- Loading -->
      <div v-else-if="displayResponse && !response" class="flex justify-center w-full">
        <div class="flex flex-col w-full md:w-4/5 space-y-5">
          <FieldAnswer :isLoading="true" />
        </div>
      </div>

    </div>
  </main>
</template>

<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { ref, onMounted } from 'vue'
import FieldAnswer from '../components/field/FieldAnswer.vue'
import type { ResponseObject } from '../types/response-object.d.ts'
import Settings from '../components/Settings.vue'

const inputText = ref('')
const response = ref<ResponseObject[]>()
const error = ref<string>()
const displayResponse = ref(false)
const inputFocused = ref(false)
const showSettings = ref(true)
const searchType = ref<'item' | 'property'>('item')
const itemScope = ref<'with_sitelinks' | 'no_sitelinks' | 'all'>('with_sitelinks')
const itemScopeOptions = [
  { value: 'with_sitelinks' as const, label: 'With sitelinks' },
  { value: 'no_sitelinks' as const, label: 'No sitelinks' },
  { value: 'all' as const, label: 'All' },
]
const useRerank = ref(false)

// Languages
const vectordbLangs = ref<string[]>([])
const otherLanguages = ref<string[]>([])
const selectedLanguage = ref<string>('all')

// Fetch /languages on mount
onMounted(async () => {
  try {
    const res = await fetch('/languages')
    const data = await res.json()
    vectordbLangs.value = ['all', ...data.vectordb_langs]
    otherLanguages.value = data.other_langs
    if (!vectordbLangs.value.includes(selectedLanguage.value.toLowerCase())) {
      selectedLanguage.value = 'all'
    }
  } catch (e) {
    console.error('Failed to fetch languages', e)
  }
})

async function search() {
  response.value = undefined
  error.value = undefined
  displayResponse.value = true

  let lang = selectedLanguage.value.toLowerCase() || 'all'

  try {
    const base = searchType.value === 'property' ? '/property/query' : '/item/query'
    const params = new URLSearchParams({
      query: inputText.value,
      lang,
      rerank: String(useRerank.value),
    })
    if (searchType.value === 'item') {
      params.set('scope', itemScope.value)
    }
    const fetchResult = await fetch(`${base}/?${params.toString()}`)

    const jsonResponse = await fetchResult.json()

    if (!lang || lang === 'all') {
      lang = 'en'
    }

    // Add the user query and lang to each result for feedback tracking
    response.value = jsonResponse.map((r: any) => ({
      ...r,
      id: r.QID ?? r.PID,
      query: inputText.value,
      lang: lang
    }))
  } catch (e) {
    displayResponse.value = false
    console.error(e)
    error.value = 'Sorry. Failed to retrieve response.'
  }
}
</script>
