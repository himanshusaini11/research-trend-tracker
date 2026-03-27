<template>
  <div class="h-full flex flex-col">
    <!-- Controls bar -->
    <div class="bg-surface border-b border-border px-6 py-3 flex items-center gap-6 shrink-0">
      <div class="flex items-center gap-3">
        <label class="text-text-muted text-xs uppercase tracking-wider">Top N</label>
        <input
          type="range" min="50" max="1000" step="50"
          v-model.number="topN"
          class="accent-accent-blue w-28"
        />
        <input
          type="number" min="1" max="1000"
          v-model.number="topN"
          class="bg-bg border border-border text-text-primary text-xs rounded px-2 py-1 w-16
                 focus:outline-none focus:border-accent-blue text-center"
        />
      </div>

      <div class="flex items-center gap-2">
        <label class="text-text-muted text-xs uppercase tracking-wider mr-1">Filter</label>
        <button
          v-for="f in filters" :key="f.value"
          @click="trendFilter = f.value"
          :class="[
            'px-3 py-1 rounded text-xs font-medium transition-colors',
            trendFilter === f.value
              ? 'bg-accent-blue text-bg'
              : 'bg-bg border border-border text-text-muted hover:border-accent-blue hover:text-text-primary'
          ]"
        >{{ f.label }}</button>
      </div>

      <div class="flex items-center gap-2">
        <label class="text-text-muted text-xs uppercase tracking-wider mr-1">Model</label>
        <button
          v-for="m in modelViews" :key="m.value"
          @click="modelView = m.value"
          :title="m.title"
          :class="[
            'px-3 py-1 rounded text-xs font-medium transition-colors',
            modelView === m.value
              ? 'bg-accent-blue text-bg'
              : 'bg-bg border border-border text-text-muted hover:border-accent-blue hover:text-text-primary'
          ]"
        >{{ m.label }}</button>
      </div>

      <input
        type="text"
        v-model="searchQuery"
        placeholder="Search concepts…"
        class="bg-bg border border-border text-text-primary text-xs rounded px-3 py-1 w-48
               focus:outline-none focus:border-accent-blue placeholder:text-text-muted"
      />

      <button
        @click="resetZoom"
        class="ml-auto text-xs text-text-muted border border-border px-3 py-1 rounded
               hover:border-accent-blue hover:text-text-primary transition-colors"
      >
        Reset Zoom
      </button>
    </div>

    <!-- Split view: 70% graph / 30% detail -->
    <div class="flex-1 flex overflow-hidden">

      <!-- LEFT: graph canvas -->
      <div class="relative overflow-hidden" style="flex: 0 0 70%; min-width: 0">
        <div v-if="store.loading" class="absolute inset-0 flex items-center justify-center z-10">
          <div class="text-text-muted text-sm">Loading graph…</div>
        </div>
        <div v-else-if="store.error" class="absolute inset-0 flex items-center justify-center z-10">
          <div class="text-accent-red text-sm">{{ store.error }}</div>
        </div>
        <GraphPanel
          ref="panel"
          :concepts="store.concepts"
          :trend-filter="trendFilter"
          :search-query="searchQuery"
          :focus-node-id="focusNodeId"
          :node-count="topN"
          @select="onCanvasSelect"
        />
      </div>

      <!-- RIGHT: detail panel -->
      <div class="shrink-0 overflow-auto bg-surface border-l border-border p-5 space-y-4" style="width: 30%">

        <!-- No selection: stats / breakdown / legend -->
        <template v-if="!selectedNode">
          <div class="bg-bg border border-border rounded-lg p-4">
            <div class="text-text-muted text-xs uppercase tracking-wider mb-2">Dataset</div>
            <template v-if="modelView === 'all'">
              <div class="text-text-primary text-sm font-semibold leading-relaxed">
                200 concepts · 1.77M edges · 145K papers
              </div>
              <div class="text-text-muted text-xs mt-1">LLM / AI · 2022–2024 · llama3.2</div>
            </template>
            <template v-else>
              <div class="text-text-primary text-sm font-semibold leading-relaxed">
                {{ store.concepts.length }} concepts · 559 papers
              </div>
              <div class="text-text-muted text-xs mt-1">Dec 29–31 2024 · qwen3.5:27b extraction</div>
            </template>
          </div>

          <div class="bg-bg border border-border rounded-lg p-4">
            <div class="text-text-muted text-xs uppercase tracking-wider mb-3">Trend Breakdown</div>
            <div class="space-y-2">
              <div v-for="t in trendStats" :key="t.trend" class="flex items-center justify-between">
                <span class="flex items-center gap-2 text-sm" :style="{ color: t.color }">
                  <span class="inline-block w-2.5 h-2.5 rounded-full" :style="{ background: t.color }"></span>
                  {{ t.label }}
                </span>
                <span class="text-text-primary text-sm font-mono">{{ t.count }}</span>
              </div>
            </div>
          </div>

          <p class="text-text-muted/60 text-xs text-center pt-1">
            Click a node to inspect · Dbl-click to zoom
          </p>
        </template>

        <!-- Node selected: detail view -->
        <template v-else>
          <!-- Header -->
          <div class="flex items-start justify-between gap-2">
            <div class="flex-1 min-w-0">
              <h2 class="text-text-primary text-base font-semibold leading-snug break-words">
                {{ selectedNode.display }}
              </h2>
              <span
                class="inline-block mt-1.5 px-2.5 py-0.5 rounded text-xs font-medium capitalize"
                :style="trendBadgeStyle(selectedNode.trend)"
              >{{ selectedNode.trend }}</span>
            </div>
            <button
              @click="clearSelection"
              class="text-text-muted hover:text-text-primary text-xl leading-none shrink-0 mt-0.5"
              title="Clear selection"
            >×</button>
          </div>

          <!-- Metrics -->
          <div class="bg-bg border border-border rounded-lg p-4 grid grid-cols-2 gap-x-4 gap-y-3">
            <div>
              <div class="text-text-muted text-xs mb-0.5">Centrality</div>
              <div class="text-text-primary font-mono text-sm">{{ fmt4(selectedNode.centrality) }}</div>
            </div>
            <div>
              <div class="text-text-muted text-xs mb-0.5">Velocity</div>
              <div class="font-mono text-sm" :style="{ color: selectedNode.velocity >= 0 ? '#00d4aa' : '#ff6b6b' }">
                {{ selectedNode.velocity >= 0 ? '+' : '' }}{{ fmt1(selectedNode.velocity) }}
              </div>
            </div>
            <div>
              <div class="text-text-muted text-xs mb-0.5">Acceleration</div>
              <div class="font-mono text-sm" :style="{ color: selectedNode.acceleration >= 0 ? '#00d4aa' : '#ff6b6b' }">
                {{ selectedNode.acceleration >= 0 ? '+' : '' }}{{ fmt1(selectedNode.acceleration) }}
              </div>
            </div>
            <div>
              <div class="text-text-muted text-xs mb-0.5">Composite</div>
              <div class="text-text-primary font-mono text-sm">{{ fmt2(selectedNode.composite_score) }}</div>
            </div>
          </div>

          <!-- Co-occurring -->
          <div class="bg-bg border border-border rounded-lg p-4">
            <div class="text-text-muted text-xs uppercase tracking-wider mb-3">Top Co-occurring</div>
            <div v-if="coOccurring.length" class="space-y-1.5">
              <div
                v-for="c in coOccurring" :key="c.id"
                class="flex items-center justify-between cursor-pointer px-2 py-1 rounded
                       hover:bg-surface transition-colors"
                @click="selectCoOccurring(c)"
              >
                <span class="text-text-primary text-xs">{{ c.display }}</span>
                <span class="text-text-muted text-[10px] font-mono">{{ c.sharedTokens }}t</span>
              </div>
            </div>
            <div v-else class="text-text-muted text-xs">None in current view</div>
          </div>

          <!-- AI Chat (Fix 6) -->
          <ConceptChat :concept-name="selectedNode.display" />
        </template>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import GraphPanel from '../components/GraphPanel.vue'
import ConceptChat from '../components/ConceptChat.vue'
import { useGraphStore } from '../stores/graph'

const store       = useGraphStore()
const panel       = ref(null)
const topN        = ref(200)
const trendFilter = ref('all')
const searchQuery = ref('')
const selectedNode = ref(null)
const focusNodeId  = ref(null)
const modelView    = ref('all')

const filters = [
  { value: 'all',          label: 'All' },
  { value: 'accelerating', label: 'Accelerating' },
  { value: 'decelerating', label: 'Decelerating' },
  { value: 'stable',       label: 'Stable' },
]

// Model views — each maps to a paper date range (or null for all papers)
const MODEL_VIEWS = {
  all:     { paperFrom: null,         paperTo: null,         label: 'All 145K',    title: 'All 144,997 papers (llama3.2 extraction)' },
  qwen35:  { paperFrom: '2024-12-29', paperTo: '2025-01-01', label: 'qwen3.5:27b', title: '559 papers Dec 29–31 2024 (qwen3.5:27b extraction)' },
}
const modelViews = Object.entries(MODEL_VIEWS).map(([value, m]) => ({ value, ...m }))

const TREND_COLORS = { accelerating: '#00d4aa', stable: '#4a9eff', decelerating: '#ff6b6b' }

const trendStats = computed(() => {
  const counts = { accelerating: 0, stable: 0, decelerating: 0 }
  for (const c of store.concepts) counts[c.trend] = (counts[c.trend] ?? 0) + 1
  return [
    { trend: 'accelerating', label: 'Accelerating', count: counts.accelerating, color: TREND_COLORS.accelerating },
    { trend: 'stable',       label: 'Stable',       count: counts.stable,       color: TREND_COLORS.stable },
    { trend: 'decelerating', label: 'Decelerating', count: counts.decelerating, color: TREND_COLORS.decelerating },
  ]
})

function toTitleCase(s) {
  return s.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

// Co-occurring concepts derived from shared tokens
const coOccurring = computed(() => {
  if (!selectedNode.value) return []
  const selId     = selectedNode.value.id ?? selectedNode.value.concept_name?.toLowerCase() ?? ''
  const selTokens = selId.split(' ').filter(t => t.length > 3)
  if (!selTokens.length) return []

  return store.concepts
    .map(c => {
      const cId     = c.concept_name.toLowerCase()
      if (cId === selId) return null
      const cTokens = cId.split(' ')
      const shared  = selTokens.filter(t => cTokens.includes(t))
      if (!shared.length) return null
      return {
        id:              cId,
        concept_name:    cId,
        display:         toTitleCase(cId),
        sharedTokens:    shared.length,
        trend:           c.trend,
        velocity:        c.velocity,
        acceleration:    c.acceleration,
        composite_score: c.composite_score,
        centrality:      c.centrality,
      }
    })
    .filter(Boolean)
    .sort((a, b) => b.sharedTokens - a.sharedTokens)
    .slice(0, 8)
})

function trendBadgeStyle(trend) {
  const map = {
    accelerating: { background: 'rgba(0,212,170,0.15)',   color: '#00d4aa' },
    decelerating: { background: 'rgba(255,107,107,0.15)', color: '#ff6b6b' },
    stable:       { background: 'rgba(74,158,255,0.15)',  color: '#4a9eff' },
  }
  return map[trend] ?? map.stable
}

const fmt1 = v => v != null ? Number(v).toFixed(1) : '—'
const fmt2 = v => v != null ? Number(v).toFixed(2) : '—'
const fmt4 = v => v != null ? Number(v).toFixed(4) : '—'

function resetZoom() { panel.value?.resetZoom() }

function onCanvasSelect(node) {
  selectedNode.value = node
  focusNodeId.value  = node?.id ?? null
}

function selectCoOccurring(c) {
  selectedNode.value = c
  focusNodeId.value  = c.id
}

function clearSelection() {
  selectedNode.value = null
  focusNodeId.value  = null
}

function loadConcepts() {
  const { paperFrom, paperTo } = MODEL_VIEWS[modelView.value]
  store.fetchConcepts(topN.value, trendFilter.value, paperFrom, paperTo)
}

// topN is handled by GraphPanel's delta-fetch — only full-refetch on filter/model change
watch([trendFilter, modelView], loadConcepts)
onMounted(loadConcepts)
</script>
