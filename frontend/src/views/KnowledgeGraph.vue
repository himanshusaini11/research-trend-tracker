<template>
  <div class="h-full flex flex-col">
    <!-- Controls bar -->
    <div class="bg-surface border-b border-border px-6 py-3 flex items-center gap-6 shrink-0">
      <div class="flex items-center gap-3">
        <label class="text-text-muted text-xs uppercase tracking-wider">Top N</label>
        <input
          type="range" min="5" max="50" step="5"
          v-model.number="topN"
          class="accent-accent-blue w-28"
        />
        <span class="text-text-primary text-sm w-6">{{ topN }}</span>
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
        >
          {{ f.label }}
        </button>
      </div>

      <button
        @click="resetZoom"
        class="ml-auto text-xs text-text-muted border border-border px-3 py-1 rounded
               hover:border-accent-blue hover:text-text-primary transition-colors"
      >
        Reset Zoom
      </button>
    </div>

    <!-- Graph panel -->
    <div class="flex-1 relative overflow-hidden">
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
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import GraphPanel from '../components/GraphPanel.vue'
import { useGraphStore } from '../stores/graph'

const store      = useGraphStore()
const panel      = ref(null)
const topN       = ref(20)
const trendFilter = ref('all')

const filters = [
  { value: 'all',           label: 'All' },
  { value: 'accelerating',  label: 'Accelerating' },
  { value: 'decelerating',  label: 'Decelerating' },
  { value: 'stable',        label: 'Stable' },
]

function resetZoom() {
  panel.value?.resetZoom()
}

watch([topN, trendFilter], () => {
  store.fetchConcepts(topN.value, trendFilter.value)
})

onMounted(() => store.fetchConcepts(topN.value, trendFilter.value))
</script>
