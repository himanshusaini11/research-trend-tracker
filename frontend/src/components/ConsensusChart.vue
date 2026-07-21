<template>
  <svg viewBox="0 0 400 116" style="width: 100%; max-width: 400px">
    <line x1="10" y1="100" x2="390" y2="100" :stroke="dividerColor" stroke-width="1" />
    <polyline :points="chartPoints" fill="none" :stroke="accentColor" stroke-width="2" />
    <g v-for="(pt, i) in chartDots" :key="i">
      <circle :cx="pt.x" :cy="pt.y" r="3" :fill="accentColor" />
      <text :x="pt.x" y="112" font-size="9" text-anchor="middle" :fill="textColor" style="opacity: .55">{{ pt.label }}</text>
    </g>
  </svg>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  rounds: { type: Array, required: true },
})

// Read the current theme's tokens at render time so the chart re-colors on
// theme toggle, same pattern GraphPanel uses for its canvas colors.
const accentColor  = ref('#ec3013')
const dividerColor = ref('#201e1d66')
const textColor    = ref('#201e1d')

function readColors() {
  const s = getComputedStyle(document.documentElement)
  accentColor.value  = s.getPropertyValue('--mn-color-accent').trim()
  dividerColor.value = s.getPropertyValue('--mn-color-divider').trim()
  textColor.value    = s.getPropertyValue('--mn-color-text').trim()
}

function onThemeChange() { readColors() }

onMounted(() => {
  readColors()
  window.addEventListener('rtt-theme-change', onThemeChange)
})
onUnmounted(() => window.removeEventListener('rtt-theme-change', onThemeChange))

// x: 10..390 across rounds, y: consensus_score (0..1) mapped to 90..10 (inverted, higher = up)
const chartDots = computed(() => {
  const n = props.rounds.length
  if (n === 0) return []
  return props.rounds.map((r, i) => ({
    x: n > 1 ? (i / (n - 1)) * 380 + 10 : 200,
    y: 90 - r.consensus_score * 80,
    label: `R${r.round_number}`,
  }))
})

const chartPoints = computed(() => chartDots.value.map(pt => `${pt.x},${pt.y}`).join(' '))
</script>
