<template>
  <div class="p-6 max-w-4xl">

    <!-- Header -->
    <div class="mb-6">
      <h2 class="text-text-primary text-lg font-semibold">ARIS — Agent Simulation</h2>
      <p class="text-text-muted text-sm mt-0.5">
        Multi-agent deliberation across researcher, VC, and policy-maker lenses.
      </p>
    </div>

    <!-- Controls -->
    <div class="flex flex-wrap gap-3 mb-6 items-end">
      <div class="flex-1 min-w-48">
        <label class="block text-text-muted text-xs mb-1">Topic context</label>
        <input
          v-model="topicContext"
          class="w-full bg-surface border border-border rounded-lg px-3 py-2
                 text-text-primary text-sm focus:outline-none focus:border-accent-blue"
          placeholder="AI/ML research"
        />
      </div>
      <div>
        <label class="block text-text-muted text-xs mb-1">Max rounds</label>
        <select
          v-model="maxRounds"
          class="bg-surface border border-border rounded-lg px-3 py-2
                 text-text-primary text-sm focus:outline-none focus:border-accent-blue"
        >
          <option v-for="n in [1, 2, 3, 4, 5]" :key="n" :value="n">{{ n }}</option>
        </select>
      </div>
      <button
        :disabled="store.running"
        class="px-4 py-2 rounded-lg text-sm font-medium transition-colors
               bg-accent-blue text-bg hover:bg-accent-blue/90
               disabled:opacity-50 disabled:cursor-not-allowed"
        @click="store.runSimulation(topicContext, maxRounds)"
      >
        {{ store.running ? 'Simulating…' : 'Run Simulation' }}
      </button>
      <button
        v-if="store.result || store.error"
        class="px-4 py-2 rounded-lg text-sm font-medium transition-colors
               border border-border text-text-muted hover:text-text-primary hover:border-text-muted"
        @click="store.reset()"
      >
        Reset
      </button>
    </div>

    <!-- Status -->
    <div v-if="store.error" class="mb-4 px-4 py-3 rounded-lg bg-accent-red/10 border border-accent-red/30">
      <p class="text-accent-red text-sm">{{ store.error }}</p>
    </div>
    <div v-if="store.running" class="mb-4 flex items-center gap-2 text-text-muted text-sm">
      <span class="animate-spin text-accent-blue">⟳</span>
      Simulation running
      <span v-if="store.jobId" class="font-mono text-xs opacity-60">({{ store.jobId.slice(0, 8) }}…)</span>
      — polling every 5s…
    </div>

    <!-- Results -->
    <div v-if="store.result">
      <div class="flex items-center justify-between mb-4">
        <div class="text-text-muted text-xs">
          {{ store.result.model_name }} ·
          {{ fmtDate(store.result.generated_at) }} ·
          {{ store.result.duration_seconds.toFixed(1) }}s
        </div>
        <span :class="confidenceBadge(store.result.results.overall_simulation_confidence)">
          {{ store.result.results.overall_simulation_confidence }} confidence
        </span>
      </div>

      <!-- Per-direction adoption reports -->
      <div
        v-for="ar in store.result.results.adoption_reports"
        :key="ar.direction"
        class="mb-6 border border-border rounded-xl overflow-hidden"
      >
        <!-- Direction header -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-border bg-surface">
          <h3 class="text-text-primary text-sm font-semibold">{{ ar.direction }}</h3>
          <div class="flex items-center gap-3">
            <span class="text-text-muted text-xs">
              consensus {{ (ar.final_consensus * 100).toFixed(0) }}%
            </span>
            <span :class="verdictBadge(ar.adoption_verdict)">
              {{ ar.adoption_verdict }}
            </span>
          </div>
        </div>

        <div class="p-4 space-y-4">
          <!-- Consensus chart -->
          <ConsensusChart :rounds="ar.rounds" />

          <!-- Death valleys -->
          <div v-if="ar.death_valleys.length">
            <p class="text-text-muted text-xs font-medium uppercase tracking-wide mb-1.5">
              Shared concerns
            </p>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="dv in ar.death_valleys" :key="dv"
                class="px-2 py-0.5 rounded text-xs bg-accent-red/10
                       text-accent-red border border-accent-red/20"
              >{{ dv }}</span>
            </div>
          </div>

          <!-- Final round agent opinions -->
          <div>
            <p class="text-text-muted text-xs font-medium uppercase tracking-wide mb-1.5">
              Round {{ ar.rounds.length }} opinions
            </p>
            <AgentPanel
              v-for="op in ar.rounds[ar.rounds.length - 1].opinions"
              :key="op.persona"
              :opinion="op"
            />
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useSimulationStore } from '../stores/simulationState'
import ConsensusChart from '../components/ConsensusChart.vue'
import AgentPanel     from '../components/AgentPanel.vue'

const store        = useSimulationStore()
const topicContext = ref('AI/ML research')
const maxRounds    = ref(3)

function fmtDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function confidenceBadge(level) {
  const map = {
    high:   'px-2.5 py-0.5 rounded text-xs font-medium bg-green-500/15 text-green-400 border border-green-500/30',
    medium: 'px-2.5 py-0.5 rounded text-xs font-medium bg-yellow-500/15 text-yellow-400 border border-yellow-500/30',
    low:    'px-2.5 py-0.5 rounded text-xs font-medium bg-red-500/15 text-red-400 border border-red-500/30',
  }
  return map[level] ?? map.low
}

function verdictBadge(verdict) {
  const map = {
    likely:    'px-2 py-0.5 rounded text-xs font-medium bg-green-500/15 text-green-400 border border-green-500/30',
    contested: 'px-2 py-0.5 rounded text-xs font-medium bg-yellow-500/15 text-yellow-400 border border-yellow-500/30',
    unlikely:  'px-2 py-0.5 rounded text-xs font-medium bg-red-500/15 text-red-400 border border-red-500/30',
  }
  return map[verdict] ?? map.contested
}
</script>
