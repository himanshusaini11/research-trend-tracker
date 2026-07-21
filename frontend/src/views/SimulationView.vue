<template>
  <div class="modernist" style="flex: 1; overflow: auto; padding: 24px">

    <!-- Controls -->
    <div style="display: flex; gap: 14px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 24px">
      <div class="field" style="width: 280px">
        <label>Topic context</label>
        <input v-model="topicContext" class="input" placeholder="AI/ML research" :disabled="store.running" />
      </div>
      <div class="field" style="width: 140px">
        <label>Max rounds</label>
        <select v-model.number="maxRounds" class="input" :disabled="store.running">
          <option v-for="n in [1, 2, 3, 4, 5]" :key="n" :value="n">{{ n }}</option>
        </select>
      </div>
      <button class="btn btn-primary" :disabled="store.running" @click="store.runSimulation(topicContext, maxRounds)">
        Run Simulation
      </button>
      <button v-if="store.result || store.error" class="btn btn-secondary" @click="store.reset()">Reset</button>
      <button class="btn btn-ghost" style="margin-left: auto" @click="toggleHistory">
        {{ historyOpen ? 'Hide past runs' : 'View past runs' }}
      </button>
    </div>

    <!-- History panel -->
    <div v-if="historyOpen" style="margin-bottom: 24px">
      <h6 style="opacity: .6; margin-bottom: 10px">PAST RUNS</h6>
      <div v-if="historyLoading" style="opacity: .6; font-size: 13px">Loading…</div>
      <table v-else-if="history.length" class="table">
        <thead><tr><th>Date</th><th>Topic</th><th>Rounds</th><th>Overall Confidence</th><th></th></tr></thead>
        <tbody>
          <tr v-for="row in history" :key="row.id" style="cursor: pointer" @click="loadHistoryRow(row)">
            <td>{{ fmtDate(row.generated_at) }}</td>
            <td>{{ row.topic_context }}</td>
            <td>{{ row.simulation_config?.max_rounds ?? '—' }}</td>
            <td>{{ row.results.overall_simulation_confidence }}</td>
            <td><span style="opacity: .5; font-size: 12px">View →</span></td>
          </tr>
        </tbody>
      </table>
      <div v-else style="opacity: .6; font-size: 13px">No past runs for this topic yet.</div>
    </div>

    <!-- Status -->
    <div v-if="store.error" style="margin-bottom: 20px; padding: 16px; background: var(--mn-color-surface); color: var(--mn-color-accent-700)">
      {{ store.error }}
    </div>
    <div v-if="store.running" style="display: flex; align-items: center; gap: 12px; padding: 16px; background: var(--mn-color-surface); margin-bottom: 20px">
      <div class="skel" style="width: 18px; height: 18px"></div>
      <span>Simulation running{{ store.jobId ? ` — job ${store.jobId.slice(0, 8)}…` : '' }} · polling every 5s…</span>
    </div>

    <!-- Empty / intro state -->
    <div v-if="!store.result && !store.running" style="padding: 40px; background: var(--mn-color-surface)">
      <h6 style="color: var(--mn-color-accent); margin-bottom: 10px">EXPERIMENTAL — ARIS</h6>
      <p style="max-width: 64ch; opacity: .8; margin-bottom: 8px">
        ARIS runs a 3-persona debate — Researcher, VC, Policymaker — against a predicted direction to stress-test it.
        Each persona argues from its own incentives across several rounds.
      </p>
      <p style="max-width: 64ch; opacity: .6; font-size: 13px">
        The resulting "verdict" is a heuristic read on adoption likelihood, not a measured forecast —
        treat it as a structured second opinion, not a number.
      </p>
    </div>

    <!-- Results -->
    <template v-if="store.result">
      <div style="margin-bottom: 16px">
        <span class="tag tag-outline">Overall confidence: {{ store.result.results.overall_simulation_confidence }}</span>
      </div>

      <div
        v-for="ar in store.result.results.adoption_reports" :key="ar.direction"
        style="border: 2px solid var(--mn-color-divider); margin-bottom: 20px"
      >
        <div style="padding: 16px; border-bottom: 2px solid var(--mn-color-divider); display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
          <h5 style="margin: 0; flex: 1">{{ ar.direction }}</h5>
          <span class="tag tag-neutral">{{ (ar.final_consensus * 100).toFixed(0) }}% consensus</span>
          <span class="tag" :class="verdictTagClass(ar.adoption_verdict)">{{ ar.adoption_verdict }}</span>
        </div>

        <div style="padding: 16px; border-bottom: 2px solid var(--mn-color-divider)">
          <ConsensusChart :rounds="ar.rounds" />
          <div v-if="ar.death_valleys.length" style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px">
            <span v-for="dv in ar.death_valleys" :key="dv" class="tag tag-outline">{{ dv }}</span>
          </div>
        </div>

        <div>
          <AgentPanel
            v-for="op in ar.rounds[ar.rounds.length - 1].opinions"
            :key="op.persona"
            :opinion="op"
          />
        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useSimulationStore } from '../stores/simulationState'
import ConsensusChart from '../components/ConsensusChart.vue'
import AgentPanel     from '../components/AgentPanel.vue'
import api from '../services/api'

const store        = useSimulationStore()
const topicContext = ref('AI/ML research')
const maxRounds    = ref(3)

// History panel — new, resolves the "no archive" gap. GET /graph/simulation/results
// already returns everything needed; no backend change required for this.
const historyOpen    = ref(false)
const historyLoading = ref(false)
const history         = ref([])

async function toggleHistory() {
  historyOpen.value = !historyOpen.value
  if (historyOpen.value) {
    historyLoading.value = true
    try {
      history.value = await api.getSimulationResults(topicContext.value, 10)
    } catch {
      history.value = []
    } finally {
      historyLoading.value = false
    }
  }
}

function loadHistoryRow(row) {
  store.loadResult(row)
  historyOpen.value = false
}

function fmtDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

// Same accent/outline/neutral pattern as AgentPanel's likelihood mapping,
// applied to the direction-level verdict enum (likely/contested/unlikely).
function verdictTagClass(verdict) {
  if (verdict === 'likely')   return 'tag-accent'
  if (verdict === 'unlikely') return 'tag-neutral'
  return 'tag-outline'
}
</script>
