<template>
  <div class="bg-surface border border-border rounded-lg mb-3 overflow-hidden">
    <button
      @click="open = !open"
      class="w-full text-left px-4 py-3 flex items-start justify-between gap-2
             hover:bg-bg/50 transition-colors"
    >
      <span class="text-text-primary text-sm font-medium leading-snug">{{ title }}</span>
      <div class="flex items-center gap-2 shrink-0">
        <span
          v-if="badge"
          :class="badgeClass"
          class="text-xs px-1.5 py-0.5 rounded font-medium"
        >
          {{ badge }}
        </span>
        <span class="text-text-muted text-xs">{{ open ? '▲' : '▼' }}</span>
      </div>
    </button>
    <div v-show="open" class="px-4 pb-3">
      <p class="text-text-muted text-xs leading-relaxed">{{ body }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  title:      { type: String,  required: true },
  body:       { type: String,  default: '' },
  badge:      { type: String,  default: '' },
  badgeClass: { type: String,  default: '' },
})

const open = ref(false)
</script>
