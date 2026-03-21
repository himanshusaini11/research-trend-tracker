<template>
  <nav class="w-52 bg-surface border-r border-border flex flex-col shrink-0">
    <!-- Logo -->
    <div class="px-5 py-5 border-b border-border">
      <div class="flex items-center gap-2">
        <span class="text-accent-blue text-xl">◈</span>
        <div>
          <div class="text-text-primary text-sm font-semibold leading-tight">Research</div>
          <div class="text-text-muted text-xs leading-tight">Trend Tracker</div>
        </div>
      </div>
    </div>

    <!-- Nav links -->
    <div class="flex-1 px-3 py-4 space-y-1">
      <RouterLink
        v-for="item in items" :key="item.path"
        :to="item.path"
        class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors"
        :class="route.path.startsWith(item.path)
          ? 'bg-accent-blue/10 text-accent-blue'
          : 'text-text-muted hover:text-text-primary hover:bg-bg'"
      >
        <span class="text-base">{{ item.icon }}</span>
        {{ item.label }}
      </RouterLink>
    </div>

    <!-- Version -->
    <div class="px-5 py-3 border-t border-border">
      <span class="text-text-muted text-xs">v2.1.0</span>
    </div>
  </nav>
</template>

<script setup>
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()

const items = [
  { path: '/dashboard/graph',       icon: '⬡', label: 'Knowledge Graph' },
  { path: '/dashboard/predictions', icon: '◎', label: 'Predictions' },
  { path: '/dashboard/velocity',    icon: '⟿', label: 'Velocity' },
]
</script>
