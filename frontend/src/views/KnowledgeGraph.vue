<template>
  <div class="modernist" style="height: 100%; display: flex; flex-direction: column">
    <!-- Controls bar -->
    <div style="display: flex; align-items: center; gap: 14px; padding: 14px 24px; flex-wrap: wrap;
                border-bottom: 2px solid var(--mn-color-divider)">

      <div v-if="!auth.isDemo && auth.isValid" class="seg">
        <label v-for="tab in graphTabs" :key="tab.value" class="seg-opt">
          <input type="radio" name="gmode" :checked="gState.graphMode === tab.value" @change="gState.graphMode = tab.value" />{{ tab.label }}
        </label>
      </div>

      <template v-if="gState.graphMode === 'global'">
        <div style="display: flex; align-items: center; gap: 8px; font-size: 12px; opacity: .75">
          <span>TOP N</span>
          <input type="range" min="50" max="1000" step="50" v-model.number="gState.topN" />
          <span>{{ gState.topN }}</span>
        </div>

        <div class="seg">
          <label v-for="f in filters" :key="f.value" class="seg-opt">
            <input type="radio" name="gfilter" :checked="gState.trendFilter === f.value" @change="gState.trendFilter = f.value" />{{ f.label }}
          </label>
        </div>

        <div class="seg">
          <label v-for="m in modelViews" :key="m.value" class="seg-opt" :title="m.title">
            <input type="radio" name="gmodel" :checked="gState.modelView === m.value" @change="gState.modelView = m.value" />{{ m.label }}
          </label>
        </div>
      </template>

      <template v-else>
        <div v-if="userTotalConcepts > 0" style="display: flex; align-items: center; gap: 8px; font-size: 12px; opacity: .75">
          <span>CONCEPTS</span>
          <input type="range" :min="1" :max="userTotalConcepts" :step="userSliderStep" v-model.number="gState.userTopN" />
          <span>{{ gState.userTopN }} / {{ userTotalConcepts }}</span>
        </div>
      </template>

      <input class="input" style="width: 180px" v-model="searchQuery" placeholder="Search concepts…" />

      <button class="btn btn-ghost" style="margin-left: auto" @click="resetZoom">RESET ZOOM</button>
    </div>

    <!-- Split view: 70% graph / 30% detail -->
    <div style="flex: 1; display: flex; min-height: 0">

      <!-- LEFT: graph canvas -->
      <div style="flex: 0 0 70%; position: relative; min-width: 0">

        <div v-if="gState.graphMode === 'user' && userTotalConcepts === 0 && !userLoading"
          style="position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center;
                 justify-content: center; gap: 14px; text-align: center; padding: 0 32px">
          <div style="width: 40px; height: 40px; border: 2px solid var(--mn-color-divider)"></div>
          <p style="opacity: .7; font-size: 14px">No papers uploaded yet — your graph is empty.</p>
          <button class="btn btn-primary" @click="$router.push('/dashboard/upload')">Upload Papers →</button>
        </div>

        <div v-else-if="activeLoading" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; z-index: 10">
          <div style="opacity: .6; font-size: 14px">Loading graph…</div>
        </div>
        <div v-else-if="activeError" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; z-index: 10">
          <div style="color: var(--mn-color-accent-700); font-size: 14px">{{ activeError }}</div>
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
      <div style="flex: 1; overflow: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px;
                  border-left: 2px solid var(--mn-color-divider)">

        <template v-if="!selectedNode">
          <div class="statcell">
            <div style="font-size: 10px; opacity: .6; text-transform: uppercase; margin-bottom: 6px">
              {{ gState.graphMode === 'global' ? 'Dataset' : 'My Graph' }}
            </div>
            <template v-if="gState.graphMode === 'global'">
              <template v-if="gState.modelView === 'all'">
                <div style="font-weight: var(--mn-font-heading-weight); font-family: var(--mn-font-heading); font-size: 15px">
                  <template v-if="globalStats">
                    {{ globalStats.concept_count.toLocaleString() }} concepts · {{ formattedEdges }} edges · {{ globalStats.total_papers.toLocaleString() }} papers
                  </template>
                  <template v-else>loading…</template>
                </div>
                <div style="opacity: .6; font-size: 12px; margin-top: 4px">LLM / AI · {{ formattedRange }} · qwen3.5:27b</div>
              </template>
              <template v-else>
                <div style="font-weight: var(--mn-font-heading-weight); font-family: var(--mn-font-heading); font-size: 15px">
                  {{ store.concepts.length }} concepts · 559 papers
                </div>
                <div style="opacity: .6; font-size: 12px; margin-top: 4px">Dec 29–31 2024 · qwen3.5:27b extraction</div>
              </template>
            </template>
            <template v-else>
              <div style="font-weight: var(--mn-font-heading-weight); font-family: var(--mn-font-heading); font-size: 15px">
                {{ userTotalConcepts }} concepts from your uploads
              </div>
              <div style="opacity: .6; font-size: 12px; margin-top: 4px">Extracted via TF-IDF · personal graph</div>
            </template>
          </div>

          <div class="statcell">
            <div style="font-size: 10px; opacity: .6; text-transform: uppercase; margin-bottom: 8px">Trend Breakdown</div>
            <div style="display: flex; flex-direction: column; gap: 6px">
              <div v-for="t in trendStats" :key="t.trend" style="display: flex; align-items: center; justify-content: space-between; font-size: 13px">
                <span :class="t.tagClass" class="tag">{{ t.label }}</span>
                <span style="font-family: var(--mn-font-heading); font-weight: var(--mn-font-heading-weight)">{{ t.count }}</span>
              </div>
            </div>
          </div>

          <p style="opacity: .5; font-size: 12px; text-align: center; padding-top: 4px">
            Click a node to inspect · Dbl-click to zoom
          </p>
        </template>

        <!-- Node selected -->
        <template v-else>
          <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 8px">
            <div>
              <h5 style="margin: 0 0 4px">{{ selectedNode.display }}</h5>
              <span class="tag" :class="trendTagClass(selectedNode.trend)">{{ selectedNode.trend }}</span>
            </div>
            <button class="btn btn-icon" @click="clearSelection">×</button>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px">
            <div class="statcell">
              <div style="font-size: 10px; opacity: .6; text-transform: uppercase">Centrality</div>
              <div style="font-family: var(--mn-font-heading); font-size: 19px; font-weight: 800">{{ fmt4(selectedNode.centrality) }}</div>
            </div>
            <div class="statcell">
              <div style="font-size: 10px; opacity: .6; text-transform: uppercase">Velocity</div>
              <div style="font-family: var(--mn-font-heading); font-size: 19px; font-weight: 800">
                {{ selectedNode.velocity >= 0 ? '+' : '' }}{{ fmt1(selectedNode.velocity) }}
              </div>
            </div>
            <div class="statcell">
              <div style="font-size: 10px; opacity: .6; text-transform: uppercase">Acceleration</div>
              <div style="font-family: var(--mn-font-heading); font-size: 19px; font-weight: 800">
                {{ selectedNode.acceleration >= 0 ? '+' : '' }}{{ fmt1(selectedNode.acceleration) }}
              </div>
            </div>
            <div class="statcell">
              <div style="font-size: 10px; opacity: .6; text-transform: uppercase">Composite</div>
              <div style="font-family: var(--mn-font-heading); font-size: 19px; font-weight: 800">{{ fmt2(selectedNode.composite_score) }}</div>
            </div>
          </div>

          <div>
            <h6 style="opacity: .6; margin-bottom: 8px">TOP CO-OCCURRING</h6>
            <div v-if="coOccurring.length" style="display: flex; flex-direction: column; gap: 6px">
              <div
                v-for="c in coOccurring" :key="c.id" class="statcell"
                style="display: flex; align-items: center; justify-content: space-between; cursor: pointer"
                @click="selectCoOccurring(c)"
              >
                <span style="font-size: 13px">{{ c.display }}</span>
                <span style="opacity: .5; font-size: 11px">{{ c.sharedTokens }}{{ gState.graphMode === 'user' ? 'w' : 't' }}</span>
              </div>
            </div>
            <div v-else style="opacity: .5; font-size: 13px">None found</div>
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
  all:    { paperFrom: null,         paperTo: null,         label: 'All papers', title: 'Full corpus (qwen3.5:27b extraction)' },
  qwen35: { paperFrom: '2024-12-29', paperTo: '2025-01-01', label: 'qwen3.5:27b', title: '559 papers Dec 29–31 2024 (qwen3.5:27b extraction)' },
}
const modelViews = Object.entries(MODEL_VIEWS).map(([value, m]) => ({ value, ...m }))

// ── Live dataset stats (Stage 1 endpoint) for the "nothing selected" card ──
const globalStats = ref(null)

const formattedEdges = computed(() => {
  if (!globalStats.value) return ''
  const n = globalStats.value.edge_count
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n.toLocaleString()
})

const formattedRange = computed(() => {
  if (!globalStats.value?.date_range_start || !globalStats.value?.date_range_end) return '—'
  const startYear = new Date(globalStats.value.date_range_start).getFullYear()
  const endYear   = new Date(globalStats.value.date_range_end).getFullYear()
  return startYear === endYear ? `${startYear}` : `${startYear}–${endYear}`
})

async function loadGlobalStats() {
  try {
    globalStats.value = await api.getGraphStats()
  } catch { /* card just keeps showing "loading…" — non-critical */ }
}

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

// Mono-accent system: accelerating -> accent tag, decelerating -> accent-2 tag,
// stable -> neutral tag. Mirrors GraphPanel's node-color mapping exactly.
function trendTagClass(trend) {
  if (trend === 'accelerating') return 'tag-accent'
  if (trend === 'decelerating') return 'tag-accent-2'
  return 'tag-neutral'
}

const trendStats = computed(() => {
  const source = gState.graphMode === 'global' ? store.concepts : userConcepts.value
  const counts = { accelerating: 0, stable: 0, decelerating: 0 }
  for (const c of source) counts[c.trend] = (counts[c.trend] ?? 0) + 1
  return [
    { trend: 'accelerating', label: 'Accelerating', count: counts.accelerating, tagClass: 'tag-accent' },
    { trend: 'stable',       label: 'Stable',       count: counts.stable,       tagClass: 'tag-neutral' },
    { trend: 'decelerating', label: 'Decelerating', count: counts.decelerating, tagClass: 'tag-accent-2' },
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
  loadGlobalStats()
  if (gState.graphMode === 'user') loadUserGraph()
})
</script>
