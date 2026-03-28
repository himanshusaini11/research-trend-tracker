<template>
  <div class="p-6 max-w-6xl">

    <!-- Mode toggle -->
    <div v-if="!auth.isDemo && auth.isValid" class="flex items-center gap-3 mb-6">
      <div class="flex items-center border border-border rounded-lg overflow-hidden">
        <button
          v-for="tab in tabs" :key="tab.value"
          @click="switchMode(tab.value)"
          :class="[
            'px-4 py-1.5 text-xs font-medium transition-colors',
            pred.mode === tab.value ? 'bg-accent-blue text-bg' : 'text-text-muted hover:text-text-primary',
          ]"
        >{{ tab.label }}</button>
      </div>
      <!-- Running indicator visible from any tab -->
      <div v-if="pred.generating" class="flex items-center gap-2">
        <span class="animate-spin text-accent-blue">⟳</span>
        <span class="text-text-muted text-xs">Generating from your papers…</span>
        <button
          @click="pred.stop()"
          class="text-xs px-2.5 py-1 rounded border border-accent-red/50 text-accent-red
                 hover:bg-accent-red/10 transition-colors"
        >Stop</button>
      </div>
    </div>

    <!-- ── GLOBAL MODE ──────────────────────────────────────────── -->
    <template v-if="pred.mode === 'global'">
      <div v-if="loadingGlobal" class="text-text-muted text-sm py-12 text-center">Loading report…</div>
      <div v-else-if="globalError" class="text-accent-red text-sm py-12 text-center">{{ globalError }}</div>

      <template v-else-if="latestGlobal">
        <!-- Header -->
        <div class="flex items-start justify-between mb-6">
          <div>
            <h2 class="text-text-primary text-lg font-semibold">{{ latestGlobal.topic_context }}</h2>
            <p class="text-text-muted text-sm mt-0.5">
              Generated {{ fmtDate(latestGlobal.generated_at) }} · {{ latestGlobal.model_name }}
            </p>
          </div>
          <div class="flex items-center gap-3 flex-wrap">
            <span class="px-2.5 py-0.5 rounded text-xs font-medium uppercase tracking-wide"
              :style="confidenceBadgeStyle(latestGlobal.report.overall_confidence)">
              {{ latestGlobal.report.overall_confidence }} confidence
            </span>
            <span class="text-text-muted text-xs">{{ latestGlobal.report.time_horizon_months }}mo horizon</span>
            <span v-if="latestGlobal.is_validated" class="text-accent-green text-xs font-medium">✓ Validated</span>
          </div>
        </div>
        <!-- Cards -->
        <div class="grid grid-cols-3 gap-5 mb-8">
          <div>
            <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">Emerging Directions</h3>
            <PredictionCard v-for="(d,i) in latestGlobal.report.emerging_directions" :key="i"
              :title="d.direction" :body="d.reasoning" :badge="d.confidence"
              :badge-style="confidenceBadgeStyle(d.confidence)" />
          </div>
          <div>
            <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">Unexplored Gaps</h3>
            <PredictionCard v-for="(g,i) in latestGlobal.report.underexplored_gaps" :key="i"
              :title="g.gap" :body="g.reasoning" />
          </div>
          <div>
            <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">Predicted Convergences</h3>
            <PredictionCard v-for="(c,i) in latestGlobal.report.predicted_convergences" :key="i"
              :title="`${c.concept_a} ↔ ${c.concept_b}`" :body="c.reasoning" />
          </div>
        </div>
        <!-- Generate button -->
        <button @click="generateGlobal" :disabled="generatingGlobal"
          class="px-5 py-2.5 bg-accent-blue text-bg text-sm font-medium rounded-lg
                 hover:bg-blue-400 disabled:opacity-50 disabled:cursor-not-allowed
                 transition-colors flex items-center gap-2">
          <span v-if="generatingGlobal" class="animate-spin">⟳</span>
          {{ generatingGlobal ? 'Generating… (5–15 min)' : 'Generate New Report (5–15 min)' }}
        </button>
        <!-- Archive -->
        <div v-if="archive.length > 1" class="mt-8">
          <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">Recent Reports</h3>
          <div class="space-y-2">
            <div v-for="r in archive.slice(1)" :key="r.id"
              class="bg-surface border border-border rounded-lg px-4 py-3 flex items-center justify-between">
              <div>
                <span class="text-text-primary text-sm">{{ fmtDate(r.generated_at) }}</span>
                <span class="text-text-muted text-xs ml-3">{{ r.topic_context }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded text-xs font-medium"
                  :style="confidenceBadgeStyle(r.report.overall_confidence)">
                  {{ r.report.overall_confidence }}
                </span>
                <span v-if="r.is_validated" class="text-accent-green text-xs font-medium">✓</span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <div v-else class="text-text-muted text-sm py-12 text-center">
        No prediction reports found. Run
        <code class="text-accent-blue">uv run python scripts/run_graph_pipeline.py</code>
        to generate one.
      </div>
    </template>

    <!-- ── USER MODE ────────────────────────────────────────────── -->
    <template v-else>
      <!-- Generating (persists across navigation) -->
      <div v-if="pred.generating" class="py-16 flex flex-col items-center gap-4">
        <span class="animate-spin text-accent-blue text-3xl">⟳</span>
        <p class="text-text-muted text-sm">Generating prediction with qwen3.5:27b…</p>
        <p class="text-text-muted text-xs">This takes 5–15 min. You can browse other tabs.</p>
        <button @click="pred.stop()"
          class="mt-2 px-4 py-2 rounded border border-accent-red/50 text-accent-red text-xs
                 hover:bg-accent-red/10 transition-colors">
          Stop Calculation
        </button>
      </div>

      <!-- Error -->
      <div v-else-if="pred.error" class="text-accent-red text-sm py-12 text-center">{{ pred.error }}</div>

      <!-- Result -->
      <template v-else-if="pred.result">
        <!-- Header -->
        <div class="flex items-start justify-between mb-6">
          <div>
            <h2 class="text-text-primary text-lg font-semibold">{{ pred.result.topic_context }}</h2>
            <p class="text-text-muted text-sm mt-0.5">
              Generated {{ fmtDate(pred.result.generated_at) }} · {{ pred.result.model_name }}
            </p>
          </div>
          <div class="flex items-center gap-3 flex-wrap">
            <span class="px-2.5 py-0.5 rounded text-xs font-medium uppercase tracking-wide"
              :style="confidenceBadgeStyle(pred.result.report.overall_confidence)">
              {{ pred.result.report.overall_confidence }} confidence
            </span>
            <span class="text-text-muted text-xs">{{ pred.result.report.time_horizon_months }}mo horizon</span>
          </div>
        </div>
        <!-- Cards -->
        <div class="grid grid-cols-3 gap-5 mb-8">
          <div>
            <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">Emerging Directions</h3>
            <PredictionCard v-for="(d,i) in pred.result.report.emerging_directions" :key="i"
              :title="d.direction" :body="d.reasoning" :badge="d.confidence"
              :badge-style="confidenceBadgeStyle(d.confidence)" />
          </div>
          <div>
            <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">Unexplored Gaps</h3>
            <PredictionCard v-for="(g,i) in pred.result.report.underexplored_gaps" :key="i"
              :title="g.gap" :body="g.reasoning" />
          </div>
          <div>
            <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">Predicted Convergences</h3>
            <PredictionCard v-for="(c,i) in pred.result.report.predicted_convergences" :key="i"
              :title="`${c.concept_a} ↔ ${c.concept_b}`" :body="c.reasoning" />
          </div>
        </div>
        <!-- Re-generate button -->
        <button @click="pred.generate()" :disabled="pred.generating"
          class="px-5 py-2.5 bg-accent-blue text-bg text-sm font-medium rounded-lg
                 hover:bg-blue-400 disabled:opacity-50 disabled:cursor-not-allowed
                 transition-colors flex items-center gap-2">
          Re-generate from My Papers
        </button>
      </template>

      <!-- Empty: no prediction yet -->
      <div v-else class="text-center py-12 space-y-4">
        <p class="text-text-muted text-sm">No prediction generated yet for your uploaded papers.</p>
        <div class="flex items-center justify-center gap-3">
          <button @click="pred.generate()"
            class="px-5 py-2 bg-accent-blue text-bg text-xs font-medium rounded-lg
                   hover:bg-blue-400 transition-colors">
            Generate Prediction from My Papers
          </button>
          <button @click="$router.push('/dashboard/upload')"
            class="px-5 py-2 border border-border text-text-muted text-xs font-medium rounded-lg
                   hover:text-text-primary transition-colors">
            Upload More Papers
          </button>
        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import PredictionCard from '../components/PredictionCard.vue'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { usePredictionStore } from '../stores/prediction'

const auth = useAuthStore()
const pred = usePredictionStore()

const tabs = [
  { value: 'global', label: 'Global (145K papers)' },
  { value: 'user',   label: 'My Papers' },
]

// ── Global mode state ──────────────────────────────────────────────
const loadingGlobal    = ref(true)
const generatingGlobal = ref(false)
const globalError      = ref(null)
const archive          = ref([])
const latestGlobal     = ref(null)

async function loadGlobal() {
  loadingGlobal.value = true
  globalError.value   = null
  try {
    archive.value      = await api.getLatestPredictions('LLM/AI research Oct-Dec 2024', 5)
    latestGlobal.value = archive.value[0] ?? null
  } catch (e) {
    globalError.value = e.response?.data?.detail ?? e.message ?? 'Failed to load predictions.'
  } finally {
    loadingGlobal.value = false
  }
}

async function generateGlobal() {
  generatingGlobal.value = true
  try {
    await api.generatePrediction(latestGlobal.value?.topic_context ?? 'LLM/AI research Oct-Dec 2024')
    await loadGlobal()
  } catch (e) {
    globalError.value = e.response?.data?.detail ?? e.message
  } finally {
    generatingGlobal.value = false
  }
}

function switchMode(m) {
  pred.mode = m
}

function fmtDate(iso) {
  return new Date(iso).toLocaleString([], {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function confidenceBadgeStyle(c) {
  const map = {
    high:   { background: 'var(--badge-high-bg)',   color: 'var(--badge-high-text)' },
    medium: { background: 'var(--badge-medium-bg)', color: 'var(--badge-medium-text)' },
    low:    { background: 'var(--badge-low-bg)',     color: 'var(--badge-low-text)' },
  }
  return map[c] ?? { background: 'var(--badge-muted-bg)', color: 'var(--badge-muted-text)' }
}

onMounted(loadGlobal)
</script>
