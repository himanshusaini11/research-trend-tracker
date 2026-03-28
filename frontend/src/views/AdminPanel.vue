<template>
  <div class="h-full overflow-auto bg-bg">
    <div class="max-w-5xl mx-auto px-6 py-8 space-y-8">

      <!-- Header -->
      <div>
        <h1 class="text-text-primary font-semibold text-lg">Admin Panel</h1>
        <p class="text-text-muted text-xs mt-0.5">System metrics and user management</p>
      </div>

      <!-- Stats grid -->
      <div v-if="stats" class="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div v-for="card in statCards" :key="card.label"
          class="bg-surface border border-border rounded-xl px-4 py-4">
          <div class="text-text-muted text-xs uppercase tracking-wider mb-1">{{ card.label }}</div>
          <div class="text-text-primary font-mono font-semibold text-xl">{{ card.value }}</div>
          <div v-if="card.sub" class="text-text-muted text-[10px] mt-0.5">{{ card.sub }}</div>
        </div>
      </div>
      <div v-else-if="statsError" class="text-accent-red text-sm">{{ statsError }}</div>
      <div v-else class="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div v-for="i in 8" :key="i"
          class="bg-surface border border-border rounded-xl px-4 py-4 animate-pulse h-20" />
      </div>

      <!-- Users table -->
      <div class="bg-surface border border-border rounded-xl overflow-hidden">
        <div class="px-5 py-3 border-b border-border flex items-center justify-between">
          <span class="text-text-primary text-sm font-medium">Registered Users</span>
          <span class="text-text-muted text-xs font-mono">{{ users.length }} total</span>
        </div>

        <div v-if="usersError" class="px-5 py-4 text-accent-red text-sm">{{ usersError }}</div>
        <div v-else-if="!usersLoaded" class="px-5 py-4 text-text-muted text-sm animate-pulse">Loading…</div>
        <table v-else class="w-full text-xs">
          <thead>
            <tr class="border-b border-border text-text-muted uppercase tracking-wider text-[10px]">
              <th class="text-left px-5 py-2.5 font-medium">Email</th>
              <th class="text-left px-4 py-2.5 font-medium">Registered</th>
              <th class="text-left px-4 py-2.5 font-medium">Last Login</th>
              <th class="text-left px-4 py-2.5 font-medium">Role</th>
              <th class="text-right px-5 py-2.5 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id"
              class="border-b border-border/50 hover:bg-bg/60 transition-colors">
              <td class="px-5 py-3 text-text-primary font-mono">{{ u.email }}</td>
              <td class="px-4 py-3 text-text-muted">{{ formatDate(u.created_at) }}</td>
              <td class="px-4 py-3 text-text-muted">{{ u.last_login ? formatDate(u.last_login) : '—' }}</td>
              <td class="px-4 py-3">
                <span :class="[
                  'px-2 py-0.5 rounded-full text-[10px] font-medium',
                  u.is_admin
                    ? 'bg-accent-blue/10 text-accent-blue border border-accent-blue/20'
                    : 'bg-bg border border-border text-text-muted',
                ]">
                  {{ u.is_admin ? 'admin' : 'user' }}
                </span>
              </td>
              <td class="px-5 py-3 text-right">
                <button
                  v-if="u.id !== currentUserId"
                  @click="toggleAdmin(u)"
                  :disabled="toggling === u.id"
                  class="text-[10px] px-2.5 py-1 rounded border transition-colors disabled:opacity-40
                         border-border text-text-muted hover:border-accent-blue hover:text-accent-blue"
                >
                  {{ toggling === u.id ? '…' : (u.is_admin ? 'Revoke admin' : 'Make admin') }}
                </button>
                <span v-else class="text-text-muted/40 text-[10px]">you</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { jwtDecode } from 'jwt-decode'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'

const auth  = useAuthStore()
const users = ref([])
const stats = ref(null)
const usersLoaded = ref(false)
const usersError  = ref('')
const statsError  = ref('')
const toggling    = ref(null)

const currentUserId = computed(() => {
  try { return jwtDecode(auth.token).sub } catch { return null }
})

const statCards = computed(() => {
  if (!stats.value) return []
  const s = stats.value
  const processed = s.total_papers ? Math.round(s.processed_papers / s.total_papers * 100) : 0
  return [
    { label: 'Total Users',    value: s.total_users,         sub: `${s.admin_users} admin` },
    { label: 'Active (7d)',    value: s.active_users_7d,     sub: 'logged in last 7 days' },
    { label: 'Papers',         value: s.total_papers.toLocaleString(), sub: `${processed}% graph-processed` },
    { label: 'Keywords',       value: s.total_keywords.toLocaleString(), sub: 'distinct indexed' },
    { label: 'Trend Scores',   value: s.total_trend_scores.toLocaleString(), sub: 'computed signals' },
    { label: 'Processed',      value: s.processed_papers.toLocaleString(), sub: 'graph-extracted' },
    {
      label: 'Last Pipeline',
      value: s.last_pipeline_run ? formatDate(s.last_pipeline_run) : '—',
      sub: 'prediction report generated',
    },
    { label: 'Admin Users',    value: s.admin_users, sub: 'with admin role' },
  ]
})

function formatDate(iso) {
  return new Date(iso).toLocaleString([], {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

async function toggleAdmin(user) {
  toggling.value = user.id
  try {
    const updated = await api.toggleAdminRole(user.id)
    const idx = users.value.findIndex(u => u.id === user.id)
    if (idx !== -1) users.value[idx] = updated
  } catch (e) {
    alert(e.response?.data?.detail ?? 'Failed to update role')
  } finally {
    toggling.value = null
  }
}

onMounted(async () => {
  const [usersResult, statsResult] = await Promise.allSettled([
    api.getAdminUsers(),
    api.getAdminStats(),
  ])

  if (usersResult.status === 'fulfilled') {
    users.value = usersResult.value
    usersLoaded.value = true
  } else {
    usersError.value = usersResult.reason?.response?.data?.detail ?? 'Failed to load users'
    usersLoaded.value = true
  }

  if (statsResult.status === 'fulfilled') {
    stats.value = statsResult.value
  } else {
    statsError.value = statsResult.reason?.response?.data?.detail ?? 'Failed to load stats'
  }
})
</script>
