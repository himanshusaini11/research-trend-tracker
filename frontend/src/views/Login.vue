<template>
  <div class="min-h-screen bg-bg flex items-center justify-center">
    <div class="w-full max-w-md">
      <!-- Logo / title -->
      <div class="text-center mb-8">
        <div class="text-accent-blue text-4xl mb-3">◈</div>
        <h1 class="text-2xl font-semibold text-text-primary">Research Trend Tracker</h1>
        <p class="text-text-muted text-sm mt-1">Graph-grounded research prediction engine</p>
      </div>

      <!-- Card -->
      <div class="bg-surface border border-border rounded-xl p-8">
        <h2 class="text-text-primary font-medium mb-1">Connect</h2>
        <p class="text-text-muted text-sm mb-6">
          Paste your JWT token from the API to continue.
        </p>

        <label class="block text-text-muted text-xs uppercase tracking-wider mb-2">
          JWT Token
        </label>
        <textarea
          v-model="tokenInput"
          rows="4"
          placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
          class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-text-primary text-sm
                 font-mono resize-none focus:outline-none focus:border-accent-blue
                 placeholder-text-muted transition-colors"
        />

        <p v-if="error" class="text-accent-red text-sm mt-2">{{ error }}</p>

        <button
          @click="connect"
          :disabled="!tokenInput.trim()"
          class="mt-4 w-full bg-accent-blue text-bg font-medium py-2.5 rounded-lg
                 hover:bg-blue-400 disabled:opacity-40 disabled:cursor-not-allowed
                 transition-colors"
        >
          Connect
        </button>

        <p class="text-text-muted text-xs mt-4 text-center">
          Generate a token:
          <code class="text-accent-blue">
            uv run python -c "from app.core.security import create_access_token; print(create_access_token({'sub':'demo'}))"
          </code>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router     = useRouter()
const auth       = useAuthStore()
const tokenInput = ref('')
const error      = ref('')

function connect() {
  const t = tokenInput.value.trim()
  if (!t) return

  try {
    auth.setToken(t)
    if (!auth.isValid) {
      auth.clear()
      error.value = 'Token is invalid or expired.'
      return
    }
    router.push('/dashboard/graph')
  } catch {
    error.value = 'Invalid token format.'
  }
}
</script>
