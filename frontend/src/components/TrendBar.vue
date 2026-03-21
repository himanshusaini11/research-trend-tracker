<template>
  <span
    class="inline-block text-xs px-2 py-0.5 rounded font-medium"
    :style="{ color: color, background: color + '22' }"
  >
    {{ trend }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  trend: { type: String, required: true },
})

const palette = {
  accelerating: '#00d4aa',
  decelerating: '#ff6b6b',
  stable:       '#4a9eff',
}

const color = computed(() => palette[props.trend] ?? '#8892a4')
</script>
