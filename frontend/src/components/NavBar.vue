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

    <!-- Theme toggle + version -->
    <div class="px-4 py-3 border-t border-border space-y-2">
      <div class="flex items-center gap-1">
        <button
          v-for="t in themes" :key="t.mode"
          @click="setTheme(t.mode)"
          :title="t.label"
          :class="[
            'flex-1 flex items-center justify-center py-1.5 rounded text-xs transition-colors',
            theme === t.mode
              ? 'bg-accent-blue/20 text-accent-blue'
              : 'text-text-muted hover:text-text-primary',
          ]"
        >
          <!-- Sun (light) -->
          <svg v-if="t.mode === 'light'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" stroke-width="2" class="w-3.5 h-3.5">
            <circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
          </svg>
          <!-- Monitor (system) -->
          <svg v-else-if="t.mode === 'system'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" stroke-width="2" class="w-3.5 h-3.5">
            <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
          </svg>
          <!-- Moon (dark) -->
          <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" stroke-width="2" class="w-3.5 h-3.5">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        </button>
      </div>
      <span class="text-text-muted text-xs">v3.0.0</span>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useTheme } from '../composables/useTheme'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const auth  = useAuthStore()
const { theme, setTheme } = useTheme()

const items = computed(() => {
  const base = [
    { path: '/dashboard/graph',       icon: '⬡', label: 'Knowledge Graph' },
    { path: '/dashboard/predictions', icon: '◎', label: 'Predictions' },
    { path: '/dashboard/velocity',    icon: '⟿', label: 'Velocity' },
  ]
  base.push({ path: '/dashboard/simulation', icon: '⬡', label: 'Simulation' })
  if (!auth.isDemo) base.push({ path: '/dashboard/upload', icon: '↑', label: 'Upload' })
  if (auth.isAdmin)  base.push({ path: '/dashboard/admin',  icon: '⚙', label: 'Admin' })
  return base
})

const themes = [
  { mode: 'light',  label: 'Light theme' },
  { mode: 'system', label: 'System theme' },
  { mode: 'dark',   label: 'Dark theme' },
]
</script>
