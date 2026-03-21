<template>
  <div class="bg-surface border border-border rounded-lg p-4 hover:border-accent-blue/40 transition-colors">
    <div class="flex items-start justify-between gap-2 mb-2">
      <span class="text-text-primary text-sm font-medium leading-snug">{{ concept.concept_name }}</span>
      <span
        class="shrink-0 text-xs px-1.5 py-0.5 rounded font-medium"
        :style="{ color: trendColor[concept.trend], background: trendColor[concept.trend] + '22' }"
      >
        {{ concept.trend }}
      </span>
    </div>
    <div class="grid grid-cols-3 gap-2 text-xs">
      <div>
        <div class="text-text-muted">composite</div>
        <div class="text-text-primary font-mono">{{ concept.composite_score.toFixed(3) }}</div>
      </div>
      <div>
        <div class="text-text-muted">velocity</div>
        <div class="text-text-primary font-mono">{{ concept.velocity.toFixed(3) }}</div>
      </div>
      <div>
        <div class="text-text-muted">accel.</div>
        <div
          class="font-mono"
          :class="concept.acceleration >= 0 ? 'text-accent-green' : 'text-accent-red'"
        >
          {{ concept.acceleration >= 0 ? '+' : '' }}{{ concept.acceleration.toFixed(3) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  concept: { type: Object, required: true },
})

const trendColor = {
  accelerating: '#00d4aa',
  decelerating: '#ff6b6b',
  stable:       '#4a9eff',
}
</script>
