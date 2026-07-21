<template>
  <div class="modernist" style="flex: 1; overflow: auto; padding: 24px">

    <!-- Mode toggle -->
    <div v-if="!auth.isDemo && auth.isValid" style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px; flex-wrap: wrap">
      <div class="seg">
        <label v-for="tab in tabs" :key="tab.value" class="seg-opt">
          <input type="radio" name="pmode" :checked="pred.mode === tab.value" @change="switchMode(tab.value)" />{{ tab.label }}
        </label>
      </div>
      <div v-if="pred.generating" style="display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--mn-color-surface)">
        <div class="skel" style="width: 16px; height: 16px"></div>
        <span style="font-size: 13px">Generating from your papers…</span>
        <button class="btn btn-secondary" @click="pred.stop()">Stop</button>
      </div>
    </div>

    <!-- ── GLOBAL MODE ──────────────────────────────────────────── -->
    <template v-if="pred.mode === 'global'">
      <div v-if="loadingGlobal" style="opacity: .6; font-size: 14px; padding: 48px 0; text-align: center">Loading report…</div>
      <div v-else-if="globalError" style="color: var(--mn-color-accent-700); font-size: 14px; padding: 48px 0; text-align: center">{{ globalError }}</div>

      <template v-else-if="latestGlobal">
        <div style="display: flex; align-items: baseline; gap: 14px; margin-bottom: 6px; flex-wrap: wrap">
          <h3 style="margin: 0">{{ latestGlobal.topic_context }}</h3>
          <span class="tag tag-outline">{{ latestGlobal.report.overall_confidence }} confidence</span>
          <span class="tag tag-neutral">{{ latestGlobal.report.time_horizon_months }}mo horizon</span>
          <span v-if="latestGlobal.is_validated" class="tag tag-accent">✓ Validated</span>
        </div>
        <p style="font-size: 12px; opacity: .6; margin-bottom: 20px">
          Generated {{ fmtDate(latestGlobal.generated_at) }} · {{ latestGlobal.model_name }}
        </p>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); border-top: 2px solid var(--mn-color-divider);
                    border-left: 2px solid var(--mn-color-divider); margin-bottom: 20px">
          <AccordionColumn title="Emerging Directions" :open="accOpen.emerging" @toggle="accOpen.emerging = !accOpen.emerging">
            <PredictionCard v-for="(d, i) in latestGlobal.report.emerging_directions" :key="i" :title="d.direction" :body="d.reasoning" />
          </AccordionColumn>
          <AccordionColumn title="Unexplored Gaps" :open="accOpen.gaps" @toggle="accOpen.gaps = !accOpen.gaps">
            <PredictionCard v-for="(g, i) in latestGlobal.report.underexplored_gaps" :key="i" :title="g.gap" :body="g.reasoning" />
          </AccordionColumn>
          <AccordionColumn title="Predicted Convergences" :open="accOpen.conv" @toggle="accOpen.conv = !accOpen.conv">
            <PredictionCard v-for="(c, i) in latestGlobal.report.predicted_convergences" :key="i" :title="`${c.concept_a} ↔ ${c.concept_b}`" :body="c.reasoning" />
          </AccordionColumn>
        </div>

        <button class="btn btn-primary" style="margin-bottom: 24px" :disabled="generatingGlobal" @click="generateGlobal">
          {{ generatingGlobal ? 'Generating… (5–15 min)' : 'Generate New Report (5–15 min)' }}
        </button>

        <template v-if="archive.length > 1">
          <h6 style="opacity: .6; margin-bottom: 10px">RECENT REPORTS</h6>
          <table class="table">
            <thead><tr><th>Date</th><th>Topic</th><th>Confidence</th><th>Validated</th></tr></thead>
            <tbody>
              <tr v-for="r in archive.slice(1)" :key="r.id">
                <td>{{ fmtDate(r.generated_at) }}</td>
                <td>{{ r.topic_context }}</td>
                <td>{{ r.report.overall_confidence }}</td>
                <td>{{ r.is_validated ? '✓' : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </template>

      <div v-else style="opacity: .6; font-size: 14px; padding: 48px 0; text-align: center">
        No prediction reports found. Run
        <code style="color: var(--mn-color-accent)">uv run python scripts/run_graph_pipeline.py</code>
        to generate one.
      </div>
    </template>

    <!-- ── USER MODE ────────────────────────────────────────────── -->
    <template v-else>
      <div v-if="pred.generating" style="padding: 64px 0; display: flex; flex-direction: column; align-items: center; gap: 16px">
        <div class="skel" style="width: 32px; height: 32px"></div>
        <p style="font-size: 14px">Generating prediction with qwen3.5:27b…</p>
        <p style="font-size: 12px; opacity: .6">This takes 5–15 min. You can browse other tabs.</p>
        <button class="btn btn-secondary" @click="pred.stop()">Stop Calculation</button>
      </div>

      <div v-else-if="pred.error" style="color: var(--mn-color-accent-700); font-size: 14px; padding: 48px 0; text-align: center">{{ pred.error }}</div>

      <template v-else-if="pred.result">
        <div style="display: flex; align-items: baseline; gap: 14px; margin-bottom: 6px; flex-wrap: wrap">
          <h3 style="margin: 0">{{ pred.result.topic_context }}</h3>
          <span class="tag tag-outline">{{ pred.result.report.overall_confidence }} confidence</span>
          <span class="tag tag-neutral">{{ pred.result.report.time_horizon_months }}mo horizon</span>
        </div>
        <p style="font-size: 12px; opacity: .6; margin-bottom: 20px">
          Generated {{ fmtDate(pred.result.generated_at) }} · {{ pred.result.model_name }}
        </p>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); border-top: 2px solid var(--mn-color-divider);
                    border-left: 2px solid var(--mn-color-divider); margin-bottom: 20px">
          <AccordionColumn title="Emerging Directions" :open="accOpen.emerging" @toggle="accOpen.emerging = !accOpen.emerging">
            <PredictionCard v-for="(d, i) in pred.result.report.emerging_directions" :key="i" :title="d.direction" :body="d.reasoning" />
          </AccordionColumn>
          <AccordionColumn title="Unexplored Gaps" :open="accOpen.gaps" @toggle="accOpen.gaps = !accOpen.gaps">
            <PredictionCard v-for="(g, i) in pred.result.report.underexplored_gaps" :key="i" :title="g.gap" :body="g.reasoning" />
          </AccordionColumn>
          <AccordionColumn title="Predicted Convergences" :open="accOpen.conv" @toggle="accOpen.conv = !accOpen.conv">
            <PredictionCard v-for="(c, i) in pred.result.report.predicted_convergences" :key="i" :title="`${c.concept_a} ↔ ${c.concept_b}`" :body="c.reasoning" />
          </AccordionColumn>
        </div>

        <button class="btn btn-secondary" :disabled="pred.generating" @click="pred.generate()">Re-generate from My Papers</button>
      </template>

      <div v-else style="text-align: center; padding: 48px; background: var(--mn-color-surface)">
        <p style="margin-bottom: 16px">No prediction generated from your papers yet.</p>
        <div style="display: flex; gap: 12px; justify-content: center">
          <button class="btn btn-primary" @click="pred.generate()">Generate Prediction from My Papers</button>
          <button class="btn btn-secondary" @click="$router.push('/dashboard/upload')">Upload More Papers</button>
        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import PredictionCard from '../components/PredictionCard.vue'
import AccordionColumn from '../components/AccordionColumn.vue'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { usePredictionStore } from '../stores/prediction'

const auth = useAuthStore()
const pred = usePredictionStore()

// Column-level accordion — matches the design exactly (whole column
// collapses, not per-item). Emerging starts open, the other two closed.
const accOpen = ref({ emerging: true, gaps: false, conv: false })

const DEFAULT_TOPIC = 'AI/ML research'  // reconciled with Simulation's default, per the redesign

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
    archive.value      = await api.getLatestPredictions(DEFAULT_TOPIC, 5)
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
    await api.generatePrediction(latestGlobal.value?.topic_context ?? DEFAULT_TOPIC)
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

onMounted(loadGlobal)
</script>
