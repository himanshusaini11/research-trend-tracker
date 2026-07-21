<template>
  <div class="modernist" style="display: flex; height: 100vh; width: 100vw; overflow: hidden;
              background: var(--mn-color-bg); color: var(--mn-color-text)">
    <NavBar />

    <div style="flex: 1; display: flex; flex-direction: column; min-width: 0">
      <!-- Top bar -->
      <div style="display: flex; align-items: center; gap: 16px; padding: 14px 24px;
                  border-bottom: 2px solid var(--mn-color-divider)">
        <h4 style="margin: 0; flex: 1">{{ currentTitle }}</h4>
        <span :style="`width: 7px; height: 7px; flex: none; background: ${auth.isValid ? '#5fa832' : 'var(--mn-color-accent)'}`"></span>
        <span style="font-size: 12px; opacity: .7">
          {{ auth.isValid ? `session valid · expires ${expiryLabel}` : 'session expired' }}
        </span>
        <span v-if="auth.isDemo" class="tag tag-neutral">DEMO</span>
        <button class="btn btn-secondary" @click="logout">Sign out</button>
      </div>

      <!-- Stats banner — live from GET /graph/stats (Stage 1) -->
      <div style="display: flex; align-items: center; gap: 22px; padding: 8px 24px; font-size: 12px;
                  border-bottom: 2px solid var(--mn-color-divider)">
        <template v-if="stats">
          <span>{{ stats.total_papers.toLocaleString() }} PAPERS</span><span>/</span>
          <span>{{ stats.concept_count.toLocaleString() }} CONCEPTS</span><span>/</span>
          <span>{{ formattedEdges }} EDGES</span><span>/</span>
          <span>{{ formattedRange }}</span>
        </template>
        <span v-else style="opacity: .5">loading…</span>
        <span class="tag tag-outline" style="margin-left: auto">● LIVE FROM API</span>
      </div>

      <main style="flex: 1; overflow: auto">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import NavBar from '../components/NavBar.vue'
import { useAuthStore } from '../stores/auth'
import api from '../services/api'

const auth   = useAuthStore()
const route  = useRoute()
const router = useRouter()

const titles = {
  '/dashboard/graph':       'Knowledge Graph',
  '/dashboard/predictions': 'Prediction Report',
  '/dashboard/velocity':    'Velocity',
  '/dashboard/simulation':  'ARIS Simulation',
  '/dashboard/upload':      'Upload Papers',
  '/dashboard/admin':       'Admin Panel',
}

const currentTitle = computed(() => titles[route.path] ?? 'Aletheia')

const expiryLabel = computed(() => {
  if (!auth.expiresAt) return ''
  const mins = Math.max(0, Math.round((auth.expiresAt.getTime() - Date.now()) / 60000))
  return `${mins}m`
})

const stats = ref(null)

const formattedEdges = computed(() => {
  if (!stats.value) return ''
  const n = stats.value.edge_count
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n.toLocaleString()
})

const formattedRange = computed(() => {
  if (!stats.value?.date_range_start || !stats.value?.date_range_end) return '—'
  const startYear = new Date(stats.value.date_range_start).getFullYear()
  const endYear   = new Date(stats.value.date_range_end).getFullYear()
  return startYear === endYear ? `${startYear}` : `${startYear}–${endYear}`
})

async function loadStats() {
  try {
    stats.value = await api.getGraphStats()
  } catch {
    // Stats banner degrades to "loading…" indefinitely on failure — non-critical, no error UI needed
  }
}

function logout() {
  auth.logout(router)
}

onMounted(loadStats)
</script>
