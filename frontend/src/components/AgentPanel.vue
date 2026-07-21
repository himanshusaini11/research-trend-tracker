<template>
  <div class="modernist">
    <div class="acc-head" @click="expanded = !expanded">
      <span>
        <span class="tag tag-neutral" style="margin-right: 8px">{{ personaLabel }}</span>
        <span class="tag" :class="likelihoodTagClass" style="margin-right: 8px">{{ opinion.adoption_likelihood }}</span>
        {{ (opinion.confidence_score * 100).toFixed(0) }}% conf
      </span>
      <span>{{ expanded ? '−' : '+' }}</span>
    </div>
    <div v-if="expanded" class="acc-body">
      <p style="margin: 0 0 8px">{{ opinion.reasoning }}</p>
      <p v-if="opinion.key_concerns.length" style="margin: 0 0 4px; font-size: 12px">
        <strong>Concerns:</strong> {{ opinion.key_concerns.join('; ') }}
      </p>
      <p v-if="opinion.key_enablers.length" style="margin: 0; font-size: 12px">
        <strong>Enablers:</strong> {{ opinion.key_enablers.join('; ') }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  opinion: { type: Object, required: true },
})

const expanded = ref(false)

const personaLabel = computed(() => props.opinion.persona.replace('_', ' '))

// Real backend values are high/medium/low (not the prototype's illustrative
// likely/contested/unlikely, which is the direction-level verdict enum).
// Same accent/outline/neutral pattern as tagForVerdict, applied to this field.
const likelihoodTagClass = computed(() => {
  const l = props.opinion.adoption_likelihood
  if (l === 'high') return 'tag-accent'
  if (l === 'low')  return 'tag-neutral'
  return 'tag-outline'
})
</script>
