<template>
  <div class="border border-border rounded-lg overflow-hidden mb-2">
    <!-- Header row — always visible -->
    <button
      class="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-bg transition-colors text-left"
      @click="expanded = !expanded"
    >
      <span :class="badgeClass">{{ opinion.persona.replace('_', ' ') }}</span>
      <span :class="likelihoodClass">{{ opinion.adoption_likelihood }}</span>
      <span class="text-text-muted text-xs ml-1">
        {{ (opinion.confidence_score * 100).toFixed(0) }}% conf
      </span>
      <span class="ml-auto text-text-muted text-xs">{{ expanded ? '▲' : '▼' }}</span>
    </button>

    <!-- Expanded body -->
    <div v-if="expanded" class="px-3 pb-3 pt-1 border-t border-border space-y-2">
      <p class="text-text-primary text-xs leading-relaxed">{{ opinion.reasoning }}</p>

      <div v-if="opinion.key_concerns.length" class="space-y-0.5">
        <p class="text-text-muted text-xs font-medium uppercase tracking-wide">Concerns</p>
        <ul class="space-y-0.5">
          <li
            v-for="c in opinion.key_concerns" :key="c"
            class="flex items-start gap-1.5 text-xs text-text-muted"
          >
            <span class="text-accent-red mt-0.5">●</span>{{ c }}
          </li>
        </ul>
      </div>

      <div v-if="opinion.key_enablers.length" class="space-y-0.5">
        <p class="text-text-muted text-xs font-medium uppercase tracking-wide">Enablers</p>
        <ul class="space-y-0.5">
          <li
            v-for="e in opinion.key_enablers" :key="e"
            class="flex items-start gap-1.5 text-xs text-text-muted"
          >
            <span class="text-accent-green mt-0.5">●</span>{{ e }}
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  opinion: { type: Object, required: true },
})

const expanded = ref(false)

const _badgeMap = {
  researcher:         'bg-blue-500/15 text-blue-400 border border-blue-500/30',
  venture_capitalist: 'bg-green-500/15 text-green-400 border border-green-500/30',
  policy_maker:       'bg-purple-500/15 text-purple-400 border border-purple-500/30',
}

const badgeClass = computed(() =>
  `px-2 py-0.5 rounded text-xs font-medium ${_badgeMap[props.opinion.persona] ?? 'bg-surface text-text-muted border border-border'}`
)

const _likelihoodMap = {
  high:   'text-accent-green text-xs font-semibold',
  medium: 'text-yellow-400 text-xs font-semibold',
  low:    'text-accent-red text-xs font-semibold',
}

const likelihoodClass = computed(() =>
  _likelihoodMap[props.opinion.adoption_likelihood] ?? 'text-text-muted text-xs'
)
</script>
