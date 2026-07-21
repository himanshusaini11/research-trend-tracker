<template>
  <div class="modernist" style="height: 100%; overflow: auto; background: var(--mn-color-bg); padding: 24px">

    <!-- Stats grid — 2px hairline via divider-color background showing through the gap -->
    <div v-if="stats" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px; background: var(--mn-color-divider); margin-bottom: 28px">
      <div v-for="card in statCards" :key="card.label" style="background: var(--mn-color-bg); padding: 16px">
        <div style="font-size: 10.5px; opacity: .6; text-transform: uppercase; margin-bottom: 6px">{{ card.label }}</div>
        <div style="font-family: var(--mn-font-heading); font-weight: 800; font-size: 24px">{{ card.value }}</div>
        <div v-if="card.sub" style="opacity: .5; font-size: 10px; margin-top: 2px">{{ card.sub }}</div>
      </div>
    </div>
    <div v-else-if="statsError" style="color: var(--mn-color-accent-700); font-size: 14px; margin-bottom: 28px">{{ statsError }}</div>
    <div v-else style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px; background: var(--mn-color-divider); margin-bottom: 28px">
      <div v-for="i in 8" :key="i" class="skel" style="height: 80px" />
    </div>

    <!-- Users table -->
    <h6 style="opacity: .6; margin-bottom: 10px">USERS</h6>
    <div v-if="usersError" style="color: var(--mn-color-accent-700); font-size: 14px">{{ usersError }}</div>
    <div v-else-if="!usersLoaded" style="opacity: .6; font-size: 14px">Loading…</div>
    <table v-else class="table">
      <thead><tr><th>Email</th><th>Registered</th><th>Last login</th><th>Role</th><th></th></tr></thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td>{{ u.email }}</td>
          <td>{{ formatDate(u.created_at) }}</td>
          <td>{{ u.last_login ? formatDate(u.last_login) : '—' }}</td>
          <td><span class="tag" :class="u.is_admin ? 'tag-accent' : 'tag-neutral'">{{ u.is_admin ? 'admin' : 'user' }}</span></td>
          <td>
            <button
              v-if="u.id !== currentUserId" class="btn btn-secondary" style="padding: 4px 10px; font-size: 12px"
              :disabled="toggling === u.id" @click="toggleAdmin(u)"
            >{{ toggling === u.id ? '…' : (u.is_admin ? 'Revoke admin' : 'Make admin') }}</button>
            <span v-else style="opacity: .4; font-size: 12px">you</span>
          </td>
        </tr>
      </tbody>
    </table>

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
