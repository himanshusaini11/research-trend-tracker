<template>
  <div class="p-6 max-w-6xl">
    <!-- Loading / error -->
    <div v-if="loading" class="text-text-muted text-sm py-12 text-center">Loading report…</div>
    <div v-else-if="error" class="text-accent-red text-sm py-12 text-center">{{ error }}</div>

    <template v-else-if="latest">
      <!-- Header -->
      <div class="flex items-start justify-between mb-6">
        <div>
          <h2 class="text-text-primary text-lg font-semibold">{{ latest.topic_context }}</h2>
          <p class="text-text-muted text-sm mt-0.5">
            Generated {{ fmtDate(latest.generated_at) }} · {{ latest.model_name }}
          </p>
        </div>
        <div class="flex items-center gap-3">
          <span
            :class="confidenceClass(latest.report.overall_confidence)"
            class="px-2.5 py-0.5 rounded text-xs font-medium uppercase tracking-wide"
          >
            {{ latest.report.overall_confidence }} confidence
          </span>
          <span class="text-text-muted text-xs">
            {{ latest.report.time_horizon_months }}mo horizon
          </span>
        </div>
      </div>

      <!-- 3 columns -->
      <div class="grid grid-cols-3 gap-5 mb-8">
        <!-- Emerging directions -->
        <div>
          <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">Emerging Directions</h3>
          <PredictionCard
            v-for="(d, i) in latest.report.emerging_directions"
            :key="i"
            :title="d.direction"
            :body="d.reasoning"
            :badge="d.confidence"
            :badge-class="confidenceClass(d.confidence)"
          />
        </div>

        <!-- Unexplored gaps -->
        <div>
          <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">Unexplored Gaps</h3>
          <PredictionCard
            v-for="(g, i) in latest.report.underexplored_gaps"
            :key="i"
            :title="g.gap"
            :body="g.reasoning"
          />
        </div>

        <!-- Predicted convergences -->
        <div>
          <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">Predicted Convergences</h3>
          <PredictionCard
            v-for="(c, i) in latest.report.predicted_convergences"
            :key="i"
            :title="`${c.concept_a} ↔ ${c.concept_b}`"
            :body="c.reasoning"
          />
        </div>
      </div>

      <!-- Generate new -->
      <button
        @click="generate"
        :disabled="generating"
        class="px-5 py-2.5 bg-accent-blue text-bg text-sm font-medium rounded-lg
               hover:bg-blue-400 disabled:opacity-50 disabled:cursor-not-allowed
               transition-colors flex items-center gap-2"
      >
        <span v-if="generating" class="animate-spin">⟳</span>
        {{ generating ? 'Generating (Ollama may take 10–30s)…' : 'Generate New Report' }}
      </button>

      <!-- Archive timeline -->
      <div v-if="archive.length > 1" class="mt-8">
        <h3 class="text-text-muted text-xs uppercase tracking-wider mb-3">Recent Reports</h3>
        <div class="space-y-2">
          <div
            v-for="r in archive.slice(1)"
            :key="r.id"
            class="bg-surface border border-border rounded-lg px-4 py-3 flex items-center justify-between"
          >
            <div>
              <span class="text-text-primary text-sm">{{ fmtDate(r.generated_at) }}</span>
              <span class="text-text-muted text-xs ml-3">{{ r.topic_context }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span
                :class="confidenceClass(r.report.overall_confidence)"
                class="px-2 py-0.5 rounded text-xs font-medium"
              >
                {{ r.report.overall_confidence }}
              </span>
              <span v-if="r.is_validated" class="text-accent-green text-xs">validated</span>
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import PredictionCard from '../components/PredictionCard.vue'
import api from '../services/api'

const loading    = ref(false)
const generating = ref(false)
const error      = ref(null)
const archive    = ref([])
const latest     = ref(null)

async function load() {
  loading.value = true
  error.value   = null
  try {
    archive.value = await api.getLatestPredictions('LLM/AI research Oct-Dec 2024', 5)
    latest.value  = archive.value[0] ?? null
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function generate() {
  generating.value = true
  try {
    await api.generatePrediction(latest.value?.topic_context ?? 'LLM/AI research Oct-Dec 2024')
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    generating.value = false
  }
}

function fmtDate(iso) {
  return new Date(iso).toLocaleString([], {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function confidenceClass(c) {
  return {
    high:   'bg-accent-green/20 text-accent-green',
    medium: 'bg-accent-blue/20 text-accent-blue',
    low:    'bg-accent-gray/20 text-accent-gray',
  }[c] ?? 'bg-accent-gray/20 text-accent-gray'
}

onMounted(load)
</script>
