<template>
  <span class="modernist tag" :class="tagClass">{{ trend }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  trend: { type: String, required: true },
})

// Mono-accent system: accelerating -> accent tag, decelerating -> accent-2
// tag, stable -> neutral tag. Mirrors GraphPanel's node-color mapping.
const tagClass = computed(() => {
  if (props.trend === 'accelerating') return 'tag-accent'
  if (props.trend === 'decelerating') return 'tag-accent-2'
  return 'tag-neutral'
})
</script>
