<template>
  <div class="flex h-screen bg-bg overflow-hidden">
    <!-- Sidebar -->
    <NavBar />

    <!-- Main area -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Top bar -->
      <header class="h-12 bg-surface border-b border-border flex items-center justify-between px-6 shrink-0">
        <span class="text-text-muted text-sm">{{ currentTitle }}</span>
        <div class="flex items-center gap-3">
          <span
            class="w-2 h-2 rounded-full"
            :class="auth.isValid ? 'bg-accent-green' : 'bg-accent-red'"
          />
          <span class="text-text-muted text-xs">
            {{ auth.isValid ? `Expires ${expiryLabel}` : 'Token expired' }}
          </span>
          <button
            @click="logout"
            class="text-text-muted text-xs hover:text-accent-red transition-colors"
          >
            Disconnect
          </button>
        </div>
      </header>

      <!-- Router outlet -->
      <main class="flex-1 overflow-auto">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import NavBar from '../components/NavBar.vue'
import { useAuthStore } from '../stores/auth'

const auth   = useAuthStore()
const route  = useRoute()
const router = useRouter()

const titles = {
  '/dashboard/graph':       'Knowledge Graph',
  '/dashboard/predictions': 'Prediction Report',
  '/dashboard/velocity':    'Velocity Chart',
}

const currentTitle = computed(() => titles[route.path] ?? 'Research Trend Tracker')

const expiryLabel = computed(() => {
  if (!auth.expiresAt) return ''
  return auth.expiresAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
})

function logout() {
  auth.clear()
  router.push('/login')
}
</script>
