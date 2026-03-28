<template>
  <div class="h-full flex flex-col">
    <!-- Controls bar -->
    <div class="bg-surface border-b border-border px-6 py-3 flex items-center gap-6 shrink-0 flex-wrap">

      <!-- Graph mode tabs (hidden for demo/unauthenticated) -->
      <div v-if="!auth.isDemo && auth.isValid" class="flex items-center border border-border rounded-lg overflow-hidden shrink-0">
        <button
          v-for="tab in graphTabs" :key="tab.value"
          @click="gState.graphMode = tab.value"
          :class="[
            'px-3 py-1.5 text-xs font-medium transition-colors',
            gState.graphMode === tab.value
              ? 'bg-accent-blue text-bg'
              : 'text-text-muted hover:text-text-primary',
          ]"
        >{{ tab.label }}</button>
      </div>

      <template v-if="gState.graphMode === 'global'">
        <!-- Top N -->
        <div class="flex items-center gap-3">
          <label class="text-text-muted text-xs uppercase tracking-wider">Top N</label>
          <input
            type="range" min="50" max="1000" step="50"
            v-model.number="gState.topN"
            class="accent-accent-blue w-28"
          />
          <input
            type="number" min="1" max="1000"
            v-model.number="gState.topN"
            class="bg-bg border border-border text-text-primary text-xs rounded px-2 py-1 w-16
                   focus:outline-none focus:border-accent-blue text-center"
          />
        </div>

        <!-- Trend filter -->
        <div class="flex items-center gap-2">
          <label class="text-text-muted text-xs uppercase tracking-wider mr-1">Filter</label>
          <button
            v-for="f in filters" :key="f.value"
            @click="gState.trendFilter = f.value"
            :class="[
              'px-3 py-1 rounded text-xs font-medium transition-colors',
              gState.trendFilter === f.value
                ? 'bg-accent-blue text-bg'
                : 'bg-bg border border-border text-text-muted hover:border-accent-blue hover:text-text-primary'
            ]"
          >{{ f.label }}</button>
        </div>

        <!-- Model view -->
        <div class="flex items-center gap-2">
          <label class="text-text-muted text-xs uppercase tracking-wider mr-1">Model</label>
          <button
            v-for="m in modelViews" :key="m.value"
            @click="gState.modelView = m.value"
            :title="m.title"
            :class="[
              'px-3 py-1 rounded text-xs font-medium transition-colors',
              gState.modelView === m.value
                ? 'bg-accent-blue text-bg'
                : 'bg-bg border border-border text-text-muted hover:border-accent-blue hover:text-text-primary'
            ]"
          >{{ m.label }}</button>
        </div>
      </template>

      <template v-else>
        <!-- My Graph: dynamic slider -->
        <div v-if="userTotalConcepts > 0" class="flex items-center gap-3">
          <label class="text-text-muted text-xs uppercase tracking-wider">Concepts</label>
          <input
            type="range" :min="1" :max="userTotalConcepts" :step="userSliderStep"
            v-model.number="gState.userTopN"
            class="accent-accent-blue w-28"
          />
          <input
            type="number" :min="1" :max="userTotalConcepts"
            v-model.number="gState.userTopN"
            class="bg-bg border border-border text-text-primary text-xs rounded px-2 py-1 w-16
                   focus:outline-none focus:border-accent-blue text-center"
          />
          <span class="text-text-muted text-xs">/ {{ userTotalConcepts }}</span>
        </div>
      </template>

      <!-- Search (both modes) -->
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
      >Reset Zoom</button>
    </div>

    <!-- Split view: 70% graph / 30% detail -->
    <div class="flex-1 flex overflow-hidden">

      <!-- LEFT: graph canvas -->
      <div class="relative overflow-hidden" style="flex: 0 0 70%; min-width: 0">

        <!-- My Graph: empty state -->
        <div v-if="gState.graphMode === 'user' && userTotalConcepts === 0 && !userLoading"
          class="absolute inset-0 flex flex-col items-center justify-center gap-4 text-center px-8">
          <div class="text-4xl">📄</div>
          <p class="text-text-primary font-medium">No uploaded papers yet</p>
          <p class="text-text-muted text-sm">Upload your own research PDFs to build a personal knowledge graph.</p>
          <button @click="$router.push('/upload')"
            class="px-5 py-2 bg-accent-blue text-bg text-xs font-medium rounded-lg hover:bg-blue-400 transition-colors">
            Upload Papers →
          </button>
        </div>

        <div v-else-if="activeLoading" class="absolute inset-0 flex items-center justify-center z-10">
          <div class="text-text-muted text-sm">Loading graph…</div>
        </div>
        <div v-else-if="activeError" class="absolute inset-0 flex items-center justify-center z-10">
          <div class="text-accent-red text-sm">{{ activeError }}</div>
        </div>

        <GraphPanel
          ref="panel"
          :concepts="activeConcepts"
          :trend-filter="gState.graphMode === 'global' ? gState.trendFilter : 'all'"
          :search-query="searchQuery"
          :focus-node-id="focusNodeId"
          :node-count="gState.graphMode === 'global' ? gState.topN : gState.userTopN"
          @select="onCanvasSelect"
        />
      </div>

      <!-- RIGHT: detail panel -->
      <div class="shrink-0 overflow-auto bg-surface border-l border-border p-5 space-y-4" style="width: 30%">

        <template v-if="!selectedNode">
          <div class="bg-bg border border-border rounded-lg p-4">
            <div class="text-text-muted text-xs uppercase tracking-wider mb-2">
              {{ gState.graphMode === 'global' ? 'Dataset' : 'My Graph' }}
            </div>
            <template v-if="gState.graphMode === 'global'">
              <template v-if="gState.modelView === 'all'">
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
            </template>
            <template v-else>
              <div class="text-text-primary text-sm font-semibold leading-relaxed">
                {{ userTotalConcepts }} concepts from your uploads
              </div>
              <div class="text-text-muted text-xs mt-1">Extracted via TF-IDF · personal graph</div>
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

        <!-- Node selected -->
        <template v-else>
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
            <button @click="clearSelection"
              class="text-text-muted hover:text-text-primary text-xl leading-none shrink-0 mt-0.5"
            >×</button>
          </div>

          <div class="bg-bg border border-border rounded-lg p-4 grid grid-cols-2 gap-x-4 gap-y-3">
            <div>
              <div class="text-text-muted text-xs mb-0.5">Centrality</div>
              <div class="text-text-primary font-mono text-sm">{{ fmt4(selectedNode.centrality) }}</div>
            </div>
            <div>
              <div class="text-text-muted text-xs mb-0.5">Velocity</div>
              <div class="font-mono text-sm" :style="{ color: selectedNode.velocity >= 0 ? 'var(--canvas-accelerating)' : 'var(--canvas-decelerating)' }">
                {{ selectedNode.velocity >= 0 ? '+' : '' }}{{ fmt1(selectedNode.velocity) }}
              </div>
            </div>
            <div>
              <div class="text-text-muted text-xs mb-0.5">Acceleration</div>
              <div class="font-mono text-sm" :style="{ color: selectedNode.acceleration >= 0 ? 'var(--canvas-accelerating)' : 'var(--canvas-decelerating)' }">
                {{ selectedNode.acceleration >= 0 ? '+' : '' }}{{ fmt1(selectedNode.acceleration) }}
              </div>
            </div>
            <div>
              <div class="text-text-muted text-xs mb-0.5">Composite</div>
              <div class="text-text-primary font-mono text-sm">{{ fmt2(selectedNode.composite_score) }}</div>
            </div>
          </div>

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
                <span class="text-text-muted text-[10px] font-mono">{{ c.sharedTokens }}{{ gState.graphMode === 'user' ? 'w' : 't' }}</span>
              </div>
            </div>
            <div v-else class="text-text-muted text-xs">None found</div>
          </div>

          <ConceptChat
            :concept-name="selectedNode.display"
            :system-prompt="gState.graphMode === 'user' ? userChatSystemPrompt : null"
          />
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
import { useAuthStore } from '../stores/auth'
import { useGraphState } from '../stores/graphState'
import api from '../services/api'

const store  = useGraphStore()
const auth   = useAuthStore()
const gState = useGraphState()
const panel  = ref(null)

// ── Mode ───────────────────────────────────────────────────────────────────
const graphTabs = [
  { value: 'global', label: 'Global Graph' },
  { value: 'user',   label: 'My Graph' },
]

// ── Global graph controls — persisted in store ─────────────────────────────
const searchQuery = ref('')   // ephemeral: search input clears on nav (intentional)

const filters = [
  { value: 'all',          label: 'All' },
  { value: 'accelerating', label: 'Accelerating' },
  { value: 'decelerating', label: 'Decelerating' },
  { value: 'stable',       label: 'Stable' },
]

const MODEL_VIEWS = {
  all:    { paperFrom: null,         paperTo: null,         label: 'All 145K',    title: 'All 144,997 papers (llama3.2 extraction)' },
  qwen35: { paperFrom: '2024-12-29', paperTo: '2025-01-01', label: 'qwen3.5:27b', title: '559 papers Dec 29–31 2024 (qwen3.5:27b extraction)' },
}
const modelViews = Object.entries(MODEL_VIEWS).map(([value, m]) => ({ value, ...m }))

// ── User graph state ───────────────────────────────────────────────────────
const userGraphData     = ref(null)
const userTotalConcepts = ref(0)
const userLoading       = ref(false)
const userError         = ref('')

const userSliderStep = computed(() =>
  Math.max(1, Math.round(userTotalConcepts.value / 20))
)

// Normalize user graph nodes to GraphPanel-compatible format
const userConcepts = computed(() => {
  if (!userGraphData.value?.nodes) return []
  return userGraphData.value.nodes.map(n => ({
    concept_name:    n.id,
    trend:           'stable',
    velocity:        0,
    acceleration:    0,
    composite_score: n.weight * 100,  // scale for node radius
    centrality:      n.weight,
  }))
})

async function loadUserGraph() {
  if (auth.isDemo || !auth.isValid) return
  userLoading.value = true
  userError.value = ''
  try {
    const data = await api.getUserGraph(gState.userTopN)
    userGraphData.value = data
    userTotalConcepts.value = data.meta?.total_concepts ?? 0
    if (gState.userTopN > userTotalConcepts.value && userTotalConcepts.value > 0) {
      gState.userTopN = userTotalConcepts.value
    }
  } catch (e) {
    userError.value = e.response?.data?.detail ?? 'Failed to load personal graph'
  } finally {
    userLoading.value = false
  }
}

// ── Unified computed for the active graph ──────────────────────────────────
const activeConcepts = computed(() =>
  gState.graphMode === 'global' ? store.concepts : userConcepts.value
)

const activeLoading = computed(() =>
  gState.graphMode === 'global' ? store.loading : userLoading.value
)

const activeError = computed(() =>
  gState.graphMode === 'global' ? store.error : userError.value
)

// ── Selection ──────────────────────────────────────────────────────────────
const selectedNode = ref(null)
const focusNodeId  = ref(null)

const TREND_COLORS = {
  accelerating: 'var(--canvas-accelerating)',
  stable:       'var(--canvas-stable)',
  decelerating: 'var(--canvas-decelerating)',
}

const trendStats = computed(() => {
  const source = gState.graphMode === 'global' ? store.concepts : userConcepts.value
  const counts = { accelerating: 0, stable: 0, decelerating: 0 }
  for (const c of source) counts[c.trend] = (counts[c.trend] ?? 0) + 1
  return [
    { trend: 'accelerating', label: 'Accelerating', count: counts.accelerating, color: TREND_COLORS.accelerating },
    { trend: 'stable',       label: 'Stable',       count: counts.stable,       color: TREND_COLORS.stable },
    { trend: 'decelerating', label: 'Decelerating', count: counts.decelerating, color: TREND_COLORS.decelerating },
  ]
})

function toTitleCase(s) {
  return s.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

const coOccurring = computed(() => {
  if (!selectedNode.value) return []

  if (gState.graphMode === 'user') {
    // Use actual graph edges for user mode
    const edges = userGraphData.value?.edges ?? []
    const selId = selectedNode.value.id ?? selectedNode.value.concept_name ?? ''
    const nodeMap = Object.fromEntries(userConcepts.value.map(c => [c.concept_name, c]))
    return edges
      .filter(e => e.source === selId || e.target === selId)
      .map(e => {
        const other = e.source === selId ? e.target : e.source
        const c = nodeMap[other]
        if (!c) return null
        return { id: other, concept_name: other, display: toTitleCase(other), sharedTokens: Math.round(e.weight * 1000), trend: c.trend, velocity: c.velocity, acceleration: c.acceleration, composite_score: c.composite_score, centrality: c.centrality }
      })
      .filter(Boolean)
      .sort((a, b) => b.sharedTokens - a.sharedTokens)
      .slice(0, 8)
  }

  // Global mode: token-overlap heuristic
  const selId     = selectedNode.value.id ?? selectedNode.value.concept_name?.toLowerCase() ?? ''
  const selTokens = selId.split(' ').filter(t => t.length > 3)
  if (!selTokens.length) return []
  return store.concepts
    .map(c => {
      const cId = c.concept_name.toLowerCase()
      if (cId === selId) return null
      const shared = selTokens.filter(t => cId.split(' ').includes(t))
      if (!shared.length) return null
      return { id: cId, concept_name: cId, display: toTitleCase(cId), sharedTokens: shared.length, trend: c.trend, velocity: c.velocity, acceleration: c.acceleration, composite_score: c.composite_score, centrality: c.centrality }
    })
    .filter(Boolean)
    .sort((a, b) => b.sharedTokens - a.sharedTokens)
    .slice(0, 8)
})

const userChatSystemPrompt = computed(() => {
  if (!selectedNode.value) return null
  return `You are a research assistant. The user is exploring their personal research knowledge graph \
built from their uploaded academic papers. The current concept is "${selectedNode.value.display}". \
Be concise (max 3 sentences) and relate your answer to the user's personal research context.`
})

function trendBadgeStyle(trend) {
  const map = {
    accelerating: { background: 'rgb(var(--color-accent-green) / 0.15)', color: 'var(--canvas-accelerating)' },
    decelerating: { background: 'rgb(var(--color-accent-red)   / 0.15)', color: 'var(--canvas-decelerating)' },
    stable:       { background: 'rgb(var(--color-accent-blue)  / 0.15)', color: 'var(--canvas-stable)' },
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

function loadGlobalConcepts() {
  const { paperFrom, paperTo } = MODEL_VIEWS[gState.modelView]
  store.fetchConcepts(gState.topN, gState.trendFilter, paperFrom, paperTo)
}

watch(() => [gState.trendFilter, gState.modelView], loadGlobalConcepts)
watch(() => gState.graphMode, (mode) => {
  clearSelection()
  if (mode === 'user') loadUserGraph()
})
watch(() => gState.userTopN, loadUserGraph)

onMounted(() => {
  loadGlobalConcepts()
  if (gState.graphMode === 'user') loadUserGraph()
})
</script>
